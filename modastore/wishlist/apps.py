from django.apps import AppConfig


class WishlistConfig(AppConfig):
    name = 'wishlist'
    verbose_name = 'علاقه‌مندی‌ها'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signals