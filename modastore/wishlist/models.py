from django.db import models
from django.conf import settings


# Create your models here.

class WishlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='کاربر',
        on_delete=models.CASCADE, related_name='wishlist_items',
    )
    product = models.ForeignKey(
        'catalog.Product', verbose_name='محصول',
        on_delete=models.CASCADE, related_name='wishlisted_by',
    )
    added_at = models.DateTimeField('تاریخ افزودن', auto_now_add=True)

    class Meta:
        verbose_name = 'علاقه‌مندی'
        verbose_name_plural = 'علاقه‌مندی‌ها'
        ordering = ['-added_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_wishlist_product'),
        ]
        indexes = [models.Index(fields=['user', '-added_at'])]

    def __str__(self):
        return f'{self.user} - {self.product}'