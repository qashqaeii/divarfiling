"""استخراج موقعیت از JSON خام posts-v2 — فقط مسیر موبایل/اندروید."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from workspace.services.columns import normalize_location_label

_FA_COMMA = re.compile(r'[,،]\s*')
_RELATIVE_TIME_PREFIX = re.compile(
    r'^(?:'
    r'پریروز|دیروز|امروز|الان|'
    r'لحظاتی\s*پیش|دقایقی\s*پیش|ثانیه‌هایی\s*پیش|'
    r'[\d۰-۹]+\s*(?:ثانیه|دقیقه|ساعت|روز|هفته|ماه|سال)\s*پیش'
    r')\s*',
    re.UNICODE,
)
_STREET_RE = re.compile(
    r'^(?:'
    r'خ(?:\.|[\s\u200c]+)|'
    r'خیابان[\s\u200c]+|'
    r'کوچه[\s\u200c]+|'
    r'بلوار[\s\u200c]+|'
    r'جاده[\s\u200c]+|'
    r'میدان[\s\u200c]+|'
    r'بزرگراه[\s\u200c]+|'
    r'آزادراه[\s\u200c]+'
    r')',
    re.UNICODE,
)
_NEIGHBORHOOD_PREFIX = 'محله '


def _safe_get(d: Any, path: List[str]) -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _find_location_headline_title(detail: Dict[str, Any]) -> str:
    sections = detail.get('sections')
    if not isinstance(sections, list):
        return ''
    for section in sections:
        if not isinstance(section, dict) or section.get('section_name') != 'TITLE':
            continue
        widgets = section.get('widgets')
        if not isinstance(widgets, list):
            continue
        for widget in widgets:
            if not isinstance(widget, dict):
                continue
            if widget.get('widget_type') != 'EXPANDABLE_SECTION':
                continue
            title = _safe_get(widget, ['data', 'title'])
            if title:
                return str(title).strip()
    return ''


def _strip_relative_time(text: str) -> str:
    t = (text or '').strip()
    for _ in range(3):
        m = _RELATIVE_TIME_PREFIX.match(t)
        if not m:
            break
        t = t[m.end():].strip()
    return t


def _split_location_body(text: str) -> List[str]:
    t = _strip_relative_time(text)
    if not t:
        return []
    if t.startswith('در '):
        body = t[3:].strip()
    else:
        idx = t.find(' در ')
        if idx >= 0:
            body = t[idx + 3:].strip()
        else:
            return []
    if not body:
        return []
    return [p.strip() for p in _FA_COMMA.split(body) if p.strip()]


def _looks_like_street(part: str) -> bool:
    s = (part or '').strip()
    if not s:
        return False
    return bool(_STREET_RE.match(s))


def _extract_neighborhood_part(part: str) -> Optional[str]:
    s = (part or '').strip()
    if not s:
        return None
    if s.startswith(_NEIGHBORHOOD_PREFIX):
        name = s[len(_NEIGHBORHOOD_PREFIX):].strip()
        return name or None
    return None


def _labels_equal(a: str, b: str) -> bool:
    return normalize_location_label(a) == normalize_location_label(b) and bool(normalize_location_label(a))


def _parse_headline_parts(
    parts: List[str],
    *,
    city: str,
    district: str,
) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {
        'city': None,
        'district': None,
        'neighborhood': None,
        'street': None,
    }
    if not parts:
        return out

    remaining = list(parts)
    if city and remaining and _labels_equal(remaining[0], city):
        remaining.pop(0)

    for part in remaining:
        if district and _labels_equal(part, district):
            continue
        nb = _extract_neighborhood_part(part)
        if nb:
            out['neighborhood'] = normalize_location_label(nb)
            continue
        if _looks_like_street(part):
            out['street'] = part.strip()
            continue
    return out


def extract_post_location(
    detail: Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """
    استخراج استان/شهر/منطقه/محله/خیابان از JSON خام دیوار.
    بدون DB، بدون حدس استان از نام شهر، بدون خواندن عنوان تبلیغاتی.
    """
    if not isinstance(detail, dict):
        detail = {}
    filters = filters if isinstance(filters, dict) else {}

    seo = detail.get('seo') if isinstance(detail.get('seo'), dict) else {}
    web_info = seo.get('web_info') if isinstance(seo.get('web_info'), dict) else {}

    city = normalize_location_label(_safe_get(web_info, ['city_persian']))
    if not city:
        city_obj = detail.get('city')
        if isinstance(city_obj, dict):
            city = normalize_location_label(city_obj.get('name'))
    if not city:
        city = normalize_location_label(filters.get('city_name'))

    district = normalize_location_label(_safe_get(web_info, ['district_persian']))

    location_raw_title = _find_location_headline_title(detail)
    parsed = _parse_headline_parts(
        _split_location_body(location_raw_title),
        city=city,
        district=district,
    )

    neighborhood = parsed.get('neighborhood')
    street = parsed.get('street')

    filter_city = normalize_location_label(filters.get('city_name'))
    province = normalize_location_label(filters.get('province_name'))
    if province and filter_city and city and not _labels_equal(filter_city, city):
        province = ''

    sources: List[str] = []
    if province:
        sources.append('filter:province')
    if normalize_location_label(_safe_get(web_info, ['city_persian'])):
        sources.append('seo:city_persian')
    elif isinstance(detail.get('city'), dict) and detail['city'].get('name'):
        sources.append('city.name')
    elif filter_city:
        sources.append('filter:city')
    if district:
        sources.append('seo:district_persian')
    if location_raw_title:
        sources.append('title:expandable_section')
    if street:
        sources.append('title:street')
    if neighborhood:
        sources.append('title:neighborhood')

    return {
        'province': province or None,
        'city': city or None,
        'district': district or None,
        'neighborhood': neighborhood,
        'street': street,
        'location_raw_title': location_raw_title or None,
        'location_sources': ','.join(sources) if sources else None,
    }


def apply_location_to_export_record(
    record: Dict[str, Any],
    location: Dict[str, Optional[str]],
) -> None:
    """افزودن افزایشی فیلدهای موقعیت به ردیف export — بدون overwrite مقادیر معتبر موجود."""
    if not location:
        return

    def _set_if_empty(key: str, value: Optional[str]) -> None:
        v = normalize_location_label(value) if value else ''
        if not v:
            return
        existing = normalize_location_label(record.get(key))
        if existing:
            return
        record[key] = v

    if location.get('province'):
        _set_if_empty('مکان_استان', location['province'])

    if location.get('city'):
        _set_if_empty('مکان_شهر', location['city'])
        _set_if_empty('شهر', location['city'])

    if location.get('district'):
        _set_if_empty('مکان_منطقه', location['district'])
        _set_if_empty('محله', location['district'])

    if location.get('neighborhood'):
        existing_nb = normalize_location_label(record.get('مکان_محله'))
        if not existing_nb:
            record['مکان_محله'] = normalize_location_label(location['neighborhood'])

    if location.get('street'):
        existing_st = str(record.get('مکان_خیابان') or '').strip()
        if not existing_st:
            record['مکان_خیابان'] = str(location['street']).strip()

    if location.get('location_raw_title'):
        existing_raw = str(record.get('مکان_عنوان_نمایشی') or '').strip()
        if not existing_raw:
            record['مکان_عنوان_نمایشی'] = str(location['location_raw_title']).strip()

    if location.get('location_sources'):
        existing_src = str(record.get('مکان_منبع_جزئیات') or '').strip()
        if not existing_src:
            record['مکان_منبع_جزئیات'] = str(location['location_sources']).strip()


def token_from_raw_detail(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ''
    we = raw.get('webengage')
    if isinstance(we, dict):
        tok = str(we.get('token') or '').strip()
        if tok:
            return tok
    return str(raw.get('token') or '').strip()


def location_tokens_agree(item_token: str, raw: Any, record_token: str) -> bool:
    item_token = str(item_token or '').strip()
    record_token = str(record_token or '').strip()
    if not item_token or not record_token or item_token != record_token:
        return False
    raw_token = token_from_raw_detail(raw)
    if raw_token and raw_token != record_token:
        return False
    return True


NEW_MOBILE_LOCATION_COLUMNS = frozenset({
    'مکان_استان',
    'مکان_محله',
    'مکان_خیابان',
    'مکان_عنوان_نمایشی',
    'مکان_منبع_جزئیات',
})

MOBILE_LOCATION_DATA_KEYS = NEW_MOBILE_LOCATION_COLUMNS

_EXISTING_LISTING_STRIP_DATA_KEYS = MOBILE_LOCATION_DATA_KEYS | frozenset({
    'مکان_شهر',
    'مکان_منطقه',
    'مکان_آدرس',
    'مکان_مختصات_lat',
    'مکان_مختصات_lng',
    'مکان_مختصات_اعتبار',
    'شهر',
    'محله',
    'منطقه',
    'آدرس',
    'city',
    'city_persian',
    'district',
    'district_persian',
    'normalized_city',
    'normalized_district',
    'عرض جغرافیایی',
    'طول جغرافیایی',
    'latitude',
    'longitude',
    'lat',
    'lng',
    'نوع مختصات',
    'نقشه_نوع',
    'نقشه_شعاع_محدوده_متر',
    'در شعاع (متر)',
})

MOBILE_LOCATION_SCALAR_KEYS = frozenset({
    'neighborhood',
    'city',
    'latitude',
    'longitude',
})


def fields_for_existing_listing_update(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    برای آگهی موجود در ingest موبایل: فیلدهای مکانی جدید را حذف می‌کند
    تا داده تاریخی کاربر overwrite نشود.
    """
    out = dict(fields)
    for key in MOBILE_LOCATION_SCALAR_KEYS:
        out.pop(key, None)
    data = dict(out.get('data') or {})
    for key in _EXISTING_LISTING_STRIP_DATA_KEYS:
        data.pop(key, None)
    out['data'] = data
    return out
