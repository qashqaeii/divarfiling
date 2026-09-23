"""HTTP helpers for ArvanCloud AIaaS (OpenAI-compatible chat completions)."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse


def normalize_arvan_base_url(base_url: str) -> str:
    """Strip whitespace and trailing slashes without duplicating path segments."""
    return (base_url or '').strip().rstrip('/')


def build_chat_completions_url(base_url: str) -> str:
    """
    Build POST URL for Arvan AIaaS chat API.

    Supports:
    - Full endpoint ending in /chat/completions
    - Base URL ending in /v1 (OpenAI SDK style)
    - Gateway endpoint URL from Arvan panel (append /chat/completions)
    """
    base = normalize_arvan_base_url(base_url)
    if not base:
        return ''
    lower = base.lower()
    if lower.endswith('/chat/completions'):
        return base
    if lower.endswith('/v1'):
        return f'{base}/chat/completions'
    return f'{base}/chat/completions'


def build_authorization_header(api_key: str) -> str:
    """Arvan REST auth: ``Authorization: apikey <KEY>`` (prefix applied once)."""
    key = (api_key or '').strip()
    if not key:
        return ''
    lower = key.lower()
    if lower.startswith('apikey '):
        return key
    return f'apikey {key}'


def extract_chat_message_content(data: Any) -> str:
    """Parse OpenAI-compatible chat completion body."""
    if not isinstance(data, dict):
        return ''
    choices = data.get('choices')
    if not isinstance(choices, list) or not choices:
        return ''
    first = choices[0]
    if not isinstance(first, dict):
        return ''
    message = first.get('message')
    if not isinstance(message, dict):
        return ''
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
    return ''


def parse_usage_tokens(data: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    usage = data.get('usage')
    if not isinstance(usage, dict):
        return None, None, None
    prompt = usage.get('prompt_tokens')
    completion = usage.get('completion_tokens')
    total = usage.get('total_tokens')
    inp = int(prompt) if prompt is not None else None
    out = int(completion) if completion is not None else None
    tot = int(total) if total is not None else None
    return inp, out, tot


def redact_url_for_error(url: str) -> str:
    """Avoid leaking tokens in URLs if ever embedded in query string."""
    try:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    except Exception:
        return 'arvan-endpoint'
