"""تست مسیر کد تخفیف — UUID سفارش، checkout و paid immutability."""
import json
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from shop.models import DiscountCode, LicensePlan, Order, Product
from shop.services.order_discount import OrderDiscountError, apply_discount_code_to_pending_order

User = get_user_model()


class OrderDiscountFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer1', password='x', phone='09120001001')
        self.other = User.objects.create_user(username='buyer2', password='x', phone='09120001002')
        self.client = Client()
        self.client.force_login(self.user)
        self.product = Product.objects.create(title='Bot', slug='bot-disc', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100_000,
            duration_days=30,
            is_active=True,
        )
        self.code = DiscountCode.objects.create(
            code='DF-FLOW01',
            discount_type='percentage',
            discount_value=Decimal('10'),
            max_uses=1,
            valid_from=timezone.now() - timezone.timedelta(hours=1),
            valid_until=timezone.now() + timezone.timedelta(days=2),
            is_active=True,
        )

    def _pending_order(self, user=None):
        return Order.objects.create(
            user=user or self.user,
            product=self.product,
            plan=self.plan,
            amount=100_000,
            original_price=100_000,
            status='pending',
        )

    def test_checkout_link_applies_code_to_uuid_order(self):
        order = self._pending_order()
        url = reverse('payment:checkout', kwargs={'order_id': order.id})
        resp = self.client.get(f'{url}?code={self.code.code}')
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.discount_code_id, self.code.pk)
        self.assertEqual(int(order.amount), 90_000)

    def test_apply_discount_wrong_user_forbidden(self):
        order = self._pending_order(user=self.other)
        with self.assertRaises(OrderDiscountError) as ctx:
            apply_discount_code_to_pending_order(order, self.user, self.code.code)
        self.assertEqual(ctx.exception.code, 'forbidden')

    def test_paid_order_not_mutated(self):
        order = self._pending_order()
        order.status = 'paid'
        order.paid_at = timezone.now()
        order.save()
        with self.assertRaises(OrderDiscountError) as ctx:
            apply_discount_code_to_pending_order(order, self.user, self.code.code)
        self.assertEqual(ctx.exception.code, 'paid')

    def test_buy_page_prefills_code_from_query(self):
        url = reverse('buy', kwargs={'slug': self.product.slug})
        resp = self.client.get(f'{url}?code={self.code.code}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.code.code)

    def test_used_count_increments_on_fulfillment_only(self):
        order = self._pending_order()
        apply_discount_code_to_pending_order(order, self.user, self.code.code)
        self.code.refresh_from_db()
        self.assertEqual(self.code.used_count, 0)
        from shop.services.order_fulfillment import fulfill_order_after_payment

        fulfill_order_after_payment(order)
        self.code.refresh_from_db()
        self.assertEqual(self.code.used_count, 1)

    @patch('shop.payment_views.zibal_service.get_merchant_id', return_value='test')
    def test_checkout_shows_discounted_amount(self, _mock_merchant):
        order = self._pending_order()
        apply_discount_code_to_pending_order(order, self.user, self.code.code)
        url = reverse('payment:checkout', kwargs={'order_id': order.id})
        resp = self.client.get(url)
        self.assertContains(resp, '90')
