import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone
from catalog.models import ProductImage, ProductVariant
from ..models import Order, OrderItem, Payment, generate_order_number


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


def start_payment(order):
    """Create a payment attempt and return the URL the user must be sent to."""
    with transaction.atomic():
        order.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.FAILED)
        payment = Payment.objects.create(order=order, amount=order.total)
    if settings.PAYMENT_GATEWAY == 'mock':
        return reverse('orders:mock_gateway', args=[payment.authority])
    raise NotImplementedError('A real payment gateway is added in phase 5.')


def finish_payment(payment_id, success):
    """Idempotent: a payment that is already settled is returned unchanged."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status != Payment.Status.PENDING:
            return payment
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        now = timezone.now()
        if success and order.status == Order.Status.PENDING and order.expires_at > now:
            payment.status = Payment.Status.SUCCESS
            payment.ref_id = f'MOCK-{secrets.randbelow(10**8):08d}'
            payment.paid_at = now
            order.status = Order.Status.PROCESSING
            order.paid_at = now
            order.save(update_fields=['status', 'paid_at'])
        else:
            payment.status = Payment.Status.FAILED
        payment.save()
    return payment