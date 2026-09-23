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


_CONFIRM_LOCK_PREFIX = 'nl_command:confirm_lock'
_CONFIRM_LOCK_SECONDS = 60


def _confirm_lock_key(user_id: int, command_id: str) -> str:
    return f'{_CONFIRM_LOCK_PREFIX}:{user_id}:{command_id}'


def try_acquire_confirm_lock(user_id: int, command_id: str) -> bool:
    """یک confirm همزمان per command — cache.add اتمیک است."""
    return cache.add(_confirm_lock_key(user_id, command_id), 1, _CONFIRM_LOCK_SECONDS)


def release_confirm_lock(user_id: int, command_id: str) -> None:
    cache.delete(_confirm_lock_key(user_id, command_id))
