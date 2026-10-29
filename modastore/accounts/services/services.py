import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ..models import OTPCode
from .sms import send_otp_sms


class OTPError(Exception):
    """Raised with a user-facing (Persian) message."""


def _hash_code(phone_number: str, code: str) -> str:
    # Bind the hash to the phone number so codes cannot be replayed on another number
    msg = f'{phone_number}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def request_otp(phone_number: str) -> None:
    now = timezone.now()
    recent = OTPCode.objects.filter(phone_number=phone_number)

    last = recent.first()
    if last and (now - last.created_at).total_seconds() < settings.OTP_RESEND_SECONDS:
        wait = settings.OTP_RESEND_SECONDS - int((now - last.created_at).total_seconds())
        raise OTPError(f'لطفاً {wait} ثانیه دیگر دوباره تلاش کنید.')

    hourly = recent.filter(created_at__gte=now - timedelta(hours=1)).count()
    if hourly >= settings.OTP_MAX_REQUESTS_PER_HOUR:
        raise OTPError('تعداد درخواست‌ها زیاد است. لطفاً بعداً تلاش کنید.')

    # Invalidate previous codes: only the newest code is valid
    recent.filter(is_used=False).update(is_used=True)

    # secrets (not random) because this is a security token
    code = ''.join(secrets.choice('0123456789') for _ in range(settings.OTP_LENGTH))
    OTPCode.objects.create(
        phone_number=phone_number,
        code_hash=_hash_code(phone_number, code),
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    send_otp_sms(phone_number, code)


def resend_wait_seconds(phone_number: str) -> int:
    """Seconds left before another code may be requested (for the countdown UI)."""
    last = OTPCode.objects.filter(phone_number=phone_number).first()
    if not last:
        return 0
    passed = (timezone.now() - last.created_at).total_seconds()
    return max(0, settings.OTP_RESEND_SECONDS - int(passed))


@transaction.atomic
def verify_otp(phone_number: str, code: str):
    """Return the user (created on first login) or raise OTPError."""
    # Row lock prevents parallel requests from bypassing the attempt limit
    otp = (
        OTPCode.objects.select_for_update()
        .filter(phone_number=phone_number, is_used=False)
        .first()
    )
    generic = OTPError('کد وارد‌شده نادرست یا منقضی شده است.')
    if otp is None or otp.expires_at < timezone.now():
        raise generic
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        raise OTPError('تعداد تلاش‌ها بیش از حد مجاز است. کد جدید دریافت کنید.')

    if not hmac.compare_digest(otp.code_hash, _hash_code(phone_number, code)):
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        raise generic

    otp.is_used = True
    otp.save(update_fields=['is_used'])

    User = get_user_model()
    user, _ = User.objects.get_or_create(phone_number=phone_number)
    if not user.is_active:
        raise OTPError('حساب کاربری شما غیرفعال شده است.')
    return user