"""تست Gateway — سناریوهای پایه با زنجیره Arvan-first."""
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

_MOCK_SUMMARY_JSON = (
    '{"summary":"خلاصه تست آگهی برای واحد نمونه در محله","highlights":[],'
    '"negotiation_tip":"","advertiser_note":""}'
)


def _patch_chain(chain):
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain)


def _make_chain_mock(*, arvan_ok=True, openrouter_ok=False, gemini_primary_ok=False, gemini_lite_ok=False):
    arvan, openrouter, primary, lite = MagicMock(), MagicMock(), MagicMock(), MagicMock()

    if arvan_ok:
        arvan.complete.return_value = ProviderResult(
            text=_MOCK_SUMMARY_JSON,
            provider='arvan',
            model='Gemini-2.5-Flash-lite',
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
            is_fallback=False,
        )
    else:
        arvan.complete.side_effect = ProviderError('429', retryable=True, code='429')

    if openrouter_ok:
        openrouter.complete.return_value = ProviderResult(
            text=_MOCK_SUMMARY_JSON,
            provider='openrouter',
            model='openai/gpt-oss-20b:free',
            input_tokens=10,
            output_tokens=5,
            latency_ms=200,
            is_fallback=True,
        )
    else:
        openrouter.complete.side_effect = ProviderError('429', retryable=True, code='429')

    if gemini_primary_ok:
        primary.complete.return_value = ProviderResult(
            text=_MOCK_SUMMARY_JSON,
            provider='gemini',
            model='gemini-3.1-flash-lite',
            input_tokens=10,
            output_tokens=5,
            latency_ms=80,
        )
    else:
        primary.complete.side_effect = ProviderError('429', retryable=True, code='429')

    if gemini_lite_ok:
        lite.complete.return_value = ProviderResult(
            text=_MOCK_SUMMARY_JSON,
            provider='gemini',
            model='gemini-2.5-flash-lite',
            input_tokens=10,
            output_tokens=5,
            latency_ms=80,
            is_fallback=True,
        )
    else:
        lite.complete.side_effect = ProviderError('429', retryable=True, code='429')

    return [arvan, openrouter, primary, lite]


@override_settings(AI_ENABLED=True, GEMINI_API_KEY='test')
class GatewayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff_ai', password='x', is_staff=True, phone='09120000003',
        )

    def test_arvan_success_skips_fallbacks(self):
        chain = _make_chain_mock(arvan_ok=True)
        with _patch_chain(chain):
            result = run(
                'listing_summary',
                self.user,
                context={**_LISTING_CTX, 'content_version': '1'},
                entity_type='listing',
                entity_id='1',
            )
            chain[1].complete.assert_not_called()
            chain[2].complete.assert_not_called()
            chain[3].complete.assert_not_called()
        self.assertEqual(result.provider, 'arvan')

    def test_arvan_fail_uses_openrouter(self):
        chain = _make_chain_mock(arvan_ok=False, openrouter_ok=True)
        with _patch_chain(chain):
            result = run(
                'listing_summary',
                self.user,
                context={**_LISTING_CTX, 'content_version': '2'},
                entity_type='listing',
                entity_id='2',
            )
        self.assertEqual(result.provider, 'openrouter')

    def test_all_fail_uses_rule_based(self):
        chain = _make_chain_mock(arvan_ok=False, openrouter_ok=False)
        with _patch_chain(chain):
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

    def test_arvan_fail_openrouter_fail_gemini_lite_succeeds(self):
        chain = _make_chain_mock(
            arvan_ok=False, openrouter_ok=False, gemini_primary_ok=False, gemini_lite_ok=True,
        )
        with _patch_chain(chain):
            result = run(
                'listing_summary',
                self.user,
                context={**_LISTING_CTX, 'content_version': '4'},
                entity_type='listing',
                entity_id='4',
            )
        self.assertEqual(result.model, 'gemini-2.5-flash-lite')
        chain[3].complete.assert_called_once()

    def test_malformed_llm_json_uses_rule_based(self):
        chain = _make_chain_mock(arvan_ok=True)
        chain[0].complete.return_value = ProviderResult(
            text='not-json',
            provider='arvan',
            model='Gemini-2.5-Flash-lite',
            input_tokens=10,
            output_tokens=5,
            latency_ms=200,
            is_fallback=False,
        )
        with _patch_chain(chain):
            result = run(
                'listing_summary',
                self.user,
                context={
                    **_LISTING_CTX,
                    'content_version': '7',
                    'benchmark_verdict': 'زیر میانه',
                },
                entity_type='listing',
                entity_id='7',
            )
        self.assertEqual(result.provider, 'rule_based')

    def test_validation_skip_never_calls_providers(self):
        chain = _make_chain_mock(arvan_ok=True)
        with _patch_chain(chain):
            result = run(
                'listing_summary',
                self.user,
                context={'title': 'بدون قیمت', 'content_version': '5'},
                entity_type='listing',
                entity_id='5',
            )
        self.assertEqual(result.provider, 'rule_based')
        chain[0].complete.assert_not_called()
