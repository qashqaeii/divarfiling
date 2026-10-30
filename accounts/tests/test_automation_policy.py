"""تست سیاست تماس و attribution."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import (
    ManagementAutomationExecution,
    ManagementAutomationRecipient,
    ManagementAutomationRule,
)
from accounts.services.automation_contact_policy import check_global_contact_policy
from accounts.services.automation_conversion import record_order_conversion
from accounts.services.admin_management_assistant import ensure_automation_rules
from shop.models import LicensePlan, Order, Product

User = get_user_model()


class AutomationPolicyTests(TestCase):
    def setUp(self):
        ensure_automation_rules()
        self.user = User.objects.create_user(username='pol1', password='x', phone='09120002001')
        self.rule_a = ManagementAutomationRule.objects.get(key='pending_recovery')
        self.rule_b = ManagementAutomationRule.objects.get(key='crm_abandoned_nudge')

    def test_global_cooldown_blocks_second_rule_within_72h(self):
        ex = ManagementAutomationExecution.objects.create(
            rule=self.rule_a, dry_run=False, status=ManagementAutomationExecution.Status.COMPLETED,
        )
        ManagementAutomationRecipient.objects.create(
            execution=ex,
            rule=self.rule_a,
            user=self.user,
            trigger_key='t1',
            status=ManagementAutomationRecipient.Status.SENT,
            sent_at=timezone.now() - timedelta(hours=1),
        )
        allowed, reason = check_global_contact_policy(self.rule_b, user_id=self.user.pk)
        self.assertFalse(allowed)
        self.assertEqual(reason, 'global_cooldown')

    def test_order_conversion_idempotent(self):
        product = Product.objects.create(title='P', slug='pol-p', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='m', plan_type='monthly', price=100_000,
            duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user, product=product, plan=plan, amount=90_000, status='paid',
            paid_at=timezone.now(),
        )
        ex = ManagementAutomationExecution.objects.create(
            rule=self.rule_a, dry_run=False, status=ManagementAutomationExecution.Status.COMPLETED,
        )
        ManagementAutomationRecipient.objects.create(
            execution=ex,
            rule=self.rule_a,
            user=self.user,
            trigger_key='t2',
            status=ManagementAutomationRecipient.Status.SENT,
            sent_at=timezone.now() - timedelta(hours=2),
        )
        self.assertEqual(record_order_conversion(order), 1)
        self.assertEqual(record_order_conversion(order), 0)
