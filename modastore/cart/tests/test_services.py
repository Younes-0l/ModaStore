"""Cart service rules: stock limits, per-item cap, DB constraint regression, guest merge."""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from cart import services
from cart.models import MAX_QTY_PER_ITEM, Cart, CartItem
from modastore.testutils import make_user, make_variant


class AddItemTests(TestCase):
    def setUp(self):
        self.cart = Cart.objects.create()

    def test_first_add_creates_item_with_valid_quantity(self):
        # Regression: creating the row with quantity=0 violated cart_item_quantity_gte_1
        v = make_variant(stock=5)
        services.add_item(self.cart, v.pk, 1)
        self.assertEqual(CartItem.objects.get().quantity, 1)

    def test_adding_twice_accumulates(self):
        v = make_variant(stock=5)
        services.add_item(self.cart, v.pk, 1)
        services.add_item(self.cart, v.pk, 2)
        self.assertEqual(CartItem.objects.get().quantity, 3)

    def test_cannot_exceed_stock(self):
        v = make_variant(stock=2)
        services.add_item(self.cart, v.pk, 2)
        with self.assertRaises(services.CartError):
            services.add_item(self.cart, v.pk, 1)
        self.assertEqual(CartItem.objects.get().quantity, 2)

    def test_first_add_above_stock_leaves_no_row_behind(self):
        v = make_variant(stock=2)
        with self.assertRaises(services.CartError):
            services.add_item(self.cart, v.pk, 3)
        self.assertFalse(CartItem.objects.exists())

    def test_per_item_cap_applies_even_with_large_stock(self):
        v = make_variant(stock=100)
        with self.assertRaises(services.CartError):
            services.add_item(self.cart, v.pk, MAX_QTY_PER_ITEM + 1)

    def test_out_of_stock_inactive_and_unknown_are_rejected(self):
        sold_out = make_variant(stock=0)
        inactive = make_variant(is_active=False)
        for pk in (sold_out.pk, inactive.pk, 999999):
            with self.subTest(pk=pk), self.assertRaises(services.CartError):
                services.add_item(self.cart, pk, 1)

    def test_inactive_product_is_rejected(self):
        v = make_variant()
        v.product.is_active = False
        v.product.save()
        with self.assertRaises(services.CartError):
            services.add_item(self.cart, v.pk, 1)

    def test_zero_or_negative_quantity_is_rejected(self):
        v = make_variant()
        for q in (0, -1):
            with self.subTest(q=q), self.assertRaises(services.CartError):
                services.add_item(self.cart, v.pk, q)


class SetQuantityTests(TestCase):
    def setUp(self):
        self.cart = Cart.objects.create()
        self.v = make_variant(stock=3)
        services.add_item(self.cart, self.v.pk, 1)
        self.item = CartItem.objects.get()

    def test_update(self):
        services.set_quantity(self.item, 3)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)

    def test_zero_removes_the_item(self):
        services.set_quantity(self.item, 0)
        self.assertFalse(CartItem.objects.exists())

    def test_above_stock_is_rejected(self):
        with self.assertRaises(services.CartError):
            services.set_quantity(self.item, 4)

    def test_item_that_became_unavailable_cannot_be_raised(self):
        self.v.stock = 0
        self.v.save()
        self.item.refresh_from_db()
        with self.assertRaises(services.CartError):
            services.set_quantity(self.item, 2)


class ConstraintTests(TestCase):
    def test_database_rejects_zero_quantity(self):
        cart = Cart.objects.create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(cart=cart, variant=make_variant(), quantity=0)

    def test_database_rejects_duplicate_variant_in_one_cart(self):
        cart, v = Cart.objects.create(), make_variant()
        CartItem.objects.create(cart=cart, variant=v, quantity=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(cart=cart, variant=v, quantity=1)


class CartDataTests(TestCase):
    def test_empty_and_missing_cart(self):
        data = services.get_cart_data(None)
        self.assertEqual((data['count'], data['total'], data['has_problems']), (0, 0, False))

    def test_totals_count_only_valid_lines(self):
        cart = Cart.objects.create()
        ok = make_variant(price=100, stock=5)
        bad = make_variant(price=1000, stock=5)
        services.add_item(cart, ok.pk, 2)
        services.add_item(cart, bad.pk, 1)
        bad.stock = 0
        bad.save()
        data = services.get_cart_data(cart)
        self.assertEqual(data['total'], 200)
        self.assertTrue(data['has_problems'])
        self.assertEqual(len(data['lines']), 2)

    def test_savings_use_old_price(self):
        cart = Cart.objects.create()
        v = make_variant(price=80, old_price=100, stock=5)
        services.add_item(cart, v.pk, 2)
        data = services.get_cart_data(cart)
        self.assertEqual((data['total'], data['total_old'], data['savings']), (160, 200, 40))


class MergeGuestCartTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.guest = Cart.objects.create()

    def test_items_move_to_the_user_cart_and_guest_cart_is_deleted(self):
        v = make_variant(stock=5)
        services.add_item(self.guest, v.pk, 2)
        services.merge_guest_cart(self.guest.pk, self.user)
        self.assertEqual(CartItem.objects.get(cart__user=self.user).quantity, 2)
        self.assertFalse(Cart.objects.filter(pk=self.guest.pk).exists())

    def test_quantities_add_up_but_are_capped_by_stock(self):
        v = make_variant(stock=3)
        mine = Cart.objects.create(user=self.user)
        services.add_item(mine, v.pk, 2)
        services.add_item(self.guest, v.pk, 2)
        services.merge_guest_cart(self.guest.pk, self.user)
        self.assertEqual(CartItem.objects.get(cart=mine).quantity, 3)

    def test_unavailable_items_are_dropped(self):
        v = make_variant(stock=2)
        services.add_item(self.guest, v.pk, 1)
        v.stock = 0
        v.save()
        services.merge_guest_cart(self.guest.pk, self.user)
        self.assertFalse(CartItem.objects.exists())

    def test_unknown_or_user_owned_cart_is_ignored(self):
        other = Cart.objects.create(user=make_user())
        services.merge_guest_cart(other.pk, self.user)   # not a guest cart
        services.merge_guest_cart(999999, self.user)
        self.assertTrue(Cart.objects.filter(pk=other.pk).exists())
