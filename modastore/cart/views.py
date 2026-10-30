from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from . import services
from .models import CartItem


# Create your views here.

def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _respond(request, ok, message, status=200):
    """JSON for fetch(), flash message + redirect for plain form posts."""
    if _is_ajax(request):
        return JsonResponse(
            {'ok': ok, 'message': message, 'count': services.cart_count(request)},
            status=200 if ok else status,
        )
    messages.add_message(request, messages.SUCCESS if ok else messages.ERROR, message)
    referer = request.META.get('HTTP_REFERER', '')
    if not ok and referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect('cart:detail')


def cart_detail(request):
    cart = services.get_cart(request, create=False)
    return render(request, 'cart/cart.html', services.get_cart_data(cart))


@require_POST
def cart_add(request):
    try:
        variant_id = int(request.POST.get('variant_id', ''))
        quantity = int(request.POST.get('quantity', '1'))
    except ValueError:
        return _respond(request, False, 'درخواست نامعتبر است.', status=400)

    cart = services.get_cart(request, create=True)
    try:
        services.add_item(cart, variant_id, quantity)
    except services.CartError as e:
        return _respond(request, False, str(e), status=409)
    return _respond(request, True, 'به سبد خرید اضافه شد.')


def _get_item_or_404(request, pk):
    cart = services.get_cart(request, create=False)
    if cart is None:
        raise Http404
    # Restricting by the current cart means other people's items return 404
    return get_object_or_404(
        CartItem.objects.select_related('variant__product'), pk=pk, cart=cart,
    )


@require_POST
def cart_update(request, pk):
    item = _get_item_or_404(request, pk)
    try:
        quantity = int(request.POST.get('quantity', ''))
        services.set_quantity(item, quantity)
    except ValueError:
        return _respond(request, False, 'تعداد نامعتبر است.', status=400)
    except services.CartError as e:
        return _respond(request, False, str(e), status=409)
    return redirect('cart:detail')


@require_POST
def cart_remove(request, pk):
    item = _get_item_or_404(request, pk)
    services.set_quantity(item, 0)
    messages.success(request, 'کالا از سبد حذف شد.')
    return redirect('cart:detail')