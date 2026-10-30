from django.db import transaction, IntegrityError
from django.db.models import Prefetch, Sum
from django.utils import timezone
from catalog.models import ProductImage, ProductVariant

from .models import MAX_QTY_PER_ITEM, Cart, CartItem

SESSION_KEY = 'guest_cart_id'


class CartError(Exception):
    """Raised with a user-facing (Persian) message."""


def get_cart(request, create=True):
    """Return the current cart (user cart or guest cart), or None if absent and create=False."""
    if request.user.is_authenticated:
        if create:
            return Cart.objects.get_or_create(user=request.user)[0]
        return Cart.objects.filter(user=request.user).first()

    cart_id = request.session.get(SESSION_KEY)
    cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if cart is None and create:
        cart = Cart.objects.create()
        request.session[SESSION_KEY] = cart.pk
    return cart


def cart_count(request):
    """Total quantity in the cart with a single query (used by the header badge)."""
    if request.user.is_authenticated:
        qs = CartItem.objects.filter(cart__user=request.user)
    else:
        cart_id = request.session.get(SESSION_KEY)
        if not cart_id:
            return 0
        qs = CartItem.objects.filter(cart_id=cart_id, cart__user__isnull=True)
    return qs.aggregate(n=Sum('quantity'))['n'] or 0


def _touch(cart_id):
    # auto_now does not fire on item changes; this keeps the stale-cart cleanup accurate
    Cart.objects.filter(pk=cart_id).update(updated_at=timezone.now())


@transaction.atomic
def add_item(cart, variant_id, quantity=1):
    if quantity < 1:
        raise CartError('تعداد نامعتبر است.')
    variant = (
        ProductVariant.objects.select_related('product')
        .filter(pk=variant_id, is_active=True, product__is_active=True)
        .first()
    )
    if variant is None:
        raise CartError('این کالا در دسترس نیست.')
    if variant.stock <= 0:
        raise CartError('این کالا ناموجود است.')

    limit = min(variant.stock, MAX_QTY_PER_ITEM)

    # Lock the existing row (if any) so two quick clicks cannot both pass the limit check
    item = (
        CartItem.objects.select_for_update()
        .filter(cart=cart, variant=variant)
        .first()
    )
    if item is None:
        if quantity > limit:
            raise CartError(f'حداکثر {limit} عدد از این کالا قابل سفارش است.')
        try:
            # Savepoint: a parallel request may create the same row first
            with transaction.atomic():
                CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
        except IntegrityError:
            # Lost the race: the row exists now, so add to it instead
            item = CartItem.objects.select_for_update().get(cart=cart, variant=variant)
        else:
            _touch(cart.pk)
            return

    new_qty = item.quantity + quantity
    if new_qty > limit:
        raise CartError(f'حداکثر {limit} عدد از این کالا قابل سفارش است.')
    item.quantity = new_qty
    item.save(update_fields=['quantity'])
    _touch(cart.pk)

@transaction.atomic
def set_quantity(item, quantity):
    if quantity <= 0:
        item.delete()
    else:
        variant = item.variant
        limit = min(variant.stock, MAX_QTY_PER_ITEM)
        if limit <= 0:
            raise CartError('این کالا ناموجود است.')
        if quantity > limit:
            raise CartError(f'حداکثر {limit} عدد از این کالا قابل سفارش است.')
        item.quantity = quantity
        item.save(update_fields=['quantity'])
    _touch(item.cart_id)


def get_cart_data(cart):
    """Everything the cart page needs. Only valid lines count towards totals."""
    if cart is None:
        return {'lines': [], 'count': 0, 'total': 0, 'total_old': 0, 'savings': 0, 'has_problems': False}

    lines = list(
        cart.items.select_related('variant__product__brand')
        .prefetch_related(Prefetch(
            'variant__product__images',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_images',
        ))
        .order_by('-added_at')
    )
    valid = [i for i in lines if i.is_valid]
    total = sum(i.line_total for i in valid)
    total_old = sum(i.line_old_total for i in valid)
    return {
        'lines': lines,
        'count': sum(i.quantity for i in lines),
        'total': total,
        'total_old': total_old,
        'savings': total_old - total,
        'has_problems': len(valid) != len(lines),
    }


@transaction.atomic
def merge_guest_cart(guest_cart_id, user):
    """Move guest items into the user's cart, capped by stock, then delete the guest cart."""
    guest = Cart.objects.select_for_update().filter(pk=guest_cart_id, user__isnull=True).first()
    if guest is None:
        return
    cart, _ = Cart.objects.get_or_create(user=user)
    existing = {i.variant_id: i for i in cart.items.all()}

    for gi in guest.items.select_related('variant__product'):
        v = gi.variant
        limit = min(v.stock, MAX_QTY_PER_ITEM)
        if not (v.is_active and v.product.is_active) or limit <= 0:
            continue
        if gi.variant_id in existing:
            item = existing[gi.variant_id]
            item.quantity = min(item.quantity + gi.quantity, limit)
            item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(cart=cart, variant=v, quantity=min(gi.quantity, limit))

    guest.delete()
    _touch(cart.pk)