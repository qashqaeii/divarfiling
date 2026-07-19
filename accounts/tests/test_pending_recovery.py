"""تست‌های فاز ۲.۱.۱ — Simulation جدا از Delivery + Journey Steps."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun
from accounts.services.pending_recovery import (
    STEP_RECOVERY_1,
    STEP_RECOVERY_1_LATE,
    STEP_RECOVERY_2,
    STEP_TOO_RECENT,
    STEP_EXPIRED,
    STEP_WAITING_FOR_STEP_2,
    SUPPRESS_ALREADY_RECEIVED_STEP,
    SUPPRESS_FREQUENCY_CAP,
    SUPPRESS_INVALID_PHONE,
    SUPPRESS_OPT_OUT,
    SUPPRESS_OUTSIDE_WINDOW,
    SUPPRESS_PENDING_VERIFICATION,
    SUPPRESS_STAFF_OR_FAKE,
    SUPPRESS_WAITING_FOR_STEP_2,
    build_pending_recovery_preview,
    classify_recovery_step,
    dry_run_decision_key,
    hash_normalized_phone,
    live_send_idempotency_key,
    run_pending_recovery,
)
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product
from shop.services.checkout_abandon import ensure_checkout_abandon_event
from shop.services.plan_funnel import checkout_abandon_idempotency_key

User = get_user_model()


def _product_plan(slug='recovery-bot'):
    product = Product.objects.create(
        title='ربات Recovery', slug=slug, description='t', is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product, name='ماهانه', plan_type='monthly',
        price=100000, duration_days=30, is_active=True,
    )
    trial = LicensePlan.objects.create(
        product=product, name='آزمایشی', plan_type='daily',
        price=50000, duration_days=1, is_active=True,
    )
    return product, plan, trial


@override_settings(
    RECOVERY_STEP_1_MIN_HOURS=2,
    RECOVERY_STEP_2_MIN_HOURS=24,
    RECOVERY_MAX_AGE_HOURS=72,
    RECOVERY_LOOKBACK_DAYS=7,
    RECOVERY_FREQUENCY_CAP_HOURS=24,
    RECOVERY_BATCH_LIMIT=100,
    PENDING_RECOVERY_FLOW_ENABLED=True,
)
class PendingRecoveryTests(TestCase):
    def setUp(self):
        self.product, self.plan, self.trial = _product_plan()
        self.other_product, self.other_plan, _ = _product_plan('recovery-other')
        self.user = User.objects.create_user(
            username='recv1', password='x', phone='09121110001',
        )
        self.user2 = User.objects.create_user(
            username='recv2', password='x', phone='09121110002',
        )
        self.now = timezone.now()

    def _backdate(self, order, hours_ago):
        Order.objects.filter(pk=order.pk).update(
            created_at=self.now - timedelta(hours=hours_ago),
        )
        order.refresh_from_db()

    def _order(self, *, user=None, product=None, plan=None, hours_ago=5, **extra):
        order = Order.objects.create(
            user=user or self.user,
            product=product or self.product,
            plan=plan or self.plan,
            amount=(plan or self.plan).price,
            status=extra.pop('status', 'pending'),
            payment_method=extra.pop('payment_method', 'zibal'),
            **extra,
        )
        self._backdate(order, hours_ago)
        return order

    def _abandon(self, order):
        ev = ensure_checkout_abandon_event(order)
        if ev is None:
            PlanFunnelEvent.objects.create(
                event_type='checkout_abandon',
                user=order.user,
                product=order.product,
                plan=order.plan,
                order=order,
                idempotency_key=checkout_abandon_idempotency_key(order.pk),
                session_key=f'order:{order.pk}',
                metadata={'order_id': str(order.pk)},
            )

    def _fixture_run(self):
        return MarketingAutomationRun.objects.create(
            flow_key='pending_recovery',
            mode=MarketingAutomationRun.Mode.DRY_RUN,
            status=MarketingAutomationRun.Status.COMPLETED,
        )

    def _fixture_real_sent(
        self,
        order,
        *,
        step_key=STEP_RECOVERY_1,
        action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
        hours_ago=1,
    ):
        from accounts.services.pending_recovery import hash_normalized_phone
        phash = hash_normalized_phone(order.user.phone)
        run = self._fixture_run()
        log = MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key='pending_recovery',
            step_key=step_key,
            user=order.user,
            phone_hash=phash,
            masked_phone='0912***01',
            order=order,
            product=order.product,
            action=action,
            reason='fixture',
            decision_key=f'fixture:decision:{order.pk}:{step_key}',
            send_idempotency_key=live_send_idempotency_key(
                step_key=step_key,
                phone_hash=phash,
                product_id=order.product_id,
                order_id=order.pk,
            ),
        )
        MarketingAutomationActionLog.objects.filter(pk=log.pk).update(
            created_at=self.now - timedelta(hours=hours_ago),
        )
        log.refresh_from_db()
        return log

    def test_classify_age_buckets(self):
        self.assertEqual(classify_recovery_step(1.5), STEP_TOO_RECENT)
        self.assertEqual(classify_recovery_step(5), STEP_RECOVERY_1)
        self.assertEqual(classify_recovery_step(30), STEP_RECOVERY_1_LATE)
        self.assertEqual(classify_recovery_step(80), STEP_EXPIRED)

    def test_two_pending_same_phone_product_only_newest(self):
        older = self._order(hours_ago=30)
        newer = self._order(hours_ago=6)
        self._abandon(older)
        self._abandon(newer)
        preview = build_pending_recovery_preview()
        recipients = preview['recovery_recipients']
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['selected_order_id'], str(newer.pk))

    def test_same_phone_two_accounts_one_recipient(self):
        u1 = User.objects.create_user(username='acc1', password='x', phone='09123334441')
        u2 = User.objects.create_user(username='acc2', password='x', phone='09123334442')
        older = self._order(user=u1, hours_ago=30)
        newer = self._order(user=u2, hours_ago=6)
        self._abandon(older)
        self._abandon(newer)
        with patch(
            'accounts.services.pending_recovery.normalize_phone',
            return_value='09123334444',
        ):
            preview = build_pending_recovery_preview()
        self.assertEqual(len(preview['recovery_recipients']), 1)

    def test_two_products_two_recipients(self):
        o1 = self._order(product=self.product, plan=self.plan, hours_ago=6)
        o2 = self._order(product=self.other_product, plan=self.other_plan, hours_ago=6)
        self._abandon(o1)
        self._abandon(o2)
        preview = build_pending_recovery_preview()
        self.assertEqual(len(preview['recovery_recipients']), 2)

    def test_order_59h_without_prior_message_is_step1_late_not_step2(self):
        order = self._order(hours_ago=59)
        self._abandon(order)
        preview = build_pending_recovery_preview()
        row = preview['recovery_recipients'][0]
        self.assertEqual(row['step_key'], STEP_RECOVERY_1_LATE)
        self.assertNotEqual(row['step_key'], STEP_RECOVERY_2)

    def test_step2_requires_real_step1_sent_and_24h(self):
        order = self._order(hours_ago=59)
        self._abandon(order)
        self._fixture_real_sent(order, step_key=STEP_RECOVERY_1, hours_ago=25)
        preview = build_pending_recovery_preview()
        row = preview['recovery_recipients'][0]
        self.assertEqual(row['step_key'], STEP_RECOVERY_2)

    def test_step1_sent_less_than_24h_ago_waits(self):
        order = self._order(hours_ago=59)
        self._abandon(order)
        self._fixture_real_sent(order, step_key=STEP_RECOVERY_1, hours_ago=5)
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 0)
        row = next(
            r for r in preview['recovery_suppressed']
            if r['order_id'] == str(order.pk)
        )
        self.assertEqual(row['suppress_reason'], SUPPRESS_WAITING_FOR_STEP_2)
        self.assertEqual(row['step_key'], STEP_WAITING_FOR_STEP_2)

    def test_expired_over_72_hours(self):
        order = self._order(hours_ago=80)
        self._abandon(order)
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 0)

    def test_real_sent_blocks_step2_repeat(self):
        order = self._order(hours_ago=59)
        self._abandon(order)
        self._fixture_real_sent(order, step_key=STEP_RECOVERY_1, hours_ago=30)
        self._fixture_real_sent(order, step_key=STEP_RECOVERY_2, hours_ago=1)
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 0)
        self.assertGreaterEqual(preview['recovery_stats']['suppressed_already_step'], 1)

    def test_failed_fixture_not_counted_as_received(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        self._fixture_real_sent(
            order,
            step_key=STEP_RECOVERY_1,
            action=MarketingAutomationActionLog.Action.FAILED,
            hours_ago=1,
        )
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 1)

    def test_would_send_does_not_block_second_dry_run(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        first = run_pending_recovery(dry_run=True, simulate_enabled=True)
        second = run_pending_recovery(dry_run=True, simulate_enabled=True)
        self.assertEqual(first['would_send'], 1)
        self.assertEqual(second['would_send'], 1)
        self.assertEqual(first['actions_created'], 1)
        self.assertEqual(second['actions_created'], 1)
        self.assertEqual(MarketingAutomationRun.objects.count(), 2)
        self.assertEqual(
            MarketingAutomationActionLog.objects.filter(
                action=MarketingAutomationActionLog.Action.WOULD_SEND,
            ).count(),
            2,
        )

    def test_would_send_does_not_trigger_frequency_cap(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        run = self._fixture_run()
        phash = hash_normalized_phone(order.user.phone)
        MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key='pending_recovery',
            step_key=STEP_RECOVERY_1,
            user=order.user,
            phone_hash=phash,
            masked_phone='0912***01',
            order=order,
            product=order.product,
            action=MarketingAutomationActionLog.Action.WOULD_SEND,
            reason='prior dry run',
            decision_key='dry_run:prior:1',
            send_idempotency_key=None,
        )
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 1)
        self.assertEqual(preview['recovery_stats']['suppressed_frequency_cap'], 0)

    def test_real_sent_triggers_frequency_cap(self):
        order = self._order(hours_ago=30)
        self._abandon(order)
        self._fixture_real_sent(order, step_key=STEP_RECOVERY_2, hours_ago=1)
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 0)
        self.assertGreaterEqual(preview['recovery_stats']['suppressed_frequency_cap'], 1)

    def test_would_send_leaves_send_idempotency_null_for_future_live(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        run_pending_recovery(dry_run=True, simulate_enabled=True)
        log = MarketingAutomationActionLog.objects.get()
        self.assertIsNone(log.send_idempotency_key)
        live_key = live_send_idempotency_key(
            step_key=log.step_key,
            phone_hash=log.phone_hash,
            product_id=order.product_id,
            order_id=order.pk,
        )
        self.assertFalse(
            MarketingAutomationActionLog.objects.filter(
                send_idempotency_key=live_key,
            ).exists()
        )

    @override_settings(PENDING_RECOVERY_FLOW_ENABLED=False)
    def test_simulate_enabled_without_live_flow(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        preview = build_pending_recovery_preview()
        self.assertEqual(preview['recovery_stats']['would_send'], 1)
        stats = run_pending_recovery(dry_run=True, simulate_enabled=True)
        self.assertEqual(stats['would_send'], 1)
        self.assertFalse(stats['flow_live_enabled'])

    @override_settings(PENDING_RECOVERY_FLOW_ENABLED=False)
    def test_runner_without_simulate_blocked_when_live_off(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        with self.assertRaises(ValueError):
            run_pending_recovery(dry_run=True, simulate_enabled=False)

    @patch('accounts.services.notifications.notify_marketing')
    def test_dry_run_no_sms_provider(self, mock_notify):
        order = self._order(hours_ago=6)
        self._abandon(order)
        run_pending_recovery(dry_run=True, simulate_enabled=True)
        mock_notify.assert_not_called()

    def test_command_requires_dry_run(self):
        with self.assertRaises(CommandError):
            call_command('run_pending_recovery')

    def test_command_simulate_enabled(self):
        order = self._order(hours_ago=6)
        self._abandon(order)
        with override_settings(PENDING_RECOVERY_FLOW_ENABLED=False):
            call_command('run_pending_recovery', '--dry-run', '--simulate-enabled')
        self.assertEqual(MarketingAutomationRun.objects.count(), 1)

    def test_pending_verification_suppressed(self):
        order = self._order(hours_ago=6, status='pending_verification')
        self._abandon(order)
        preview = build_pending_recovery_preview()
        reasons = [r['suppress_reason'] for r in preview['recovery_suppressed']]
        self.assertIn(SUPPRESS_PENDING_VERIFICATION, reasons)

    def test_invalid_phone_and_opt_out_and_staff(self):
        bad = User.objects.create_user(username='badph', password='x', phone='123')
        o1 = self._order(user=bad, hours_ago=6)
        self._abandon(o1)
        self.user.marketing_sms_opt_out = True
        self.user.save(update_fields=['marketing_sms_opt_out'])
        o2 = self._order(hours_ago=6)
        self._abandon(o2)
        staff = User.objects.create_user(
            username='staffu', password='x', phone='09125556677', is_staff=True,
        )
        o3 = self._order(user=staff, hours_ago=6)
        self._abandon(o3)
        preview = build_pending_recovery_preview()
        reasons = {r['suppress_reason'] for r in preview['recovery_suppressed']}
        self.assertIn(SUPPRESS_INVALID_PHONE, reasons)
        self.assertIn(SUPPRESS_OPT_OUT, reasons)
        self.assertIn(SUPPRESS_STAFF_OR_FAKE, reasons)

    def test_acceptance_like_production_shape(self):
        u22 = User.objects.create_user(username='u22', password='x', phone='09199999024')
        u61 = User.objects.create_user(username='u61', password='x', phone='09155555090')
        u73 = User.objects.create_user(username='u73', password='x', phone='09155555057')
        u79 = User.objects.create_user(username='u79', password='x', phone='09133333014')

        for hours in (139, 138):
            o = self._order(user=u22, plan=self.trial, hours_ago=hours)
            self._abandon(o)
        o22m = self._order(user=u22, plan=self.plan, hours_ago=139)
        self._abandon(o22m)
        o61 = self._order(user=u61, plan=self.trial, hours_ago=135)
        self._abandon(o61)
        o73 = self._order(user=u73, plan=self.trial, hours_ago=59)
        self._abandon(o73)
        o79a = self._order(user=u79, plan=self.plan, hours_ago=5.5)
        o79b = self._order(user=u79, plan=self.plan, hours_ago=5.3)
        self._abandon(o79a)
        self._abandon(o79b)

        preview = build_pending_recovery_preview()
        stats = preview['recovery_stats']
        self.assertEqual(stats['raw_abandon_events'], 7)
        self.assertEqual(stats['would_send'], 2)
        steps = {r['step_key'] for r in preview['recovery_recipients']}
        self.assertIn(STEP_RECOVERY_1, steps)
        self.assertIn(STEP_RECOVERY_1_LATE, steps)
        self.assertNotIn(STEP_RECOVERY_2, steps)

    def test_decision_key_scoped_to_run(self):
        order = self._order(hours_ago=6)
        key1 = dry_run_decision_key(
            run_id=1, step_key=STEP_RECOVERY_1,
            phone_hash='abc', product_id=1, order_id=order.pk,
        )
        key2 = dry_run_decision_key(
            run_id=2, step_key=STEP_RECOVERY_1,
            phone_hash='abc', product_id=1, order_id=order.pk,
        )
        self.assertNotEqual(key1, key2)
