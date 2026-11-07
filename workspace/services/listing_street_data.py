"""هم‌ترازی کلید نمایشی خیابان و کلید فنی مکان_خیابان در Listing.data."""
from __future__ import annotations

from typing import Any, Dict, Tuple

_STREET_EMPTY = frozenset({'', '-', '—', 'nan', 'none', 'null'})

# برچسب‌های موقعیت — در باکس «امکانات» نمایش داده نمی‌شوند
LOCATION_FIELD_LABELS = frozenset({
    'خیابان', 'شهر', 'محله', 'منطقه', 'استان', 'آدرس',
    'مکان_خیابان', 'مکان_شهر', 'مکان_محله', 'مکان_منطقه', 'مکان_استان', 'مکان_آدرس',
})


def is_location_field_label(label: str) -> bool:
    return (label or '').strip() in LOCATION_FIELD_LABELS


def normalize_street_storage_value(val: Any) -> str:
    s = str(val or '').strip()
    if not s or s.lower() in _STREET_EMPTY:
        return ''
    return s


def sync_street_in_feature_data(feature_data: Dict[str, Any] | None, street: Any) -> Dict[str, Any]:
    """هم‌ترازی کلیدهای خیابان در feature_data فایل شخصی."""
    out = dict(feature_data or {})
    normalized = normalize_street_storage_value(street)
    if normalized:
        out['خیابان'] = normalized
        out['مکان_خیابان'] = normalized
    else:
        out.pop('خیابان', None)
        out.pop('مکان_خیابان', None)
    return out


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


def _street_from_amenities_text(text: str) -> str:
    import re

    for token in re.split(r'[\n،,|]+', str(text or '').strip()):
        raw = token.strip()
        if not raw or ':' not in raw:
            continue
        label, _, val = raw.partition(':')
        if label.strip() != 'خیابان':
            continue
        street = normalize_street_storage_value(val)
        if street:
            return street
    return ''


def property_street_for_display(prop, *, user=None) -> str:
    """خیابان فایل شخصی — feature_data، متن امکانات، یا آگهی منبع."""
    fd = getattr(prop, 'feature_data', None) or {}
    if isinstance(fd, dict):
        street = normalize_street_storage_value(fd.get('خیابان') or fd.get('مکان_خیابان'))
        if street:
            return street

    street = _street_from_amenities_text(getattr(prop, 'amenities', None) or '')
    if street:
        return street

    owner = user or getattr(prop, 'user', None)
    if owner is not None:
        from workspace.services.crm import resolve_listing_for_property

        listing = resolve_listing_for_property(owner, prop)
        if listing is not None:
            street = listing_street_for_display(listing)
            if street:
                return street
    return ''


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
