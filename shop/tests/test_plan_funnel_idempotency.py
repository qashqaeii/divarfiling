"""تست‌های Idempotency و ثبت مرکزی payment_success + پوشش DQ."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.plan_bi import SCHEMA_VERSION, load_period_buyers
from accounts.services.plan_bi.data_quality import build_data_quality
from shop.models import (
    CardTransferSubmission,
    LicensePlan,
    Order,
    PaymentSettings,
    PlanFunnelEvent,
    Product,
    Transaction,
)
from shop.services.order_fulfillment import approve_card_transfer, fulfill_order_after_payment
from shop.services.plan_funnel import (
    ensure_payment_success_event,
    is_bi_production_order,
    payment_success_idempotency_key,
)
from shop.services.zibal import ZibalVerifyResult

User = get_user_model()


def _product_plan(slug='funnel-idem-bot'):
    product = Product.objects.create(
        title='ربات', slug=slug, description='t', is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product, name='ماهانه', plan_type='monthly',
        price=100000, duration_days=30, is_active=True,
    )
    return product, plan


class PaymentSuccessIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='funnelu1', password='x', phone='09121110001',
        )
        self.product, self.plan = _product_plan()
        self.order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=self.plan.price, status='pending',
        )

    def test_fulfill_creates_one_payment_success(self):
        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        qs = PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order)
        self.assertEqual(qs.count(), 1)
        ev = qs.get()
        self.assertEqual(ev.idempotency_key, payment_success_idempotency_key(self.order.id))
        self.assertEqual(ev.metadata.get('user_id'), self.user.id)

    def test_fulfill_twice_still_one_event(self):
        fulfill_order_after_payment(self.order)
        fulfill_order_after_payment(self.order)
        ensure_payment_success_event(self.order)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order).count(),
            1,
        )

    def test_staff_order_excluded_from_funnel_emit(self):
        staff = User.objects.create_user(
            username='stafffunnel', password='x', phone='09121110002', is_staff=True,
        )
        order = Order.objects.create(
            user=staff, product=self.product, plan=self.plan,
            amount=self.plan.price, status='pending',
        )
        fulfill_order_after_payment(order)
        self.assertFalse(is_bi_production_order(order))
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=order).count(),
            0,
        )

    def test_fake_track_excluded(self):
        self.order.zibal_track_id = 'FAKE-ABC123'
        self.order.save(update_fields=['zibal_track_id'])
        fulfill_order_after_payment(self.order)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order).count(),
            0,
        )

    def test_zero_amount_fulfill_emits(self):
        self.order.amount = 0
        self.order.save(update_fields=['amount'])
        fulfill_order_after_payment(self.order)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order).count(),
            1,
        )

    def test_card_transfer_approve_emits(self):
        self.order.payment_method = 'card_transfer'
        self.order.status = 'pending_verification'
        self.order.save()
        sub = CardTransferSubmission.objects.create(
            order=self.order,
            status='pending',
            reference_number='REF-CARD-1',
        )
        reviewer = User.objects.create_user(
            username='reviewer1', password='x', phone='09121110003', is_staff=True,
        )
        approve_card_transfer(sub, reviewer)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order).count(),
            1,
        )

    def test_record_funnel_false_skips_event(self):
        fulfill_order_after_payment(self.order, record_funnel=False)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order).count(),
            0,
        )


@override_settings(
    ZIBAL_MERCHANT_ID='zibal',
    ZIBAL_REQUEST_URL='https://gateway.zibal.ir/v1/request',
    ZIBAL_VERIFY_URL='https://gateway.zibal.ir/v1/verify',
    ZIBAL_START_PAY_URL='https://gateway.zibal.ir/start/',
)
class ZibalCallbackFunnelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='zibalfunnel', password='pass1234', phone='09121110004',
        )
        self.product, self.plan = _product_plan('zibal-funnel-bot')
        self.order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=Decimal('150000'), status='pending', zibal_track_id='TRACK-F1',
        )
        PaymentSettings.objects.update_or_create(
            pk=1, defaults={'zibal_enabled': True, 'card_transfer_enabled': False},
        )
        Transaction.objects.create(
            order=self.order, zibal_track_id='TRACK-F1',
            amount=self.order.amount, status='pending',
        )
        self.client.login(username='zibalfunnel', password='pass1234')

    @patch('shop.payment_views.zibal_service.verify_payment')
    def test_callback_success_one_event(self, mock_verify):
        mock_verify.return_value = ZibalVerifyResult(
            result_code=100, message='ok', ref_number='R1',
            paid_amount_rial=1500000, card_number='6037', raw={},
        )
        url = reverse('payment:callback')
        params = {'trackId': 'TRACK-F1', 'success': '1', 'status': '2'}
        self.client.get(url, params)
        self.client.get(url, params)  # تکراری پشت‌سرهم
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=self.order).count(),
            1,
        )


class ConcurrentFulfillFunnelTests(TransactionTestCase):
    def test_double_fulfill_one_event(self):
        user = User.objects.create_user(
            username='racefunnel', password='x', phone='09121110005',
        )
        product, plan = _product_plan('race-funnel-bot')
        order = Order.objects.create(
            user=user, product=product, plan=plan,
            amount=plan.price, status='pending',
        )
        fulfill_order_after_payment(order)
        fulfill_order_after_payment(order)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order_id=order.id).count(),
            1,
        )


class PaymentSuccessRollbackTests(TransactionTestCase):
    """payment_success داخل همان atomic fulfill است؛ Rollback نباید Event بگذارد."""

    def test_fulfill_outer_rollback_leaves_no_payment_success(self):
        from django.db import transaction

        user = User.objects.create_user(
            username='rollbackfunnel', password='x', phone='09121110055',
        )
        product, plan = _product_plan('rollback-funnel-bot')
        order = Order.objects.create(
            user=user, product=product, plan=plan,
            amount=plan.price, status='pending',
        )
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                fulfill_order_after_payment(order)
                self.assertEqual(
                    PlanFunnelEvent.objects.filter(
                        event_type='payment_success', order_id=order.id,
                    ).count(),
                    1,
                )
                raise RuntimeError('force fulfill rollback')

        self.assertEqual(
            PlanFunnelEvent.objects.filter(
                event_type='payment_success', order_id=order.id,
            ).count(),
            0,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')
        self.assertIsNone(order.paid_at)


class DataQualityCoverageTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan('dq-cov-bot')
        self.tracking_anchor = timezone.now() - timedelta(days=3)
        PlanFunnelEvent.objects.create(
            event_type='pricing_view',
            session_key='dq-s',
            product=self.product,
            created_at=self.tracking_anchor,
        )
        # force created_at
        PlanFunnelEvent.objects.filter(session_key='dq-s').update(created_at=self.tracking_anchor)

    def test_historical_vs_post_tracking(self):
        buyer = User.objects.create_user(username='dqb1', password='x', phone='09121110006')
        staff = User.objects.create_user(
            username='dqstaff', password='x', phone='09121110007', is_staff=True,
        )
        # قبل از tracking
        old = Order.objects.create(
            user=buyer, product=self.product, plan=self.plan,
            amount=self.plan.price, status='paid',
            paid_at=self.tracking_anchor - timedelta(days=10),
        )
        # بعد از tracking + event
        new = Order.objects.create(
            user=buyer, product=self.product, plan=self.plan,
            amount=self.plan.price, status='paid',
            paid_at=self.tracking_anchor + timedelta(hours=1),
        )
        PlanFunnelEvent.objects.create(
            event_type='payment_success',
            user=buyer,
            order=new,
            idempotency_key=payment_success_idempotency_key(new.id),
            metadata={'order_id': str(new.id)},
            created_at=self.tracking_anchor + timedelta(hours=1),
        )
        # staff نباید در Production باشد
        Order.objects.create(
            user=staff, product=self.product, plan=self.plan,
            amount=self.plan.price, status='paid',
            paid_at=self.tracking_anchor + timedelta(hours=2),
        )

        since = timezone.now() - timedelta(days=30)
        buyers = load_period_buyers(since=since)
        dq = build_data_quality(
            since=since, buyers=buyers, pricing_views=10, checkout_views=8,
        )
        self.assertEqual(dq['schema_version'], SCHEMA_VERSION)
        hist = dq['historical_coverage']
        post = dq['post_tracking_coverage']
        # Production: old + new (staff حذف) = 2 historical; post = 1 (new)
        self.assertEqual(hist['total'], 2)
        self.assertEqual(hist['linked'], 1)  # فقط new به event وصل است (از طریق payment_success)
        self.assertEqual(post['total'], 1)
        self.assertEqual(post['linked'], 1)
        self.assertFalse(post['sample_sufficient'])  # < MIN_SAMPLE
        self.assertFalse(dq['tracking_reliable'])

    def test_legacy_events_without_key_ok(self):
        PlanFunnelEvent.objects.create(
            event_type='checkout_view', session_key='legacy', idempotency_key=None,
        )
        self.assertEqual(PlanFunnelEvent.objects.filter(idempotency_key__isnull=True).count(), 2)

    def _seed_post_tracking_orders(self, *, total: int, linked: int):
        """total سفارش paid پس از tracking؛ linked تا با payment_success."""
        buyer = User.objects.create_user(
            username=f'dqtier-{total}-{linked}', password='x', phone='09121110999',
        )
        orders = []
        for i in range(total):
            o = Order.objects.create(
                user=buyer, product=self.product, plan=self.plan,
                amount=self.plan.price, status='paid',
                paid_at=self.tracking_anchor + timedelta(hours=i + 1),
            )
            orders.append(o)
            if i < linked:
                PlanFunnelEvent.objects.create(
                    event_type='payment_success',
                    user=buyer,
                    order=o,
                    idempotency_key=payment_success_idempotency_key(o.id),
                    metadata={'order_id': str(o.id)},
                    created_at=self.tracking_anchor + timedelta(hours=i + 1),
                )
        return orders

    def test_coverage_below_50_locks_conversion(self):
        # 5 سفارش، ۲ لینک = ۴۰٪ → insufficient / قفل
        self._seed_post_tracking_orders(total=5, linked=2)
        since = timezone.now() - timedelta(days=30)
        dq = build_data_quality(
            since=since,
            buyers=load_period_buyers(since=since),
            pricing_views=20,
            checkout_views=15,
        )
        post = dq['post_tracking_coverage']
        self.assertTrue(post['sample_sufficient'])
        self.assertEqual(post['coverage'], 40.0)
        self.assertFalse(dq['tracking_reliable'])
        self.assertFalse(dq['conversion_provisional'])
        self.assertFalse(dq['funnel_conversions_available'])
        item = next(i for i in dq['items'] if i['key'] == 'post_tracking_coverage')
        self.assertEqual(item['status'], 'insufficient')

    def test_coverage_50_to_70_is_provisional(self):
        # 5 سفارش، ۳ لینک = ۶۰٪ → partial / موقت
        self._seed_post_tracking_orders(total=5, linked=3)
        since = timezone.now() - timedelta(days=30)
        dq = build_data_quality(
            since=since,
            buyers=load_period_buyers(since=since),
            pricing_views=20,
            checkout_views=15,
        )
        post = dq['post_tracking_coverage']
        self.assertEqual(post['coverage'], 60.0)
        self.assertTrue(dq['conversion_provisional'])
        self.assertFalse(dq['tracking_reliable'])
        self.assertTrue(dq['funnel_conversions_available'])
        self.assertIn('موقت', dq['conversions']['pricing_to_paid']['display'])
        item = next(i for i in dq['items'] if i['key'] == 'post_tracking_coverage')
        self.assertEqual(item['status'], 'partial')

    def test_coverage_70_plus_is_good(self):
        # 5 سفارش، ۴ لینک = ۸۰٪ → good
        self._seed_post_tracking_orders(total=5, linked=4)
        since = timezone.now() - timedelta(days=30)
        dq = build_data_quality(
            since=since,
            buyers=load_period_buyers(since=since),
            pricing_views=20,
            checkout_views=15,
        )
        post = dq['post_tracking_coverage']
        self.assertEqual(post['coverage'], 80.0)
        self.assertTrue(dq['tracking_reliable'])
        self.assertFalse(dq['conversion_provisional'])
        self.assertTrue(dq['funnel_conversions_available'])
        item = next(i for i in dq['items'] if i['key'] == 'post_tracking_coverage')
        self.assertEqual(item['status'], 'good')
