"""Checkout and payment views: access control, full happy path, gateway callback."""
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from cart.models import Cart
from modastore.testutils import fill_cart, make_address, make_order, make_user, make_variant
from orders.services import services
from orders.models import Order, Payment
from orders.views import SESSION_ADDRESS_KEY

from .test_services import ZP, zp_response


class CheckoutAccessTests(TestCase):
    def test_everything_requires_login(self):
        urls = [
            reverse('orders:checkout'), reverse('orders:review'), reverse('orders:list'),
            reverse('orders:pay', args=['MS000000001']), reverse('orders:result', args=['MS000000001']),
            reverse('orders:detail', args=['MS000000001']),
        ]
        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse('accounts:login'), r['Location'])

    def test_empty_cart_redirects_back_to_the_cart(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(reverse('orders:checkout')), reverse('cart:detail'))

    def test_cart_with_problems_cannot_proceed(self):
        user = make_user()
        v = make_variant(stock=3)
        fill_cart(user, (v, 1))
        v.stock = 0
        v.save()
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('orders:checkout')), reverse('cart:detail'))

    def test_review_without_a_chosen_address_goes_back_to_step_two(self):
        user = make_user()
        fill_cart(user, (make_variant(), 1))
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('orders:review')), reverse('orders:checkout'))


@override_settings(PAYMENT_GATEWAY='mock', SHIPPING_FEE=0)
class FullCheckoutFlowTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.address = make_address(self.user)
        self.v = make_variant(stock=3, price=500_000)
        fill_cart(self.user, (self.v, 2))
        self.client.force_login(self.user)

    def _place(self):
        self.client.post(reverse('orders:checkout'),
                         {'mode': 'saved', 'address_id': self.address.pk})
        return self.client.post(reverse('orders:review'))

    def test_saved_address_flow_to_a_paid_order(self):
        r = self.client.post(reverse('orders:checkout'), {'mode': 'saved', 'address_id': self.address.pk})
        self.assertRedirects(r, reverse('orders:review'))
        r = self.client.post(reverse('orders:review'))
        order = Order.objects.get()
        self.assertRedirects(r, reverse('orders:pay', args=[order.number]))
        self.assertNotIn(SESSION_ADDRESS_KEY, self.client.session)

        r = self.client.post(reverse('orders:pay', args=[order.number]))
        payment = order.payments.get()
        self.assertRedirects(r, reverse('orders:mock_gateway', args=[payment.authority]),
                             fetch_redirect_response=False)
        r = self.client.post(reverse('orders:mock_gateway', args=[payment.authority]), {'result': 'success'})
        self.assertRedirects(r, reverse('orders:result', args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(self.client.get(reverse('orders:result', args=[order.number])).status_code, 200)
        self.assertContains(self.client.get(reverse('orders:list')), order.number)

    def test_new_address_is_validated_and_saved(self):
        self.address.delete()
        bad = self.client.post(reverse('orders:checkout'), {'mode': 'new', 'receiver_name': ''})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(self.user.addresses.count(), 0)
        good = self.client.post(reverse('orders:checkout'), {
            'mode': 'new', 'receiver_name': 'علی رضایی', 'receiver_phone': '09121234567',
            'province': 'تهران', 'city': 'تهران', 'postal_code': '1234567890',
            'title': 'خانه', 'full_address': 'خیابان ولیعصر، پلاک ۱',
        })
        self.assertRedirects(good, reverse('orders:review'))
        self.assertEqual(self.user.addresses.count(), 1)

    def test_someone_elses_address_cannot_be_selected(self):
        foreign = make_address(make_user())
        r = self.client.post(reverse('orders:checkout'), {'mode': 'saved', 'address_id': foreign.pk})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(SESSION_ADDRESS_KEY, self.client.session)

    def test_failed_mock_payment_keeps_the_order_payable(self):
        self._place()
        order = Order.objects.get()
        self.client.post(reverse('orders:pay', args=[order.number]))
        payment = order.payments.get()
        self.client.post(reverse('orders:mock_gateway', args=[payment.authority]), {'result': 'fail'})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(self.client.get(reverse('orders:pay', args=[order.number])).status_code, 200)

    def test_double_submit_of_review_does_not_create_two_orders(self):
        self._place()
        r = self.client.post(reverse('orders:review'))     # cart is empty now
        self.assertRedirects(r, reverse('cart:detail'))
        self.assertEqual(Order.objects.count(), 1)

    def test_out_of_stock_at_submit_sends_user_back_with_message_and_no_order(self):
        self.client.post(reverse('orders:checkout'), {'mode': 'saved', 'address_id': self.address.pk})
        self.v.stock = 1
        self.v.save()
        r = self.client.post(reverse('orders:review'))
        self.assertRedirects(r, reverse('cart:detail'))
        self.assertFalse(Order.objects.exists())

    def test_cancel_via_post_releases_stock(self):
        self._place()
        order = Order.objects.get()
        self.client.post(reverse('orders:cancel', args=[order.number]))
        order.refresh_from_db(), self.v.refresh_from_db()
        self.assertEqual((order.status, self.v.stock), (Order.Status.CANCELED, 3))

    def test_cancel_requires_post(self):
        self._place()
        order = Order.objects.get()
        self.assertEqual(self.client.get(reverse('orders:cancel', args=[order.number])).status_code, 405)


class OrderPrivacyTests(TestCase):
    def setUp(self):
        self.owner, self.stranger = make_user(), make_user()
        self.order = make_order(self.owner, make_variant())
        self.payment = Payment.objects.create(order=self.order, amount=self.order.total)
        self.client.force_login(self.stranger)

    def test_other_users_order_is_404_everywhere(self):
        n = self.order.number
        for name in ('detail', 'pay', 'result'):
            self.assertEqual(self.client.get(reverse(f'orders:{name}', args=[n])).status_code, 404, name)
        self.assertEqual(self.client.post(reverse('orders:cancel', args=[n])).status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_other_users_mock_payment_is_404(self):
        with override_settings(PAYMENT_GATEWAY='mock'):
            r = self.client.post(reverse('orders:mock_gateway', args=[self.payment.authority]), {'result': 'success'})
        self.assertEqual(r.status_code, 404)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)

    def test_order_list_shows_only_own_orders(self):
        self.assertNotContains(self.client.get(reverse('orders:list')), self.order.number)


class MockGatewayGuardTests(TestCase):
    def test_fake_bank_does_not_exist_when_a_real_gateway_is_configured(self):
        user = make_user()
        order = make_order(user, make_variant())
        payment = Payment.objects.create(order=order, amount=order.total)
        self.client.force_login(user)
        with override_settings(PAYMENT_GATEWAY='zarinpal'):
            r = self.client.post(reverse('orders:mock_gateway', args=[payment.authority]), {'result': 'success'})
        self.assertEqual(r.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @override_settings(PAYMENT_GATEWAY='mock')
    def test_mock_endpoint_ignores_zarinpal_payments(self):
        user = make_user()
        order = make_order(user, make_variant())
        payment = Payment.objects.create(order=order, amount=order.total, gateway=Payment.Gateway.ZARINPAL)
        self.client.force_login(user)
        r = self.client.post(reverse('orders:mock_gateway', args=[payment.authority]), {'result': 'success'})
        self.assertEqual(r.status_code, 404)


@override_settings(**ZP)
class PaymentCallbackTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = services.place_order(
            self.user, fill_cart(self.user, (make_variant(stock=2), 1)), make_address(self.user),
        )
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response({'code': 100, 'authority': 'AUTH' * 9})):
            services.start_payment(self.order)
        self.url = reverse('orders:callback')

    def test_unknown_authority_is_404(self):
        self.assertEqual(self.client.get(self.url, {'Authority': 'nope', 'Status': 'OK'}).status_code, 404)

    def test_callback_works_without_login_and_completes_the_order(self):
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response({'code': 100, 'ref_id': 99})):
            r = self.client.get(self.url, {'Authority': 'AUTH' * 9, 'Status': 'OK'})
        self.assertRedirects(r, reverse('orders:result', args=[self.order.number]),
                             fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)

    def test_forged_ok_status_is_not_enough_the_bank_is_asked(self):
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response(None, {'code': -51})):
            self.client.get(self.url, {'Authority': 'AUTH' * 9, 'Status': 'OK'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_cancelled_at_the_bank(self):
        self.client.get(self.url, {'Authority': 'AUTH' * 9, 'Status': 'NOK'})
        self.assertEqual(self.order.payments.get().status, Payment.Status.FAILED)

    def test_unreachable_bank_shows_the_retry_page(self):
        with mock.patch('orders.gateway.requests.post', side_effect=__import__('requests').Timeout):
            r = self.client.get(self.url, {'Authority': 'AUTH' * 9, 'Status': 'OK'})
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'orders/verify_retry.html')
        self.assertEqual(self.order.payments.get().status, Payment.Status.PENDING)

    def test_mock_payments_cannot_be_settled_through_the_callback(self):
        p = Payment.objects.create(order=self.order, amount=self.order.total, authority='MOCKAUTH')
        r = self.client.get(self.url, {'Authority': 'MOCKAUTH', 'Status': 'OK'})
        self.assertEqual(r.status_code, 404)


class ExpireOrdersCommandTests(TestCase):
    def test_command_cancels_overdue_orders(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone
        user = make_user()
        v = make_variant(stock=3)
        order = services.place_order(user, fill_cart(user, (v, 1)), make_address(user))
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        call_command('expire_orders')
        order.refresh_from_db(), v.refresh_from_db()
        self.assertEqual((order.status, v.stock), (Order.Status.CANCELED, 3))
