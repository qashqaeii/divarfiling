"""تنظیمات generation به‌ازای هر feature — override روی default provider."""
from __future__ import annotations

from typing import Any, Dict

from django.conf import settings

from ai_workspace.constants import FEATURE_GENERATION

_DEFAULT_TEMPERATURE = 0.4
_DEFAULT_MAX_TOKENS = 1200


def get_feature_generation(feature: str) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(FEATURE_GENERATION.get(feature) or {})
    settings_map = getattr(settings, 'AI_FEATURE_GENERATION', None) or {}
    if isinstance(settings_map, dict):
        extra = settings_map.get(feature)
        if isinstance(extra, dict):
            merged.update(extra)
    temperature = float(merged.get('temperature', _DEFAULT_TEMPERATURE))
    max_tokens = int(merged.get('max_tokens', _DEFAULT_MAX_TOKENS))
    return {
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
