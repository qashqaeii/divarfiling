"""Singleton Providerها — یک instance برای کل پروسه."""
from __future__ import annotations

from django.conf import settings

from ai_workspace.providers.arvan import ArvanAIProvider, is_arvan_configured
from ai_workspace.providers.gemini import GeminiProvider
from ai_workspace.providers.openrouter import OpenRouterProvider
from ai_workspace.providers.rule_based import RuleBasedProvider

GEMINI_PRIMARY = GeminiProvider(model_setting='GEMINI_MODEL')
GEMINI_LITE = GeminiProvider(model_setting='GEMINI_FALLBACK_MODEL')

ARVAN = ArvanAIProvider()
OPENROUTER = OpenRouterProvider()

RULE_BASED = RuleBasedProvider()


def is_openrouter_configured() -> bool:
    """OpenRouter فقط با API key فعال می‌شود؛ مدل‌ها runtime از :free discovery/env."""
    return bool((getattr(settings, 'OPENROUTER_API_KEY', '') or '').strip())


def get_http_provider_chain():
    """
    زنجیره HTTP production (اولین provider = attempt 1 در gateway):

    Arvan (if configured)
      → OpenRouter :free (if OPENROUTER_API_KEY)
      → Gemini Primary
      → Gemini Lite

    Rollback: ARVAN_AI_ENABLED=false → OpenRouter → Gemini → Lite
    """
    chain = []
    if is_arvan_configured():
        chain.append(ARVAN)
    if is_openrouter_configured():
        chain.append(OPENROUTER)
    chain.extend([GEMINI_PRIMARY, GEMINI_LITE])
    return chain


# Backward compatibility — prefer get_http_provider_chain() at runtime.
HTTP_PROVIDER_CHAIN = get_http_provider_chain()
