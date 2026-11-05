"""هم‌ترازی کلید نمایشی خیابان و کلید فنی مکان_خیابان در Listing.data."""
from __future__ import annotations

from typing import Any, Dict, Tuple

_STREET_EMPTY = frozenset({'', '-', '—', 'nan', 'none', 'null'})


def normalize_street_storage_value(val: Any) -> str:
    s = str(val or '').strip()
    if not s or s.lower() in _STREET_EMPTY:
        return ''
    return s


def sync_street_keys_in_listing_data(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    اگر فقط ستون/کلید «خیابان» پر باشد، مکان_خیابان را تکمیل می‌کند.
    مقدار معتبر موجود مکان_خیابان overwrite نمی‌شود.
    """
    out = dict(data or {})
    tech = normalize_street_storage_value(out.get('مکان_خیابان'))
    disp = normalize_street_storage_value(out.get('خیابان'))
    if not tech and disp:
        out['مکان_خیابان'] = disp
    return out


def listing_street_for_display(listing) -> str:
    """خیابان نرمال‌شده برای نمایش UI (کارت، خلاصه موقعیت)."""
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    data = sync_street_keys_in_listing_data(data)
    return normalize_street_storage_value(data.get('مکان_خیابان'))


def property_street_for_display(prop) -> str:
    """خیابان ذخیره‌شده روی فایل شخصی (feature_data)."""
    fd = getattr(prop, 'feature_data', None) or {}
    if not isinstance(fd, dict):
        return ''
    return normalize_street_storage_value(fd.get('خیابان') or fd.get('مکان_خیابان'))


def listing_street_backfill_plan(data: Dict[str, Any] | None) -> Tuple[bool, str]:
    """آیا فقط مکان_خیابان خالی از روی خیابان قابل تکمیل است؟"""
    block = dict(data or {})
    tech = normalize_street_storage_value(block.get('مکان_خیابان'))
    if tech:
        return False, ''
    disp = normalize_street_storage_value(block.get('خیابان'))
    if not disp:
        return False, ''
    return True, disp
