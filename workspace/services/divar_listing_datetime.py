"""تبدیل زمان آگهی دیوار — منبع: ساعت محلی ایران (Asia/Tehran)."""
from __future__ import annotations

import re
from datetime import datetime, timezone as dt_timezone
from typing import Any, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_tz

from workspace.services.jalali_input import _normalize_digits, parse_jalali_datetime_string

TEHRAN = ZoneInfo('Asia/Tehran')

# کلیدهای ذخیره در Listing.data (ISO با timezone)
DATA_KEY_LAST_BUMPED_AT = 'last_bumped_at'
DATA_KEY_LAST_UPDATED_AT = 'last_updated_at'

SHAMSI_KEY_PUBLISH = 'انتشار_تاریخ_شمسی'
SHAMSI_KEY_LAST_BUMPED = 'انتشار_آخرین_نردبان_شمسی'
SHAMSI_KEY_LAST_UPDATED = 'انتشار_آخرین_به‌روزرسانی_شمسی'

EXPORT_COL_PUBLISH = ('تاریخ انتشار', 'ایجاد آگهی')
EXPORT_COL_LAST_BUMPED = ('آخرین نردبان',)
EXPORT_COL_LAST_UPDATED = ('آخرین به‌روزرسانی',)

EXPLICIT_PUBLISH_DATA_KEYS = (SHAMSI_KEY_PUBLISH, 'تاریخ انتشار', 'ایجاد آگهی')
EXPLICIT_BUMP_DATA_KEYS = (SHAMSI_KEY_LAST_BUMPED, 'آخرین نردبان')
EXPLICIT_UPDATED_DATA_KEYS = (SHAMSI_KEY_LAST_UPDATED, 'آخرین به‌روزرسانی')

_EMPTY_MARKERS = frozenset({'', '-', '—', 'nan', 'none', 'null'})


def _is_empty_value(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in _EMPTY_MARKERS


def _pick_first_non_empty(data: dict, keys: Sequence[str]) -> str:
    for key in keys:
        if key not in data:
            continue
        val = data.get(key)
        if _is_empty_value(val):
            continue
        return str(val).strip()
    return ''


def parse_divar_listing_datetime(val: Any) -> Optional[datetime]:
    """
    زمان آگهی دیوار:
    - رشته شمسی YYYY/MM/DD HH:MM → ساعت دیوار در تهران
    - ISO با Z/offset → همان لحظه (بدون تفسیر دوباره به‌عنوان محلی)
    - datetime آگاه → بدون جابه‌جایی اضافه
    - datetime ناآگاه میلادی → فرض محلی تهران (خروجی اکسل قدیمی)
    """
    if val is None or (isinstance(val, float) and str(val) == 'nan'):
        return None
    if isinstance(val, datetime):
        if dj_tz.is_aware(val):
            return val.astimezone(TEHRAN)
        return val.replace(tzinfo=TEHRAN)

    s = _normalize_digits(str(val).strip())
    if not s or s.lower() in _EMPTY_MARKERS:
        return None

    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?', s):
        try:
            normalized = s.replace('Z', '+00:00')
            if len(normalized) == 16 and 'T' in normalized:
                normalized += ':00'
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=TEHRAN)
            return dt.astimezone(TEHRAN)
        except ValueError:
            pass

    year_m = re.match(r'^(\d{4})', s)
    if year_m:
        year = int(year_m.group(1))
        if 1300 <= year <= 1500:
            jalali_dt = parse_jalali_datetime_string(s)
            if jalali_dt:
                return jalali_dt.replace(tzinfo=TEHRAN)

    for fmt in (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ):
        try:
            naive = datetime.strptime(s[:19], fmt)
            if 1300 <= naive.year <= 1500:
                continue
            return naive.replace(tzinfo=TEHRAN)
        except ValueError:
            continue
    return None


def divar_listing_datetime_to_storage_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    aware = dt if dj_tz.is_aware(dt) else dt.replace(tzinfo=TEHRAN)
    return aware.astimezone(dt_timezone.utc).isoformat()


def listing_datetime_to_jalali_label(dt: Any) -> str:
    """نمایش شمسی آگهی — یک بار localtime تهران."""
    parsed = dt if isinstance(dt, datetime) else parse_divar_listing_datetime(dt)
    if not parsed:
        return ''
    if dj_tz.is_aware(parsed):
        parsed = parsed.astimezone(TEHRAN)
    else:
        parsed = parsed.replace(tzinfo=TEHRAN)
    import jdatetime

    jdt = jdatetime.datetime.fromgregorian(datetime=parsed.replace(tzinfo=None))
    if jdt.hour or jdt.minute:
        return jdt.strftime('%Y/%m/%d %H:%M')
    return jdt.strftime('%Y/%m/%d')


def has_explicit_publish_in_export_data(data: Optional[dict]) -> bool:
    return bool(_pick_first_non_empty(data or {}, EXPLICIT_PUBLISH_DATA_KEYS))


def has_explicit_last_bumped_in_export_data(data: Optional[dict]) -> bool:
    return bool(_pick_first_non_empty(data or {}, EXPLICIT_BUMP_DATA_KEYS))


def has_explicit_last_updated_in_export_data(data: Optional[dict]) -> bool:
    return bool(_pick_first_non_empty(data or {}, EXPLICIT_UPDATED_DATA_KEYS))


def enrich_listing_schedule_data(data: dict) -> dict:
    """تکمیل کلیدهای ISO و شمسی در data — بدون جایگزینی عمدی با خالی."""
    out = dict(data or {})

    pub_raw = _pick_first_non_empty(out, list(EXPLICIT_PUBLISH_DATA_KEYS))
    if pub_raw:
        out.setdefault(SHAMSI_KEY_PUBLISH, pub_raw)
        pub_dt = parse_divar_listing_datetime(pub_raw)
        if pub_dt:
            out['published_at_iso'] = divar_listing_datetime_to_storage_iso(pub_dt)

    bump_raw = _pick_first_non_empty(out, list(EXPLICIT_BUMP_DATA_KEYS))
    if bump_raw:
        out.setdefault(SHAMSI_KEY_LAST_BUMPED, bump_raw)
        bump_dt = parse_divar_listing_datetime(bump_raw)
        if bump_dt:
            out[DATA_KEY_LAST_BUMPED_AT] = divar_listing_datetime_to_storage_iso(bump_dt)

    upd_raw = _pick_first_non_empty(out, list(EXPLICIT_UPDATED_DATA_KEYS))
    if upd_raw:
        out.setdefault(SHAMSI_KEY_LAST_UPDATED, upd_raw)
        upd_dt = parse_divar_listing_datetime(upd_raw)
        if upd_dt:
            out[DATA_KEY_LAST_UPDATED_AT] = divar_listing_datetime_to_storage_iso(upd_dt)

    return out


def merge_listing_schedule_data(old: Optional[dict], new: Optional[dict]) -> dict:
    """کلیدهای زمان‌بندی آگهی — بدون پاک‌کردن نردبان/به‌روزرسانی معتبر با ورودی خالی."""
    merged = dict(old or {})
    raw_new = dict(new or {})
    enriched = enrich_listing_schedule_data(raw_new)

    explicit_bump = has_explicit_last_bumped_in_export_data(raw_new)
    explicit_updated = has_explicit_last_updated_in_export_data(raw_new)

    for key, val in enriched.items():
        if val is None or _is_empty_value(val):
            continue
        if key in ('مکان_خیابان', 'خیابان'):
            old_st = str(merged.get(key) or '').strip()
            if old_st and old_st not in ('-', '—', 'nan', 'None'):
                continue
        if key in (SHAMSI_KEY_LAST_BUMPED, DATA_KEY_LAST_BUMPED_AT) and not explicit_bump:
            continue
        if key in (SHAMSI_KEY_LAST_UPDATED, DATA_KEY_LAST_UPDATED_AT) and not explicit_updated:
            continue
        merged[key] = val

    if not explicit_bump:
        for key in (SHAMSI_KEY_LAST_BUMPED, DATA_KEY_LAST_BUMPED_AT):
            if key in (old or {}):
                merged[key] = (old or {})[key]
    if not explicit_updated:
        for key in (SHAMSI_KEY_LAST_UPDATED, DATA_KEY_LAST_UPDATED_AT):
            if key in (old or {}):
                merged[key] = (old or {})[key]

    return merged


def parse_published_at_from_export_row(row: dict) -> Optional[datetime]:
    from workspace.services.columns import _pick_row_value

    raw = _pick_row_value(row, 'published_at')
    if _is_empty_value(raw):
        raw = _pick_first_non_empty(row, EXPLICIT_PUBLISH_DATA_KEYS)
    return parse_divar_listing_datetime(raw)


def resolve_listing_last_bump_datetime(listing) -> Optional[datetime]:
    """زمان آخرین نردبان — فقط وقتی قابل parse است (نه به‌روزرسانی/انتشار)."""
    data = getattr(listing, 'data', None) or {}
    candidates: list[Any] = []
    iso = data.get(DATA_KEY_LAST_BUMPED_AT)
    if not _is_empty_value(iso):
        candidates.append(iso)
    shamsi = _pick_first_non_empty(data, EXPLICIT_BUMP_DATA_KEYS)
    if shamsi and shamsi not in candidates:
        candidates.append(shamsi)
    for raw in candidates:
        parsed = parse_divar_listing_datetime(raw)
        if parsed:
            return parsed
    return None


def resolve_listing_last_bump_jalali_label(listing) -> str:
    """برچسب شمسی «آخرین نردبان» با ارقام فارسی — برای نمایش بدون فیلتر تمپلیت."""
    from workspace.services.jalali_input import to_persian_digits

    parsed = resolve_listing_last_bump_datetime(listing)
    if not parsed:
        return ''
    label = listing_datetime_to_jalali_label(parsed)
    return to_persian_digits(label) if label else ''
