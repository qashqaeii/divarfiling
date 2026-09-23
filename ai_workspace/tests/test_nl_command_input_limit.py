"""nl_command input length limits."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.constants import MAX_NL_COMMAND_CHARS, NL_COMMAND_INPUT_TOO_LONG_MESSAGE
from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.service import parse_command
from ai_workspace.services.quota import get_or_create_quota

from ai_workspace.tests.test_nl_command import _patch_chain_ok

User = get_user_model()


def _text(length: int) -> str:
    return 'ف' * length


@override_settings(AI_ENABLED=True)
class NLCommandInputLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='nl_len', password='x', is_staff=True)

    @_patch_chain_ok()
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_1499_chars_accepted(self, _lic, _chain):
        result = parse_command(self.user, text=_text(1499))
        self.assertEqual(result['intent'], 'create_reminder')

    @_patch_chain_ok()
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_1500_chars_accepted(self, _lic, _chain):
        result = parse_command(self.user, text=_text(1500))
        self.assertEqual(result['intent'], 'create_reminder')

    @patch('ai_workspace.services.nl_command.service.gateway_run')
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_1501_chars_rejected(self, _lic, gateway_run):
        quota = get_or_create_quota(self.user)
        used_before = quota.nl_command_used

        with self.assertRaises(NLCommandError) as ctx:
            parse_command(self.user, text=_text(1501))

        exc = ctx.exception
        self.assertEqual(exc.code, 'input_too_long')
        self.assertEqual(exc.error_code, 'input_too_long')
        self.assertEqual(str(exc), NL_COMMAND_INPUT_TOO_LONG_MESSAGE)
        gateway_run.assert_not_called()

        quota.refresh_from_db()
        self.assertEqual(quota.nl_command_used, used_before)

    def test_max_constant(self):
        self.assertEqual(MAX_NL_COMMAND_CHARS, 1500)
