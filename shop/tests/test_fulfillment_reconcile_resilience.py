"""Phase 04A: a broken fulfillment must not block the next paid order.

These tests mock entitlement issuance and gateway verification. They never
call the external payment provider or grant a real customer entitlement.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment_recovery import run_fulfillment_reconcile_batch

User = get_user_model()


class FulfillmentReconcileBatchIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='reconcile04_buyer', phone='09129996401', password='x',
        )
        self.product = Product.objects.create(
            title='Recovery test product', slug='recovery04-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )

    def make_pending(self, *, hours_ago):
        return Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=Decimal('100000'), status='paid',
            paid_at=timezone.now() - timedelta(hours=hours_ago),
            fulfillment_status=Order.FulfillmentStatus.PENDING,
        )

    @patch('shop.services.order_fulfillment_recovery.reconcile_gateway_payment_mismatch', return_value=0)
    @patch('shop.services.order_fulfillment_recovery.logger.exception')
    def test_one_issuance_exception_does_not_block_later_paid_order(self, log_error, gateway):
        first = self.make_pending(hours_ago=4)
        second = self.make_pending(hours_ago=1)
        attempts = []

        def recover(order):
            attempts.append(order.pk)
            if order.pk == first.pk:
                raise RuntimeError('synthetic legacy issuance failure')
            Order.objects.filter(pk=order.pk).update(
                fulfillment_status=Order.FulfillmentStatus.COMPLETE,
            )

        with patch(
            'shop.services.order_fulfillment_recovery.reconcile_order_fulfillment',
            side_effect=recover,
        ):
            stats = run_fulfillment_reconcile_batch(limit=2)

        self.assertEqual(attempts, [first.pk, second.pk])
        self.assertEqual(stats, {
            'gateway_mismatch_fixed': 0,
            'fulfillment_retried': 2,
            'fulfillment_completed': 1,
        })
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.fulfillment_status, Order.FulfillmentStatus.PENDING)
        self.assertEqual(second.fulfillment_status, Order.FulfillmentStatus.COMPLETE)
        self.assertEqual(log_error.call_count, 1)
        gateway.assert_called_once_with(limit=2)

    @patch('shop.services.order_fulfillment_recovery.reconcile_gateway_payment_mismatch', return_value=3)
    @patch('shop.services.order_fulfillment_recovery.reconcile_order_fulfillment')
    def test_bounded_batch_keeps_existing_metrics_contract(self, retry, gateway):
        self.make_pending(hours_ago=3)
        self.make_pending(hours_ago=2)
        self.make_pending(hours_ago=1)

        stats = run_fulfillment_reconcile_batch(limit=1)

        self.assertEqual(stats, {
            'gateway_mismatch_fixed': 3,
            'fulfillment_retried': 1,
            'fulfillment_completed': 0,
        })
        retry.assert_called_once()
        gateway.assert_called_once_with(limit=1)

    @patch('shop.services.order_fulfillment_recovery.reconcile_gateway_payment_mismatch', return_value=0)
    @patch('shop.services.order_fulfillment_recovery.reconcile_order_fulfillment')
    @patch('shop.services.order_fulfillment_recovery.logger.exception')
    def test_error_during_refresh_does_not_terminate_remaining_batch(
        self, log_error, retry, gateway,
    ):
        first = self.make_pending(hours_ago=3)
        second = self.make_pending(hours_ago=2)
        original_refresh = Order.refresh_from_db

        def refresh_with_failure(order, *args, **kwargs):
            if order.pk == first.pk and kwargs.get('fields') == ['fulfillment_status']:
                raise RuntimeError('synthetic refresh error')
            return original_refresh(order, *args, **kwargs)

        with patch.object(Order, 'refresh_from_db', new=refresh_with_failure):
            stats = run_fulfillment_reconcile_batch(limit=2)

        self.assertEqual(stats['fulfillment_retried'], 2)
        self.assertEqual(stats['fulfillment_completed'], 0)
        self.assertEqual(retry.call_count, 2)
        self.assertEqual(log_error.call_count, 1)
