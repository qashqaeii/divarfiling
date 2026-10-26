"""ذخیره موقت نتیجه Import مخاطبین — برای نمایش batch بدون لیست طولانی در Session."""
from __future__ import annotations

import uuid
from typing import List, Optional, Tuple

from django.core.cache import cache

_CACHE_PREFIX = 'crm_contact_import_batch:'
_TTL_SECONDS = 48 * 3600
_MAX_IDS_STORED = 20_000


def create_import_batch(user_id: int, contact_ids: List[int], *, stats: Optional[dict] = None) -> str:
    batch_id = uuid.uuid4().hex
    ids = contact_ids[:_MAX_IDS_STORED]
    payload = {
        'user_id': user_id,
        'ids': ids,
        'total_created': len(contact_ids),
        'truncated': len(contact_ids) > len(ids),
        'stats': stats or {},
    }
    cache.set(f'{_CACHE_PREFIX}{batch_id}', payload, timeout=_TTL_SECONDS)
    return batch_id


def get_import_batch(user_id: int, batch_id: str) -> Optional[dict]:
    if not batch_id or batch_id == 'last':
        return None
    payload = cache.get(f'{_CACHE_PREFIX}{batch_id}')
    if not payload or payload.get('user_id') != user_id:
        return None
    return payload


def resolve_import_batch_qs_ids(user_id: int, batch_id: str) -> Tuple[Optional[List[int]], Optional[dict]]:
    payload = get_import_batch(user_id, batch_id)
    if not payload:
        return None, None
    return list(payload.get('ids') or []), payload
