"""تبدیل JSON خام دیوار به فیلدهای Listing — هم‌تراز با export_divar_items."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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


def _extract_consultant_name(widget_list: List[Dict[str, Any]]) -> str:
    for widget in widget_list or []:
        if widget.get('widget_type') != 'EVENT_ROW':
            continue
        action = _safe_get(widget, ['data', 'action']) or {}
        if _safe_get(action, ['payload', 'web_info', 'title']) == 'PREMIUM_PANEL_BRAND_LANDING':
            return str(_safe_get(widget, ['data', 'title']) or '').strip()
    return ''


def flatten_divar_detail(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    if not isinstance(detail, dict):
        detail = {}

    seo = detail.get('seo') or {}
    share = detail.get('share') or {}
    webengage = detail.get('webengage') or {}
    analytics = detail.get('analytics') or {}
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
    price_per_meter = None
    area = None
    rooms = ''
    floor = ''
    year = ''
    rent_convertibility = ''
    has_rent_slider = False
    attrs: List[str] = []
    features_kv: Dict[str, str] = {}
    lat = lng = None
    images: List[str] = []
    video_url = ''
    business_type = str(webengage.get('business_type') or '').strip()
    tags: List[str] = []

    for s in sections:
        sec = s.get('section_name')
        if sec == 'LIST_DATA':
            for w in s.get('widgets') or []:
                wtype = w.get('widget_type')
                data = w.get('data') or {}
                if wtype == 'GROUP_INFO_ROW':
                    for it in data.get('items') or []:
                        t = str(it.get('title') or '').strip()
                        v = str(it.get('value') or '').strip()
                        if t or v:
                            attrs.append(f'{t}:{v}')
                            if t == 'متراژ':
                                try:
                                    area = float(_to_en_digits(v).replace('متر', '').strip())
                                except ValueError:
                                    pass
                            elif t == 'اتاق':
                                rooms = v
                elif wtype == 'UNEXPANDABLE_ROW':
                    t = str(data.get('title') or '').strip()
                    v = str(data.get('value') or '').strip()
                    if t == 'قیمت کل':
                        price = _parse_money(v)
                    elif t == 'قیمت هر متر':
                        price_per_meter = _parse_money(v)
                    elif t in ('ودیعه', 'رهن', 'رهن کامل', 'بیعانه'):
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
                    elif t or v:
                        attrs.append(f'{t}:{v}')
                elif wtype == 'FEATURE_ROW':
                    fr_title = str(data.get('title') or '').strip()
                    if fr_title and not rent_convertibility:
                        if 'قابل تبدیل' in fr_title and 'غیر' not in fr_title:
                            rent_convertibility = 'قابل تبدیل'
                        elif 'غیر قابل تبدیل' in fr_title or 'غیرقابل تبدیل' in fr_title:
                            rent_convertibility = 'غیر قابل تبدیل'
                elif wtype == 'RENT_SLIDER':
                    has_rent_slider = True
                    if deposit is None:
                        deposit = _parse_money(str(_safe_get(data, ['credit', 'transformed_value']) or ''))
                        if deposit is None:
                            deposit = _parse_money(str(_safe_get(data, ['credit', 'value']) or ''))
                    if rent is None:
                        rent = _parse_money(str(_safe_get(data, ['rent', 'transformed_value']) or ''))
                        if rent is None:
                            rent = _parse_money(str(_safe_get(data, ['rent', 'value']) or ''))
                elif wtype == 'GROUP_FEATURE_ROW':
                    for item in data.get('items') or []:
                        ft = str(item.get('title') or '')
                        fv = str(item.get('value') or '')
                        if 'آگهی‌دهنده' in ft or 'آگهی دهنده' in ft:
                            business_type = fv or business_type
                        if ft:
                            features_kv[ft] = fv

        elif sec == 'MAP':
            for w in s.get('widgets') or []:
                if w.get('widget_type') != 'MAP_ROW':
                    continue
                loc = _safe_get(w, ['data', 'location']) or {}
                lat_val = (
                    _safe_get(loc, ['exact_data', 'point', 'latitude'])
                    or _safe_get(loc, ['fuzzy_data', 'point', 'latitude'])
                    or loc.get('latitude')
                )
                lng_val = (
                    _safe_get(loc, ['exact_data', 'point', 'longitude'])
                    or _safe_get(loc, ['fuzzy_data', 'point', 'longitude'])
                    or loc.get('longitude')
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
                        vurl = _safe_get(it, ['video_url']) or ''
                        if vurl:
                            video_url = vurl
                else:
                    for img in _safe_get(w, ['data', 'images']) or []:
                        url = img.get('url') if isinstance(img, dict) else str(img)
                        if url:
                            images.append(url)

        elif sec == 'TAGS':
            for w in s.get('widgets') or []:
                if w.get('widget_type') == 'WRAPPER_ROW':
                    for ch in _safe_get(w, ['data', 'chip_list', 'chips']) or []:
                        t = ch.get('text')
                        if t:
                            tags.append(t)

    if price is None and isinstance(webengage.get('price'), int):
        price = webengage.get('price')
    if deposit is None and isinstance(webengage.get('credit'), int):
        deposit = webengage.get('credit')
    if rent is None and isinstance(webengage.get('rent'), int):
        rent = webengage.get('rent')
    if rent_convertibility == '' and has_rent_slider:
        rent_convertibility = 'قابل تبدیل'

    widget_list = detail.get('business_lazy_widget_list') or detail.get('widget_list') or []
    consultant_name = _extract_consultant_name(widget_list)

    link = share.get('web_url') or (f'https://divar.ir/v/{token_val}' if token_val else '')

    flat = {
        'token': token_val,
        'title': title,
        'description': description,
        'price': price,
        'price_per_meter': price_per_meter,
        'deposit': deposit,
        'rent': rent,
        'rent_convertibility': rent_convertibility,
        'area': area,
        'rooms': rooms,
        'floor': floor,
        'year': year,
        'city': city,
        'district': district,
        'neighborhood': district,
        'latitude': lat,
        'longitude': lng,
        'business_type': business_type,
        'consultant_name': consultant_name,
        'link': link,
        'images': images,
        'video_url': video_url,
        'tags': tags,
        'attributes': attrs,
        'features': features_kv,
        'category_slug': analytics.get('cat3') or analytics.get('cat2') or webengage.get('category') or '',
    }
    flat['data'] = {**flat, 'raw': detail}
    return flat


def is_roommate_ad(flat: Dict[str, Any], category_slug: str = '') -> bool:
    if category_slug and 'rent' not in category_slug.lower():
        return False
    text = f"{flat.get('title', '')} {flat.get('description', '')}"
    return bool(ROOMATE_PATTERN.search(text))


def is_consultant_ad(flat: Dict[str, Any]) -> bool:
    business = str(flat.get('business_type') or '').strip().lower()
    if business in CONSULTANT_BUSINESS_TYPES:
        return True
    if flat.get('consultant_name'):
        return True
    return 'مشاور' in business or 'آژانس' in business
