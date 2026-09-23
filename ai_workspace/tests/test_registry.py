"""Registry — production HTTP provider chain."""
from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from ai_workspace.providers.arvan import ArvanAIProvider
from ai_workspace.providers.gemini import GeminiProvider
from ai_workspace.providers.openrouter import OpenRouterProvider
from ai_workspace.providers.registry import ARVAN, get_http_provider_chain


class RegistryChainTests(SimpleTestCase):
    @override_settings(
        ARVAN_AI_ENABLED=True,
        ARVAN_AI_API_KEY='k',
        ARVAN_AI_BASE_URL='https://example.com/v1',
        ARVAN_AI_MODEL='Gemini-2.5-Flash-lite',
        OPENROUTER_API_KEY='or-key',
        GEMINI_API_KEY='g',
    )
    def test_full_production_chain_order(self):
        chain = get_http_provider_chain()
        self.assertEqual(len(chain), 4)
        self.assertIs(chain[0], ARVAN)
        self.assertIsInstance(chain[1], OpenRouterProvider)
        self.assertIsInstance(chain[2], GeminiProvider)
        self.assertIsInstance(chain[3], GeminiProvider)

    @override_settings(
        ARVAN_AI_ENABLED=False,
        ARVAN_AI_API_KEY='',
        OPENROUTER_API_KEY='or-key',
        GEMINI_API_KEY='g',
    )
    def test_rollback_arvan_disabled_openrouter_first(self):
        chain = get_http_provider_chain()
        self.assertEqual(len(chain), 3)
        self.assertIsInstance(chain[0], OpenRouterProvider)
        self.assertIsInstance(chain[1], GeminiProvider)

    @override_settings(
        ARVAN_AI_ENABLED=False,
        ARVAN_AI_API_KEY='',
        OPENROUTER_API_KEY='',
        GEMINI_API_KEY='g',
    )
    def test_gemini_only_when_no_arvan_no_openrouter(self):
        chain = get_http_provider_chain()
        self.assertEqual(len(chain), 2)
        self.assertTrue(all(isinstance(p, GeminiProvider) for p in chain))

    @override_settings(
        ARVAN_AI_ENABLED=True,
        ARVAN_AI_API_KEY='k',
        ARVAN_AI_BASE_URL='https://example.com/v1',
        ARVAN_AI_MODEL='M',
        OPENROUTER_API_KEY='',
    )
    def test_arvan_without_openrouter(self):
        chain = get_http_provider_chain()
        self.assertEqual(len(chain), 3)
        self.assertIsInstance(chain[0], ArvanAIProvider)
        self.assertFalse(any(isinstance(p, OpenRouterProvider) for p in chain))
