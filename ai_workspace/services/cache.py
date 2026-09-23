"""کش نتایج AI."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from ai_workspace.models import AICache


def cache_namespace() -> str:
    return (getattr(settings, 'AI_CACHE_VERSION', 'v2') or 'v2').strip()


def _cache_key(
    feature: str,
    entity_id: str,
    content_version: str,
    prompt_hash: str,
) -> str:
    """کلید کش — namespace rollout + feature/entity/version/prompt."""
    raw = f'{cache_namespace()}:{feature}:{entity_id}:{content_version}:{prompt_hash}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get(
    feature: str,
    entity_id: str,
    content_version: str,
    prompt_hash: str,
) -> Optional[Dict[str, Any]]:
    key = _cache_key(feature, entity_id, content_version, prompt_hash)
    row = AICache.objects.filter(cache_key=key, expires_at__gt=timezone.now()).first()
    if not row:
        return None
    return {
        'text': row.result_text,
        'data': row.result_json or {},
        'from_cache': True,
    }


def invalidate(
    feature: str,
    entity_id: str,
    content_version: str,
    prompt_hash: str,
) -> None:
    key = _cache_key(feature, entity_id, content_version, prompt_hash)
    AICache.objects.filter(cache_key=key).delete()


def store(
    feature: str,
    entity_id: str,
    content_version: str,
    prompt_hash: str,
    *,
    text: str,
    data: Optional[Dict[str, Any]] = None,
    ttl_hours: int = 168,
) -> None:
    key = _cache_key(feature, entity_id, content_version, prompt_hash)
    expires = timezone.now() + timedelta(hours=ttl_hours)
    payload = data if data is not None else {}
    if not payload and text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
    AICache.objects.update_or_create(
        cache_key=key,
        defaults={
            'feature_code': feature,
            'result_text': text,
            'result_json': payload,
            'expires_at': expires,
        },
    )
