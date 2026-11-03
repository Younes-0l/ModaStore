from datetime import timedelta
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from ..models import Review, ReviewVote
from catalog.models import Product
from orders.models import Order, OrderItem


SORTS = {
    'newest': ('جدیدترین', '-created_at'),
    'helpful': ('مفیدترین', '-helpful_count'),
    'high': ('بالاترین امتیاز', '-rating'),
    'low': ('پایین‌ترین امتیاز', 'rating'),
}
PAID_STATUSES = (Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED)


class ReviewError(Exception):
    """Raised with a user-facing (Persian) message."""


def recalculate(product_id):
    """Refresh the stored average and count. update() leaves updated_at untouched."""
    agg = Review.objects.filter(
        product_id=product_id, status=Review.Status.APPROVED,
    ).order_by().aggregate(avg=Avg('rating'), n=Count('id'))
    Product.objects.filter(pk=product_id).update(
        rating_avg=round(agg['avg'] or 0, 2), rating_count=agg['n'],
    )


def _verified_purchase(user, product):
    return (
        OrderItem.objects.filter(
            order__user=user, order__status__in=PAID_STATUSES, variant__product=product,
        )
        .order_by('-order__created_at')
        .first()
    )


def _is_trusted(user):
    need = getattr(settings, 'REVIEWS_TRUSTED_MIN_APPROVED', 2)
    if not need:
        return False
    agg = Review.objects.filter(user=user).order_by().aggregate(
        ok=Count('id', filter=Q(status=Review.Status.APPROVED)),
        bad=Count('id', filter=Q(status=Review.Status.REJECTED)),
    )
    return agg['ok'] >= need and agg['bad'] == 0


def submit_review(user, product, review):
    """Save a new or edited review (an unsaved ModelForm instance) with the right status."""
    now = timezone.now()
    if review.pk is None:
        limit = getattr(settings, 'REVIEWS_MAX_NEW_PER_HOUR', 5)
        recent = Review.objects.filter(user=user, created_at__gte=now - timedelta(hours=1)).count()
        if recent >= limit:
            raise ReviewError('تعداد نظرهای ثبت‌شده در این ساعت زیاد است. بعداً تلاش کنید.')

    purchase = _verified_purchase(user, product)
    review.product = product
    review.user = user
    review.is_verified_buyer = purchase is not None
    review.purchased_variant = (
        ' · '.join(p for p in (purchase.color, purchase.storage) if p) if purchase else ''
    )

    if _is_trusted(user):
        review.status = Review.Status.APPROVED
        review.moderated_at = now
    else:
        review.status = Review.Status.PENDING
        review.moderated_at = None
    review.moderated_by = None

    try:
        with transaction.atomic():
            review.save()
    except IntegrityError:
        raise ReviewError('شما قبلاً برای این محصول نظر ثبت کرده‌اید.')
    return review


@transaction.atomic
def set_helpful(user, review_id, active):
    """Idempotent. The review row is locked so parallel votes cannot corrupt the counter."""
    review = Review.objects.select_for_update().filter(
        pk=review_id, status=Review.Status.APPROVED,
    ).first()
    if review is None:
        raise ReviewError('این نظر در دسترس نیست.')
    if review.user_id == user.pk:
        raise ReviewError('نمی‌توانید به نظر خودتان رأی دهید.')

    if active:
        ReviewVote.objects.get_or_create(review=review, user=user)
    else:
        ReviewVote.objects.filter(review=review, user=user).delete()
    count = review.votes.count()
    Review.objects.filter(pk=review.pk).update(helpful_count=count)
    return count


def _qs(params, *drop):
    q = params.copy()
    for key in drop:
        q.pop(key, None)
    return q.urlencode()


def product_reviews_context(request, product):
    """Everything the reviews tab needs (a handful of small queries)."""
    params = request.GET
    sort = params.get('rsort', 'newest')
    if sort not in SORTS:
        sort = 'newest'
    buyers_only = params.get('rbuyers') == '1'

    approved = Review.objects.filter(product=product, status=Review.Status.APPROVED)

    # Star distribution and recommendation share, from all approved reviews
    counts = dict(approved.order_by().values_list('rating').annotate(n=Count('id')))
    total = sum(counts.values())
    rows = [
        {'star': s, 'n': counts.get(s, 0), 'pct': round(counts.get(s, 0) * 100 / total) if total else 0}
        for s in (5, 4, 3, 2, 1)
    ]
    rec = approved.order_by().exclude(recommend=None).aggregate(
        yes=Count('id', filter=Q(recommend=True)), all=Count('id'),
    )
    recommend_pct = round(rec['yes'] * 100 / rec['all']) if rec['all'] >= 3 else None

    listing = approved.select_related('user')
    if buyers_only:
        listing = listing.filter(is_verified_buyer=True)
    listing = listing.order_by(SORTS[sort][1], '-created_at', '-id')
    paginator = Paginator(listing, 5)
    page_obj = paginator.get_page(params.get('rpage'))

    my_review, voted_ids = None, set()
    if request.user.is_authenticated:
        my_review = Review.objects.filter(user=request.user, product=product).first()
        voted_ids = set(
            ReviewVote.objects.filter(user=request.user, review__in=list(page_obj))
            .values_list('review_id', flat=True)
        )

    return {'rv': {
        'rows': rows, 'total': total, 'recommend_pct': recommend_pct,
        'page_obj': page_obj, 'paginator': paginator,
        'sort': sort, 'sorts': [(k, v[0]) for k, v in SORTS.items()],
        'buyers_only': buyers_only,
        'my_review': my_review, 'voted_ids': voted_ids,
        # Query strings that keep the other review options when one changes
        'q_sort': _qs(params, 'rsort', 'rpage'),
        'q_buyers': _qs(params, 'rbuyers', 'rpage'),
        'q_page': _qs(params, 'rpage'),
    }}