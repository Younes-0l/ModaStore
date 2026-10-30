# cart/signals.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from . import services


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    if request is None:
        return
    cart_id = request.session.get(services.SESSION_KEY)
    if cart_id:
        services.merge_guest_cart(cart_id, user)
        request.session.pop(services.SESSION_KEY, None)