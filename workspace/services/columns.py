"""نگاشت و نرمال‌سازی ستون‌های Divar."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from django.db.models import Q
from django.utils import timezone as dj_tz

from workspace.services.divar_listing_datetime import (
    SHAMSI_KEY_LAST_BUMPED,
    enrich_listing_schedule_data,
    parse_divar_listing_datetime,
    parse_published_at_from_export_row,
)
from workspace.services.jalali_input import _normalize_digits, parse_jalali_datetime_string
from workspace.services.property_images import (
    deduplicate_divar_image_urls,
    normalize_external_image_url,
)

COLUMN_ALIASES: Dict[str, List[str]] = {
    'token': ['شناسه', 'token', 'id', 'آگهی_id', 'listing_id'],
    'title': ['عنوان', 'title', 'نام'],
    'price': ['قیمت', 'price', 'قیمت کل'],
    'deposit': ['ودیعه', 'deposit', 'رهن', 'ودیعه (تومان)'],
    'rent': ['اجاره', 'rent', 'اجاره ماهانه', 'اجاره (تومان)'],
    'area': ['متراژ', 'area', 'متراژ (متر)', 'متراژ مفید'],
    'rooms': ['اتاق', 'rooms', 'تعداد اتاق', 'اتاق خواب'],
    'neighborhood': ['محله', 'مکان_منطقه', 'district', 'district_persian', 'منطقه'],
    'city': ['شهر', 'مکان_شهر', 'city', 'city_persian'],
    'latitude': ['عرض جغرافیایی', 'مکان_مختصات_lat', 'latitude', 'lat'],
    'longitude': ['طول جغرافیایی', 'مکان_مختصات_lng', 'longitude', 'lng'],
    'business_type': ['نوع آگهی دهنده', 'فروشنده_business_type', 'business_type', 'نوع آگهی‌دهنده'],
    'description': ['توضیحات', 'description', 'متن آگهی'],
    'link': ['لینک', 'url', 'link', 'آدرس آگهی'],
    'published_at': ['ایجاد آگهی', 'تاریخ انتشار', 'published_at', 'created_at'],
    'expires_at': ['انقضا آگهی', 'expires_at', 'انتشار_unavailable_after'],
    'last_bumped_at': ['آخرین نردبان', SHAMSI_KEY_LAST_BUMPED],
    'last_updated_at': ['آخرین به‌روزرسانی', 'انتشار_آخرین_به‌روزرسانی_شمسی'],
    'images': ['لینک تصاویر', 'تصاویر', 'images', 'عکس‌ها', 'رسانه_تصاویر', 'لینک تصویر اول'],
    'build_year': ['ساخت', 'سال ساخت', 'build_year', 'سن بنا'],
    'floor': ['طبقه', 'floor'],
    'parking': ['پارکینگ', 'parking'],
    'elevator': ['آسانسور', 'elevator'],
    'storage': ['انباری', 'storage', 'انبار'],
}

_EXPORT_TEXT_MONEY = frozenset({"توافقی", "متعارف", "رایگان", "رهن کامل"})
_TEXTUAL_MONEY_STATUS_KEYS = frozenset({"free", "negotiable", "customary", "full_deposit"})
_MONEY_STATUS_ROW_KEYS = {
    "price": ("مالی_قیمت_کل_وضعیت", "مالی_قیمت_کل_عدد", "مالی_قیمت_کل_نمایش"),
    "deposit": ("اجاره_ودیعه_وضعیت", "اجاره_ودیعه_عدد", "اجاره_ودیعه_نمایش"),
    "rent": ("اجاره_ماهانه_وضعیت", "اجاره_ماهانه_عدد", "اجاره_ماهانه_نمایش"),
}

CONSULTANT_NAME_KEYS = (
    'نام مشاور / آژانس',
    'مشاور_نام',
    'agency_name',
    'نام آژانس',
    'نام مشاور',
)


def extract_consultant_name(data: Optional[Dict[str, Any]]) -> str:
    """نام آژانس/مشاور از دادهٔ خام آگهی (اکسل استخراج)."""
    if not isinstance(data, dict):
        return ''
    for key in CONSULTANT_NAME_KEYS:
        val = data.get(key)
        if val is None:
            continue
        text = normalize_location_label(val)
        if text:
            return text
    return ''


def normalize_location_label(val: Any) -> str:
    """نام شهر/محله/منطقه — placeholderهای خالی مثل '-' نادیده گرفته می‌شوند."""
    s = _safe_str(val)
    if not s or s.lower() in ('nan', 'none', '-', '—'):
        return ''
    return s


def _find_column(df: pd.DataFrame, field: str) -> Optional[str]:
    aliases = COLUMN_ALIASES.get(field, [])
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def _safe_int(val: Any) -> Optional[int]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        s = str(val).strip().replace(',', '').replace('٬', '')
        if not s or s.lower() in ('nan', 'none', '-'):
            return None
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        s = str(val).strip().replace(',', '').replace('٬', '')
        if not s or s.lower() in ('nan', 'none', '-'):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_str(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    return str(val).strip()


def _aware(dt: datetime) -> datetime:
    if dj_tz.is_aware(dt):
        return dt
    return dj_tz.make_aware(dt, dj_tz.get_current_timezone())


def _parse_datetime(val: Any) -> Optional[datetime]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return _aware(val)
    s = _normalize_digits(_safe_str(val))
    if not s:
        return None
    year_m = re.match(r'^(\d{4})', s)
    if year_m:
        year = int(year_m.group(1))
        if 1300 <= year <= 1500:
            jalali_dt = parse_jalali_datetime_string(s)
            return _aware(jalali_dt) if jalali_dt else None
    for fmt in (
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d',
    ):
        try:
            return _aware(datetime.strptime(s[:19], fmt))
        except ValueError:
            continue
    return None


def _split_image_tokens(s: str) -> List[str]:
    if '|' in s:
        return [part.strip() for part in s.split('|') if part.strip()]
    if ',' in s:
        return [part.strip() for part in s.split(',') if part.strip()]
    return [s.strip()] if s.strip() else []


def _parse_images(val: Any) -> List[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    if isinstance(val, list):
        out: List[str] = []
        for item in val:
            url = normalize_external_image_url(str(item))
            if url:
                out.append(url)
        return deduplicate_divar_image_urls(out)
    s = _safe_str(val)
    if s.startswith('['):
        import json
        try:
            arr = json.loads(s.replace("'", '"'))
            out = []
            for item in arr:
                url = normalize_external_image_url(str(item))
                if url:
                    out.append(url)
            return deduplicate_divar_image_urls(out)
        except (json.JSONDecodeError, ValueError):
            pass
    out: List[str] = []
    for token in _split_image_tokens(s):
        url = normalize_external_image_url(token)
        if url:
            out.append(url)
    return deduplicate_divar_image_urls(out)


def _pick_row_value(row: Dict[str, Any], field: str) -> Any:
    for alias in COLUMN_ALIASES.get(field, []):
        if alias in row:
            return row[alias]
    return None


def _export_money_is_textual(raw: Any) -> bool:
    if raw is None:
        return False
    s = str(raw).strip()
    if not s or s in ("-", "—", "nan", "None"):
        return False
    return s in _EXPORT_TEXT_MONEY


def _listing_money_scalar(row: Dict[str, Any], field: str) -> Optional[int]:
    """عدد اسکالر Listing — بدون ساخت قیمت از برچسب متنی."""
    raw = _pick_row_value(row, field)
    if _export_money_is_textual(raw):
        return None
    if raw is not None:
        s = str(raw).strip()
        if s not in ("", "-", "—", "nan", "None"):
            parsed = _safe_int(raw)
            if parsed is not None:
                return parsed

    status_key, num_key, display_key = _MONEY_STATUS_ROW_KEYS.get(field, ("", "", ""))
    status = row.get(status_key)
    if status in _TEXTUAL_MONEY_STATUS_KEYS:
        return None
    if display_key in row and _export_money_is_textual(row.get(display_key)):
        return None
    if num_key in row:
        num_raw = row.get(num_key)
        if num_raw is not None and str(num_raw).strip() not in ("", "-", "—", "nan", "None"):
            parsed = _safe_int(num_raw)
            if parsed is not None:
                return parsed
    return None


def _is_na(val: Any) -> bool:
    if val is None:
        return True
    try:
        return bool(pd.isna(val))
    except (TypeError, ValueError):
        return False


def json_safe_value(val: Any) -> Any:
    """تبدیل مقادیر pandas/numpy به انواع قابل ذخیره در JSONField."""
    if _is_na(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        f = float(val)
        return None if pd.isna(f) else f
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.isoformat()
    if isinstance(val, dict):
        return {str(k): json_safe_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [json_safe_value(v) for v in val]
    if isinstance(val, str):
        s = val.strip()
        return None if s in ('', '-', '—', 'nan', 'None') else val
    if isinstance(val, (int, float, bool)):
        if isinstance(val, float) and pd.isna(val):
            return None
        return val
    if hasattr(val, 'item') and not isinstance(val, (str, bytes, dict, list)):
        try:
            return json_safe_value(val.item())
        except (ValueError, AttributeError):
            pass
    return val


def json_safe_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k): json_safe_value(v) for k, v in data.items()}


def assert_json_serializable(data: Dict[str, Any]) -> Dict[str, Any]:
    """اطمینان از سریال‌پذیری — برای ذخیره در JSONField."""
    safe = json_safe_dict(data)
    json.dumps(safe, ensure_ascii=False)
    return safe


def _export_data_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return assert_json_serializable(enrich_listing_schedule_data(dict(row)))


def _rooms_from_row_data(row: Dict[str, Any], rooms: str) -> str:
    if rooms:
        return rooms
    for key in ('اتاق', 'تعداد اتاق', 'rooms'):
        val = row.get(key)
        if val is not None and str(val).strip() not in ('', '-', '—'):
            return _safe_str(val)
    return ''


def export_record_to_listing_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """تبدیل یک ردیف export فارسی (اکسل/JSON) به فیلدهای Listing — بدون DataFrame."""
    token = _safe_str(_pick_row_value(row, 'token'))
    if not token:
        token = f'row_{hash(tuple(row.values())) % 10**8}'

    data = _export_data_from_row(row)
    rooms = _rooms_from_row_data(row, _safe_str(_pick_row_value(row, 'rooms')))

    return {
        'token': token,
        'title': _safe_str(_pick_row_value(row, 'title')),
        'price': _listing_money_scalar(row, 'price'),
        'deposit': _listing_money_scalar(row, 'deposit'),
        'rent': _listing_money_scalar(row, 'rent'),
        'area': _safe_float(_pick_row_value(row, 'area')),
        'rooms': rooms,
        'neighborhood': normalize_location_label(_pick_row_value(row, 'neighborhood')),
        'city': normalize_location_label(_pick_row_value(row, 'city')),
        'latitude': _safe_float(_pick_row_value(row, 'latitude')),
        'longitude': _safe_float(_pick_row_value(row, 'longitude')),
        'business_type': _safe_str(_pick_row_value(row, 'business_type')),
        'description': _safe_str(_pick_row_value(row, 'description')),
        'link': _safe_str(_pick_row_value(row, 'link')),
        'images': _parse_images(_pick_row_value(row, 'images')),
        'published_at': parse_published_at_from_export_row(row),
        'expires_at': parse_divar_listing_datetime(_pick_row_value(row, 'expires_at')),
        'data': data,
    }


def row_to_listing_fields(row: pd.Series, df: pd.DataFrame) -> Dict[str, Any]:
    """تبدیل یک ردیف DataFrame به فیلدهای Listing."""
    cols = {f: _find_column(df, f) for f in COLUMN_ALIASES}
    token_col = cols['token']
    token = _safe_str(row[token_col]) if token_col else ''
    if not token:
        for c in df.columns:
            if 'شناسه' in c or c.lower() == 'token':
                token = _safe_str(row[c])
                break

    raw_data = {str(col): row[col] for col in df.columns}
    data = assert_json_serializable(enrich_listing_schedule_data(raw_data))

    title = _safe_str(row[cols['title']]) if cols['title'] else ''
    description = _safe_str(row[cols['description']]) if cols['description'] else ''
    business_type_raw = _safe_str(row[cols['business_type']]) if cols['business_type'] else ''
    from workspace.services.advertiser_signal import (
        detect_advertiser_signal,
        normalize_business_type_for_storage,
    )
    # برچسب‌های نمایشی اکسل (مالک واقعی / مشاور پنهان) را به شخصی/مشاور/بنگاه برگردان
    business_type = normalize_business_type_for_storage(business_type_raw) or business_type_raw

    advertiser_signal = detect_advertiser_signal(
        title=title,
        description=description,
        business_type=business_type,
        data=data,
    )

    money_row = {str(k): json_safe_value(v) for k, v in data.items()}

    return {
        'token': token or f'row_{hash(tuple(row.values)) % 10**8}',
        'title': title,
        'price': _listing_money_scalar(money_row, 'price'),
        'deposit': _listing_money_scalar(money_row, 'deposit'),
        'rent': _listing_money_scalar(money_row, 'rent'),
        'area': _safe_float(row[cols['area']]) if cols['area'] else None,
        'rooms': _rooms_from_row_data(data, _safe_str(row[cols['rooms']]) if cols['rooms'] else ''),
        'neighborhood': normalize_location_label(row[cols['neighborhood']]) if cols['neighborhood'] else '',
        'city': normalize_location_label(row[cols['city']]) if cols['city'] else '',
        'latitude': _safe_float(row[cols['latitude']]) if cols['latitude'] else None,
        'longitude': _safe_float(row[cols['longitude']]) if cols['longitude'] else None,
        'business_type': business_type,
        'advertiser_signal': advertiser_signal,
        'description': description,
        'link': _safe_str(row[cols['link']]) if cols['link'] else '',
        'images': _parse_images(row[cols['images']]) if cols['images'] else [],
        'published_at': parse_published_at_from_export_row(money_row) if cols['published_at'] else None,
        'expires_at': parse_divar_listing_datetime(row[cols['expires_at']]) if cols['expires_at'] else None,
        'data': data,
    }


def _most_common_location_label(series: pd.Series) -> str:
    from collections import Counter

    labels = [normalize_location_label(v) for v in series.dropna()]
    labels = [label for label in labels if label]
    if not labels:
        return ''
    return Counter(labels).most_common(1)[0][0]


def detect_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    """تشخیص نوع معامله و مکان از داده."""
    meta: Dict[str, Any] = {}
    has_rent = any('اجاره' in c or 'rent' in c for c in df.columns)
    has_deposit = any('ودیعه' in c or 'deposit' in c or 'رهن' in c for c in df.columns)
    has_price = any('قیمت' in c or c == 'price' for c in df.columns)

    if has_rent and has_deposit and not has_price:
        meta['transaction_type'] = 'اجاره'
    elif has_rent and has_deposit and has_price:
        meta['transaction_type'] = 'ترکیبی'
    elif has_price:
        meta['transaction_type'] = 'فروش'
    else:
        meta['transaction_type'] = 'نامشخص'

    city_col = _find_column(df, 'city')
    if city_col and len(df) > 0:
        city = _most_common_location_label(df[city_col])
        if city:
            meta['city'] = city

    nb_col = _find_column(df, 'neighborhood')
    if nb_col and len(df) > 0:
        district = _most_common_location_label(df[nb_col])
        if district:
            meta['district'] = district

    return meta


def is_consultant(business_type: str) -> bool:
    bt = (business_type or '').strip().lower()
    return 'مشاور' in bt or 'business' in bt or 'agency' in bt


def consultant_q(qs):
    """فیلتر آگهی‌های مشاور در QuerySet."""
    return qs.filter(
        Q(business_type__icontains='مشاور')
        | Q(business_type__icontains='business')
        | Q(business_type__icontains='agency')
    )
