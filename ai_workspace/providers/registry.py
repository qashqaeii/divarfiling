"""Singleton Providerها — یک instance برای کل پروسه."""
from __future__ import annotations

from ai_workspace.providers.arvan import ArvanAIProvider, is_arvan_configured
from ai_workspace.providers.gemini import GeminiProvider
from ai_workspace.providers.openrouter import OpenRouterProvider
from ai_workspace.providers.rule_based import RuleBasedProvider

# Primary: کیفیت بهتر (RPD محدود — از settings)
GEMINI_PRIMARY = GeminiProvider(model_setting='GEMINI_MODEL')

# Fallback داخل Gemini: Lite با RPD بالاتر
GEMINI_LITE = GeminiProvider(model_setting='GEMINI_FALLBACK_MODEL')

# Production backup — ArvanCloud AIaaS (paid, stable)
ARVAN = ArvanAIProvider()

# LEGACY_INACTIVE — OpenRouter :free removed from production chain (see docs/ARVAN_AI_INTEGRATION.md)
OPENROUTER = OpenRouterProvider()

RULE_BASED = RuleBasedProvider()


def get_http_provider_chain():
    """
    زنجیره HTTP فعال production:
    Gemini Primary → Gemini Lite → Arvan (if configured) → (Gateway) RuleBased
    """
    chain = [GEMINI_PRIMARY, GEMINI_LITE]
    if is_arvan_configured():
        chain.append(ARVAN)
    return chain


# Backward compatibility for imports; prefer get_http_provider_chain() at runtime.
HTTP_PROVIDER_CHAIN = get_http_provider_chain()
