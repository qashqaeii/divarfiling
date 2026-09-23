"""Registry — production HTTP provider chain."""
from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from ai_workspace.providers.gemini import GeminiProvider
from ai_workspace.providers.openrouter import OpenRouterProvider
from ai_workspace.providers.registry import ARVAN, get_http_provider_chain


class RegistryChainTests(SimpleTestCase):
    def test_openrouter_not_in_active_chain(self):
        chain = get_http_provider_chain()
        self.assertFalse(any(isinstance(p, OpenRouterProvider) for p in chain))

    @override_settings(
        ARVAN_AI_ENABLED=False,
        ARVAN_AI_API_KEY='',
        ARVAN_AI_BASE_URL='',
    )
    def test_arvan_omitted_when_disabled(self):
        chain = get_http_provider_chain()
        self.assertEqual(len(chain), 2)
        self.assertTrue(all(isinstance(p, GeminiProvider) for p in chain))

    @override_settings(
        ARVAN_AI_ENABLED=True,
        ARVAN_AI_API_KEY='k',
        ARVAN_AI_BASE_URL='https://example.com/v1',
        ARVAN_AI_MODEL='Gemini-2.5-Flash-lite',
    )
    def test_arvan_in_chain_when_configured(self):
        chain = get_http_provider_chain()
        self.assertEqual(len(chain), 3)
        self.assertIs(chain[2], ARVAN)
