from django.db import models
from django.conf import settings


# Create your models here.

class ContactMessage(models.Model):
    """A message sent through the public contact form (read in the admin)."""

    class Subject(models.TextChoices):
        ORDER = 'order', 'سفارش و پرداخت'
        PRODUCT = 'product', 'سوال درباره کالا'
        RETURN = 'return', 'مرجوعی و ضمانت'
        OTHER = 'other', 'سایر موارد'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='کاربر', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='contact_messages',
    )
    name = models.CharField('نام', max_length=80)
    phone = models.CharField('موبایل', max_length=11)
    subject = models.CharField('موضوع', max_length=10, choices=Subject.choices, default=Subject.OTHER)
    message = models.TextField('پیام', max_length=2000)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    is_handled = models.BooleanField('بررسی شد', default=False, db_index=True)
    created_at = models.DateTimeField('تاریخ ارسال', auto_now_add=True)

    class Meta:
        verbose_name = 'پیام تماس'
        verbose_name_plural = 'پیام‌های تماس'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.get_subject_display()}'
