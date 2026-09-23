"""ArvanCloud AIaaS — production HTTP backup after Gemini (replaces OpenRouter free)."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

from ai_workspace.providers.arvan_http import (
    build_authorization_header,
    build_chat_completions_url,
    extract_chat_message_content,
    parse_usage_tokens,
)
from ai_workspace.providers.base import ProviderError, ProviderResult

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})


def is_arvan_enabled() -> bool:
    return bool(getattr(settings, 'ARVAN_AI_ENABLED', False))


def is_arvan_configured() -> bool:
    if not is_arvan_enabled():
        return False
    if not (getattr(settings, 'ARVAN_AI_API_KEY', '') or '').strip():
        return False
    if not (getattr(settings, 'ARVAN_AI_BASE_URL', '') or '').strip():
        return False
    if not (getattr(settings, 'ARVAN_AI_MODEL', '') or '').strip():
        return False
    return True


def _models_to_try() -> List[str]:
    primary = (getattr(settings, 'ARVAN_AI_MODEL', '') or '').strip()
    fallback = (getattr(settings, 'ARVAN_AI_FALLBACK_MODEL', '') or '').strip()
    models: List[str] = []
    if primary:
        models.append(primary)
    if fallback and fallback != primary:
        models.append(fallback)
    return models


def _sleep_retry_after(resp: requests.Response | None) -> None:
    if resp is None:
        return
    raw = resp.headers.get('Retry-After')
    if not raw:
        return
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return
    if seconds > 0:
        time.sleep(min(seconds, 5))


class ArvanAIProvider:
    name = 'arvan'

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        generation: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        if not is_arvan_configured():
            raise ProviderError(
                'Arvan AI not configured',
                retryable=True,
                code='not_configured',
            )

        api_key = (getattr(settings, 'ARVAN_AI_API_KEY', '') or '').strip()
        url = build_chat_completions_url(getattr(settings, 'ARVAN_AI_BASE_URL', '') or '')
        if not url:
            raise ProviderError('Arvan base URL invalid', retryable=True, code='invalid_url')

        auth = build_authorization_header(api_key)
        timeout = int(getattr(settings, 'ARVAN_AI_TIMEOUT_SECONDS', 10))
        max_retries = max(0, int(getattr(settings, 'ARVAN_AI_MAX_RETRIES', 1)))
        gen = generation or {}
        temperature = float(gen.get('temperature', getattr(settings, 'ARVAN_AI_TEMPERATURE', 0.4)))
        max_tokens = int(gen.get('max_tokens', getattr(settings, 'ARVAN_AI_MAX_TOKENS', 1200)))

        models = _models_to_try()
        if not models:
            raise ProviderError('Arvan model not configured', retryable=True, code='no_model')

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': user})

        last_error: ProviderError | None = None

        for model in models:
            body: Dict[str, Any] = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
            }
            # JSON mode: rely on prompt contract + gateway parser (no response_format guess).

            for attempt in range(max_retries + 1):
                started = time.perf_counter()
                resp: requests.Response | None = None
                try:
                    resp = requests.post(
                        url,
                        json=body,
                        headers={
                            'Authorization': auth,
                            'Content-Type': 'application/json',
                        },
                        timeout=timeout,
                    )
                except requests.Timeout as exc:
                    last_error = ProviderError('Arvan timeout', retryable=True, code='timeout')
                    if attempt < max_retries:
                        time.sleep(0.25 * (2 ** attempt))
                        continue
                    break
                except requests.ConnectionError as exc:
                    last_error = ProviderError('Arvan connection error', retryable=True, code='connection_error')
                    if attempt < max_retries:
                        time.sleep(0.25 * (2 ** attempt))
                        continue
                    break
                except requests.RequestException:
                    last_error = ProviderError('Arvan network error', retryable=True, code='connection_error')
                    if attempt < max_retries:
                        time.sleep(0.25 * (2 ** attempt))
                        continue
                    break

                latency_ms = int((time.perf_counter() - started) * 1000)
                status = resp.status_code

                if status == 401:
                    raise ProviderError('Arvan auth error', retryable=False, code='auth_error')
                if status == 429:
                    last_error = ProviderError('Arvan rate limited', retryable=True, code='rate_limited')
                    if attempt < max_retries:
                        _sleep_retry_after(resp)
                        time.sleep(0.25 * (2 ** attempt))
                        continue
                    break
                if status in _RETRYABLE_HTTP:
                    last_error = ProviderError(
                        f'Arvan upstream HTTP {status}',
                        retryable=True,
                        code='upstream_5xx' if status >= 500 else 'rate_limited',
                    )
                    if attempt < max_retries:
                        _sleep_retry_after(resp)
                        time.sleep(0.25 * (2 ** attempt))
                        continue
                    break
                if status >= 400:
                    last_error = ProviderError(
                        f'Arvan HTTP {status}',
                        retryable=False,
                        code='client_error',
                    )
                    break

                try:
                    data = resp.json()
                except ValueError:
                    last_error = ProviderError('Arvan invalid response', retryable=True, code='invalid_response')
                    break

                if isinstance(data, dict) and data.get('error'):
                    err = data['error']
                    if isinstance(err, dict):
                        code = str(err.get('code', '') or '')
                        msg = str(err.get('message', '') or 'arvan_error')
                    else:
                        code = ''
                        msg = 'arvan_error'
                    retryable = code in ('429', '500', '502', '503') or 'rate' in msg.lower()
                    last_error = ProviderError('Arvan API error', retryable=retryable, code=code or 'api_error')
                    if retryable and attempt < max_retries:
                        time.sleep(0.25 * (2 ** attempt))
                        continue
                    break

                text = extract_chat_message_content(data)
                if not text:
                    last_error = ProviderError('Arvan empty response', retryable=True, code='empty_response')
                    if attempt < max_retries:
                        continue
                    break

                inp, out, _tot = parse_usage_tokens(data if isinstance(data, dict) else {})
                routed_model = (data.get('model') if isinstance(data, dict) else None) or model
                logger.info(
                    'arvan_complete ok model=%s latency_ms=%s prompt_tokens=%s completion_tokens=%s',
                    routed_model,
                    latency_ms,
                    inp,
                    out,
                )
                return ProviderResult(
                    text=text,
                    provider=self.name,
                    model=str(routed_model),
                    input_tokens=inp,
                    output_tokens=out,
                    latency_ms=latency_ms,
                    is_fallback=False,
                )

        if last_error:
            raise last_error
        raise ProviderError('Arvan request failed', retryable=True, code='unknown')
