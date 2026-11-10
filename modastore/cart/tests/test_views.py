"""Cart HTTP behaviour: ajax/no-JS responses, ownership, guest session, merge on login."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cart import services
from cart.models import Cart, CartItem
from modastore.testutils import make_user, make_variant

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class CartAddTests(TestCase):
    def setUp(self):
        self.url = reverse('cart:add')
        self.v = make_variant(stock=2)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_ajax_success_returns_json_with_count(self):
        r = self.client.post(self.url, {'variant_id': self.v.pk, 'quantity': 2}, **AJAX)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['ok'], True)
        self.assertEqual(r.json()['count'], 2)

    def test_guest_cart_is_created_and_remembered_in_session(self):
        self.client.post(self.url, {'variant_id': self.v.pk}, **AJAX)
        cart = Cart.objects.get()
        self.assertIsNone(cart.user)
        self.assertEqual(self.client.session[services.SESSION_KEY], cart.pk)

    def test_ajax_over_limit_returns_409_json(self):
        r = self.client.post(self.url, {'variant_id': self.v.pk, 'quantity': 3}, **AJAX)
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()['ok'])
        self.assertIn('2', r.json()['message'])

    def test_garbage_input_returns_400(self):
        r = self.client.post(self.url, {'variant_id': 'abc'}, **AJAX)
        self.assertEqual(r.status_code, 400)

    def test_no_js_redirects_to_the_cart_with_a_message(self):
        r = self.client.post(self.url, {'variant_id': self.v.pk})
        self.assertRedirects(r, reverse('cart:detail'))

    def test_no_js_error_goes_back_to_the_referer(self):
        ref = 'http://testserver/products/'
        r = self.client.post(self.url, {'variant_id': self.v.pk, 'quantity': 9}, HTTP_REFERER=ref)
        self.assertRedirects(r, ref, fetch_redirect_response=False)

    def test_foreign_referer_is_not_followed(self):
        r = self.client.post(
            self.url, {'variant_id': self.v.pk, 'quantity': 9}, HTTP_REFERER='https://evil.example/',
        )
        self.assertRedirects(r, reverse('cart:detail'))

    def test_logged_in_user_gets_a_user_cart(self):
        user = make_user()
        self.client.force_login(user)
        self.client.post(self.url, {'variant_id': self.v.pk}, **AJAX)
        self.assertEqual(Cart.objects.get().user, user)


class CartItemOwnershipTests(TestCase):
    def setUp(self):
        self.owner, self.other = make_user(), make_user()
        self.cart = Cart.objects.create(user=self.owner)
        services.add_item(self.cart, make_variant(stock=5).pk, 1)
        self.item = CartItem.objects.get()

    def test_other_user_gets_404_and_item_survives(self):
        self.client.force_login(self.other)
        for name, data in (('remove', {}), ('update', {'quantity': 3})):
            r = self.client.post(reverse(f'cart:{name}', args=[self.item.pk]), data)
            self.assertEqual(r.status_code, 404, name)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 1)

    def test_guest_with_no_cart_gets_404(self):
        r = self.client.post(reverse('cart:remove', args=[self.item.pk]))
        self.assertEqual(r.status_code, 404)

    def test_owner_can_update_and_remove(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('cart:update', args=[self.item.pk]), {'quantity': 3})
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)
        self.client.post(reverse('cart:remove', args=[self.item.pk]))
        self.assertFalse(CartItem.objects.exists())

    def test_invalid_update_quantity_is_a_400(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse('cart:update', args=[self.item.pk]), {'quantity': 'x'}, **AJAX)
        self.assertEqual(r.status_code, 400)

    def test_remove_requires_post(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('cart:remove', args=[self.item.pk])).status_code, 405)


class CartPageTests(TestCase):
    def test_empty_cart_page_renders_for_a_new_guest(self):
        self.assertEqual(self.client.get(reverse('cart:detail')).status_code, 200)
        self.assertFalse(Cart.objects.exists())   # viewing must not create carts

    def test_header_count_reflects_cart(self):
        v = make_variant(stock=5)
        self.client.post(reverse('cart:add'), {'variant_id': v.pk, 'quantity': 3}, **AJAX)
        r = self.client.get(reverse('cart:detail'))
        self.assertEqual(r.context['cart_count'], 3)

    def test_problem_lines_are_flagged(self):
        v = make_variant(stock=5)
        self.client.post(reverse('cart:add'), {'variant_id': v.pk}, **AJAX)
        v.stock = 0
        v.save()
        r = self.client.get(reverse('cart:detail'))
        self.assertTrue(r.context['has_problems'])


class GuestMergeOnLoginTests(TestCase):
    def test_guest_cart_is_merged_when_the_user_logs_in(self):
        v = make_variant(stock=5)
        self.client.post(reverse('cart:add'), {'variant_id': v.pk, 'quantity': 2}, **AJAX)
        guest_id = Cart.objects.get().pk
        user = make_user()
        self.client.force_login(user)       # fires user_logged_in with the session
        self.assertEqual(CartItem.objects.get(cart__user=user).quantity, 2)
        self.assertFalse(Cart.objects.filter(pk=guest_id).exists())
