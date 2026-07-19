"""تست‌های مرحله 1.4 — checkout_abandon + Preview (بدون SMS)."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.services.admin_marketing_send import MarketingSendError, create_campaign_draft
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product
from shop.services.checkout_abandon import (
    CHECKOUT_SOURCE_ORDER,
    EXCLUDE_CANCELLED,
    EXCLUDE_FAILED,
    EXCLUDE_INVALID_PHONE,
    EXCLUDE_NEWER_PAID_SAME_PRODUCT,
    EXCLUDE_PAID,
    EXCLUDE_PENDING_VERIFICATION,
    EXCLUDE_STAFF_OR_FAKE,
    EXCLUDE_TOO_RECENT,
    build_abandoned_checkout_preview,
    ensure_checkout_abandon_event,
    evaluate_order_for_abandon,
    process_checkout_abandons,
    resolve_checkout_detection_source,
)
from shop.services.plan_funnel import checkout_abandon_idempotency_key

User = get_user_model()


def _product_plan(slug='abandon-bot'):
    product = Product.objects.create(
        title='ربات Abandon', slug=slug, description='t', is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product, name='ماهانه', plan_type='monthly',
        price=100000, duration_days=30, is_active=True,
    )
    return product, plan


@override_settings(CHECKOUT_ABANDON_HOURS=2, CHECKOUT_ABANDON_BATCH_LIMIT=100)
class CheckoutAbandonTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan()
        self.other_product, self.other_plan = _product_plan('abandon-other')
        self.user = User.objects.create_user(
            username='abandonu1', password='x', phone='09123330001',
        )
        self.now = timezone.now()

    def _order(self, *, status='pending', hours_ago=3, user=None, product=None, plan=None, phone_user=None, **extra):
        u = phone_user or user or self.user
        p = product or self.product
        pl = plan or self.plan
        order = Order.objects.create(
            user=u, product=p, plan=pl,
            amount=pl.price, status=status,
            payment_method=extra.pop('payment_method', 'zibal'),
            **extra,
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=self.now - timedelta(hours=hours_ago),
        )
        order.refresh_from_db()
        return order

    def test_stale_pending_creates_one_abandon(self):
        order = self._order(hours_ago=3)
        stats = process_checkout_abandons(hours=2, dry_run=False)
        self.assertEqual(stats['created'], 1)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='checkout_abandon', order=order).count(),
            1,
        )
        ev = PlanFunnelEvent.objects.get(order=order, event_type='checkout_abandon')
        self.assertEqual(ev.idempotency_key, checkout_abandon_idempotency_key(order.id))

    def test_recent_pending_no_event(self):
        self._order(hours_ago=1)
        stats = process_checkout_abandons(hours=2, dry_run=False)
        self.assertEqual(stats['created'], 0)
        self.assertEqual(PlanFunnelEvent.objects.filter(event_type='checkout_abandon').count(), 0)
        ev = evaluate_order_for_abandon(Order.objects.get(), hours=2)
        self.assertEqual(ev.exclude_reason, EXCLUDE_TOO_RECENT)

    def test_pending_verification_excluded(self):
        order = self._order(status='pending_verification', hours_ago=5)
        self.assertEqual(process_checkout_abandons(hours=2)['created'], 0)
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertFalse(any(r['order_id'] == str(order.pk) for r in preview['eligible']))
        excluded = next(r for r in preview['excluded'] if r['order_id'] == str(order.pk))
        self.assertEqual(excluded['exclude_reason'], EXCLUDE_PENDING_VERIFICATION)

    def test_paid_excluded(self):
        order = self._order(status='paid', hours_ago=5)
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertFalse(any(r['order_id'] == str(order.pk) for r in preview['eligible']))
        row = next(r for r in preview['excluded'] if r['order_id'] == str(order.pk))
        self.assertEqual(row['exclude_reason'], EXCLUDE_PAID)

    def test_failed_excluded_not_abandon(self):
        order = self._order(status='failed', hours_ago=5)
        self.assertEqual(process_checkout_abandons(hours=2)['created'], 0)
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertFalse(any(r['order_id'] == str(order.pk) for r in preview['eligible']))
        row = next(r for r in preview['excluded'] if r['order_id'] == str(order.pk))
        self.assertEqual(row['exclude_reason'], EXCLUDE_FAILED)

    def test_cancelled_excluded(self):
        order = self._order(status='cancelled', hours_ago=5)
        preview = build_abandoned_checkout_preview(hours=2)
        row = next(r for r in preview['excluded'] if r['order_id'] == str(order.pk))
        self.assertEqual(row['exclude_reason'], EXCLUDE_CANCELLED)

    def test_staff_superuser_fake_excluded(self):
        staff = User.objects.create_user(
            username='abandonstaff', password='x', phone='09123330002', is_staff=True,
        )
        superu = User.objects.create_user(
            username='abandonsuper', password='x', phone='09123330003', is_superuser=True,
        )
        staff_o = self._order(hours_ago=5, phone_user=staff)
        super_o = self._order(hours_ago=5, phone_user=superu)
        fake_o = self._order(hours_ago=5, zibal_track_id='FAKE-XYZ')
        self.assertEqual(process_checkout_abandons(hours=2)['created'], 0)
        preview = build_abandoned_checkout_preview(hours=2)
        for o in (staff_o, super_o, fake_o):
            self.assertFalse(any(r['order_id'] == str(o.pk) for r in preview['eligible']))
            row = next(r for r in preview['excluded'] if r['order_id'] == str(o.pk))
            self.assertEqual(row['exclude_reason'], EXCLUDE_STAFF_OR_FAKE)

    def test_job_idempotent(self):
        self._order(hours_ago=4)
        process_checkout_abandons(hours=2)
        process_checkout_abandons(hours=2)
        self.assertEqual(PlanFunnelEvent.objects.filter(event_type='checkout_abandon').count(), 1)
        stats = process_checkout_abandons(hours=2)
        self.assertEqual(stats['already_recorded'], 1)
        self.assertEqual(stats['created'], 0)

    def test_abandon_then_paid_keeps_event_drops_active(self):
        order = self._order(hours_ago=4)
        ensure_checkout_abandon_event(order)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='checkout_abandon', order=order).count(),
            1,
        )
        order.status = 'paid'
        order.paid_at = timezone.now()
        order.save(update_fields=['status', 'paid_at'])
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertFalse(any(r['order_id'] == str(order.pk) for r in preview['eligible']))
        row = next(r for r in preview['excluded'] if r['order_id'] == str(order.pk))
        self.assertEqual(row['exclude_reason'], EXCLUDE_PAID)
        self.assertTrue(row['has_abandon_event'])
        self.assertIn('تاریخی', row['note'])

    def test_newer_paid_same_product_excluded(self):
        stale = self._order(hours_ago=5)
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=self.plan.price, status='paid', paid_at=timezone.now(),
        )
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertFalse(any(r['order_id'] == str(stale.pk) for r in preview['eligible']))
        row = next(r for r in preview['excluded'] if r['order_id'] == str(stale.pk))
        self.assertEqual(row['exclude_reason'], EXCLUDE_NEWER_PAID_SAME_PRODUCT)

    def test_two_orders_same_user_no_cross_link(self):
        o1 = self._order(hours_ago=5)
        o2 = self._order(hours_ago=6, product=self.other_product, plan=self.other_plan)
        process_checkout_abandons(hours=2)
        e1 = PlanFunnelEvent.objects.get(order=o1, event_type='checkout_abandon')
        e2 = PlanFunnelEvent.objects.get(order=o2, event_type='checkout_abandon')
        self.assertEqual(e1.idempotency_key, checkout_abandon_idempotency_key(o1.id))
        self.assertEqual(e2.idempotency_key, checkout_abandon_idempotency_key(o2.id))
        self.assertNotEqual(e1.idempotency_key, e2.idempotency_key)
        self.assertEqual(e1.metadata['order_id'], str(o1.id))
        self.assertEqual(e2.metadata['order_id'], str(o2.id))

    def test_checkout_view_without_order_id_not_user_linked(self):
        order = self._order(hours_ago=5)
        # checkout_view فقط با user — نباید به Order حدس زده شود
        PlanFunnelEvent.objects.create(
            event_type='checkout_view',
            user=self.user,
            product=self.product,
            plan=self.plan,
            session_key='sess-no-order',
            metadata={},
        )
        src = resolve_checkout_detection_source(order)
        self.assertEqual(src['source'], CHECKOUT_SOURCE_ORDER)
        self.assertEqual(src['label'], 'order_created_at')
        preview = build_abandoned_checkout_preview(hours=2)
        row = next(
            r for r in preview['eligible'] + preview['excluded']
            if r['order_id'] == str(order.pk)
        )
        self.assertEqual(row['checkout_source'], 'order_created_at')

    def test_linked_checkout_event_when_order_id_present(self):
        order = self._order(hours_ago=5)
        linked = PlanFunnelEvent.objects.create(
            event_type='checkout_view',
            user=self.user,
            product=self.product,
            plan=self.plan,
            order=order,
            session_key='sess-linked',
            metadata={'order_id': str(order.pk)},
        )
        src = resolve_checkout_detection_source(order)
        self.assertEqual(src['source'], 'linked_checkout_event')
        self.assertEqual(src['checkout_event_id'], linked.pk)

    def test_invalid_phone_in_excluded(self):
        bad = User.objects.create_user(
            username='abandonbadphone', password='x', phone='12345',
        )
        order = self._order(hours_ago=5, phone_user=bad)
        process_checkout_abandons(hours=2)
        self.assertEqual(
            PlanFunnelEvent.objects.filter(event_type='checkout_abandon', order=order).count(),
            1,
        )
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertFalse(any(r['order_id'] == str(order.pk) for r in preview['eligible']))
        row = next(r for r in preview['excluded'] if r['order_id'] == str(order.pk))
        self.assertEqual(row['exclude_reason'], EXCLUDE_INVALID_PHONE)

    @patch('accounts.services.notifications.notify_marketing')
    def test_preview_sends_no_sms(self, mock_notify):
        self._order(hours_ago=5)
        process_checkout_abandons(hours=2)
        build_abandoned_checkout_preview(hours=2)
        mock_notify.assert_not_called()

    def test_send_campaign_blocked_for_segment(self):
        with self.assertRaises(MarketingSendError) as ctx:
            create_campaign_draft(
                name='test',
                created_by=self.user,
                segment_key='abandoned_checkout',
                message_template='hi',
                discount_mode='none',
            )
        self.assertEqual(ctx.exception.code, 'preview_only_segment')

    def test_management_command_dry_run(self):
        self._order(hours_ago=5)
        call_command('record_checkout_abandons', '--dry-run', '--hours=2')
        self.assertEqual(PlanFunnelEvent.objects.filter(event_type='checkout_abandon').count(), 0)
        call_command('record_checkout_abandons', '--hours=2')
        self.assertEqual(PlanFunnelEvent.objects.filter(event_type='checkout_abandon').count(), 1)

    def test_eligible_appears_in_preview(self):
        order = self._order(hours_ago=5)
        process_checkout_abandons(hours=2)
        preview = build_abandoned_checkout_preview(hours=2)
        self.assertEqual(preview['preview_only'], True)
        self.assertEqual(preview['send_enabled'], False)
        row = next(r for r in preview['eligible'] if r['order_id'] == str(order.pk))
        self.assertTrue(row['has_abandon_event'])
        self.assertEqual(row['checkout_source'], 'order_created_at')
        self.assertTrue(row['include_reason_label'])
