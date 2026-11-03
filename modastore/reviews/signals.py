from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Review
from .services import services



@receiver([post_save, post_delete], sender=Review)
def refresh_product_rating(sender, instance, **kwargs):
    transaction.on_commit(lambda: services.recalculate(instance.product_id))