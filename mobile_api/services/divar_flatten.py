"""تبدیل JSON خام دیوار به فیلدهای Listing — هم‌تراز با export_divar_items ویندوز."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from workspace.services.columns import export_record_to_listing_fields, extract_consultant_name

logger = logging.getLogger(__name__)

_SCRAPER_SRC = Path(__file__).resolve().parents[3] / 'src'
_WINDOWS_FLATTEN = None
_WINDOWS_EXPORT = None
_WINDOWS_IMPORT_TRIED = False

_PERSIAN = '۰۱۲۳۴۵۶۷۸۹'
_ARABIC = '٠١٢٣٤٥٦٧٨٩'

ROOMATE_PATTERN = re.compile(
    r'هم[\s\-]?(?:خو?ن?ه|خانه)[\s\-]?[ای‌ی]?',
    re.IGNORECASE | re.UNICODE,
)

CONSULTANT_BUSINESS_TYPES = {
    'premium-panel', 'premium_panel', 'business', 'consultant', 'agency',
    'بنگاه', 'مشاور', 'آژانس',
}


def _ensure_windows_modules():
    global _WINDOWS_FLATTEN, _WINDOWS_EXPORT, _WINDOWS_IMPORT_TRIED
    if _WINDOWS_IMPORT_TRIED:
        return _WINDOWS_FLATTEN, _WINDOWS_EXPORT
    _WINDOWS_IMPORT_TRIED = True
    src = str(_SCRAPER_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from export_divar_items import export_rows_to_records, flatten_post_detail  # noqa: WPS433
        _WINDOWS_FLATTEN = flatten_post_detail
        _WINDOWS_EXPORT = export_rows_to_records
    except Exception as exc:
        logger.warning('Windows scraper import failed: %s', exc)
        _WINDOWS_FLATTEN = None
        _WINDOWS_EXPORT = None
    return _WINDOWS_FLATTEN, _WINDOWS_EXPORT


def _safe_get(d: Any, path: List[str], default=None):
    node = d
    for key in path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return default
    return node


def _to_en_digits(text: str) -> str:
    if not isinstance(text, str):
        return str(text or '')
    trans = {ord(p): str(i) for i, p in enumerate(_PERSIAN)}
    trans.update({ord(a): str(i) for i, a in enumerate(_ARABIC)})
    return text.translate(trans)


def _parse_money(text: str) -> Optional[int]:
    if not text:
        return None
    raw = str(text)
    t = _to_en_digits(raw)
    t = t.replace(' تومان', '').replace('تومان', '').replace(' ریال', '').replace('ریال', '')
    t = t.replace('٬', '').replace(',', '').replace('،', '')
    digits = '0123456789'
    cleaned = ''.join(ch for ch in t if ch in digits)
    if not cleaned:
        return None
    try:
        amount = int(cleaned)
    except ValueError:
        return None
    tl = _to_en_digits(raw).lower()
    if 'میلیارد' in tl:
        return amount * 1_000_000_000
    if 'میلیون' in tl:
        return amount * 1_000_000
    if 'هزار' in tl:
        return amount * 1_000
    return amount


def _advertiser_type_persian(row: Dict[str, Any]) -> str:
    consultant = str(row.get('نام مشاور / آژانس') or row.get('مشاور_نام') or '').strip()
    business = str(
        row.get('نوع آگهی دهنده')
        or row.get('فروشنده_business_type')
        or row.get('business_type')
        or ''
    ).strip().lower()
    if consultant or business in CONSULTANT_BUSINESS_TYPES or 'premium' in business:
        return 'مشاور'
    if business == 'personal' or not business:
        return 'شخصی'
    if 'مشاور' in business or 'آژانس' in business:
        return 'مشاور'
    return business or 'شخصی'


def _export_normalize_row(raw_row: Dict[str, Any], category: str) -> Dict[str, Any]:
    """همان نرمال‌سازی اکسل ویندوز — ستون‌های فارسی یکتا."""
    _, export_fn = _ensure_windows_modules()
    if export_fn is None:
        return raw_row
    try:
        records = export_fn([raw_row], category=category)
        return records[0] if records else raw_row
    except Exception as exc:
        logger.warning('export_rows_to_records failed: %s', exc)
        return raw_row


def _raw_flatten_row(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    flatten_fn, _ = _ensure_windows_modules()
    if flatten_fn is not None:
        try:
            return flatten_fn(detail)
        except Exception as exc:
            logger.warning('flatten_post_detail failed, using legacy: %s', exc)
    return _legacy_raw_row(detail, token)


def _legacy_raw_row(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    """Fallback اگر import ویندوز ممکن نبود — خروجی خام مشابه flatten_post_detail."""
    if not isinstance(detail, dict):
        detail = {}

    seo = detail.get('seo') or {}
    share = detail.get('share') or {}
    webengage = detail.get('webengage') or {}
    sections = detail.get('sections') or []

    token_val = webengage.get('token') or token or ''
    if not token_val and share.get('web_url'):
        token_val = str(share['web_url']).rstrip('/').split('/')[-1]

    title = ''
    for s in sections:
        if s.get('section_name') == 'TITLE':
            for w in s.get('widgets') or []:
                if w.get('widget_type') in ('LEGEND_TITLE_ROW', 'TITLE_ROW'):
                    title = _safe_get(w, ['data', 'title']) or _safe_get(w, ['data', 'text']) or title
            break
    if not title:
        title = _safe_get(seo, ['web_info', 'title']) or _safe_get(seo, ['title']) or ''

    description = ''
    for s in sections:
        if s.get('section_name') == 'DESCRIPTION':
            for w in s.get('widgets') or []:
                if w.get('widget_type') == 'DESCRIPTION_ROW':
                    description = _safe_get(w, ['data', 'text']) or ''
                    if description:
                        break

    city = _safe_get(seo, ['web_info', 'city_persian']) or ''
    district = _safe_get(seo, ['web_info', 'district_persian']) or ''

    price = deposit = rent = None
    area = None
    rooms = floor = year = ''
    features_kv: Dict[str, str] = {}
    lat = lng = None
    images: List[str] = []
    has_rent_slider = False
    slider_credit = slider_rent = None

    for s in sections:
        sec = s.get('section_name')
        if sec == 'LIST_DATA':
            for w in s.get('widgets') or []:
                wtype = w.get('widget_type')
                data = w.get('data') or {}
                if wtype == 'UNEXPANDABLE_ROW':
                    t = str(data.get('title') or '').strip()
                    v = str(data.get('value') or '').strip()
                    if t == 'قیمت کل':
                        price = _parse_money(v)
                    elif t in ('ودیعه', 'رهن', 'رهن کامل'):
                        deposit = _parse_money(v)
                    elif t in ('اجارهٔ ماهانه', 'اجاره ماهانه'):
                        rent = _parse_money(v)
                    elif t == 'متراژ':
                        try:
                            area = float(_to_en_digits(v).replace('متر', '').strip())
                        except ValueError:
                            pass
                    elif t == 'اتاق':
                        rooms = v
                    elif t == 'طبقه':
                        floor = v
                    elif t in ('ساخت', 'سال ساخت'):
                        year = v
                elif wtype == 'RENT_SLIDER':
                    has_rent_slider = True
                    slider_credit = _parse_money(str(data.get('credit', {}).get('value') or ''))
                    slider_rent = _parse_money(str(data.get('rent', {}).get('value') or ''))
                elif wtype == 'GROUP_FEATURE_ROW':
                    for item in data.get('items') or []:
                        ft = str(item.get('title') or '')
                        if ft:
                            available = item.get('available', True)
                            features_kv[ft] = 'دارد' if available else 'ندارد'
        elif sec == 'MAP':
            for w in s.get('widgets') or []:
                if w.get('widget_type') == 'MAP_ROW':
                    loc = _safe_get(w, ['data', 'location']) or {}
                    lat_val = (
                        _safe_get(loc, ['exact_data', 'point', 'latitude'])
                        or _safe_get(loc, ['fuzzy_data', 'point', 'latitude'])
                    )
                    lng_val = (
                        _safe_get(loc, ['exact_data', 'point', 'longitude'])
                        or _safe_get(loc, ['fuzzy_data', 'point', 'longitude'])
                    )
                    if lat_val is not None and lng_val is not None:
                        lat = float(lat_val)
                        lng = float(lng_val)
        elif sec == 'IMAGE':
            for w in s.get('widgets') or []:
                if w.get('widget_type') == 'IMAGE_CAROUSEL':
                    for it in _safe_get(w, ['data', 'items']) or []:
                        url = _safe_get(it, ['image', 'url']) or ''
                        if url:
                            images.append(url)

    if deposit is None:
        deposit = slider_credit
    if rent is None:
        rent = slider_rent
    if deposit is None and isinstance(webengage.get('credit'), int):
        deposit = webengage.get('credit')
    if rent is None and isinstance(webengage.get('rent'), int):
        rent = webengage.get('rent')

    widget_list = detail.get('business_lazy_widget_list') or []
    consultant_name = ''
    for widget in widget_list or []:
        if widget.get('widget_type') != 'EVENT_ROW':
            continue
        action = _safe_get(widget, ['data', 'action']) or {}
        if action.get('type') == 'PREMIUM_PANEL_BRAND_LANDING':
            consultant_name = str(_safe_get(widget, ['data', 'title']) or '').strip()
            break

    row: Dict[str, Any] = {
        'token': token_val,
        'شناسه': token_val,
        'عنوان': title,
        'توضیحات': description,
        'مکان_شهر': city,
        'مکان_منطقه': district,
        'مالی_قیمت_کل_عدد': price,
        'اجاره_ودیعه_عدد': deposit,
        'اجاره_ماهانه_عدد': rent,
        'متراژ': area,
        'اتاق': rooms,
        'طبقه': floor,
        'ساخت': year,
        'latitude': lat,
        'longitude': lng,
        'مکان_مختصات_lat': str(lat) if lat else '',
        'مکان_مختصات_lng': str(lng) if lng else '',
        'فروشنده_business_type': webengage.get('business_type') or '',
        'مشاور_نام': consultant_name,
        'لینک': share.get('web_url') or (f'https://divar.ir/v/{token_val}' if token_val else ''),
        'images': ' | '.join(images),
        'رسانه_تصاویر': ' | '.join(images),
        'اجاره_قابل_تبدیل': 'قابل تبدیل' if has_rent_slider else '',
    }
    row.update(features_kv)
    for amenity in ('آسانسور', 'پارکینگ', 'انباری'):
        if amenity in features_kv:
            row[amenity] = features_kv[amenity]
    if features_kv:
        parts = [
            f'{k}: {v}' if v not in ('دارد', 'ندارد') else f'{k} {v}'
            for k, v in features_kv.items()
        ]
        row['ویژگی_ها_و_امکانات'] = ' | '.join(parts)
    return row


def _fields_to_flat_dict(fields: Dict[str, Any], export_row: Dict[str, Any]) -> Dict[str, Any]:
    """شکل خروجی برای extraction_ingest و فیلترهای مشاور/همخانه."""
    consultant_name = extract_consultant_name(export_row)
    business_type = _advertiser_type_persian(export_row)
    return {
        'token': fields['token'],
        'title': fields.get('title') or '',
        'description': fields.get('description') or '',
        'price': fields.get('price'),
        'deposit': fields.get('deposit'),
        'rent': fields.get('rent'),
        'area': fields.get('area'),
        'rooms': fields.get('rooms') or '',
        'city': fields.get('city') or '',
        'district': fields.get('neighborhood') or '',
        'neighborhood': fields.get('neighborhood') or '',
        'latitude': fields.get('latitude'),
        'longitude': fields.get('longitude'),
        'business_type': business_type,
        'consultant_name': consultant_name,
        'link': fields.get('link') or '',
        'images': fields.get('images') or [],
        'data': fields.get('data') or {},
    }


def flatten_divar_detail(
    detail: Dict[str, Any],
    token: str = '',
    category: str = 'apartment-rent',
) -> Dict[str, Any]:
    """Flatten کامل — همان pipeline ویندوز: raw → export columns → Listing fields."""
    if not isinstance(detail, dict):
        detail = {}

    raw_row = _raw_flatten_row(detail, token)
    export_row = _export_normalize_row(raw_row, category)
    fields = export_record_to_listing_fields(export_row)
    if token and not fields.get('token'):
        fields['token'] = token
    return _fields_to_flat_dict(fields, export_row)


def is_roommate_ad(flat: Dict[str, Any], category_slug: str = '') -> bool:
    if category_slug and 'rent' not in category_slug.lower():
        return False
    text = f"{flat.get('title', '')} {flat.get('description', '')}"
    return bool(ROOMATE_PATTERN.search(text))


def is_consultant_ad(flat: Dict[str, Any]) -> bool:
    business = str(flat.get('business_type') or '').strip().lower()
    if business in CONSULTANT_BUSINESS_TYPES or business == 'مشاور':
        return True
    if flat.get('consultant_name'):
        return True
    return 'مشاور' in business or 'آژانس' in business
