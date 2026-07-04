"""Singleton Providerها — یک instance برای کل پروسه."""
from __future__ import annotations

from ai_workspace.providers.gemini import GeminiProvider
from ai_workspace.providers.openrouter import OpenRouterProvider
from ai_workspace.providers.rule_based import RuleBasedProvider

# Primary: کیفیت بهتر (RPD محدود — از settings)
GEMINI_PRIMARY = GeminiProvider(model_setting='GEMINI_MODEL')

# Fallback داخل Gemini: Lite با RPD بالاتر (۵۰۰/روز در داشبورد 3.1 Flash Lite)
GEMINI_LITE = GeminiProvider(model_setting='GEMINI_FALLBACK_MODEL')

OPENROUTER = OpenRouterProvider()

RULE_BASED = RuleBasedProvider()

# زنجیره HTTP — فقط وقتی قبلی fail شود
HTTP_PROVIDER_CHAIN = [
    GEMINI_PRIMARY,
    GEMINI_LITE,
    OPENROUTER,
]
