"""تست Management Automation Runtime."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    ManagementAutomationExecution,
    ManagementAutomationRecipient,
    ManagementAutomationRule,
    UserDiscountIssuance,
)
from accounts.services.admin_management_assistant import ensure_automation_rules
from accounts.services.management_automation_runner import (
    AutomationCandidate,
    in_quiet_hours,
    revalidate_candidate,
    rule_is_due,
    run_management_automations,
    run_rule,
    _process_candidate,
    _trigger_already_handled,
)
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from licenses.models import License
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran', SMS_PROVIDER='console')
class ManagementAutomationRunnerTests(TestCase):
    def setUp(self):
        ensure_automation_rules()
        self.user = User.objects.create_user(
            username='ru1', password='x', phone='09120000201',
        )
        self.staff = User.objects.create_user(
            username='staff_r', password='x', phone='09120000202', is_staff=True,
        )
        self.product = Product.objects.create(title='P', slug='run-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product, name='م', plan_type='monthly', price=100000,
            duration_days=30, is_active=True,
        )

    def _activate_rule(self, key: str) -> ManagementAutomationRule:
        rule = ManagementAutomationRule.objects.get(key=key)
        rule.is_active = True
        rule.is_paused = False
        rule.save(update_fields=['is_active', 'is_paused', 'updated_at'])
        return rule

    def test_inactive_rule_not_run(self):
        rule = ManagementAutomationRule.objects.get(key='pending_recovery')
        rule.is_active = False
        rule.save()
        summary = run_management_automations(dry_run=True, rule_key='pending_recovery')
        self.assertEqual(summary['rules_run'], 0)

    def test_daily_cadence_skips_same_day(self):
        rule = self._activate_rule('license_expiring_3d')
        rule.last_run_at = timezone.now()
        rule.save(update_fields=['last_run_at'])
        self.assertFalse(rule_is_due(rule))
        ex = run_rule(rule, dry_run=True, force=False)
        self.assertIsNone(ex)

    def test_hourly_cadence_allows_after_hour(self):
        rule = self._activate_rule('pending_recovery')
        rule.cadence = ManagementAutomationRule.Cadence.HOURLY
        rule.last_run_at = timezone.now() - timedelta(hours=2)
        rule.save()
        self.assertTrue(rule_is_due(rule))

    def test_dedup_trigger_key(self):
        rule = self._activate_rule('pending_recovery')
        execution = ManagementAutomationExecution.objects.create(rule=rule, dry_run=True)
        trig = 'pending_order:999'
        ManagementAutomationRecipient.objects.create(
            execution=execution,
            rule=rule,
            trigger_key=trig,
            status=ManagementAutomationRecipient.Status.SENT,
            sent_at=timezone.now(),
        )
        self.assertTrue(_trigger_already_handled(rule, trig))

    def test_revalidate_paid_pending_skips(self):
        rule = ManagementAutomationRule.objects.get(key='pending_recovery')
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )
        candidate = AutomationCandidate(
            trigger_key=f'pending_order:{order.pk}',
            user=self.user,
            phone='09120000201',
            metadata={'order_id': order.pk, 'user_id': self.user.pk},
        )
        ok, reason = revalidate_candidate(rule, candidate)
        self.assertFalse(ok)
        self.assertEqual(reason, 'order_paid_or_gone')

    def _pending_order(self, user, *, hours_ago: int = 5):
        order = Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=100000,
            status=PENDING_ORDER_STATUSES[0],
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago),
        )
        order.refresh_from_db()
        return order

    def test_dry_run_no_real_sms(self):
        rule = self._activate_rule('pending_recovery')
        self._pending_order(self.user, hours_ago=5)
        with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
            ex = run_rule(rule, dry_run=True, force=True)
            self.assertIsNotNone(ex)
            mock_send.assert_not_called()
            self.assertTrue(
                ManagementAutomationRecipient.objects.filter(
                    execution=ex,
                    status=ManagementAutomationRecipient.Status.DRY_RUN,
                ).exists()
            )

    def test_failure_one_recipient_does_not_stop_run(self):
        rule = self._activate_rule('pending_recovery')
        self._pending_order(self.user, hours_ago=5)
        user2 = User.objects.create_user(username='ru2', password='x', phone='09120000203')
        self._pending_order(user2, hours_ago=5)
        with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
            mock_send.side_effect = [
                (False, type('L', (), {'pk': 1, 'error_message': 'fail'})()),
                (True, type('L', (), {'pk': 2, 'error_message': ''})()),
            ]
            ex = run_rule(rule, dry_run=False, force=True)
            ex.refresh_from_db()
            self.assertEqual(ex.status, ManagementAutomationExecution.Status.COMPLETED)
            self.assertGreaterEqual(ex.failed_count, 1)
            self.assertGreaterEqual(ex.success_count, 1)

    def test_max_recipients_limit(self):
        rule = self._activate_rule('pending_recovery')
        rule.max_recipients_per_run = 1
        rule.save(update_fields=['max_recipients_per_run'])
        for i in range(3):
            u = User.objects.create_user(username=f'pu{i}', password='x', phone=f'0912000030{i}')
            self._pending_order(u, hours_ago=5)
        ex = run_rule(rule, dry_run=True, force=True)
        self.assertEqual(ex.processed_count, 1)

    def test_sms_low_rule_no_user_sms(self):
        rule = self._activate_rule('sms_balance_low')
        with patch('accounts.services.management_automation_runner.get_sms_balance_snapshot') as mock_bal:
            mock_bal.return_value = {'ok': True, 'is_low': True, 'credit': 1000}
            with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
                ex = run_rule(rule, dry_run=False, force=True)
                mock_send.assert_not_called()
                self.assertIsNotNone(ex)
                self.assertEqual(ex.success_count, 1)
                rec = ManagementAutomationRecipient.objects.get(execution=ex)
                self.assertEqual(rec.status, ManagementAutomationRecipient.Status.ALERT)
                self.assertIsNone(rec.user)

    def test_revalidate_renewed_license_skips(self):
        rule = ManagementAutomationRule.objects.get(key='license_expiring_3d')
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )
        lic = License.objects.create(
            order=order,
            license_key='KEY-RUN-1',
            plan=self.plan,
            status='active',
            expires_at=timezone.now() + timedelta(days=2),
        )
        new_order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )
        License.objects.create(
            order=new_order,
            license_key='KEY-RUN-2',
            plan=self.plan,
            status='active',
            expires_at=timezone.now() + timedelta(days=30),
        )
        candidate = AutomationCandidate(
            trigger_key=f'license_expiring:{lic.pk}:{lic.expires_at.date()}',
            user=self.user,
            phone='09120000201',
            metadata={'license_id': lic.pk, 'user_id': self.user.pk},
        )
        lic.status = 'expired'
        lic.save(update_fields=['status'])
        ok, reason = revalidate_candidate(rule, candidate)
        self.assertFalse(ok)

    def test_management_command(self):
        rule = self._activate_rule('sms_balance_low')
        with patch('accounts.services.management_automation_runner.get_sms_balance_snapshot') as mock_bal:
            mock_bal.return_value = {'ok': True, 'is_low': True, 'credit': 500}
            call_command('run_management_automations', '--dry-run', f'--rule-key={rule.key}', '--force')
        self.assertTrue(ManagementAutomationExecution.objects.filter(rule=rule, dry_run=True).exists())

    def test_execution_counters(self):
        rule = self._activate_rule('sms_balance_low')
        with patch('accounts.services.management_automation_runner.get_sms_balance_snapshot') as mock_bal:
            mock_bal.return_value = {'ok': True, 'is_low': True, 'credit': 500}
            ex = run_rule(rule, dry_run=True, force=True)
        self.assertGreaterEqual(ex.matched_count, 1)
        self.assertEqual(ex.success_count, 1)

    def test_quiet_hours_blocks_sms(self):
        rule = self._activate_rule('pending_recovery')
        rule.quiet_hours_start = 0
        rule.quiet_hours_end = 24
        rule.save()
        self.assertTrue(in_quiet_hours(rule))
        ex = run_rule(rule, dry_run=True, force=True)
        self.assertIsNone(ex)

    def test_pending_recovery_allows_after_old_paid_order(self):
        rule = ManagementAutomationRule.objects.get(key='pending_recovery')
        paid = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=100_000,
            status='paid',
            paid_at=timezone.now() - timedelta(days=30),
        )
        pending = self._pending_order(self.user, hours_ago=5)
        candidate = AutomationCandidate(
            trigger_key=f'pending_order:{pending.pk}',
            user=self.user,
            phone='09120000201',
            metadata={'order_id': str(pending.pk), 'user_id': self.user.pk},
        )
        ok, reason = revalidate_candidate(rule, candidate)
        self.assertTrue(ok, msg=reason)
        self.assertIsNotNone(paid.pk)

    def test_pending_recovery_skips_after_newer_paid(self):
        rule = ManagementAutomationRule.objects.get(key='pending_recovery')
        pending = self._pending_order(self.user, hours_ago=5)
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=100_000,
            status='paid',
            paid_at=timezone.now(),
        )
        candidate = AutomationCandidate(
            trigger_key=f'pending_order:{pending.pk}',
            user=self.user,
            phone='09120000201',
            metadata={'order_id': str(pending.pk), 'user_id': self.user.pk},
        )
        ok, reason = revalidate_candidate(rule, candidate)
        self.assertFalse(ok)
        self.assertEqual(reason, 'user_has_paid_order_after')

    def test_dry_run_does_not_issue_discount_code(self):
        rule = self._activate_rule('pending_recovery_discount')
        order = self._pending_order(self.user, hours_ago=30)
        before = UserDiscountIssuance.objects.count()
        with patch('accounts.services.management_automation_runner.notify_marketing'):
            ex = run_rule(rule, dry_run=True, force=True)
        self.assertIsNotNone(ex)
        self.assertEqual(UserDiscountIssuance.objects.count(), before)

    def test_live_after_dry_run_can_send(self):
        rule = self._activate_rule('pending_recovery')
        self._pending_order(self.user, hours_ago=5)
        ex_dry = run_rule(rule, dry_run=True, force=True)
        self.assertIsNotNone(ex_dry)
        with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
            mock_send.return_value = (True, type('L', (), {'pk': 9, 'error_message': ''})())
            ex_live = run_rule(rule, dry_run=False, force=True)
        self.assertIsNotNone(ex_live)
        self.assertTrue(
            ManagementAutomationRecipient.objects.filter(
                rule=rule,
                status=ManagementAutomationRecipient.Status.SENT,
            ).exists()
        )


@override_settings(TIME_ZONE='Asia/Tehran')
class ManagementAutomationHistoryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff_h', password='x', phone='09120000299', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)
        ensure_automation_rules()

    def test_history_tab_shows_executions(self):
        rule = ManagementAutomationRule.objects.first()
        ManagementAutomationExecution.objects.create(
            rule=rule,
            status=ManagementAutomationExecution.Status.COMPLETED,
            matched_count=5,
            success_count=3,
            skipped_count=2,
        )
        resp = self.client.get(reverse('admin_panel_assistant') + '?tab=history')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Match')

    def test_non_staff_history_denied(self):
        user = User.objects.create_user(username='nstaff', password='x', phone='09120000300')
        c = Client()
        c.force_login(user)
        resp = c.get(reverse('admin_panel_assistant') + '?tab=history')
        self.assertEqual(resp.status_code, 403)
