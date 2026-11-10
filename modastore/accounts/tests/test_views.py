from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Address
from modastore.testutils import make_address, make_user

try:
    from accounts.services.services import otp as otp_service
except ImportError:  # pragma: no cover
    from accounts.services import services as otp_service

PHONE = '09120000001'
ADDRESS = dict(
    title='خانه', receiver_name='علی رضایی', receiver_phone='09121234567',
    province='تهران', city='تهران', postal_code='1234567890',
    full_address='خیابان ولیعصر، پلاک ۱',
)


@override_settings(OTP_RESEND_SECONDS=120, OTP_TTL_SECONDS=120, OTP_MAX_ATTEMPTS=5,
                   OTP_MAX_REQUESTS_PER_HOUR=5, OTP_LENGTH=6)
class LoginFlowTests(TestCase):
    def request_code(self, phone=PHONE, **extra):
        with mock.patch.object(otp_service, 'send_otp_sms') as sms:
            response = self.client.post(reverse('accounts:login'), {'phone_number': phone, **extra})
        return response, (sms.call_args.args[1] if sms.called else None)

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse('accounts:login')).status_code, 200)

    def test_invalid_phone_shows_error_and_sends_nothing(self):
        response, code = self.request_code('123')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(code)
        self.assertTrue(response.context['form'].errors)

    def test_valid_phone_redirects_to_verify_and_remembers_the_number(self):
        response, code = self.request_code('+989120000001')    # normalized to 0912...
        self.assertRedirects(response, reverse('accounts:verify'), fetch_redirect_response=False)
        self.assertEqual(self.client.session['otp_phone'], PHONE)
        self.assertEqual(len(code), 6)

    def test_verify_without_a_started_login_goes_back_to_login(self):
        response = self.client.get(reverse('accounts:verify'))
        self.assertRedirects(response, reverse('accounts:login'), fetch_redirect_response=False)

    def test_new_user_full_flow_lands_on_profile(self):
        _, code = self.request_code()
        response = self.client.post(reverse('accounts:verify'), {'code': code})
        self.assertRedirects(response, reverse('accounts:profile'), fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertNotIn('otp_phone', self.client.session)

    def test_returning_user_with_a_name_lands_on_home(self):
        make_user(phone_number=PHONE, first_name='علی')
        _, code = self.request_code()
        response = self.client.post(reverse('accounts:verify'), {'code': code})
        self.assertRedirects(response, reverse('catalog:home'), fetch_redirect_response=False)

    def test_persian_digits_in_the_code_are_accepted(self):
        _, code = self.request_code()
        persian = code.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
        response = self.client.post(reverse('accounts:verify'), {'code': persian})
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_wrong_code_shows_an_error_and_does_not_log_in(self):
        _, code = self.request_code()
        wrong = '000000' if code != '000000' else '111111'
        response = self.client.post(reverse('accounts:verify'), {'code': wrong})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_next_is_kept_through_the_whole_flow(self):
        response, code = self.request_code(next='/cart/')
        self.assertRedirects(response, reverse('accounts:verify') + '?next=/cart/',
                             fetch_redirect_response=False)
        response = self.client.post(reverse('accounts:verify'), {'code': code, 'next': '/cart/'})
        self.assertRedirects(response, '/cart/', fetch_redirect_response=False)

    def test_unsafe_next_is_ignored(self):
        for target in ('https://evil.example/steal', '//evil.example/steal'):
            with self.subTest(target=target):
                self.client.logout()
                OTPCodeCleanup.clear()
                _, code = self.request_code(next=target)
                response = self.client.post(reverse('accounts:verify'), {'code': code, 'next': target})
                self.assertEqual(response.status_code, 302)
                self.assertNotIn('evil.example', response.url)

    def test_resend_too_soon_shows_a_message(self):
        self.request_code()
        response = self.client.post(reverse('accounts:resend'), follow=True)
        self.assertRedirects(response, reverse('accounts:verify'))
        self.assertTrue([m for m in response.context['messages'] if m.level_tag == 'error'])

    def test_logged_in_user_is_sent_away_from_login(self):
        self.client.force_login(make_user())
        response = self.client.get(reverse('accounts:login'))
        self.assertRedirects(response, reverse('catalog:home'), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        self.client.post(reverse('accounts:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


class OTPCodeCleanup:
    """Removes old codes so a second request in the same test is not rate limited."""

    @staticmethod
    def clear():
        from accounts.models import OTPCode
        OTPCode.objects.all().delete()


class ProfileAndAddressTests(TestCase):
    def setUp(self):
        self.user = make_user(first_name='علی', last_name='رضایی')
        self.client.force_login(self.user)

    def test_profile_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
            fetch_redirect_response=False,
        )

    def test_profile_update(self):
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'مریم', 'last_name': 'احمدی', 'email': 'm@example.com',
        })
        self.assertRedirects(response, reverse('accounts:profile'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email), ('مریم', 'm@example.com'))

    def test_first_address_becomes_default(self):
        self.client.post(reverse('accounts:address_add'), ADDRESS)
        self.assertTrue(Address.objects.get().is_default)

    def test_only_one_default_address(self):
        first = make_address(self.user, is_default=True)
        self.client.post(reverse('accounts:address_add'), {**ADDRESS, 'title': 'محل کار', 'is_default': 'on'})
        second = Address.objects.exclude(pk=first.pk).get()
        first.refresh_from_db()
        self.assertTrue(second.is_default)
        self.assertFalse(first.is_default)

    def test_persian_postal_code_is_normalized(self):
        self.client.post(reverse('accounts:address_add'), {**ADDRESS, 'postal_code': '۱۲۳۴۵۶۷۸۹۰'})
        self.assertEqual(Address.objects.get().postal_code, '1234567890')

    def test_invalid_address_is_not_saved(self):
        response = self.client.post(reverse('accounts:address_add'), {**ADDRESS, 'postal_code': '123'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Address.objects.exists())

    def test_other_users_address_cannot_be_edited_or_deleted(self):
        other = make_address(make_user())
        self.assertEqual(self.client.get(reverse('accounts:address_edit', args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('accounts:address_delete', args=[other.pk])).status_code, 404)
        self.assertTrue(Address.objects.filter(pk=other.pk).exists())

    def test_delete_own_address_requires_post(self):
        address = make_address(self.user)
        self.assertEqual(self.client.get(reverse('accounts:address_delete', args=[address.pk])).status_code, 405)
        self.client.post(reverse('accounts:address_delete', args=[address.pk]))
        self.assertFalse(Address.objects.filter(pk=address.pk).exists())
