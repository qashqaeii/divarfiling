"""OpenRouter — Backup فقط بعد از خطای Gemini."""
from __future__ import annotations

import time
from typing import Any, Dict, List

import requests
from django.conf import settings

from ai_workspace.providers.base import ProviderError, ProviderResult
from ai_workspace.services.openrouter_models import get_free_models

# لیست مدل‌ها روزی یک‌بار refresh می‌شود؛ روی 429 همان درخواست مدل بعدی امتحان می‌شود.

_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def _extract_message_text(message: Dict[str, Any]) -> str:
    content = message.get('content')
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text':
                parts.append(str(block.get('text', '')))
        joined = '\n'.join(p for p in parts if p).strip()
        if joined:
            return joined
    reasoning = message.get('reasoning')
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return ''


class OpenRouterProvider:
    name = 'openrouter'

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> ProviderResult:
        api_key = getattr(settings, 'OPENROUTER_API_KEY', '') or ''
        if not api_key:
            raise ProviderError('OPENROUTER_API_KEY not configured', retryable=False, code='no_key')

        models = get_free_models()
        if not models:
            raise ProviderError('No free models configured', retryable=False, code='no_models')

        base_url = (getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1') or '').rstrip('/')
        timeout = int(getattr(settings, 'OPENROUTER_TIMEOUT_SECONDS', 8))
        site_url = getattr(settings, 'SITE_URL', 'https://divarfiling.ir')

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': user})

        last_error: ProviderError | None = None
        for model in models:
            body: Dict[str, Any] = {
                'model': model,
                'messages': messages,
                'max_tokens': 800,
                'temperature': 0.4,
            }
            if json_mode:
                body['response_format'] = {'type': 'json_object'}

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': site_url,
                'X-Title': 'DivarFiling',
            }

            started = time.perf_counter()
            try:
                resp = requests.post(
                    f'{base_url}/chat/completions',
                    json=body,
                    headers=headers,
                    timeout=timeout,
                )
            except requests.Timeout as exc:
                last_error = ProviderError('OpenRouter timeout', retryable=True, code='timeout')
                continue
            except requests.RequestException as exc:
                last_error = ProviderError(str(exc), retryable=True, code='network')
                continue

            latency_ms = int((time.perf_counter() - started) * 1000)

            if resp.status_code in _RETRYABLE_HTTP:
                last_error = ProviderError(
                    f'OpenRouter HTTP {resp.status_code} ({model})',
                    retryable=True,
                    code=str(resp.status_code),
                )
                continue
            if not resp.ok:
                last_error = ProviderError(
                    f'OpenRouter HTTP {resp.status_code} ({model})',
                    retryable=resp.status_code >= 500,
                    code=str(resp.status_code),
                )
                continue

            data = resp.json()
            if data.get('error'):
                err = data['error']
                code = str(err.get('code', ''))
                last_error = ProviderError(
                    str(err.get('message', 'openrouter_error')),
                    retryable=code in ('429', '500', '502', '503'),
                    code=code,
                )
                continue

            try:
                message = data['choices'][0]['message']
            except (KeyError, IndexError, TypeError):
                last_error = ProviderError('OpenRouter empty response', retryable=True, code='empty')
                continue

            text = _extract_message_text(message)
            if not text:
                last_error = ProviderError('OpenRouter empty text', retryable=True, code='empty_text')
                continue

            usage = data.get('usage') or {}
            routed_model = data.get('model') or model
            return ProviderResult(
                text=text,
                provider=self.name,
                model=routed_model,
                input_tokens=usage.get('prompt_tokens'),
                output_tokens=usage.get('completion_tokens'),
                latency_ms=latency_ms,
                is_fallback=True,
            )

        if last_error:
            raise last_error
        raise ProviderError('OpenRouter all models failed', retryable=True, code='all_failed')
