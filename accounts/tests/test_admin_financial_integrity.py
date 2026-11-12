"""Admin Premium V2 / 01B — calendar, renewal and gateway reconciliation contracts."""
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.services.admin_dashboard import (
    _date_range,
    _orders_paid_for_period,
    _today,
    get_formal_renewal_orders_qs,
    get_licensing_center_stats,
    get_today_stats,
    paid_orders_queryset_for_panel_days,
)
from accounts.services.admin_licenses_center import (
    _formal_renewals_between,
    _renewals_between,
    get_licenses_center_context,
)
from licenses.models import License
from shop.models import LicensePlan, Order, OrderRenewalItem, Product, Transaction
from shop.services.order_fulfillment_recovery import reconcile_gateway_payment_mismatch

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran', USE_TZ=True)
class BusinessCalendarContractsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calendar_buyer', phone='09128881001', password='x',
        )
        self.product = Product.objects.create(
            title='Calendar Product', slug='calendar-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )

    def test_utc_date_boundary_does_not_move_today_to_yesterday(self):
        # UTC Nov 12 21:15 is local Nov 13 00:45 in Tehran.
        instant = datetime(2026, 11, 12, 21, 15, tzinfo=dt_timezone.utc)
        with timezone.override('Asia/Tehran'):
            with patch('django.utils.timezone.now', return_value=instant):
                self.assertEqual(_today().isoformat(), '2026-11-13')
                self.assertEqual(_date_range(1)[0], _today())
                self.assertEqual(_date_range(7)[1], _today())

                Order.objects.create(
                    user=self.user, product=self.product, plan=self.plan,
                    amount=Decimal('100000'), status='paid', paid_at=instant,
                )
                self.assertEqual(_orders_paid_for_period(1), 1)
                self.assertEqual(paid_orders_queryset_for_panel_days(1).count(), 1)
                self.assertEqual(get_today_stats()['revenue_today'], 100000)
                self.assertEqual(get_today_stats()['orders_paid_today'], 1)


@override_settings(TIME_ZONE='Asia/Tehran')
class RenewalClassificationContractsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(
            username='renewal_buyer', phone='09128881002', password='x',
        )
        self.product = Product.objects.create(
            title='Renewal Product', slug='renewal-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )

    def _paid(self, day, amount=100000):
        return Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=Decimal(amount), status='paid',
            paid_at=timezone.make_aware(datetime.combine(day, time(12, 0))),
        )

    def test_multi_license_renewal_is_one_formal_order_not_two(self):
        first = self._paid(self.today - timedelta(days=40))
        licenses = [
            License.objects.create(
                order=first, sequence=i, plan=self.plan,
                license_key=f'RENEWAL-TEST-KEY-{i}', status='active',
            )
            for i in (1, 2)
        ]
        renewal = self._paid(self.today, amount=200000)
        for lic in licenses:
            OrderRenewalItem.objects.create(
                order=renewal, license=lic,
                unit_original_price=Decimal('100000'),
                unit_final_price=Decimal('100000'),
            )
        self._paid(self.today, amount=120000)  # New-key repeat purchase.

        start, end = _date_range(30)
        self.assertEqual(_renewals_between(start, end), 2)
        self.assertEqual(_formal_renewals_between(start, end), 1)
        self.assertEqual(get_formal_renewal_orders_qs().count(), 1)

        center = get_licenses_center_context(days=30)
        self.assertEqual(center['renewal_breakdown']['formal_renewals_range'], 1)
        self.assertEqual(center['renewal_breakdown']['new_key_repurchase_range'], 1)

        summary = get_licensing_center_stats()
        self.assertEqual(summary['renewal_orders'], 2)
        self.assertEqual(summary['formal_renewal_orders'], 1)
        self.assertEqual(summary['new_key_repurchase_orders'], 1)

    def test_classic_single_key_renewal_still_formal(self):
        first = self._paid(self.today - timedelta(days=40))
        lic = License.objects.create(
            order=first, plan=self.plan, license_key='RENEWAL-CLASSIC-KEY',
            status='active',
        )
        renewal = self._paid(self.today)
        renewal.renewal_license = lic
        renewal.save(update_fields=['renewal_license'])
        start, end = _date_range(30)
        self.assertEqual(_formal_renewals_between(start, end), 1)


class GatewayReconcileContractsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='gateway_reconcile', phone='09128881003', password='x',
        )
        self.product = Product.objects.create(
            title='Gateway Product', slug='gateway-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )

    def _transaction(self, *, method, track):
        order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=Decimal('100000'), status='pending_verification',
            payment_method=method,
        )
        Transaction.objects.create(
            order=order, zibal_track_id=track, amount=order.amount,
            status='paid',
        )
        return order

    @patch('shop.services.order_fulfillment_recovery.complete_order_fulfillment')
    @patch('shop.services.order_fulfillment_recovery.mark_order_paid_after_gateway')
    @patch('shop.services.zibal.verify_payment')
    def test_only_zibal_transactions_reverified(
        self, verify, mark, complete,
    ):
        self._transaction(method='card_transfer', track='CARD-123')
        self._transaction(method='zibal', track='CARD-legacy')
        gate = self._transaction(method='zibal', track='ZIBAL-123')
        self.assertEqual(reconcile_gateway_payment_mismatch(limit=10), 1)
        verify.assert_called_once()
        mark.assert_called_once_with(gate, record_funnel=False)
        complete.assert_called_once_with(gate)

    @patch('shop.services.order_fulfillment_recovery.complete_order_fulfillment')
    @patch('shop.services.order_fulfillment_recovery.mark_order_paid_after_gateway')
    @patch('shop.services.zibal.verify_payment')
    def test_one_failed_payment_update_does_not_abort_batch(
        self, verify, mark, complete,
    ):
        first = self._transaction(method='zibal', track='ZIBAL-201')
        second = self._transaction(method='zibal', track='ZIBAL-202')

        def mark_with_one_failure(order, **kwargs):
            if order.pk == first.pk:
                raise RuntimeError('simulated database error')
            return order

        mark.side_effect = mark_with_one_failure
        self.assertEqual(reconcile_gateway_payment_mismatch(limit=10), 1)
        self.assertEqual(verify.call_count, 2)
        complete.assert_called_once_with(second)

    @patch('shop.services.order_fulfillment_recovery.complete_order_fulfillment')
    @patch('shop.services.order_fulfillment_recovery.mark_order_paid_after_gateway')
    @patch('shop.services.zibal.verify_payment')
    def test_fulfillment_error_still_counts_repaired_payment(
        self, verify, mark, complete,
    ):
        order = self._transaction(method='zibal', track='ZIBAL-300')
        complete.side_effect = RuntimeError('simulated fulfillment error')
        self.assertEqual(reconcile_gateway_payment_mismatch(limit=10), 1)
        mark.assert_called_once_with(order, record_funnel=False)
        complete.assert_called_once_with(order)
