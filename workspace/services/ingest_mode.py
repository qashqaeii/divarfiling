"""تعیین حالت ingest — snapshot در برابر incremental."""
from __future__ import annotations

from workspace.constants import INGEST_MODE_INCREMENTAL, INGEST_MODE_SNAPSHOT
from workspace.services.folder_import import normalize_file_identity


def _has_folder_path(path_info: dict | None) -> bool:
    return bool(normalize_file_identity((path_info or {}).get('relative_path', '')))

__all__ = [
    'INGEST_MODE_INCREMENTAL',
    'INGEST_MODE_SNAPSHOT',
    'resolve_ingest_mode',
    'should_prune_stale_listings',
]


def resolve_ingest_mode(
    *,
    path_info: dict | None = None,
    metadata_extra: dict | None = None,
    is_mobile: bool = False,
) -> str:
    """
    snapshot: payload نماینده وضعیت فعلی منبع است — آگهی‌های غایب prune می‌شوند.
    incremental: فقط افزودن/به‌روزرسانی — آگهی‌های قدیمی بدون حضور در payload باقی می‌مانند.

    شواهد رفتار فعلی:
    - آپلود ویندوز با مسیر پوشه → snapshot (prune_stale قبلی)
    - استخراج موبایل/ابر → incremental (merge چند استخراج پیاپی)
    - آپلود تکی وب بدون مسیر → incremental
    """
    extra = metadata_extra or {}
    explicit = str(extra.get('ingest_mode') or '').strip().lower()
    if explicit in (INGEST_MODE_SNAPSHOT, INGEST_MODE_INCREMENTAL):
        return explicit
    if is_mobile:
        return INGEST_MODE_INCREMENTAL
    if _has_folder_path(path_info):
        return INGEST_MODE_SNAPSHOT
    return INGEST_MODE_INCREMENTAL


def should_prune_stale_listings(
    *,
    is_update: bool,
    ingest_mode: str,
) -> bool:
    return bool(is_update and ingest_mode == INGEST_MODE_SNAPSHOT)
