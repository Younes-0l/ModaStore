from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.db.models import Prefetch
from django.views.decorators.http import require_POST
from accounts.models import Address
from accounts.services.addresses import save_address
from cart import services as cart_services
from .services import services
from .forms import CheckoutAddressForm
from .models import Order, OrderItem, Payment


SESSION_ADDRESS_KEY = 'checkout_address_id'

# Create your views here.

def _checkout_cart(request):
    """Return (cart, data, redirect_response). The response is set when checkout cannot proceed."""
    cart = cart_services.get_cart(request, create=False)
    data = cart_services.get_cart_data(cart)
    if not data['lines']:
        messages.error(request, 'سبد خرید شما خالی است.')
        return None, None, redirect('cart:detail')
    if data['has_problems']:
        messages.error(request, 'ابتدا مشکلات سبد خرید را برطرف کنید.')
        return None, None, redirect('cart:detail')
    return cart, data, None


def _totals(data):
    fee = services.shipping_fee(data['total'])
    return {'shipping': fee, 'payable': data['total'] + fee}


def _get_order(request, number):
    # Filtering by user: other people's orders return 404
    return get_object_or_404(Order, number=number, user=request.user)


# ---------- Step 2: shipping information ----------

@login_required
def checkout_address(request):
    cart, data, early = _checkout_cart(request)
    if early:
        return early

    addresses = list(request.user.addresses.all()[:4])
    mode = request.POST.get('mode')
    if mode not in ('saved', 'new') or (mode == 'saved' and not addresses):
        mode = 'saved' if addresses else 'new'

    form = CheckoutAddressForm(
        request.POST if request.method == 'POST' and mode == 'new' else None,
        initial={
            'receiver_name': request.user.full_name,
            'receiver_phone': request.user.phone_number,
            'title': 'خانه',
        },
    )

    if request.method == 'POST':
        if mode == 'saved':
            address = next((a for a in addresses if str(a.pk) == request.POST.get('address_id')), None)
            if address is None:
                messages.error(request, 'لطفاً یک آدرس را انتخاب کنید.')
            else:
                request.session[SESSION_ADDRESS_KEY] = address.pk
                return redirect('orders:review')
        elif form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            save_address(address)
            request.session[SESSION_ADDRESS_KEY] = address.pk
            return redirect('orders:review')

    selected_id = request.session.get(SESSION_ADDRESS_KEY)
    if addresses and selected_id not in [a.pk for a in addresses]:
        selected_id = addresses[0].pk

    return render(request, 'orders/checkout_address.html', {
        **data, **_totals(data),
        'form': form, 'addresses': addresses, 'mode': mode, 'selected_id': selected_id,
    })


# ---------- Step 3: review and place the order ----------

@login_required
def checkout_review(request):
    cart, data, early = _checkout_cart(request)
    if early:
        return early

    address = Address.objects.filter(pk=request.session.get(SESSION_ADDRESS_KEY), user=request.user).first()
    if address is None:
        return redirect('orders:checkout')

    if request.method == 'POST':
        # Free the stock held by abandoned orders before checking availability
        services.expire_overdue_orders()
        try:
            order = services.place_order(request.user, cart, address)
        except services.CheckoutError as e:
            messages.error(request, str(e))
            return redirect('cart:detail')
        request.session.pop(SESSION_ADDRESS_KEY, None)
        return redirect('orders:pay', number=order.number)

    return render(request, 'orders/checkout_review.html', {
        **data, **_totals(data),
        'address': address,
        'timeout_minutes': settings.ORDER_PAYMENT_TIMEOUT_MINUTES,
    })


# ---------- Step 4: payment ----------

@login_required
def pay(request, number):
    order = services.expire_if_overdue(_get_order(request, number))
    if order.status != Order.Status.PENDING:
        return redirect('orders:result', number=order.number)
    if request.method == 'POST':
        return redirect(services.start_payment(order))
    return render(request, 'orders/pay.html', {'order': order})


@login_required
@require_POST
def cancel(request, number):
    order = _get_order(request, number)
    if services.cancel_order(order.pk):
        messages.success(request, 'سفارش لغو شد و موجودی کالاها آزاد شد.')
    return redirect('orders:detail', number=order.number)


def _mock_only():
    if settings.PAYMENT_GATEWAY != 'mock':
        raise Http404


@login_required
def mock_gateway(request, authority):
    """Development-only fake bank page."""
    _mock_only()
    payment = get_object_or_404(Payment, authority=authority, order__user=request.user)
    if payment.status != Payment.Status.PENDING:
        return redirect('orders:result', number=payment.order.number)
    if request.method == 'POST':
        services.finish_payment(payment.pk, success=request.POST.get('result') == 'success')
        return redirect('orders:result', number=payment.order.number)
    return render(request, 'orders/gateway.html', {'payment': payment})


# ---------- Step 5: confirmation ----------

@login_required
def result(request, number):
    order = services.expire_if_overdue(_get_order(request, number))
    if order.status == Order.Status.PENDING and not order.payments.exists():
        return redirect('orders:pay', number=order.number)
    return render(request, 'orders/result.html', {
        'order': order,
        'payment': order.payments.first(),
        # 6 means "every step is done"
        'step': 6 if order.is_paid else 4,
    })


# ---------- Order history ----------

@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')[:30]
    return render(request, 'orders/list.html', {'orders': orders})


@login_required
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('variant__product')),
        ),
        number=number, user=request.user,
    )
    order = services.expire_if_overdue(order)
    return render(request, 'orders/detail.html', {'order': order})