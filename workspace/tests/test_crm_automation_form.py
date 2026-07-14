"""تست فرم قوانین اتوماسیون CRM."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CRMAutomationRuleForm

User = get_user_model()


class CRMAutomationRuleFormTests(TestCase):
    def test_action_status_select_renders_status_options(self):
        form = CRMAutomationRuleForm()
        html = str(form['action_status'])
        self.assertEqual(type(form.fields['action_status']).__name__, 'ChoiceField')
        self.assertGreater(html.count('<option'), 1)
        self.assertIn('جدید', html)
        self.assertIn('بایگانی', html)

    def test_set_status_requires_action_status(self):
        form = CRMAutomationRuleForm({
            'name': 'قانون تست',
            'is_active': 'on',
            'trigger': 'inactive_days',
            'trigger_days': '3',
            'trigger_statuses': 'جدید',
            'action': 'set_status',
            'action_status': '',
            'action_reminder_title': '',
            'action_reminder_days': '1',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('action_status', form.errors)
