"""Unknown / out-of-scope handling — M1 UX contract."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ai_workspace.constants import (
    NL_COMMAND_EXAMPLE_PHRASES,
    NL_COMMAND_PARSE_FAILED_MESSAGE,
    NL_COMMAND_UNKNOWN_MESSAGE,
)
from ai_workspace.providers.base import ProviderResult
from ai_workspace.services.nl_command.service import NLCommandError, parse_command
from ai_workspace.services.nl_command.state import load_state
from workspace.models import Reminder

User = get_user_model()


def _unknown_json():
    return json.dumps({
        'intent': 'unknown',
        'confidence': 0.95,
        'data': {
            'contact_name': None,
            'title': None,
            'note': None,
            'date_text': None,
            'time_text': None,
        },
        'missing_fields': [],
        'ambiguous_fields': [],
        'requires_confirmation': False,
    }, ensure_ascii=False)


def _patch_unknown_chain():
    provider = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock()
    provider.complete.return_value = ProviderResult(
        text=_unknown_json(),
        provider='arvan',
        model='Gemini-2.5-Flash-lite',
        input_tokens=5,
        output_tokens=8,
        latency_ms=50,
        is_fallback=False,
    )
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])


@override_settings(AI_ENABLED=True)
class NLCommandUnknownBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='unk_u', password='x', is_staff=True)
        cache.clear()

    @_patch_unknown_chain()
    def test_unknown_response_contract(self, _chain):
        result = parse_command(self.user, text='امروز چند شنبه است؟')
        self.assertTrue(result['ok'])
        self.assertEqual(result['intent'], 'unknown')
        self.assertFalse(result['can_confirm'])
        self.assertIsNone(result['command_id'])
        self.assertIsNone(result['preview'])
        self.assertEqual(result['message'], NL_COMMAND_UNKNOWN_MESSAGE)
        self.assertEqual(result['examples'], list(NL_COMMAND_EXAMPLE_PHRASES))
        self.assertIn('ai', result)

    @_patch_unknown_chain()
    def test_unknown_no_command_state(self, _chain):
        parse_command(self.user, text='یه جوک بگو')
        self.assertIsNone(load_state(self.user.pk, 'nonexistent-id'))

    @_patch_unknown_chain()
    def test_unknown_no_reminder_mutation(self, _chain):
        parse_command(self.user, text='امروز چند شنبه است؟')
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 0)

    @_patch_unknown_chain()
    def test_unsupported_phrases(self, _chain):
        for text in (
            'امروز چند شنبه است؟',
            'یه جوک تعریف کن',
            'یه فایل تو پونک ثبت کن',
            'قیمت دلار چنده؟',
        ):
            result = parse_command(self.user, text=text)
            self.assertEqual(result['intent'], 'unknown')
            self.assertFalse(result['can_confirm'])
            self.assertIsNone(result['command_id'])


@override_settings(AI_ENABLED=True)
class NLCommandUnknownViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='unk_v', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.user)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @_patch_unknown_chain()
    def test_parse_endpoint_unknown_json(self, _chain, _lic):
        url = reverse('workspace:ai_workspace:nl_parse')
        resp = self.client.post(
            url,
            data=json.dumps({'text': 'امروز چند شنبه است؟'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['intent'], 'unknown')
        self.assertEqual(body['message'], NL_COMMAND_UNKNOWN_MESSAGE)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_parse_failed_message(self, _lic):
        with patch(
            'ai_workspace.services.nl_command.service.gateway_run',
            side_effect=NLCommandError(
                NL_COMMAND_PARSE_FAILED_MESSAGE,
                code='parse_failed',
                status=503,
            ),
        ):
            url = reverse('workspace:ai_workspace:nl_parse')
            resp = self.client.post(
                url,
                data=json.dumps({'text': '???'}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()['code'], 'parse_failed')
        self.assertIn('قابل تشخیص', resp.json()['error'])
