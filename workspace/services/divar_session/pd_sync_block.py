"""مسدودسازی sync خودکار فایل sessions برای خطوط منفصل‌شده از نشست مرکزی."""
from __future__ import annotations

from accounts.phone_utils import normalize_phone
from workspace.divar_session_models import DivarAccountSession, DivarPdSessionFileSyncBlock


def is_phone_detector_file_sync_blocked(phone: str) -> bool:
    key = normalize_phone(phone or '')
    if not key:
        return False
    return DivarPdSessionFileSyncBlock.objects.filter(phone=key).exists()


def block_phone_detector_file_sync(
    phone: str,
    *,
    reason: str,
    session: DivarAccountSession | None = None,
) -> None:
    key = normalize_phone(phone or '')
    if not key:
        return
    DivarPdSessionFileSyncBlock.objects.update_or_create(
        phone=key,
        defaults={
            'reason': reason,
            'session': session,
        },
    )


def clear_phone_detector_file_sync_block(phone: str) -> None:
    key = normalize_phone(phone or '')
    if not key:
        return
    DivarPdSessionFileSyncBlock.objects.filter(phone=key).delete()


def blocked_phones_set() -> set[str]:
    return set(DivarPdSessionFileSyncBlock.objects.values_list('phone', flat=True))
