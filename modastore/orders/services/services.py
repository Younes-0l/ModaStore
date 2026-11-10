import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone
from catalog.models import ProductImage, ProductVariant
from ..models import Order, OrderItem, Payment, generate_order_number
import logging
from .. import gateway


logger = logging.getLogger(__name__)
SETTLED = (Payment.Status.SUCCESS, Payment.Status.REFUND_NEEDED, Payment.Status.REFUNDED)

class CheckoutError(Exception):
    """Raised with a user-facing (Persian) message."""


def shipping_fee(subtotal):
    threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', None)
    if threshold and subtotal >= threshold:
        return 0
    return settings.SHIPPING_FEE


@transaction.atomic
def place_order(user, cart, address):
    """Validate stock under row locks, snapshot everything, reserve stock, empty the cart."""
    lines = list(
        cart.items.select_related('variant__product')
        .prefetch_related(Prefetch(
            'variant__product__images',
            queryset=ProductImage.objects.filter(is_main=True),
            to_attr='main_images',
        ))
        .order_by('variant_id')
    )
    if not lines:
        raise CheckoutError('سبد خرید شما خالی است.')

    # Lock in a fixed order (by pk) so two checkouts cannot deadlock each other
    locked = {
        v.pk: v for v in
        ProductVariant.objects.select_for_update(of=('self',))
        .select_related('product')
        .filter(pk__in=[ln.variant_id for ln in lines])
        .order_by('pk')
    }

    subtotal = 0
    for ln in lines:
        v = locked.get(ln.variant_id)
        if v is None or not (v.is_active and v.product.is_active):
            raise CheckoutError('یکی از کالاهای سبد دیگر در دسترس نیست.')
        if ln.quantity > v.stock:
            raise CheckoutError(f'موجودی «{v.product.name}» کافی نیست.')
        subtotal += v.price * ln.quantity

    fee = shipping_fee(subtotal)
    order = Order.objects.create(
        number=generate_order_number(),
        user=user,
        receiver_name=address.receiver_name,
        receiver_phone=address.receiver_phone,
        province=address.province,
        city=address.city,
        postal_code=address.postal_code,
        full_address=address.full_address,
        subtotal=subtotal,
        shipping_fee=fee,
        total=subtotal + fee,
        expires_at=timezone.now() + timedelta(minutes=settings.ORDER_PAYMENT_TIMEOUT_MINUTES),
    )

    items = []
    for ln in lines:
        v = locked[ln.variant_id]
        images = ln.variant.product.main_images
        items.append(OrderItem(
            order=order, variant=v, product_name=v.product.name, sku=v.sku,
            color=v.color, storage=v.storage, unit_price=v.price, quantity=ln.quantity,
            image_name=images[0].image.name if images else '',
        ))
        v.stock -= ln.quantity   # reserve stock
        v.save(update_fields=['stock'])
    OrderItem.objects.bulk_create(items)

    cart.items.all().delete()
    return order


@transaction.atomic
def cancel_order(order_id):
    """Cancel an unpaid order and give its stock back. Returns True if it was canceled."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != Order.Status.PENDING:
        return False

    items = list(order.items.filter(variant__isnull=False).order_by('variant_id'))
    variants = {
        v.pk: v for v in
        ProductVariant.objects.select_for_update()
        .filter(pk__in=[i.variant_id for i in items]).order_by('pk')
    }
    for i in items:
        v = variants.get(i.variant_id)
        if v:
            v.stock += i.quantity
            v.save(update_fields=['stock'])

    order.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.FAILED)
    order.status = Order.Status.CANCELED
    order.save(update_fields=['status'])
    return True


def expire_overdue_orders():
    """Cancel every unpaid order whose payment window is over."""
    ids = list(
        Order.objects.filter(status=Order.Status.PENDING, expires_at__lte=timezone.now())
        .values_list('pk', flat=True)
    )
    return sum(1 for pk in ids if cancel_order(pk))


def expire_if_overdue(order):
    if order.status == Order.Status.PENDING and order.expires_at <= timezone.now():
        cancel_order(order.pk)
        order.refresh_from_db()
    return order


def _callback_url():
    return settings.SITE_URL.rstrip('/') + reverse('orders:callback')


def start_payment(order):
    """Create a payment attempt and return the URL the user must be sent to."""
    if order.status != Order.Status.PENDING or order.expires_at <= timezone.now():
        raise CheckoutError('مهلت پرداخت این سفارش تمام شده است.')

    use_mock = settings.PAYMENT_GATEWAY == 'mock'
    with transaction.atomic():
        order.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.FAILED)
        payment = Payment.objects.create(
            order=order, amount=order.total,
            gateway=Payment.Gateway.MOCK if use_mock else Payment.Gateway.ZARINPAL,
        )
    if use_mock:
        return reverse('orders:mock_gateway', args=[payment.authority])

    try:
        authority = gateway.request_payment(
            amount=order.total, callback_url=_callback_url(),
            description=f'سفارش {order.number}',
            mobile=order.user.phone_number, order_number=order.number,
        )
    except gateway.GatewayError as exc:
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.FAILED)
        raise CheckoutError(str(exc))
    # From now on the gateway's authority identifies this payment
    Payment.objects.filter(pk=payment.pk).update(authority=authority)
    return gateway.start_url(authority)


def _reserve_again(order):
    """Take stock again for an order that was canceled before its money arrived."""
    items = list(order.items.order_by('variant_id'))
    if not items or any(i.variant_id is None for i in items):
        return False
    variants = {
        v.pk: v for v in
        ProductVariant.objects.select_for_update(of=('self',))
        .select_related('product')
        .filter(pk__in=[i.variant_id for i in items]).order_by('pk')
    }
    for i in items:
        v = variants.get(i.variant_id)
        if v is None or v.stock < i.quantity:
            return False
    for i in items:
        v = variants[i.variant_id]
        v.stock -= i.quantity
        v.save(update_fields=['stock'])
    return True


def _apply_paid(payment_id, ref_id):
    """Record a payment that the gateway confirmed. Idempotent and safe under concurrency."""
    with transaction.atomic():
        order_id = Payment.objects.values_list('order_id', flat=True).get(pk=payment_id)
        # Same lock order everywhere (order, then payment): no deadlock with cancel_order
        order = Order.objects.select_for_update().get(pk=order_id)
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status in SETTLED:
            return payment

        now = timezone.now()
        payment.ref_id = ref_id
        payment.paid_at = now

        can_fulfil = False
        if payment.amount == order.total:
            if order.status == Order.Status.PENDING:
                # Money arrived: accept it even if the window just closed but the
                # order was not canceled yet (its stock is still reserved)
                can_fulfil = True
            elif order.status == Order.Status.CANCELED:
                can_fulfil = _reserve_again(order)

        if can_fulfil:
            payment.status = Payment.Status.SUCCESS
            order.status = Order.Status.PROCESSING
            order.paid_at = now
            order.save(update_fields=['status', 'paid_at'])
            order.payments.filter(status=Payment.Status.PENDING).exclude(pk=payment.pk).update(
                status=Payment.Status.FAILED,
            )
        else:
            # Paid twice, amount mismatch, or the stock is gone: an admin must refund
            payment.status = Payment.Status.REFUND_NEEDED
            logger.warning('Payment %s (order %s) needs a refund', payment.pk, order.number)
        payment.save()
        return payment


def settle_gateway_payment(payment, status_ok):
    """Called when the user comes back from the bank. Safe to call many times."""
    if payment.status in SETTLED:
        return payment
    if not status_ok:
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED,
        )
        return payment
    # Network call: no DB locks are held here. A payment we marked FAILED earlier
    # (a superseded attempt or an expired order) is verified too, since the gateway is the truth.
    paid, ref_id = gateway.verify(payment.amount, payment.authority)
    if not paid:
        Payment.objects.filter(pk=payment.pk, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED,
        )
        return payment
    return _apply_paid(payment.pk, ref_id)


def finish_payment(payment_id, success):
    """Mock gateway: same rules as the real one, so both paths are testable."""
    payment = Payment.objects.get(pk=payment_id)
    if payment.status in SETTLED:
        return payment
    if success:
        return _apply_paid(payment_id, f'MOCK-{secrets.randbelow(10**8):08d}')
    Payment.objects.filter(pk=payment_id, status=Payment.Status.PENDING).update(
        status=Payment.Status.FAILED,
    )
    payment.refresh_from_db()
    return payment