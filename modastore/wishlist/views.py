from django.shortcuts import render, redirect
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Prefetch
from django.http import JsonResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from catalog.models import Product, ProductImage, ProductVariant
from .services import services
from .models import WishlistItem
from .signals import SESSION_KEY


# Create your views here.

def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _safe_next(request):
    """Return the posted next target only if it points to this site."""
    target = request.POST.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return target
    return ''


def _fail(request, message, status, nxt=''):
    if _is_ajax(request):
        return JsonResponse({'ok': False, 'message': message}, status=status)
    messages.error(request, message)
    return redirect(nxt or 'catalog:home')


@require_POST
def wishlist_set(request):
    nxt = _safe_next(request)

    try:
        product_id = int(request.POST.get('product_id', ''))
    except ValueError:
        return _fail(request, 'درخواست نامعتبر است.', 400, nxt)
    active = request.POST.get('active') == '1'

    if not request.user.is_authenticated:
        if active:
            # Remember the wish; it is applied right after a successful login
            request.session[SESSION_KEY] = product_id
        login_url = reverse('accounts:login')
        if nxt:
            login_url += '?' + urlencode({'next': nxt})
        if _is_ajax(request):
            return JsonResponse({
                'ok': False,
                'message': 'برای ذخیره علاقه‌مندی‌ها وارد حساب خود شوید.',
                'login_url': login_url,
            }, status=401)
        return redirect(login_url)

    try:
        services.set_state(request.user, product_id, active)
    except services.WishlistError as e:
        return _fail(request, str(e), 409, nxt)

    if _is_ajax(request):
        return JsonResponse({'ok': True, 'active': active, 'count': services.count(request.user)})
    messages.success(
        request, 'به علاقه‌مندی‌ها اضافه شد.' if active else 'از علاقه‌مندی‌ها حذف شد.',
    )
    return redirect(nxt or 'wishlist:list')


@login_required
def wishlist_list(request):
    has_active_variant = ProductVariant.objects.filter(
        product_id=OuterRef('product_id'), is_active=True,
    )
    # Page over the ids first (cheap), then load full products for that page only
    ids_qs = (
        WishlistItem.objects.filter(user=request.user, product__is_active=True)
        .filter(Exists(has_active_variant))
        .order_by('-added_at', '-id')
        .values_list('product_id', flat=True)
    )
    paginator = Paginator(ids_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    ids = list(page_obj.object_list)

    by_id = {
        p.pk: p for p in Product.objects.filter(pk__in=ids)
        .select_related('brand')
        .prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.filter(is_active=True)),
            Prefetch(
                'images', queryset=ProductImage.objects.filter(is_main=True),
                to_attr='main_images',
            ),
        )
    }
    products = [by_id[i] for i in ids if i in by_id]

    return render(request, 'wishlist/list.html', {
        'products': products, 'page_obj': page_obj, 'paginator': paginator,
    })