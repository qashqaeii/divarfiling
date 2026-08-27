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
    get_automation_rule_detail,
    get_management_assistant_context,
    preview_automation_rule,
    preview_insight_recipients,
    preview_rule_message,
    toggle_automation_rule,
    update_automation_rule_settings,
)
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from licenses.models import License
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

    def test_preview_license_expiring_recipients(self):
        product = Product.objects.create(title='P', slug='maa-lic', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='ماهانه', plan_type='monthly', price=100000,
            duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status='paid',
        )
        License.objects.create(
            order=order,
            plan=plan,
            status='active',
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )
        data = preview_insight_recipients('license_expiring_3d')
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['count'], 1)
        self.assertTrue(data['recipients'])
        self.assertIn('display', data['recipients'][0])

    def test_context_tabs(self):
        ctx = get_management_assistant_context(tab='automations')
        self.assertEqual(ctx['tab'], 'automations')
        self.assertTrue(ctx['automation_rules'])

    def test_preview_automation_rule(self):
        product = Product.objects.create(title='P', slug='maa-auto', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='ماهانه', plan_type='monthly', price=100000,
            duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status='paid',
        )
        License.objects.create(
            order=order,
            plan=plan,
            status='active',
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )
        ensure_automation_rules()
        data = preview_automation_rule('license_expiring_3d')
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['count'], 1)
        self.assertIn('ready_count', data)
        self.assertTrue(data['recipients'])
        self.assertIn('status', data['recipients'][0])

    def test_automation_rule_detail(self):
        ensure_automation_rules()
        data = get_automation_rule_detail('license_expiring_3d')
        self.assertTrue(data['ok'])
        self.assertIn('rule', data)
        self.assertIn('stats_30d', data)
        self.assertIn('audience', data)
        self.assertIn('sample_message', data)

    def test_insight_automation_active_note(self):
        ensure_automation_rules()
        toggle_automation_rule(
            rule_key='license_expiring_3d',
            active=True,
            user=self.staff,
        )
        product = Product.objects.create(title='P', slug='maa-ins', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000,
            duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status='paid',
        )
        License.objects.create(
            order=order,
            plan=plan,
            status='active',
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )
        ctx = get_management_assistant_context(tab='suggestions')
        expiring = next(i for i in ctx['insights'] if i['key'] == 'license_expiring_3d')
        self.assertTrue(expiring['automation_active'])
        self.assertIn('اتوماسیون', expiring['recommendation'])

    def test_update_automation_settings(self):
        ensure_automation_rules()
        result = update_automation_rule_settings(
            rule_key='license_expiring_3d',
            cooldown_days=5,
            max_recipients_per_run=40,
            cadence='hourly',
            quiet_hours_start=23,
            quiet_hours_end=8,
        )
        self.assertTrue(result['ok'])
        rule = ManagementAutomationRule.objects.get(key='license_expiring_3d')
        self.assertEqual(rule.cooldown_days, 5)
        self.assertEqual(rule.max_recipients_per_run, 40)
        self.assertEqual(rule.cadence, 'hourly')

    def test_update_message_template_and_reset(self):
        ensure_automation_rules()
        custom = 'سلام{name_part}، پیام تست: {link}'
        result = update_automation_rule_settings(
            rule_key='license_expiring_3d',
            message_template=custom,
        )
        self.assertTrue(result['ok'])
        rule = ManagementAutomationRule.objects.get(key='license_expiring_3d')
        self.assertEqual(rule.message_template, custom)

        preview = preview_rule_message('license_expiring_3d', message_template=custom)
        self.assertTrue(preview['ok'])
        self.assertIn('پیام تست', preview['sample_message'])

        reset = update_automation_rule_settings(
            rule_key='license_expiring_3d',
            reset_template=True,
        )
        self.assertTrue(reset['ok'])
        rule.refresh_from_db()
        self.assertEqual(rule.message_template, '')


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

    def test_automation_detail_json(self):
        ensure_automation_rules()
        url = reverse('admin_panel_assistant_automation_detail')
        resp = self.client.get(url, {'rule_key': 'license_expiring_3d'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('audience', data)

    def test_automation_preview_json(self):
        ensure_automation_rules()
        url = reverse('admin_panel_assistant_automation_preview')
        resp = self.client.get(url, {'rule_key': 'license_expiring_3d'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('ok', resp.json())

    def test_automation_settings_json(self):
        ensure_automation_rules()
        url = reverse('admin_panel_assistant_automation_settings')
        resp = self.client.post(
            url,
            data='{"rule_key":"license_expiring_3d","confirm_save":"1","cooldown_days":6}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_automation_message_preview_json(self):
        ensure_automation_rules()
        url = reverse('admin_panel_assistant_automation_message_preview')
        resp = self.client.get(url, {'rule_key': 'license_expiring_3d'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['sample_message'])

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
        self.assertContains(resp, 'ecc-cmd-assistant-card')
        self.assertEqual(resp.content.decode().count('ecc-section ecc-cmd-assistant'), 1)
