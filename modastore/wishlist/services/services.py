from catalog.models import Product
from ..models import WishlistItem


MAX_ITEMS = 200


class WishlistError(Exception):
    """Raised with a user-facing (Persian) message."""


def get_ids(user):
    return set(WishlistItem.objects.filter(user=user).values_list('product_id', flat=True))


def count(user):
    return WishlistItem.objects.filter(user=user).count()


def set_state(user, product_id, active):
    """Idempotent: calling it twice with the same value changes nothing the second time."""
    if not active:
        WishlistItem.objects.filter(user=user, product_id=product_id).delete()
        return

    if not Product.objects.filter(pk=product_id, is_active=True).exists():
        raise WishlistError('این محصول در دسترس نیست.')

    items = WishlistItem.objects.filter(user=user)
    if not items.filter(product_id=product_id).exists() and items.count() >= MAX_ITEMS:
        raise WishlistError(f'حداکثر {MAX_ITEMS} کالا را می‌توانید ذخیره کنید.')

    # get_or_create handles two parallel requests creating the same row
    WishlistItem.objects.get_or_create(user=user, product_id=product_id)