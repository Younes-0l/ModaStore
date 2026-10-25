from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


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