"""تست Variable Registry و Message Template Editor."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ManagementAutomationRule
from accounts.services.admin_management_assistant import (
    ensure_automation_rules,
    preview_rule_message,
    send_automation_test_message,
    update_automation_rule_settings,
)
from accounts.services.automation_message_templates import (
    RULE_DEFAULT_TEMPLATES,
    build_sample_context,
    parse_template_variables,
    render_template,
    safe_render,
    validate_template,
    variables_for_rule,
)
from accounts.services.management_automation_runner import run_rule
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from licenses.models import License
from shop.models import LicensePlan, Order, Product

User = get_user_model()


class AutomationMessageTemplateRegistryTests(TestCase):
    def test_parse_variables(self):
        used = parse_template_variables('سلام {name_part} — {link}')
        self.assertEqual(used, ['name_part', 'link'])

    def test_unknown_variable_rejected(self):
        result = validate_template('سلام {unknown_var}', 'license_expiring_3d')
        self.assertFalse(result.ok)
        self.assertIn('unknown_var', result.error)

    def test_rule_specific_variable_rejected(self):
        result = validate_template('سلام {academy_link}', 'license_expiring_3d')
        self.assertFalse(result.ok)
        self.assertIn('academy_link', result.error)

    def test_valid_template_for_rule(self):
        tpl = RULE_DEFAULT_TEMPLATES['license_expiring_3d']
        result = validate_template(tpl, 'license_expiring_3d')
        self.assertTrue(result.ok)
        self.assertIn('name_part', result.variables_used)

    def test_variables_for_rule_context_aware(self):
        keys = {v['key'] for v in variables_for_rule('users_onboarding')}
        self.assertIn('academy_link', keys)
        self.assertNotIn('code', keys)

    def test_safe_render_no_eval(self):
        ctx = build_sample_context('license_expiring_3d')
        ctx['__class__'] = 'bad'
        rendered = safe_render('سلام {name_part}', ctx)
        self.assertIn('علی', rendered)
        self.assertNotIn('bad', rendered)

    def test_optional_missing_code_strict_send(self):
        tpl = 'کد {code} برای {link}'
        result = render_template(
            tpl,
            {'code': '', 'link': 'https://example.com'},
            rule_key='pending_recovery',
            strict_send=True,
        )
        self.assertFalse(result.ok)
        self.assertIn('code', result.missing_variables)

    def test_optional_missing_code_preview_warns(self):
        tpl = 'کد {code} برای {link}'
        result = render_template(
            tpl,
            {'code': '', 'link': 'https://example.com'},
            rule_key='pending_recovery',
            strict_send=False,
        )
        self.assertTrue(result.ok)
        self.assertTrue(any('code' in w for w in result.warnings))

    def test_persian_unicode_render(self):
        ctx = build_sample_context('license_expiring_3d')
        rendered = safe_render(RULE_DEFAULT_TEMPLATES['license_expiring_3d'], ctx)
        self.assertIn('👋', rendered)
        self.assertIn('روز', rendered)


@override_settings(TIME_ZONE='Asia/Tehran', SMS_PROVIDER='console')
class AutomationMessagePersistenceTests(TestCase):
    def setUp(self):
        ensure_automation_rules()
        self.staff = User.objects.create_user(
            username='tpl_staff', password='x', phone='09120001001', is_staff=True,
        )

    def test_save_valid_custom_template(self):
        custom = 'سلام{name_part} — {days_left} روز · {link}'
        result = update_automation_rule_settings(
            rule_key='license_expiring_3d',
            message_template=custom,
            updated_by=self.staff,
        )
        self.assertTrue(result['ok'])
        rule = ManagementAutomationRule.objects.get(key='license_expiring_3d')
        self.assertEqual(rule.message_template, custom)
        self.assertIsNotNone(rule.message_template_updated_at)
        self.assertEqual(rule.message_template_updated_by_id, self.staff.pk)

    def test_save_unknown_variable_rejected(self):
        result = update_automation_rule_settings(
            rule_key='license_expiring_3d',
            message_template='سلام {evil_var}',
            updated_by=self.staff,
        )
        self.assertFalse(result['ok'])

    def test_reset_to_default(self):
        update_automation_rule_settings(
            rule_key='license_expiring_3d',
            message_template='سلام {name_part} {link}',
            updated_by=self.staff,
        )
        reset = update_automation_rule_settings(
            rule_key='license_expiring_3d',
            reset_template=True,
            updated_by=self.staff,
        )
        self.assertTrue(reset['ok'])
        rule = ManagementAutomationRule.objects.get(key='license_expiring_3d')
        self.assertEqual(rule.message_template, '')

    def test_preview_sample_and_recipient(self):
        preview = preview_rule_message('license_expiring_3d', mode='sample')
        self.assertTrue(preview['ok'])
        self.assertTrue(preview['sample_message'])

    def test_test_send_staff_only_and_logged(self):
        with patch('accounts.services.notifications.notify_marketing', return_value=(True, type('L', (), {'pk': 1})())) as mock_send:
            result = send_automation_test_message(
                rule_key='license_expiring_3d',
                user=self.staff,
                message_template=RULE_DEFAULT_TEMPLATES['license_expiring_3d'],
            )
        self.assertTrue(result['ok'])
        self.assertTrue(result.get('test_send'))
        mock_send.assert_called_once()


@override_settings(TIME_ZONE='Asia/Tehran', SMS_PROVIDER='console')
class AutomationMessageRuntimeTests(TestCase):
    def setUp(self):
        ensure_automation_rules()
        self.user = User.objects.create_user(
            username='tpl_u1', password='x', phone='09120001002',
        )
        self.product = Product.objects.create(title='P', slug='tpl-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product, name='ماهانه', plan_type='monthly', price=100000,
            duration_days=30, is_active=True,
        )

    def _activate(self, key):
        rule = ManagementAutomationRule.objects.get(key=key)
        rule.is_active = True
        rule.is_paused = False
        return rule

    def test_runtime_uses_custom_template(self):
        rule = self._activate('license_expiring_3d')
        custom = 'سلام{name_part} تست سفارشی {link}'
        rule.message_template = custom
        rule.save(update_fields=['message_template'])

        order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=100000, status='paid',
        )
        License.objects.create(
            order=order, plan=self.plan, status='active',
            expires_at=timezone.now() + timedelta(days=2),
        )

        with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
            mock_send.return_value = (True, type('L', (), {'pk': 1})())
            ex = run_rule(rule, dry_run=False, force=True)
        self.assertIsNotNone(ex)
        self.assertTrue(mock_send.called)
        sent_text = mock_send.call_args.kwargs.get('text') or mock_send.call_args[0][1]
        self.assertIn('تست سفارشی', sent_text)

    def test_invalid_template_blocks_real_sms(self):
        rule = self._activate('pending_recovery')
        rule.message_template = 'سلام {bad_variable}'
        rule.save(update_fields=['message_template'])

        order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=100000, status=PENDING_ORDER_STATUSES[0],
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=5),
        )

        with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
            ex = run_rule(rule, dry_run=False, force=True)
        self.assertIsNotNone(ex)
        mock_send.assert_not_called()
        ex.refresh_from_db()
        self.assertEqual(ex.status, 'failed')

    def test_missing_code_skips_recipient_not_corrupt_sms(self):
        rule = self._activate('pending_recovery')
        rule.message_template = 'سلام{name_part} کد {code} · {link}'
        rule.save(update_fields=['message_template'])

        order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=100000, status=PENDING_ORDER_STATUSES[0],
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=5),
        )

        with patch('accounts.services.management_automation_runner.notify_marketing') as mock_send:
            ex = run_rule(rule, dry_run=False, force=True)
        mock_send.assert_not_called()
        self.assertGreaterEqual(ex.skipped_count, 1)


@override_settings(TIME_ZONE='Asia/Tehran')
class AutomationMessageViewTests(TestCase):
    def setUp(self):
        ensure_automation_rules()
        self.staff = User.objects.create_user(
            username='tpl_staff2', password='x', phone='09120001003', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_message_preview_json_modes(self):
        url = reverse('admin_panel_assistant_automation_message_preview')
        resp = self.client.get(url, {
            'rule_key': 'license_expiring_3d',
            'mode': 'sample',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('sms_info', data)

    def test_save_message_rejects_invalid_template(self):
        url = reverse('admin_panel_assistant_automation_settings')
        resp = self.client.post(
            url,
            data=json.dumps({
                'rule_key': 'license_expiring_3d',
                'confirm_save': '1',
                'message_template': 'سلام {not_allowed}',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])

    def test_non_staff_denied_preview(self):
        user = User.objects.create_user(username='tpl_norm', password='x', phone='09120001004')
        c = Client()
        c.force_login(user)
        url = reverse('admin_panel_assistant_automation_message_preview')
        resp = c.get(url, {'rule_key': 'license_expiring_3d'})
        self.assertEqual(resp.status_code, 403)

    def test_detail_includes_allowed_variables(self):
        url = reverse('admin_panel_assistant_automation_detail')
        resp = self.client.get(url, {'rule_key': 'license_expiring_3d'})
        self.assertEqual(resp.status_code, 200)
        rule = resp.json()['rule']
        self.assertIn('allowed_variables', rule)
        self.assertIn('template_valid', rule)
