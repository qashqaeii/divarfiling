"""PII stripping and payload safety for Management AI."""
from __future__ import annotations

import re
from typing import Any

from accounts.services.management_ai.schemas import PII_KEY_PATTERNS

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(r'(?:\+98|0098|98|0)?9\d{9}')


def _key_is_sensitive(key: str) -> bool:
    lowered = (key or '').lower()
    return any(part in lowered for part in PII_KEY_PATTERNS)


def _scrub_string(value: str) -> str:
    text = value
    text = _EMAIL_RE.sub('[redacted]', text)
    text = _PHONE_RE.sub('[redacted]', text)
    return text


def sanitize_value(value: Any, parent_key: str = '') -> Any:
    if _key_is_sensitive(parent_key):
        return None
    if isinstance(value, dict):
        return sanitize_snapshot_dict(value)
    if isinstance(value, list):
        return [sanitize_value(item, parent_key) for item in value]
    if isinstance(value, str):
        return _scrub_string(value)
    return value


def sanitize_snapshot_dict(data: dict) -> dict:
    clean: dict = {}
    for key, val in data.items():
        if _key_is_sensitive(key):
            continue
        clean[key] = sanitize_value(val, key)
    if isinstance(clean.get('facts'), list):
        scrubbed_facts = []
        for item in clean['facts']:
            if not isinstance(item, dict):
                continue
            scrubbed_facts.append({
                k: sanitize_value(v, k) if isinstance(v, str) else v
                for k, v in item.items()
                if not _key_is_sensitive(k)
            })
        clean['facts'] = scrubbed_facts
    return clean


def assert_no_pii(payload: dict) -> None:
    """Raise ValueError if obvious PII patterns remain in serialized payload."""
    import json

    blob = json.dumps(payload, ensure_ascii=False, default=str)
    if _EMAIL_RE.search(blob):
        raise ValueError('PII: email detected in management AI payload')
    if _PHONE_RE.search(blob):
        raise ValueError('PII: phone detected in management AI payload')
    for token in ('password', 'api_key', 'Bearer '):
        if token.lower() in blob.lower():
            raise ValueError(f'PII/sensitive token detected: {token}')
