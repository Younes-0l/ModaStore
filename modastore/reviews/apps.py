from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    name = 'reviews'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'نظرات'

    def ready(self):
        from . import signals  # noqa: F401