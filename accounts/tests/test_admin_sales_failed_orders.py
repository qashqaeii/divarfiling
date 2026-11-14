from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.services.admin_sales_failed_orders import (
    build_failed_order_rows,
    resolve_order_failure,
)
from shop.models import LicensePlan, Order, Product, Transaction

User = get_user_model()


class AdminSalesFailedOrderReasonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fail_buyer', phone='09120000099')
        self.product = Product.objects.create(
            title='Test', slug='test-fail-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=250000, duration_days=30, is_active=True,
        )

    def test_transaction_cancelled_message(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal('250000'),
            status='failed',
            payment_method='zibal',
        )
        Transaction.objects.create(
            order=order,
            zibal_track_id='TRACK-CANCEL-1',
            amount=order.amount,
            status='cancelled',
            gateway_message='پرداخت توسط شما لغو شد.',
        )
        failure = resolve_order_failure(order=order)
        self.assertEqual(failure['category'], 'cancelled')
        self.assertIn('لغو', failure['reason_full'])

    def test_build_rows_preserves_order(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal('250000'),
            status='failed',
        )
        Transaction.objects.create(
            order=order,
            zibal_track_id='TRACK-FAIL-2',
            amount=order.amount,
            status='failed',
            gateway_message='خطا در تایید پرداخت',
            gateway_result_code=201,
        )
        rows = build_failed_order_rows([order])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['order'].pk, order.pk)
        self.assertIn('خطا', rows[0]['failure']['reason_full'])