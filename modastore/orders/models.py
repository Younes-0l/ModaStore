from django.db import models
import secrets
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone


# Create your models here.

def generate_order_number():
    """Random public order number (not guessable like a sequential ID)."""
    while True:
        number = f'MS{secrets.randbelow(10**9):09d}'
        if not Order.objects.filter(number=number).exists():
            return number


def new_authority():
    return secrets.token_urlsafe(24)


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار پرداخت'
        PROCESSING = 'processing', 'در حال پردازش'
        SHIPPED = 'shipped', 'ارسال شده'
        DELIVERED = 'delivered', 'تحویل داده شده'
        CANCELED = 'canceled', 'لغو شده'

    number = models.CharField('شماره سفارش', max_length=12, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='کاربر',
        on_delete=models.PROTECT, related_name='orders',
    )
    status = models.CharField(
        'وضعیت', max_length=20, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )

    # Address snapshot: later edits to the user's address must not change old orders
    receiver_name = models.CharField('نام گیرنده', max_length=100)
    receiver_phone = models.CharField('موبایل گیرنده', max_length=11)
    province = models.CharField('استان', max_length=60)
    city = models.CharField('شهر', max_length=60)
    postal_code = models.CharField('کد پستی', max_length=10)
    full_address = models.TextField('آدرس کامل')

    subtotal = models.PositiveBigIntegerField('جمع کالاها (تومان)')
    shipping_fee = models.PositiveBigIntegerField('هزینه ارسال (تومان)', default=0)
    total = models.PositiveBigIntegerField('مبلغ نهایی (تومان)')

    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    expires_at = models.DateTimeField('مهلت پرداخت')
    paid_at = models.DateTimeField('تاریخ پرداخت', null=True, blank=True)

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return self.number

    @property
    def is_paid(self):
        return self.status in (self.Status.PROCESSING, self.Status.SHIPPED, self.Status.DELIVERED)

    @property
    def seconds_left(self):
        return max(0, int((self.expires_at - timezone.now()).total_seconds()))


class OrderItem(models.Model):
    """Price and product details are copied here at order time."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        'catalog.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    product_name = models.CharField('نام محصول', max_length=200)
    sku = models.CharField('SKU', max_length=50, blank=True)
    color = models.CharField('رنگ', max_length=50, blank=True)
    storage = models.CharField('حافظه', max_length=50, blank=True)
    image_name = models.CharField(max_length=255, blank=True)
    unit_price = models.PositiveBigIntegerField('قیمت واحد (تومان)')
    quantity = models.PositiveSmallIntegerField('تعداد')

    class Meta:
        verbose_name = 'آیتم سفارش'
        verbose_name_plural = 'آیتم‌های سفارش'

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def image_url(self):
        return default_storage.url(self.image_name) if self.image_name else ''


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        SUCCESS = 'success', 'موفق'
        FAILED = 'failed', 'ناموفق'
        REFUND_NEEDED = 'refund_needed', 'نیاز به بازگشت وجه'
        REFUNDED = 'refunded', 'بازگشت وجه انجام شد'

    class Gateway(models.TextChoices):
        MOCK = 'mock', 'آزمایشی'
        ZARINPAL = 'zarinpal', 'زرین‌پال'

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    gateway = models.CharField('درگاه', max_length=20, choices=Gateway.choices, default=Gateway.MOCK)
    authority = models.CharField(max_length=64, unique=True, default=new_authority, editable=False)
    amount = models.PositiveBigIntegerField('مبلغ (تومان)')
    status = models.CharField('وضعیت', max_length=20, choices=Status.choices, default=Status.PENDING)
    ref_id = models.CharField('شماره پیگیری', max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order.number} - {self.get_status_display()}'