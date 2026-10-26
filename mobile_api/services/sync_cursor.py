"""Cursor صفحه‌بندی Delta Sync موبایل."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime

SYNC_PROTOCOL_VERSION = 2


class SyncCursorError(ValueError):
    """Cursor نامعتبر یا دست‌کاری‌شده."""


def encode_cursor(state: Dict[str, Any]) -> str:
    raw = json.dumps(state, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii')


def decode_cursor(token: Optional[str], *, strict: bool = False) -> Dict[str, Any]:
    if not token or not str(token).strip():
        return {}
    try:
        raw = base64.urlsafe_b64decode(str(token).strip().encode('ascii'))
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, dict):
            if strict:
                raise SyncCursorError('invalid_cursor')
            return {}
        if strict and not data.get('session_started'):
            raise SyncCursorError('invalid_cursor')
        return data
    except SyncCursorError:
        raise
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        if strict:
            raise SyncCursorError('invalid_cursor')
        return {}


def parse_cursor_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        dt = parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def keyset_filter(qs, *, updated_field: str, pk_field: str, cursor_piece: Optional[dict]):
    if not cursor_piece:
        return qs
    dt = parse_cursor_dt(cursor_piece.get('updated_at'))
    pk = cursor_piece.get('pk')
    if dt is None or pk is None:
        return qs
    from django.db.models import Q
    return qs.filter(
        Q(**{f'{updated_field}__gt': dt})
        | Q(**{updated_field: dt, f'{pk_field}__gt': pk}),
    )


def page_keyset(
    rows: list,
    limit: int,
    *,
    updated_attr: str = 'updated_at',
    pk_attr: str = 'pk',
) -> Tuple[list, bool, Optional[dict]]:
    has_more = len(rows) > limit
    page = rows[:limit]
    if not has_more or not page:
        return page, False, None
    last = page[-1]
    updated = getattr(last, updated_attr, None)
    pk = getattr(last, pk_attr, None)
    if updated is None or pk is None:
        return page, False, None
    if timezone.is_naive(updated):
        updated = timezone.make_aware(updated, timezone.get_current_timezone())
    return page, True, {'updated_at': updated.isoformat(), 'pk': pk}
