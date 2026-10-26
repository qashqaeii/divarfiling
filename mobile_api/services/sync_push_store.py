"""ذخیره نتیجه Push Sync برای Idempotency."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mobile_api.models import MobileSyncOperation


def get_cached_push_results(user, op_ids: List[str]) -> Dict[str, MobileSyncOperation]:
    cleaned = [str(o).strip()[:128] for o in op_ids if str(o or '').strip()]
    if not cleaned:
        return {}
    rows = MobileSyncOperation.objects.filter(user=user, op_id__in=cleaned)
    return {r.op_id: r for r in rows}


def reserve_push_op(user, op_id: str, entity: str) -> str:
    """
    رزرو اتمی op_id قبل از اجرا.
    خروجی: execute | replay_ok | replay_conflict | in_progress
    """
    op_id = str(op_id or '').strip()[:128]
    if not op_id:
        return 'execute'
    rec, created = MobileSyncOperation.objects.get_or_create(
        user=user,
        op_id=op_id,
        defaults={
            'entity': (entity or '')[:40],
            'status': MobileSyncOperation.STATUS_PROCESSING,
            'server_id': None,
            'conflict_reason': '',
        },
    )
    if created:
        return 'execute'
    if rec.status == MobileSyncOperation.STATUS_OK and rec.server_id:
        return 'replay_ok'
    if rec.status == MobileSyncOperation.STATUS_CONFLICT:
        return 'replay_conflict'
    if rec.status == MobileSyncOperation.STATUS_PROCESSING:
        return 'in_progress'
    return 'replay_conflict'


def get_push_op(user, op_id: str) -> Optional[MobileSyncOperation]:
    op_id = str(op_id or '').strip()[:128]
    if not op_id:
        return None
    return MobileSyncOperation.objects.filter(user=user, op_id=op_id).first()


def record_push_success(user, op_id: str, *, entity: str, server_id: int) -> None:
    op_id = str(op_id or '').strip()[:128]
    if not op_id:
        return
    MobileSyncOperation.objects.update_or_create(
        user=user,
        op_id=op_id,
        defaults={
            'entity': entity[:40],
            'server_id': server_id,
            'status': MobileSyncOperation.STATUS_OK,
            'conflict_reason': '',
        },
    )


def record_push_conflict(user, op_id: str, *, entity: str, reason: str) -> None:
    op_id = str(op_id or '').strip()[:128]
    if not op_id:
        return
    MobileSyncOperation.objects.update_or_create(
        user=user,
        op_id=op_id,
        defaults={
            'entity': entity[:40],
            'server_id': None,
            'status': MobileSyncOperation.STATUS_CONFLICT,
            'conflict_reason': (reason or '')[:300],
        },
    )
