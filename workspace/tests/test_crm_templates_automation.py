"""تست‌های هدفمند قالب پیام و اتوماسیون CRM."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMAutomationRule, CRMMessageTemplate

User = get_user_model()


class CRMMessageTemplateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121110001', phone='09121110001', password='pass12345')
        self.other = User.objects.create_user(username='09121110002', phone='09121110002', password='pass12345')
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse('workspace:crm_templates')

    def test_save_template_preserves_special_body(self):
        body = (
            'سلام {name} — آژانس «{agency}»\n'
            'خط دوم با "نقل‌قول" و \'گیومه\''
        )
        resp = self.client.post(self.url, {
            'action': 'save',
            'name': 'قالب تست',
            'category': 'پیگیری',
            'channel': 'واتساپ',
            'body': body,
        })
        self.assertEqual(resp.status_code, 302)
        tpl = CRMMessageTemplate.objects.get(user=self.user, name='قالب تست')
        self.assertEqual(tpl.body, body)

    def test_edit_payload_in_page_json(self):
        body = 'متن {name}'
        tpl = CRMMessageTemplate.objects.create(
            user=self.user,
            name='نمونه',
            category='پیگیری',
            channel='پیامک',
            body=body,
            is_system=False,
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="crmTplEditData"', html)
        marker = 'id="crmTplEditData"'
        chunk = html.split(marker, 1)[1]
        raw = chunk.split('>', 1)[1].split('</script>', 1)[0].strip()
        payload = json.loads(raw)
        self.assertEqual(payload[str(tpl.pk)]['body'], body)

    def test_cannot_delete_other_users_template(self):
        foreign = CRMMessageTemplate.objects.create(
            user=self.other,
            name='بیگانه',
            category='پیگیری',
            channel='واتساپ',
            body='x',
            is_system=False,
        )
        resp = self.client.post(self.url, {
            'action': 'delete',
            'template_id': foreign.pk,
        })
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(CRMMessageTemplate.objects.filter(pk=foreign.pk).exists())

    def test_system_template_delete_blocked(self):
        tpl = CRMMessageTemplate.objects.filter(user=self.user, is_system=True).first()
        if not tpl:
            tpl = CRMMessageTemplate.objects.create(
                user=self.user,
                name='سیستمی',
                category='پیگیری',
                channel='واتساپ',
                body='sys',
                is_system=True,
            )
        resp = self.client.post(self.url, {
            'action': 'delete',
            'template_id': tpl.pk,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CRMMessageTemplate.objects.filter(pk=tpl.pk).exists())


class CRMAutomationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121110003', phone='09121110003', password='pass12345')
        self.other = User.objects.create_user(username='09121110004', phone='09121110004', password='pass12345')
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse('workspace:crm_automation')

    def test_automation_page_uses_safe_preview_dom(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('previewEl.replaceChildren()', html)
        self.assertNotIn('previewEl.innerHTML =', html)

    def test_save_rule_does_not_run_automation(self):
        before = CRMAutomationRule.objects.filter(user=self.user).count()
        resp = self.client.post(self.url, {
            'action': 'save',
            'name': 'قانون QA',
            'is_active': 'on',
            'trigger': 'inactive_days',
            'trigger_days': '5',
            'trigger_statuses': 'جدید',
            'action': 'create_reminder',
            'action_reminder_title': 'پیگیری',
            'action_reminder_days': '1',
            'action_status': '',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CRMAutomationRule.objects.filter(user=self.user).count(), before + 1)

    def test_cannot_toggle_other_users_rule(self):
        rule = CRMAutomationRule.objects.create(
            user=self.other,
            name='بیگانه',
            trigger_days=3,
            trigger_statuses='جدید',
            action='create_reminder',
            action_reminder_title='x',
            action_reminder_days=1,
        )
        resp = self.client.post(self.url, {
            'action': 'toggle',
            'rule_id': rule.pk,
        })
        self.assertEqual(resp.status_code, 404)
