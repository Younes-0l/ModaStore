from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.conf import settings


# Iranian mobile format: 09xxxxxxxxx (11 digits)
phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید ۱۱ رقم باشد و با ۰۹ شروع شود.',
)

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, password, **extra_fields):
        if not phone_number:
            raise ValueError('The phone number is required.')
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Customers log in via OTP, so no password is needed
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not password:
            raise ValueError('Superuser must have a password.')
        return self._create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField('شماره موبایل', max_length=11, unique=True, validators=[phone_validator])
    first_name = models.CharField('نام', max_length=100, blank=True)
    last_name = models.CharField('نام خانوادگی', max_length=100, blank=True)
    email = models.EmailField('ایمیل', blank=True)
    is_active = models.BooleanField('فعال', default=True)
    is_staff = models.BooleanField('دسترسی به پنل مدیریت', default=False)
    date_joined = models.DateTimeField('تاریخ عضویت', default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    def __str__(self):
        return self.phone_number

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class OTPCode(models.Model):
    """A one-time login code. Only a keyed hash of the code is stored."""

    phone_number = models.CharField('شماره موبایل', max_length=11, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)
    expires_at = models.DateTimeField('زمان انقضا')
    attempts = models.PositiveSmallIntegerField('تعداد تلاش', default=0)
    is_used = models.BooleanField('استفاده‌شده', default=False)

    class Meta:
        verbose_name = 'کد یکبارمصرف'
        verbose_name_plural = 'کدهای یکبارمصرف'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['phone_number', '-created_at'])]

    def __str__(self):
        return f'{self.phone_number} ({self.created_at:%Y-%m-%d %H:%M})'


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='کاربر',
        on_delete=models.CASCADE, related_name='addresses',
    )
    title = models.CharField('عنوان', max_length=50, help_text='مثلاً: خانه، محل کار')
    receiver_name = models.CharField('نام گیرنده', max_length=100)
    receiver_phone = models.CharField(
        'موبایل گیرنده', max_length=11, validators=[phone_validator],
    )
    province = models.CharField('استان', max_length=60)
    city = models.CharField('شهر', max_length=60)
    postal_code = models.CharField(
        'کد پستی', max_length=10,
        validators=[RegexValidator(r'^\d{10}$', 'کد پستی باید ۱۰ رقم باشد.')],
    )
    full_address = models.TextField('آدرس کامل')
    is_default = models.BooleanField('آدرس پیش‌فرض', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'آدرس'
        verbose_name_plural = 'آدرس‌ها'
        ordering = ['-is_default', '-created_at']
        constraints = [
            # At most one default address per user
            models.UniqueConstraint(
                fields=['user'], condition=models.Q(is_default=True),
                name='unique_default_address_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.title} - {self.city}'