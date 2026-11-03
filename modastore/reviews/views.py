from django.shortcuts import render, get_object_or_404, redirect
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from catalog.models import Product
from .services import services
from .forms import ReviewForm
from .models import Review


# Create your views here.

def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _safe_next(request):
    target = request.POST.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return target
    return ''


def _product_url(product):
    return reverse('catalog:product_detail', args=[product.slug]) + '#reviews'


@login_required
def review_write(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    existing = Review.objects.filter(user=request.user, product=product).first()
    form = ReviewForm(request.POST or None, instance=existing)

    if request.method == 'POST' and form.is_valid():
        try:
            review = services.submit_review(request.user, product, form.save(commit=False))
        except services.ReviewError as e:
            form.add_error(None, str(e))
        else:
            if review.status == Review.Status.APPROVED:
                messages.success(request, 'نظر شما ثبت شد. ممنون از همراهی‌تان!')
            else:
                messages.success(request, 'نظر شما ثبت شد و پس از بررسی منتشر می‌شود.')
            return redirect(_product_url(product))

    return render(request, 'reviews/write.html', {
        'form': form, 'product': product, 'existing': existing,
        'image': product.images.filter(is_main=True).first() or product.images.first(),
    })


@login_required
@require_POST
def review_delete(request, pk):
    # Filtering by user: other people's reviews return 404
    review = get_object_or_404(Review.objects.select_related('product'), pk=pk, user=request.user)
    product = review.product
    review.delete()
    messages.success(request, 'نظر شما حذف شد.')
    return redirect(_product_url(product))


@require_POST
def review_helpful(request, pk):
    nxt = _safe_next(request)

    if not request.user.is_authenticated:
        login_url = reverse('accounts:login') + ('?' + urlencode({'next': nxt}) if nxt else '')
        if _is_ajax(request):
            return JsonResponse({
                'ok': False, 'login_url': login_url,
                'message': 'برای ثبت رأی وارد حساب خود شوید.',
            }, status=401)
        return redirect(login_url)

    active = request.POST.get('active') == '1'
    try:
        count = services.set_helpful(request.user, pk, active)
    except services.ReviewError as e:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'message': str(e)}, status=409)
        messages.error(request, str(e))
        return redirect(nxt or 'catalog:home')

    if _is_ajax(request):
        return JsonResponse({'ok': True, 'active': active, 'count': count})
    return redirect(nxt or 'catalog:home')