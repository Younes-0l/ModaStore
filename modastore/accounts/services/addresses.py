from django.db import transaction
from ..models import Address


def save_address(address):
    """Keep exactly one default address; the first address becomes default."""
    with transaction.atomic():
        has_other = Address.objects.filter(user=address.user).exclude(pk=address.pk).exists()
        if not has_other:
            address.is_default = True
        if address.is_default:
            Address.objects.filter(user=address.user, is_default=True).exclude(
                pk=address.pk
            ).update(is_default=False)
        address.save()