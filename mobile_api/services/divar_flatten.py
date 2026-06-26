"""تبدیل JSON خام دیوار به فیلدهای Listing — هم‌تراز با export_divar_items ویندوز."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRAPER_SRC = Path(__file__).resolve().parents[3] / 'src'
_WINDOWS_FLATTEN = None
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

_SKIP_DATA_KEYS = frozenset({
    'raw', 'widget_list', 'business_lazy_widget_list', 'sections',
    'attributes', 'features',
})

_JSON_BLOB_PREFIX = ('{', '[')


def _ensure_windows_flatten():
    global _WINDOWS_FLATTEN, _WINDOWS_IMPORT_TRIED
    if _WINDOWS_IMPORT_TRIED:
        return _WINDOWS_FLATTEN
    _WINDOWS_IMPORT_TRIED = True
    src = str(_SCRAPER_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from export_divar_items import flatten_post_detail  # noqa: WPS433
        _WINDOWS_FLATTEN = flatten_post_detail
    except Exception:
        _WINDOWS_FLATTEN = None
    return _WINDOWS_FLATTEN


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
    t = _to_en_digits(str(text))
    t = t.replace(' تومان', '').replace('تومان', '').replace('٬', '').replace(',', '')
    digits = ''.join(ch for ch in t if ch in '0123456789')
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _first_int(row: Dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        val = row.get(key)
        if val is None or val == '':
            continue
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return int(val)
        parsed = _parse_money(str(val))
        if parsed is not None:
            return parsed
    return None


def _first_float(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        val = row.get(key)
        if val is None or val == '':
            continue
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        try:
            return float(_to_en_digits(str(val)).replace('متر', '').strip())
        except ValueError:
            continue
    return None


def _first_str(row: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = row.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text not in ('-', '—', 'nan', 'None'):
            return text
    return ''


def _parse_attr_field(attrs: str, field: str) -> str:
    for part in str(attrs or '').split('|'):
        piece = part.strip()
        if ':' not in piece:
            continue
        title, value = piece.split(':', 1)
        if title.strip() == field:
            return value.strip()
    return ''


def _advertiser_type_persian(row: Dict[str, Any]) -> str:
    consultant = _first_str(row, 'مشاور_نام', 'نام مشاور / آژانس')
    business = _first_str(row, 'فروشنده_business_type', 'business_type').lower()
    if consultant or business in CONSULTANT_BUSINESS_TYPES or 'premium' in business:
        return 'مشاور'
    if business == 'personal' or not business:
        return 'شخصی'
    if 'مشاور' in business or 'آژانس' in business:
        return 'مشاور'
    return business or 'شخصی'


def _sanitize_listing_data(row: Dict[str, Any]) -> Dict[str, Any]:
    """دادهٔ Listing.data — فقط مقادیر تخت قابل نمایش (بدون raw JSON)."""
    out: Dict[str, Any] = {}
    for key, val in row.items():
        if key in _SKIP_DATA_KEYS:
            continue
        if isinstance(val, (dict, list)):
            continue
        if val is None:
            continue
        text = str(val).strip()
        if not text or text in ('-', '—', 'nan', 'None'):
            continue
        if text.startswith(_JSON_BLOB_PREFIX):
            continue
        out[key] = val
    advertiser = _advertiser_type_persian(row)
    out['نوع آگهی دهنده'] = advertiser
    out['نوع آگهی‌دهنده'] = advertiser
    return out


def _map_windows_row_to_listing(row: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    attrs = _first_str(row, 'attributes', 'ویژگی_ها_و_امکانات')
    token_val = _first_str(row, 'token', 'شناسه') or token
    images_raw = row.get('images') or row.get('رسانه_تصاویر') or ''
    if isinstance(images_raw, list):
        images = [str(u).strip() for u in images_raw if str(u).strip()]
    else:
        images = [u.strip() for u in str(images_raw).split('|') if u.strip()]

    area = _first_float(row, 'متراژ', 'area')
    if area is None:
        area_text = _parse_attr_field(attrs, 'متراژ')
        if area_text:
            try:
                area = float(_to_en_digits(area_text).replace('متر', '').strip())
            except ValueError:
                area = None

    rooms = _first_str(row, 'اتاق', 'rooms') or _parse_attr_field(attrs, 'اتاق')
    floor = _first_str(row, 'طبقه', 'floor') or _parse_attr_field(attrs, 'طبقه')
    year = _first_str(row, 'ساخت', 'سال ساخت', 'build_year') or _parse_attr_field(attrs, 'ساخت')

    price = _first_int(row, 'مالی_قیمت_کل_عدد', 'price', 'قیمت')
    deposit = _first_int(row, 'اجاره_ودیعه_عدد', 'deposit', 'ودیعه')
    rent = _first_int(row, 'اجاره_ماهانه_عدد', 'rent', 'اجاره')

    lat_raw = _first_str(row, 'latitude', 'مکان_مختصات_lat', 'عرض جغرافیایی')
    lng_raw = _first_str(row, 'longitude', 'مکان_مختصات_lng', 'طول جغرافیایی')
    lat = float(lat_raw) if lat_raw else None
    lng = float(lng_raw) if lng_raw else None

    consultant_name = _first_str(row, 'مشاور_نام', 'نام مشاور / آژانس')
    business_type = _advertiser_type_persian(row)

    listing_data = _sanitize_listing_data(row)
    if floor:
        listing_data['طبقه'] = floor
    if year:
        listing_data['ساخت'] = year
    if rooms:
        listing_data['اتاق'] = rooms
    if area is not None:
        listing_data['متراژ'] = area

    return {
        'token': token_val,
        'title': _first_str(row, 'عنوان', 'title'),
        'description': _first_str(row, 'توضیحات', 'description'),
        'price': price,
        'price_per_meter': _first_int(row, 'مالی_قیمت_هر_متر_عدد', 'price_per_meter'),
        'deposit': deposit,
        'rent': rent,
        'rent_convertibility': _first_str(row, 'اجاره_قابل_تبدیل', 'rent_convertibility'),
        'area': area,
        'rooms': rooms,
        'floor': floor,
        'year': year,
        'city': _first_str(row, 'مکان_شهر', 'city_persian', 'شهر', 'city'),
        'district': _first_str(row, 'مکان_منطقه', 'district_persian', 'محله', 'district'),
        'neighborhood': _first_str(row, 'مکان_منطقه', 'district_persian', 'محله', 'neighborhood'),
        'latitude': lat,
        'longitude': lng,
        'business_type': business_type,
        'consultant_name': consultant_name,
        'link': _first_str(row, 'لینک', 'link', 'share_link'),
        'images': images,
        'video_url': _first_str(row, 'رسانه_ویدیو', 'video_url'),
        'tags': _first_str(row, 'برچسب‌ها', 'tags'),
        'data': listing_data,
    }


def _legacy_flatten_divar_detail(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    """Fallback اگر import ویندوز ممکن نبود."""
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
                    elif t in ('ودیعه', 'رهن'):
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
                elif wtype == 'GROUP_FEATURE_ROW':
                    for item in data.get('items') or []:
                        ft = str(item.get('title') or '')
                        fv = str(item.get('value') or '')
                        if ft:
                            features_kv[ft] = fv
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

    widget_list = detail.get('business_lazy_widget_list') or []
    consultant_name = ''
    for widget in widget_list or []:
        if widget.get('widget_type') != 'EVENT_ROW':
            continue
        action = _safe_get(widget, ['data', 'action']) or {}
        if action.get('type') == 'PREMIUM_PANEL_BRAND_LANDING':
            consultant_name = str(_safe_get(widget, ['data', 'title']) or '').strip()
            break

    for amenity in ('آسانسور', 'پارکینگ', 'انباری'):
        if amenity in features_kv:
            pass

    row = {
        'token': token_val,
        'شناسه': token_val,
        'عنوان': title,
        'title': title,
        'توضیحات': description,
        'description': description,
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
    }
    row.update(features_kv)
    if features_kv:
        parts = [
            f'{k}: {v}' if v not in ('دارد', 'ندارد') else f'{k} {v}'
            for k, v in features_kv.items()
        ]
        row['ویژگی_ها_و_امکانات'] = ' | '.join(parts)

    return _map_windows_row_to_listing(row, token_val)


def flatten_divar_detail(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    """Flatten کامل — اولویت با منطق ویندوز (`flatten_post_detail`)."""
    if not isinstance(detail, dict):
        detail = {}

    windows_flatten = _ensure_windows_flatten()
    if windows_flatten is not None:
        try:
            row = windows_flatten(detail)
            return _map_windows_row_to_listing(row, token)
        except Exception:
            pass

    return _legacy_flatten_divar_detail(detail, token)


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
