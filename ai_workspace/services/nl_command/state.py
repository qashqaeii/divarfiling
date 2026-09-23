"""Command state کوتاه‌مدت — Redis/cache."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, Optional

from django.core.cache import cache

TTL_SECONDS = 15 * 60
_KEY_PREFIX = 'nl_command'


def _cache_key(user_id: int, command_id: str) -> str:
    return f'{_KEY_PREFIX}:{user_id}:{command_id}'


def new_command_id() -> str:
    return str(uuid.uuid4())


def text_hash(text: str) -> str:
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()[:16]


def save_state(user_id: int, command_id: str, payload: Dict[str, Any]) -> None:
    cache.set(_cache_key(user_id, command_id), payload, TTL_SECONDS)


def load_state(user_id: int, command_id: str) -> Optional[Dict[str, Any]]:
    return cache.get(_cache_key(user_id, command_id))


def delete_state(user_id: int, command_id: str) -> None:
    cache.delete(_cache_key(user_id, command_id))
