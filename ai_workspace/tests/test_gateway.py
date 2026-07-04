"""تست Gateway و Provider chain."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.providers.base import ProviderError, ProviderResult
from ai_workspace.services.gateway import run

User = get_user_model()

_LISTING_CTX = {
    'title': 'آپارتمان',
    'price_label': '۱۲ میلیارد تومان',
}


def _make_chain_mock(*, primary_ok=True, secondary_ok=False, openrouter_ok=False):
    primary = MagicMock()
    lite = MagicMock()
    openrouter = MagicMock()

    if primary_ok:
        primary.complete.return_value = ProviderResult(
            text='{"summary":"ok","highlights":[],"negotiation_tip":"","advertiser_note":""}',
            provider='gemini',
            model='gemini-3.1-flash-lite',
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
        )
    else:
        primary.complete.side_effect = ProviderError('429', retryable=True, code='429')

    if secondary_ok:
        lite.complete.return_value = ProviderResult(
            text='{"summary":"lite","highlights":[],"negotiation_tip":"","advertiser_note":""}',
            provider='gemini',
            model='gemini-2.5-flash-lite',
            input_tokens=10,
            output_tokens=5,
            latency_ms=80,
            is_fallback=True,
        )
    else:
        lite.complete.side_effect = ProviderError('429', retryable=True, code='429')

    if openrouter_ok:
        openrouter.complete.return_value = ProviderResult(
            text='{"summary":"backup","highlights":[],"negotiation_tip":"","advertiser_note":""}',
            provider='openrouter',
            model='openai/gpt-oss-20b:free',
            input_tokens=10,
            output_tokens=5,
            latency_ms=200,
            is_fallback=True,
        )
    else:
        openrouter.complete.side_effect = ProviderError('429', retryable=True, code='429')

    return [primary, lite, openrouter]


@override_settings(AI_ENABLED=True, GEMINI_API_KEY='test', OPENROUTER_API_KEY='')
class GatewayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff_ai', password='x', is_staff=True, phone='09120000003',
        )

    def test_gemini_success_skips_fallbacks(self):
        chain = _make_chain_mock(primary_ok=True)
        with patch('ai_workspace.services.gateway.HTTP_PROVIDER_CHAIN', chain):
            result = run(
                'listing_summary',
                self.user,
                context={**_LISTING_CTX, 'content_version': '1'},
                entity_type='listing',
                entity_id='1',
            )
            chain[1].complete.assert_not_called()
            chain[2].complete.assert_not_called()
        self.assertEqual(result.provider, 'gemini')

    def test_gemini_fail_uses_openrouter(self):
        chain = _make_chain_mock(primary_ok=False, secondary_ok=False, openrouter_ok=True)
        with patch('ai_workspace.services.gateway.HTTP_PROVIDER_CHAIN', chain):
            result = run(
                'listing_summary',
                self.user,
                context={**_LISTING_CTX, 'content_version': '2'},
                entity_type='listing',
                entity_id='2',
            )
        self.assertEqual(result.provider, 'openrouter')

    def test_all_fail_uses_rule_based(self):
        chain = _make_chain_mock(primary_ok=False, secondary_ok=False, openrouter_ok=False)
        with patch('ai_workspace.services.gateway.HTTP_PROVIDER_CHAIN', chain):
            result = run(
                'listing_summary',
                self.user,
                context={
                    **_LISTING_CTX,
                    'content_version': '3',
                    'benchmark_verdict': 'زیر میانه',
                },
                entity_type='listing',
                entity_id='3',
            )
        self.assertEqual(result.provider, 'rule_based')
        self.assertTrue(result.is_fallback)

    def test_primary_fail_lite_succeeds(self):
        chain = _make_chain_mock(primary_ok=False, secondary_ok=True, openrouter_ok=False)
        with patch('ai_workspace.services.gateway.HTTP_PROVIDER_CHAIN', chain):
            result = run(
                'listing_summary',
                self.user,
                context={**_LISTING_CTX, 'content_version': '4'},
                entity_type='listing',
                entity_id='4',
            )
        self.assertEqual(result.model, 'gemini-2.5-flash-lite')
        chain[2].complete.assert_not_called()

    def test_validation_skip_never_calls_providers(self):
        chain = _make_chain_mock(primary_ok=True)
        with patch('ai_workspace.services.gateway.HTTP_PROVIDER_CHAIN', chain):
            result = run(
                'listing_summary',
                self.user,
                context={'title': 'بدون قیمت', 'content_version': '5'},
                entity_type='listing',
                entity_id='5',
            )
        self.assertEqual(result.provider, 'rule_based')
        chain[0].complete.assert_not_called()
