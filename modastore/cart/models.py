from django.db import models
from django.conf import settings
from catalog.models import ProductVariant

MAX_QTY_PER_ITEM = 10
# Create your models here.

class Cart(models.Model):
    """A logged-in user's cart, or a guest cart (user is empty, id is kept in the session)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='کاربر', null=True, blank=True,
        on_delete=models.CASCADE, related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سبد خرید'
        verbose_name_plural = 'سبدهای خرید'

    def __str__(self):
        return f'Cart #{self.pk} ({self.user or "guest"})'


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(ProductVariant, verbose_name='تنوع محصول', on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField('تعداد', default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'آیتم سبد'
        verbose_name_plural = 'آیتم‌های سبد'
        constraints = [
            models.UniqueConstraint(fields=['cart', 'variant'], name='unique_variant_per_cart'),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name='cart_item_quantity_gte_1'),
        ]

    def __str__(self):
        return f'{self.variant} x {self.quantity}'

    @property
    def is_available(self):
        v = self.variant
        return v.is_active and v.product.is_active and v.stock > 0

    @property
    def exceeds_stock(self):
        return self.quantity > self.variant.stock

    @property
    def is_valid(self):
        return self.is_available and not self.exceeds_stock

    @property
    def max_quantity(self):
        return min(self.variant.stock, MAX_QTY_PER_ITEM)

    @property
    def line_total(self):
        return self.variant.price * self.quantity

    @property
    def line_old_total(self):
        return (self.variant.old_price or self.variant.price) * self.quantity