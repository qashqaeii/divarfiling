"""تبدیل JSON خام دیوار به فیلدهای Listing."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _safe_get(d: Dict[str, Any], path: List[str], default=None):
    node: Any = d
    for key in path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return default
    return node


_PERSIAN = '۰۱۲۳۴۵۶۷۸۹'
_ARABIC = '٠١٢٣٤٥٦٧٨٩'


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


def flatten_divar_detail(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    """استخراج فیلدهای کلیدی از پاسخ posts-v2/web."""
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
    rooms = ''
    floor = ''
    year = ''
    lat = lng = None
    images: List[str] = []
    business_type = ''

    for s in sections:
        if s.get('section_name') == 'LIST_DATA':
            for w in s.get('widgets') or []:
                wtype = w.get('widget_type')
                data = w.get('data') or {}
                if wtype == 'UNEXPANDABLE_ROW':
                    t = str(data.get('title') or '').strip()
                    v = str(data.get('value') or '').strip()
                    if t == 'قیمت کل':
                        price = _parse_money(v)
                    elif t in ('ودیعه', 'رهن', 'رهن کامل', 'بیعانه'):
                        deposit = _parse_money(v)
                    elif t in ('اجارهٔ ماهانه', 'اجاره ماهانه'):
                        rent = _parse_money(v)
                    elif t == 'متراژ':
                        try:
                            area = float(_to_en_digits(v).replace('متر', '').strip())
                        except ValueError:
                            area = None
                    elif t == 'اتاق':
                        rooms = v
                    elif t == 'طبقه':
                        floor = v
                    elif t in ('ساخت', 'سال ساخت'):
                        year = v
                elif wtype == 'GROUP_FEATURE_ROW':
                    for item in data.get('items') or []:
                        t = str(item.get('title') or '')
                        if 'آگهی‌دهنده' in t or 'آگهی دهنده' in t:
                            business_type = str(item.get('value') or '')

        if s.get('section_name') == 'MAP':
            for w in s.get('widgets') or []:
                loc = _safe_get(w, ['data', 'location']) or {}
                if loc.get('latitude') and loc.get('longitude'):
                    lat = float(loc['latitude'])
                    lng = float(loc['longitude'])

        if s.get('section_name') == 'IMAGE':
            for w in s.get('widgets') or []:
                for img in _safe_get(w, ['data', 'images']) or []:
                    url = img.get('url') if isinstance(img, dict) else str(img)
                    if url:
                        images.append(url)

    link = share.get('web_url') or (f'https://divar.ir/v/{token_val}' if token_val else '')

    flat = {
        'token': token_val,
        'title': title,
        'description': description,
        'price': price,
        'deposit': deposit,
        'rent': rent,
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
        'link': link,
        'images': images,
    }
    flat['data'] = {**flat, 'raw': detail}
    return flat


def is_roommate_ad(flat: Dict[str, Any]) -> bool:
    """فیلتر همخانه — مشابه منطق دسکتاپ."""
    keywords = ('همخانه', 'هم خانه', 'همخونه', 'هم خونه', 'هم‌خانه')
    text = f"{flat.get('title', '')} {flat.get('description', '')}"
    return any(k in text for k in keywords)
