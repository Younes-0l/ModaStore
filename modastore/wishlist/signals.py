from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .services import services


SESSION_KEY = 'wishlist_pending'


@receiver(user_logged_in)
def apply_pending_wish(sender, request, user, **kwargs):
    """A guest pressed a heart, logged in, and the product is saved for them now."""
    if request is None:
        return
    product_id = request.session.pop(SESSION_KEY, None)
    if product_id:
        try:
            services.set_state(user, product_id, True)
        except services.WishlistError:
            pass