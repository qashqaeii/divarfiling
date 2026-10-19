"""فراخوانی مدل برای دستیار عمومی — بدون سهمیه کاربر میزکار."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings

from ai_workspace.providers.base import ProviderError
from ai_workspace.providers.registry import get_http_provider_chain

logger = logging.getLogger(__name__)

FEATURE = 'public_assistant'


def _generation() -> Dict[str, Any]:
    defaults = {
        'temperature': float(getattr(settings, 'PUBLIC_ASSISTANT_TEMPERATURE', 0.35)),
        'max_tokens': int(getattr(settings, 'PUBLIC_ASSISTANT_MAX_TOKENS', 900)),
    }
    extra = (getattr(settings, 'AI_FEATURE_GENERATION', None) or {}).get(FEATURE)
    if isinstance(extra, dict):
        defaults.update(extra)
    return defaults


def complete(system: str, user: str) -> tuple[Optional[str], str, str, int, Optional[int], Optional[int]]:
    """
    خروجی: text, provider, model, latency_ms, input_tokens, output_tokens
    در صورت شکست همه providerها: text=None
    """
    generation = _generation()
    chain = get_http_provider_chain()
    last_code = ''
    for provider in chain:
        try:
            result = provider.complete(
                system=system,
                user=user,
                json_mode=False,
                generation=generation,
            )
            return (
                (result.text or '').strip(),
                result.provider,
                result.model,
                result.latency_ms,
                result.input_tokens,
                result.output_tokens,
            )
        except ProviderError as exc:
            last_code = exc.code or 'provider_error'
            logger.warning('public_assistant provider failed: %s %s', provider.name, last_code)
            continue
    logger.error('public_assistant all providers failed last=%s', last_code)
    return None, '', '', 0, None, None
