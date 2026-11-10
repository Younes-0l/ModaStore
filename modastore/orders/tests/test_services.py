"""Order placement, cancellation/expiry and the payment state machine (mock + ZarinPal)."""
from datetime import timedelta
from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from cart import services as cart_services
from modastore.testutils import fill_cart, make_address, make_order, make_user, make_variant
from orders import gateway
from orders.services import services
from orders.models import Order, Payment

ZP = dict(
    PAYMENT_GATEWAY='zarinpal', ZARINPAL_MERCHANT_ID='x' * 36, ZARINPAL_SANDBOX=True,
    SITE_URL='http://testserver',
)


def zp_response(data=None, errors=None):
    """Fake requests.Response for the ZarinPal v4 API."""
    resp = mock.Mock()
    resp.json.return_value = {'data': data if data is not None else [], 'errors': errors if errors is not None else []}
    return resp


@override_settings(SHIPPING_FEE=50_000, FREE_SHIPPING_THRESHOLD=None, ORDER_PAYMENT_TIMEOUT_MINUTES=30)
class PlaceOrderTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.address = make_address(self.user)

    def test_order_snapshots_prices_address_and_reserves_stock(self):
        v = make_variant(price=1_000_000, stock=5, color='مشکی', storage='128GB')
        cart = fill_cart(self.user, (v, 2))
        order = services.place_order(self.user, cart, self.address)

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual((order.subtotal, order.shipping_fee, order.total), (2_000_000, 50_000, 2_050_000))
        item = order.items.get()
        self.assertEqual((item.unit_price, item.quantity, item.color, item.storage), (1_000_000, 2, 'مشکی', '128GB'))
        self.assertEqual(item.product_name, v.product.name)
        v.refresh_from_db()
        self.assertEqual(v.stock, 3)
        self.assertFalse(cart.items.exists())
        self.assertTrue(order.number.startswith('MS'))
        self.assertGreater(order.expires_at, timezone.now() + timedelta(minutes=29))

    def test_snapshots_survive_later_changes(self):
        v = make_variant(price=100, stock=5)
        order = services.place_order(self.user, fill_cart(self.user, (v, 1)), self.address)
        v.price = 999
        v.save()
        self.address.city = 'شیراز'
        self.address.save()
        order.refresh_from_db()
        self.assertEqual(order.items.get().unit_price, 100)
        self.assertEqual(order.city, 'تهران')

    @override_settings(FREE_SHIPPING_THRESHOLD=1_000_000)
    def test_free_shipping_at_or_above_threshold(self):
        self.assertEqual(services.shipping_fee(1_000_000), 0)
        self.assertEqual(services.shipping_fee(999_999), 50_000)

    def test_empty_cart_is_rejected(self):
        cart = fill_cart(self.user)
        with self.assertRaises(services.CheckoutError):
            services.place_order(self.user, cart, self.address)

    def test_stock_that_disappeared_after_adding_blocks_the_order_and_changes_nothing(self):
        ok, short = make_variant(stock=5), make_variant(stock=5)
        cart = fill_cart(self.user, (ok, 1), (short, 3))
        short.stock = 2
        short.save()
        with self.assertRaises(services.CheckoutError):
            services.place_order(self.user, cart, self.address)
        ok.refresh_from_db()
        self.assertEqual(ok.stock, 5)               # rolled back
        self.assertEqual(cart.items.count(), 2)     # cart untouched
        self.assertFalse(Order.objects.exists())

    def test_deactivated_variant_blocks_the_order(self):
        v = make_variant(stock=5)
        cart = fill_cart(self.user, (v, 1))
        v.is_active = False
        v.save()
        with self.assertRaises(services.CheckoutError):
            services.place_order(self.user, cart, self.address)

    def test_last_unit_cannot_be_bought_twice(self):
        v = make_variant(stock=1)
        first, second = make_user(), make_user()
        c1, c2 = fill_cart(first, (v, 1)), fill_cart(second, (v, 1))
        services.place_order(first, c1, make_address(first))
        with self.assertRaises(services.CheckoutError):
            services.place_order(second, c2, make_address(second))
        v.refresh_from_db()
        self.assertEqual(v.stock, 0)


class CancelAndExpireTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.v = make_variant(stock=5)
        self.order = services.place_order(
            self.user, fill_cart(self.user, (self.v, 2)), make_address(self.user),
        )

    def test_cancel_returns_stock_and_fails_open_payments(self):
        payment = Payment.objects.create(order=self.order, amount=self.order.total)
        self.assertTrue(services.cancel_order(self.order.pk))
        self.order.refresh_from_db(), self.v.refresh_from_db(), payment.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELED)
        self.assertEqual(self.v.stock, 5)
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_cancel_is_idempotent_and_never_double_restocks(self):
        services.cancel_order(self.order.pk)
        self.assertFalse(services.cancel_order(self.order.pk))
        self.v.refresh_from_db()
        self.assertEqual(self.v.stock, 5)

    def test_paid_orders_cannot_be_canceled(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.PROCESSING)
        self.assertFalse(services.cancel_order(self.order.pk))
        self.v.refresh_from_db()
        self.assertEqual(self.v.stock, 3)

    def test_expire_overdue_only_touches_overdue_pending_orders(self):
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        fresh = make_order(self.user, make_variant(stock=5))
        paid = make_order(self.user, make_variant(stock=5), status=Order.Status.PROCESSING,
                          expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(services.expire_overdue_orders(), 1)
        for o, status in ((self.order, 'canceled'), (fresh, 'pending'), (paid, 'processing')):
            o.refresh_from_db()
            self.assertEqual(o.status, status)

    def test_expire_if_overdue(self):
        self.assertEqual(services.expire_if_overdue(self.order).status, Order.Status.PENDING)
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        order = Order.objects.get(pk=self.order.pk)
        self.assertEqual(services.expire_if_overdue(order).status, Order.Status.CANCELED)


@override_settings(PAYMENT_GATEWAY='mock')
class MockPaymentTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.v = make_variant(stock=3)
        self.order = services.place_order(
            self.user, fill_cart(self.user, (self.v, 1)), make_address(self.user),
        )

    def test_start_payment_creates_a_mock_attempt_and_supersedes_older_ones(self):
        url1 = services.start_payment(self.order)
        url2 = services.start_payment(self.order)
        self.assertIn('/payment/gateway/', url2)
        self.assertNotEqual(url1, url2)
        self.assertEqual(self.order.payments.filter(status=Payment.Status.PENDING).count(), 1)
        self.assertEqual(self.order.payments.filter(status=Payment.Status.FAILED).count(), 1)

    def test_start_payment_refused_for_expired_or_canceled_orders(self):
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.order.refresh_from_db()
        with self.assertRaises(services.CheckoutError):
            services.start_payment(self.order)

    def test_success_marks_order_paid(self):
        services.start_payment(self.order)
        payment = self.order.payments.get()
        services.finish_payment(payment.pk, True)
        payment.refresh_from_db(), self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertTrue(payment.ref_id.startswith('MOCK-'))
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertIsNotNone(self.order.paid_at)

    def test_failure_keeps_order_pending_and_stock_reserved(self):
        services.start_payment(self.order)
        payment = self.order.payments.get()
        services.finish_payment(payment.pk, False)
        payment.refresh_from_db(), self.order.refresh_from_db(), self.v.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.v.stock, 2)

    def test_finishing_twice_is_idempotent(self):
        services.start_payment(self.order)
        payment = self.order.payments.get()
        services.finish_payment(payment.pk, True)
        first_ref = Payment.objects.get(pk=payment.pk).ref_id
        services.finish_payment(payment.pk, True)
        services.finish_payment(payment.pk, False)    # a late "fail" must not undo success
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.ref_id), (Payment.Status.SUCCESS, first_ref))

    def test_paying_a_canceled_order_re_reserves_stock(self):
        services.start_payment(self.order)
        payment = self.order.payments.get()
        services.cancel_order(self.order.pk)       # window ran out, stock released
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PENDING)
        services.finish_payment(payment.pk, True)
        self.order.refresh_from_db(), self.v.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.v.stock, 2)

    def test_paying_a_canceled_order_whose_stock_is_gone_needs_a_refund(self):
        services.start_payment(self.order)
        payment = self.order.payments.get()
        services.cancel_order(self.order.pk)
        self.v.refresh_from_db()
        self.v.stock = 0                            # someone else bought everything
        self.v.save()
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PENDING)
        services.finish_payment(payment.pk, True)
        payment.refresh_from_db(), self.order.refresh_from_db(), self.v.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUND_NEEDED)
        self.assertEqual(self.order.status, Order.Status.CANCELED)
        self.assertEqual(self.v.stock, 0)

    def test_amount_mismatch_needs_a_refund(self):
        payment = Payment.objects.create(order=self.order, amount=self.order.total - 1)
        services.finish_payment(payment.pk, True)
        payment.refresh_from_db(), self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUND_NEEDED)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_second_successful_payment_for_a_paid_order_needs_a_refund(self):
        p1 = Payment.objects.create(order=self.order, amount=self.order.total)
        services.finish_payment(p1.pk, True)
        p2 = Payment.objects.create(order=self.order, amount=self.order.total)
        services.finish_payment(p2.pk, True)
        p2.refresh_from_db()
        self.assertEqual(p2.status, Payment.Status.REFUND_NEEDED)

    def test_success_fails_other_open_attempts(self):
        p1 = Payment.objects.create(order=self.order, amount=self.order.total)
        p2 = Payment.objects.create(order=self.order, amount=self.order.total)
        services.finish_payment(p2.pk, True)
        p1.refresh_from_db()
        self.assertEqual(p1.status, Payment.Status.FAILED)


@override_settings(**ZP)
class ZarinPalTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.v = make_variant(stock=3, price=2_000_000)
        self.order = services.place_order(
            self.user, fill_cart(self.user, (self.v, 1)), make_address(self.user),
        )

    def _start(self, authority='A' * 36):
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response({'code': 100, 'authority': authority})) as post:
            url = services.start_payment(self.order)
        return url, post

    def test_request_sends_rial_amount_and_returns_the_gateway_url(self):
        url, post = self._start()
        body = post.call_args.kwargs['json']
        self.assertEqual(body['amount'], self.order.total * 10)      # Toman -> Rial
        self.assertEqual(body['callback_url'], 'http://testserver/payment/callback/')
        self.assertIn('sandbox.zarinpal.com', post.call_args.args[0])
        self.assertEqual(url, gateway.start_url('A' * 36))
        payment = self.order.payments.get()
        self.assertEqual((payment.authority, payment.gateway), ('A' * 36, Payment.Gateway.ZARINPAL))

    def test_rejected_request_marks_the_attempt_failed_and_raises(self):
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response(None, {'code': -9})):
            with self.assertRaises(services.CheckoutError):
                services.start_payment(self.order)
        self.assertEqual(self.order.payments.get().status, Payment.Status.FAILED)

    def test_network_error_is_reported_as_checkout_error(self):
        with mock.patch('orders.gateway.requests.post', side_effect=requests.ConnectionError):
            with self.assertRaises(services.CheckoutError):
                services.start_payment(self.order)

    @override_settings(ZARINPAL_MERCHANT_ID='')
    def test_missing_merchant_id_is_reported(self):
        with self.assertRaises(services.CheckoutError):
            services.start_payment(self.order)

    def _settle(self, verify_data, status_ok=True):
        self._start()
        payment = self.order.payments.get()
        with mock.patch('orders.gateway.requests.post', return_value=zp_response(verify_data)) as post:
            result = services.settle_gateway_payment(payment, status_ok)
        return payment, result, post

    def test_verified_payment_completes_the_order(self):
        payment, _, post = self._settle({'code': 100, 'ref_id': 12345})
        payment.refresh_from_db(), self.order.refresh_from_db()
        self.assertEqual((payment.status, payment.ref_id), (Payment.Status.SUCCESS, '12345'))
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(post.call_args.kwargs['json']['amount'], self.order.total * 10)

    def test_code_101_already_verified_still_counts_as_paid(self):
        payment, _, _ = self._settle({'code': 101, 'ref_id': 777})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

    def test_bank_status_nok_fails_without_calling_verify(self):
        self._start()
        payment = self.order.payments.get()
        with mock.patch('orders.gateway.requests.post') as post:
            services.settle_gateway_payment(payment, status_ok=False)
        post.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_verify_says_not_paid_fails_the_payment(self):
        self._start('B' * 36)
        p2 = self.order.payments.get(authority='B' * 36)
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response(None, {'code': -51})):
            services.settle_gateway_payment(p2, True)
        p2.refresh_from_db(), self.order.refresh_from_db()
        self.assertEqual(p2.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_unreadable_answer_raises_and_leaves_the_payment_pending(self):
        self._start()
        payment = self.order.payments.get()
        with mock.patch('orders.gateway.requests.post', return_value=zp_response()):
            with self.assertRaises(gateway.GatewayError):
                services.settle_gateway_payment(payment, True)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_callback_replay_does_not_call_the_bank_again(self):
        payment, _, _ = self._settle({'code': 100, 'ref_id': 1})
        payment.refresh_from_db()
        with mock.patch('orders.gateway.requests.post') as post:
            services.settle_gateway_payment(payment, True)
        post.assert_not_called()

    def test_money_arriving_after_expiry_is_accepted_and_stock_re_reserved(self):
        self._start()
        payment = self.order.payments.get()
        services.cancel_order(self.order.pk)       # also marks the attempt FAILED
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response({'code': 100, 'ref_id': 5})):
            services.settle_gateway_payment(payment, True)    # gateway is the truth
        payment.refresh_from_db(), self.order.refresh_from_db(), self.v.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.v.stock, 2)

    def test_money_after_expiry_with_no_stock_left_goes_to_the_refund_queue(self):
        self._start()
        payment = self.order.payments.get()
        services.cancel_order(self.order.pk)
        type(self.v).objects.filter(pk=self.v.pk).update(stock=0)
        with mock.patch('orders.gateway.requests.post',
                        return_value=zp_response({'code': 100, 'ref_id': 5})):
            services.settle_gateway_payment(payment, True)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUND_NEEDED)
