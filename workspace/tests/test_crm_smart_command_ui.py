"""Contextual smart command UI — templates and profiles."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from workspace.services.crm_smart_command import SMART_COMMAND_PROFILES, inject_smart_command_context

User = get_user_model()


def _ai_patches():
    return (
        patch('ai_workspace.constants.is_ai_enabled', return_value=True),
        patch('ai_workspace.constants.is_feature_enabled', return_value=True),
    )


@override_settings(AI_ENABLED=True)
class SmartCommandProfileTests(TestCase):
    def test_profiles_have_allowed_intents(self):
        self.assertEqual(SMART_COMMAND_PROFILES['today']['allowed_intent'], 'create_reminder')
        self.assertEqual(SMART_COMMAND_PROFILES['contacts']['allowed_intent'], 'create_contact')
        self.assertEqual(
            SMART_COMMAND_PROFILES['properties']['allowed_intent'],
            'create_personal_property',
        )

    def test_inject_disabled_when_ai_off(self):
        ctx = {}
        user = User.objects.create_user(username='sc_u', password='x')
        with patch('ai_workspace.constants.is_ai_enabled', return_value=False):
            inject_smart_command_context(ctx, type('R', (), {'user': user})(), 'contacts')
        self.assertFalse(ctx['smart_command']['enabled'])


@override_settings(AI_ENABLED=True)
class SmartCommandTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sc_tpl', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _get(self, url_name: str):
        p_ai, p_feat = _ai_patches()
        with p_ai, p_feat:
            return self.client.get(reverse(url_name))

    def _render_contacts(self):
        return self._get('workspace:crm_contacts')

    def _render_properties(self):
        return self._get('workspace:crm_properties')

    def _render_today(self):
        return self._get('workspace:crm_today')

    def test_contacts_page_has_contact_composer(self):
        res = self._render_contacts()
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('data-allowed-intent="create_contact"', html)
        self.assertIn('ثبت سریع مخاطب', html)
        self.assertIn('crm-smart-command.js', html)
        self.assertIn('crm-smart-command-voice.js', html)
        self.assertIn('data-sc="voice-btn"', html)
        self.assertIn('aria-label="شروع فرمان صوتی"', html)
        self.assertIn('data-sc="voice-icon-stop"', html)

    def test_properties_page_has_property_composer(self):
        res = self._render_properties()
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('data-allowed-intent="create_personal_property"', html)
        self.assertIn('ثبت سریع فایل', html)

    def test_today_page_has_reminder_composer(self):
        res = self._render_today()
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('data-allowed-intent="create_reminder"', html)
        self.assertIn('ثبت سریع یادآوری', html)
        self.assertNotIn('data-allowed-intent="create_contact"', html)

    def test_preview_markup_split_by_intent(self):
        res = self._render_contacts()
        html = res.content.decode()
        self.assertIn('data-sc="preview-contact"', html)
        self.assertIn('data-sc="contact-sections"', html)
        self.assertIn('data-sc="preview-reminder"', html)
        self.assertIn('data-sc="preview-property"', html)
        self.assertNotIn('crm-nl-command__sheet-reminder', html)
        self.assertNotIn('crm-nl-command__sheet-contact', html)
        self.assertNotIn('data-field="contact_name">—', html)
