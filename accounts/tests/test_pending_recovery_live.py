"""تست‌های فاز ۲.۲ — Live SMS + Idempotency + state machine."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun, SmsMessageLog
from accounts.services.pending_recovery import (
    STEP_RECOVERY_1,
    live_send_idempotency_key,
    run_pending_recovery,
)
from accounts.services.pending_recovery_live import (
    build_recovery_sms_text,
    execute_reserved_send,
    get_live_config,
    reserve_live_send,
    run_pending_recovery_live,
    validate_live_send_prerequisites,
)
from shop.models import LicensePlan, Order, Product
from shop.services.checkout_abandon import ensure_checkout_abandon_event

User = get_user_model()


def _product_plan(slug='live-recovery-bot'):
    product = Product.objects.create(
        title='ربات Live Recovery', slug=slug, description='t', is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product, name='ماهانه', plan_type='monthly',
        price=100000, duration_days=30, is_active=True,
    )
    return product, plan


@override_settings(
    RECOVERY_STEP_1_MIN_HOURS=2,
    RECOVERY_STEP_2_MIN_HOURS=24,
    RECOVERY_MAX_AGE_HOURS=72,
    RECOVERY_LOOKBACK_DAYS=7,
    RECOVERY_FREQUENCY_CAP_HOURS=24,
    RECOVERY_BATCH_LIMIT=100,
    PENDING_RECOVERY_FLOW_ENABLED=True,
    RECOVERY_LIVE_SEND_ENABLED=True,
    RECOVERY_LIVE_TEST_ONLY=True,
    RECOVERY_LIVE_TEST_PHONE='09129998877',
    RECOVERY_LIVE_MAX_SENDS_PER_RUN=1,
    SMS_PROVIDER='console',
    SMS_ENABLED=True,
    SITE_URL='https://test.divarfiling.ir',
)
class PendingRecoveryLiveTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan()
        self.user = User.objects.create_user(
            username='live1', password='x', phone='09121110001', first_name='علی',
        )
        self.now = timezone.now()

    def _backdate(self, order, hours_ago):
        Order.objects.filter(pk=order.pk).update(
            created_at=self.now - timedelta(hours=hours_ago),
        )
        order.refresh_from_db()

    def _order(self, *, hours_ago=5, **extra):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status=extra.pop('status', 'pending'),
            payment_method=extra.pop('payment_method', 'zibal'),
            **extra,
        )
        self._backdate(order, hours_ago)
        ensure_checkout_abandon_event(order)
        return order

    def _dry_run_resolution(self, order):
        from accounts.services.pending_recovery import resolve_pending_recovery_audience

        data = resolve_pending_recovery_audience(simulate_enabled=False)
        for res in data['resolutions']:
            if res.order.pk == order.pk and res.would_send:
                return res
        would = [r for r in data['resolutions'] if r.would_send]
        self.assertTrue(would, msg='no would_send resolution')
        return would[0]

    def test_validate_requires_confirm_and_switches(self):
        with self.assertRaises(ValueError):
            validate_live_send_prerequisites(confirm_live=False)

        with override_settings(PENDING_RECOVERY_FLOW_ENABLED=False):
            with self.assertRaises(ValueError):
                validate_live_send_prerequisites(confirm_live=True)

        with override_settings(RECOVERY_LIVE_SEND_ENABLED=False):
            with self.assertRaises(ValueError):
                validate_live_send_prerequisites(confirm_live=True)

        with override_settings(RECOVERY_LIVE_TEST_PHONE=''):
            with self.assertRaises(ValueError):
                validate_live_send_prerequisites(confirm_live=True, test_only=True)

    def test_build_recovery_sms_text(self):
        order = self._order(hours_ago=5)
        text = build_recovery_sms_text(order, step_key=STEP_RECOVERY_1)
        self.assertIn('علی', text)
        self.assertIn('ربات Live Recovery', text)
        self.assertIn(f'/payment/checkout/{order.pk}/', text)

    def test_reserve_blocks_duplicate_in_flight(self):
        order = self._order(hours_ago=5)
        res = self._dry_run_resolution(order)
        cfg = get_live_config()
        run = MarketingAutomationRun.objects.create(
            flow_key='pending_recovery',
            mode=MarketingAutomationRun.Mode.LIVE,
        )

        log1, err1 = reserve_live_send(run=run, res=res, cfg=cfg)
        self.assertIsNone(err1)
        self.assertEqual(log1.action, MarketingAutomationActionLog.Action.SEND_REQUESTED)

        log2, err2 = reserve_live_send(run=run, res=res, cfg=cfg)
        self.assertIsNone(log2)
        self.assertTrue(err2.startswith('in_flight_or_done'))

    def test_execute_marks_provider_accepted(self):
        order = self._order(hours_ago=5)
        res = self._dry_run_resolution(order)
        cfg = get_live_config()
        run = MarketingAutomationRun.objects.create(
            flow_key='pending_recovery',
            mode=MarketingAutomationRun.Mode.LIVE,
        )
        log, _ = reserve_live_send(run=run, res=res, cfg=cfg)
        action, sms_log = execute_reserved_send(log, cfg=cfg)
        self.assertEqual(action, MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED)
        self.assertIsNotNone(sms_log)
        log.refresh_from_db()
        self.assertEqual(log.sms_log_id, sms_log.pk)
        self.assertEqual(log.metadata.get('send_target_redirected'), True)
        self.assertEqual(sms_log.phone, '09129998877')

    def test_run_live_max_one_send(self):
        self._order(hours_ago=5)
        user2 = User.objects.create_user(username='live2', password='x', phone='09121110002')
        order2 = Order.objects.create(
            user=user2,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
            payment_method='zibal',
        )
        self._backdate(order2, hours_ago=30)
        ensure_checkout_abandon_event(order2)

        stats = run_pending_recovery_live(confirm_live=True, test_only=True)
        self.assertEqual(stats['provider_accepted'], 1)
        self.assertGreaterEqual(stats['would_send'], 2)
        self.assertGreaterEqual(stats['skipped'], 1)

        accepted = MarketingAutomationActionLog.objects.filter(
            action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
        ).count()
        self.assertEqual(accepted, 1)

    def test_command_live_requires_confirm(self):
        with self.assertRaises(CommandError):
            call_command('run_pending_recovery', '--live')

    def test_command_live_success(self):
        self._order(hours_ago=5)
        call_command(
            'run_pending_recovery',
            '--live',
            '--confirm-live',
            '--test-only',
        )
        self.assertEqual(
            MarketingAutomationActionLog.objects.filter(
                action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            ).count(),
            1,
        )

    def test_command_blocks_without_mode(self):
        with self.assertRaises(CommandError):
            call_command('run_pending_recovery')

    @patch('accounts.services.pending_recovery_live.notify_marketing')
    def test_ambiguous_error_keeps_send_requested(self, mock_notify):
        mock_notify.side_effect = TimeoutError('provider timeout')
        order = self._order(hours_ago=5)
        res = self._dry_run_resolution(order)
        cfg = get_live_config()
        run = MarketingAutomationRun.objects.create(
            flow_key='pending_recovery',
            mode=MarketingAutomationRun.Mode.LIVE,
        )
        log, _ = reserve_live_send(run=run, res=res, cfg=cfg)
        action, sms_log = execute_reserved_send(log, cfg=cfg)
        self.assertEqual(action, MarketingAutomationActionLog.Action.SEND_REQUESTED)
        self.assertIsNone(sms_log)
        log.refresh_from_db()
        self.assertEqual(log.reason, 'ambiguous_provider_error')

    def test_dry_run_still_no_provider_accepted(self):
        self._order(hours_ago=5)
        stats = run_pending_recovery(dry_run=True, simulate_enabled=True)
        self.assertGreater(stats['would_send'], 0)
        self.assertEqual(
            MarketingAutomationActionLog.objects.filter(
                action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            ).count(),
            0,
        )

    def test_failed_retry_blocked_without_flag(self):
        order = self._order(hours_ago=5)
        from accounts.services.pending_recovery import hash_normalized_phone

        phash = hash_normalized_phone(order.user.phone)
        send_key = live_send_idempotency_key(
            step_key=STEP_RECOVERY_1,
            phone_hash=phash,
            product_id=order.product_id,
            order_id=order.pk,
        )
        run = MarketingAutomationRun.objects.create(
            flow_key='pending_recovery',
            mode=MarketingAutomationRun.Mode.LIVE,
        )
        MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key='pending_recovery',
            step_key=STEP_RECOVERY_1,
            user=order.user,
            phone_hash=phash,
            order=order,
            product=order.product,
            action=MarketingAutomationActionLog.Action.FAILED,
            reason='provider_rejected',
            decision_key=f'live:decision:{send_key}',
            send_idempotency_key=send_key,
        )
        res = self._dry_run_resolution(order)
        cfg = get_live_config()
        log, err = reserve_live_send(run=run, res=res, cfg=cfg)
        self.assertIsNone(log)
        self.assertEqual(err, 'failed_previous')
