"""Gemini API — با retry داخلی (یک بار) و مدل قابل تنظیم."""
from __future__ import annotations

import time
from typing import Any, Dict

import requests
from django.conf import settings

from ai_workspace.providers.base import ProviderError, ProviderResult

_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


class GeminiProvider:
    name = 'gemini'

    def __init__(self, *, model_setting: str = 'GEMINI_MODEL'):
        self.model_setting = model_setting

    def _resolve_model(self) -> str:
        return getattr(settings, self.model_setting, '') or getattr(
            settings, 'GEMINI_MODEL', 'gemini-2.5-flash-lite',
        )

    def complete(self, *, system: str, user: str, json_mode: bool = False) -> ProviderResult:
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
        if not api_key:
            raise ProviderError('GEMINI_API_KEY not configured', retryable=False, code='no_key')

        model = self._resolve_model()
        timeout = int(getattr(settings, 'GEMINI_TIMEOUT_SECONDS', 10))
        last_error: ProviderError | None = None

        for attempt in range(2):
            try:
                return self._call_once(
                    api_key=api_key,
                    model=model,
                    system=system,
                    user=user,
                    json_mode=json_mode,
                    timeout=timeout,
                )
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= 1:
                    raise
        if last_error:
            raise last_error
        raise ProviderError('Gemini failed', retryable=True, code='unknown')

    def _call_once(
        self,
        *,
        api_key: str,
        model: str,
        system: str,
        user: str,
        json_mode: bool,
        timeout: int,
    ) -> ProviderResult:
        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{model}:generateContent?key={api_key}'
        )
        body: Dict[str, Any] = {
            'contents': [{'parts': [{'text': user}]}],
            'generationConfig': {
                'temperature': 0.4,
                'maxOutputTokens': 1024,
            },
        }
        if system:
            body['systemInstruction'] = {'parts': [{'text': system}]}
        if json_mode:
            body['generationConfig']['responseMimeType'] = 'application/json'

        started = time.perf_counter()
        try:
            resp = requests.post(url, json=body, timeout=timeout)
        except requests.Timeout as exc:
            raise ProviderError('Gemini timeout', retryable=True, code='timeout') from exc
        except requests.RequestException as exc:
            raise ProviderError(str(exc), retryable=True, code='network') from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        content_type = (resp.headers.get('Content-Type') or '').lower()
        body_preview = (resp.text or '')[:200].lower()
        if 'text/html' in content_type or body_preview.startswith('<!doctype'):
            # صفحه HTML گوگل — معمولاً IP سرور به generativelanguage.googleapis.com دسترسی ندارد.
            raise ProviderError(
                'Gemini unreachable (HTML 403 — likely IP/geo block on server)',
                retryable=True,
                code='geo_blocked',
            )

        if resp.status_code in _RETRYABLE_HTTP:
            raise ProviderError(
                f'Gemini HTTP {resp.status_code}',
                retryable=True,
                code=str(resp.status_code),
            )
        if resp.status_code in (400, 401):
            raise ProviderError(
                f'Gemini HTTP {resp.status_code}',
                retryable=False,
                code=str(resp.status_code),
            )
        if resp.status_code == 403:
            # ممکن است مخصوص یک مدل باشد — Gateway به Lite/OpenRouter می‌رود.
            raise ProviderError(
                f'Gemini HTTP {resp.status_code}',
                retryable=True,
                code=str(resp.status_code),
            )
        if not resp.ok:
            raise ProviderError(
                f'Gemini HTTP {resp.status_code}',
                retryable=resp.status_code >= 500,
                code=str(resp.status_code),
            )

        data = resp.json()
        if 'error' in data:
            err = data['error']
            status = str(err.get('status', ''))
            retryable = status in ('RESOURCE_EXHAUSTED', 'UNAVAILABLE', 'INTERNAL', 'DEADLINE_EXCEEDED')
            raise ProviderError(status or 'gemini_error', retryable=retryable, code=status)

        try:
            text = data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError('Gemini empty response', retryable=True, code='empty') from exc

        usage = data.get('usageMetadata') or {}
        return ProviderResult(
            text=(text or '').strip(),
            provider=self.name,
            model=model,
            input_tokens=usage.get('promptTokenCount'),
            output_tokens=usage.get('candidatesTokenCount'),
            latency_ms=latency_ms,
            is_fallback=self.model_setting != 'GEMINI_MODEL',
        )
