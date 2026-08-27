"""تست دستیار مدیریت — Rule Engine، UI و API."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ManagementAutomationRule
from accounts.services.admin_management_assistant import (
    AUTOMATION_RULE_CATALOG,
    build_management_insights,
    ensure_automation_rules,
    get_assistant_preview,
    get_management_assistant_context,
    toggle_automation_rule,
)
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class ManagementAssistantServiceTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff1', password='x', phone='09120000101', is_staff=True,
        )
        self.user = User.objects.create_user(
            username='u1', password='x', phone='09120000102',
        )

    def test_build_insights_structure(self):
        insights = build_management_insights()
        self.assertIsInstance(insights, list)
        for ins in insights:
            self.assertTrue(ins.title)
            self.assertTrue(ins.what_happened)
            self.assertTrue(ins.importance)
            self.assertTrue(ins.recommendation)
            self.assertIn(ins.severity, ('critical', 'high', 'medium', 'opportunity'))

    def test_pending_orders_insight(self):
        product = Product.objects.create(title='P', slug='maa-p', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000,
            duration_days=30, is_active=True,
        )
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status=PENDING_ORDER_STATUSES[0],
        )
        keys = [i.key for i in build_management_insights()]
        self.assertIn('pending_orders', keys)

    def test_ensure_automation_rules(self):
        ensure_automation_rules()
        self.assertEqual(
            ManagementAutomationRule.objects.count(),
            len(AUTOMATION_RULE_CATALOG),
        )

    def test_toggle_automation(self):
        ensure_automation_rules()
        key = AUTOMATION_RULE_CATALOG[0]['key']
        result = toggle_automation_rule(rule_key=key, active=True, user=self.staff)
        self.assertTrue(result['ok'])
        rule = ManagementAutomationRule.objects.get(key=key)
        self.assertTrue(rule.is_active)

    def test_assistant_preview(self):
        preview = get_assistant_preview()
        self.assertIn('total', preview)
        self.assertIn('top_insights', preview)

    def test_context_tabs(self):
        ctx = get_management_assistant_context(tab='automations')
        self.assertEqual(ctx['tab'], 'automations')
        self.assertTrue(ctx['automation_rules'])


@override_settings(TIME_ZONE='Asia/Tehran')
class ManagementAssistantViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff2', password='x', phone='09120000103', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_page_loads(self):
        url = reverse('admin_panel_assistant')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'دستیار مدیریت')
        self.assertContains(resp, 'پیشنهادها')

    def test_nav_active(self):
        self.assertEqual(
            resolve_admin_panel_nav_active('/accounts/admin-panel/assistant/'),
            'assistant',
        )

    def test_preview_json(self):
        url = reverse('admin_panel_assistant_preview')
        resp = self.client.get(url, {'insight': 'pending_orders'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('ok', data)

    def test_automation_toggle_json(self):
        ensure_automation_rules()
        url = reverse('admin_panel_assistant_automation')
        resp = self.client.post(
            url,
            data='{"rule_key": "license_expiring_3d", "active": true}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_non_staff_denied(self):
        user = User.objects.create_user(username='norm', password='x', phone='09120000104')
        c = Client()
        c.force_login(user)
        resp = c.get(reverse('admin_panel_assistant'))
        self.assertEqual(resp.status_code, 403)

    def test_command_center_preview(self):
        resp = self.client.get(reverse('admin_panel'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'دستیار مدیریت')
