"""Small factories shared by the whole test suite (no third-party packages needed)."""
import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Address
from cart.models import Cart
from cart import services as cart_services
from catalog.models import Brand, Category, Product, ProductVariant
from orders.models import Order, OrderItem, generate_order_number

_n = itertools.count(1)


def make_user(**extra):
    phone = extra.pop('phone_number', f'0912{next(_n):07d}')
    return get_user_model().objects.create_user(phone_number=phone, **extra)


def make_superuser(phone='09100000000', password='pass12345'):
    return get_user_model().objects.create_superuser(phone_number=phone, password=password)


def make_category(name='موبایل', parent=None, **kw):
    obj, _ = Category.objects.get_or_create(name=name, parent=parent, defaults=kw)
    return obj


def make_brand(name='سامسونگ', **kw):
    obj, _ = Brand.objects.get_or_create(name=name, defaults=kw)
    return obj


def make_product(name=None, brand=None, category=None, **kw):
    kw.setdefault('is_active', True)
    return Product.objects.create(
        name=name or f'گوشی نمونه {next(_n)}',
        brand=brand or make_brand(),
        category=category or make_category(),
        **kw,
    )


def make_variant(product=None, **kw):
    n = next(_n)
    kw.setdefault('sku', f'SKU-{n}')
    kw.setdefault('price', 1_000_000)
    kw.setdefault('stock', 5)
    return ProductVariant.objects.create(product=product or make_product(), **kw)


def make_address(user, **kw):
    data = dict(
        title='خانه', receiver_name='علی رضایی', receiver_phone='09121234567',
        province='تهران', city='تهران', postal_code='1234567890',
        full_address='خیابان ولیعصر، پلاک ۱',
    )
    data.update(kw)
    return Address.objects.create(user=user, **data)


def fill_cart(user, *items):
    """items are (variant, quantity) pairs; returns the user's cart."""
    cart, _ = Cart.objects.get_or_create(user=user)
    for variant, quantity in items:
        cart_services.add_item(cart, variant.pk, quantity)
    return cart


def make_order(user, variant, quantity=1, status=Order.Status.PENDING, **kw):
    """Build an order directly (no stock changes), e.g. to simulate a past purchase."""
    total = variant.price * quantity
    order = Order.objects.create(
        number=generate_order_number(), user=user, status=status,
        receiver_name='علی رضایی', receiver_phone='09121234567',
        province='تهران', city='تهران', postal_code='1234567890', full_address='آدرس تست',
        subtotal=total, shipping_fee=0, total=total,
        expires_at=kw.pop('expires_at', timezone.now() + timedelta(minutes=30)), **kw,
    )
    OrderItem.objects.create(
        order=order, variant=variant, product_name=variant.product.name, sku=variant.sku,
        color=variant.color, storage=variant.storage, unit_price=variant.price, quantity=quantity,
    )
    return order
