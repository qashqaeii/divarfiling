"""ذخیره نتیجه Push Sync برای Idempotency."""
from __future__ import annotations

from datetime import timedelta
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from mobile_api.models import MobileSyncOperation

PUSH_PROCESSING_STALE_MINUTES = 15


def get_cached_push_results(user, op_ids: List[str]) -> Dict[str, MobileSyncOperation]:
    cleaned = [str(o).strip()[:128] for o in op_ids if str(o or '').strip()]
    if not cleaned:
        return {}
    rows = MobileSyncOperation.objects.filter(user=user, op_id__in=cleaned)
    return {r.op_id: r for r in rows}


def _processing_is_stale(rec: MobileSyncOperation) -> bool:
    if rec.status != MobileSyncOperation.STATUS_PROCESSING:
        return False
    cutoff = timezone.now() - timedelta(minutes=PUSH_PROCESSING_STALE_MINUTES)
    return rec.updated_at < cutoff


def _fingerprint_mismatch(rec: MobileSyncOperation, fingerprint: str) -> bool:
    if not fingerprint:
        return False
    stored = (rec.payload_fingerprint or '').strip()
    if not stored:
        return False
    return stored != fingerprint


def reserve_push_op(user, op_id: str, entity: str, *, fingerprint: str = '') -> str:
    """
    رزرو اتمی op_id قبل از اجرا.
    خروجی: execute | replay_ok | replay_conflict | in_progress | payload_mismatch
    """
    op_id = str(op_id or '').strip()[:128]
    if not op_id:
        return 'execute'
    fp = (fingerprint or '')[:64]
    with transaction.atomic():
        rec, created = MobileSyncOperation.objects.select_for_update().get_or_create(
            user=user,
            op_id=op_id,
            defaults={
                'entity': (entity or '')[:40],
                'status': MobileSyncOperation.STATUS_PROCESSING,
                'server_id': None,
                'conflict_reason': '',
                'payload_fingerprint': fp,
            },
        )
        if created:
            return 'execute'
        if _fingerprint_mismatch(rec, fp):
            return 'payload_mismatch'
        if rec.status == MobileSyncOperation.STATUS_OK and rec.server_id:
            return 'replay_ok'
        if rec.status == MobileSyncOperation.STATUS_CONFLICT:
            return 'replay_conflict'
        if rec.status == MobileSyncOperation.STATUS_PROCESSING:
            if _processing_is_stale(rec):
                rec.entity = (entity or '')[:40]
                rec.payload_fingerprint = fp
                rec.conflict_reason = ''
                rec.save(update_fields=['entity', 'payload_fingerprint', 'conflict_reason', 'updated_at'])
                return 'execute'
            return 'in_progress'
    return 'replay_conflict'


def get_push_op(user, op_id: str) -> Optional[MobileSyncOperation]:
    op_id = str(op_id or '').strip()[:128]
    if not op_id:
        return None
    return MobileSyncOperation.objects.filter(user=user, op_id=op_id).first()


def record_push_success(user, op_id: str, *, entity: str, server_id: int, fingerprint: str = '') -> None:
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
            'payload_fingerprint': (fingerprint or '')[:64],
        },
    )


def record_push_conflict(user, op_id: str, *, entity: str, reason: str, fingerprint: str = '') -> None:
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
            'payload_fingerprint': (fingerprint or '')[:64],
        },
    )
