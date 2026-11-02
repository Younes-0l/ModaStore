from django.utils.functional import SimpleLazyObject
from .services import services


def wishlist(request):
    """wishlist_ids is lazy: the query runs only if a template actually uses it."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'wishlist_ids': frozenset()}
    return {'wishlist_ids': SimpleLazyObject(lambda: services.get_ids(user))}