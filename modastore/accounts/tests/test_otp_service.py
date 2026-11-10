from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import OTPCode
from modastore.testutils import make_user

# The module that contains request_otp / verify_otp / OTPError.
# Change this import if your file has a different name.
try:
    from accounts.services.services import otp as otp_service
except ImportError:  # pragma: no cover
    from accounts.services import services as otp_service

PHONE = '09120000001'
OTP_SETTINGS = dict(
    OTP_LENGTH=6, OTP_TTL_SECONDS=120, OTP_RESEND_SECONDS=120,
    OTP_MAX_ATTEMPTS=5, OTP_MAX_REQUESTS_PER_HOUR=5,
)


def issue_code(phone=PHONE):
    """Request a code and capture the plain text that would have been sent by SMS."""
    with mock.patch.object(otp_service, 'send_otp_sms') as sms:
        otp_service.request_otp(phone)
    sms.assert_called_once()
    return sms.call_args.args[1]


def age(phone, seconds):
    """Make existing codes look older, so the resend wait does not block the test."""
    OTPCode.objects.filter(phone_number=phone).update(
        created_at=timezone.now() - timedelta(seconds=seconds),
    )


def wrong_code(code):
    return '000000' if code != '000000' else '111111'


@override_settings(**OTP_SETTINGS)
class RequestOtpTests(TestCase):
    def test_code_is_six_digits_and_stored_only_as_hash(self):
        code = issue_code()
        self.assertRegex(code, r'^\d{6}$')
        otp = OTPCode.objects.get(phone_number=PHONE)
        self.assertEqual(len(otp.code_hash), 64)
        self.assertNotEqual(otp.code_hash, code)
        self.assertEqual(otp.code_hash, otp_service._hash_code(PHONE, code))

    def test_hash_is_bound_to_the_phone_number(self):
        self.assertNotEqual(
            otp_service._hash_code('09120000001', '123456'),
            otp_service._hash_code('09120000002', '123456'),
        )

    def test_code_expires_after_ttl(self):
        issue_code()
        otp = OTPCode.objects.get()
        self.assertAlmostEqual((otp.expires_at - otp.created_at).total_seconds(), 120, delta=3)

    def test_resending_too_soon_is_rejected_and_sends_nothing(self):
        issue_code()
        with mock.patch.object(otp_service, 'send_otp_sms') as sms:
            with self.assertRaises(otp_service.OTPError):
                otp_service.request_otp(PHONE)
        sms.assert_not_called()
        self.assertEqual(OTPCode.objects.count(), 1)

    def test_new_code_invalidates_the_previous_one(self):
        old = issue_code()
        age(PHONE, 130)
        new = issue_code()
        self.assertEqual(OTPCode.objects.filter(is_used=False).count(), 1)
        if old != new:
            with self.assertRaises(otp_service.OTPError):
                otp_service.verify_otp(PHONE, old)
        self.assertEqual(otp_service.verify_otp(PHONE, new).phone_number, PHONE)

    def test_hourly_limit(self):
        for _ in range(5):
            OTPCode.objects.create(phone_number=PHONE, code_hash='x' * 64, expires_at=timezone.now())
        age(PHONE, 600)
        with mock.patch.object(otp_service, 'send_otp_sms') as sms:
            with self.assertRaises(otp_service.OTPError):
                otp_service.request_otp(PHONE)
        sms.assert_not_called()

    def test_limits_are_per_phone_number(self):
        issue_code('09120000001')
        issue_code('09120000002')   # a different number is not blocked
        self.assertEqual(OTPCode.objects.count(), 2)

    def test_resend_wait_seconds(self):
        self.assertEqual(otp_service.resend_wait_seconds(PHONE), 0)
        issue_code()
        self.assertGreater(otp_service.resend_wait_seconds(PHONE), 100)
        age(PHONE, 500)
        self.assertEqual(otp_service.resend_wait_seconds(PHONE), 0)


@override_settings(**OTP_SETTINGS)
class VerifyOtpTests(TestCase):
    def test_success_creates_the_user_on_first_login(self):
        code = issue_code()
        user = otp_service.verify_otp(PHONE, code)
        self.assertEqual(user.phone_number, PHONE)
        self.assertTrue(OTPCode.objects.get().is_used)

    def test_existing_user_is_reused(self):
        existing = make_user(phone_number=PHONE)
        user = otp_service.verify_otp(PHONE, issue_code())
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_code_cannot_be_used_twice(self):
        code = issue_code()
        otp_service.verify_otp(PHONE, code)
        with self.assertRaises(otp_service.OTPError):
            otp_service.verify_otp(PHONE, code)

    def test_wrong_attempts_are_persisted(self):
        """Regression: raising inside transaction.atomic() used to roll the counter back."""
        code = issue_code()
        for expected in (1, 2, 3):
            with self.assertRaises(otp_service.OTPError):
                otp_service.verify_otp(PHONE, wrong_code(code))
            self.assertEqual(OTPCode.objects.get().attempts, expected)

    def test_code_is_burned_after_max_attempts(self):
        code = issue_code()
        for _ in range(5):
            with self.assertRaises(otp_service.OTPError):
                otp_service.verify_otp(PHONE, wrong_code(code))
        otp = OTPCode.objects.get()
        self.assertEqual(otp.attempts, 5)
        self.assertTrue(otp.is_used)
        with self.assertRaises(otp_service.OTPError):
            otp_service.verify_otp(PHONE, code)     # even the right code is dead now
        self.assertFalse(get_user_model().objects.filter(phone_number=PHONE).exists())

    def test_expired_code_is_rejected(self):
        code = issue_code()
        OTPCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(otp_service.OTPError):
            otp_service.verify_otp(PHONE, code)

    def test_unknown_phone_is_rejected(self):
        with self.assertRaises(otp_service.OTPError):
            otp_service.verify_otp('09129999999', '123456')

    def test_code_for_another_number_does_not_work(self):
        code = issue_code('09120000001')
        with self.assertRaises(otp_service.OTPError):
            otp_service.verify_otp('09120000002', code)

    def test_inactive_user_cannot_log_in_and_code_is_consumed(self):
        make_user(phone_number=PHONE, is_active=False)
        code = issue_code()
        with self.assertRaises(otp_service.OTPError):
            otp_service.verify_otp(PHONE, code)
        self.assertTrue(OTPCode.objects.get().is_used)
