"""نرمال‌سازی و تطبیق موقعیت جغرافیایی برای Matching."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

# نام‌های جایگزین شناخته‌شده — کلید و مقدار هر دو نرمال‌شده ذخیره نمی‌شوند؛ هنگام مقایسه نرمال می‌شوند.
_NEIGHBORHOOD_ALIASES = {
    'سعادت آباد': 'سعادت‌آباد',
    'سعادت اباد': 'سعادت‌آباد',
    'پونک': 'پونک',
    'پونک جنوبی': 'پونک',
    'پونک شمالی': 'پونک',
    'ولنجک': 'ولنجک',
    'زعفرانیه': 'زعفرانیه',
    'نیاوران': 'نیاوران',
    'جردن': 'جردن',
    'آرژانتین': 'جردن',
}

_ARABIC_TO_PERSIAN = str.maketrans({
    'ي': 'ی',
    'ك': 'ک',
    'ة': 'ه',
    'ؤ': 'و',
    'إ': 'ا',
    'أ': 'ا',
    'ٱ': 'ا',
})

_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def normalize_geo_text(value: str) -> str:
    if not value:
        return ''
    text = str(value).strip().translate(_ARABIC_TO_PERSIAN)
    text = text.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
    text = text.replace('\u200c', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def canonical_neighborhood_name(value: str) -> str:
    norm = normalize_geo_text(value)
    if not norm:
        return ''
    for alias, canonical in _NEIGHBORHOOD_ALIASES.items():
        if normalize_geo_text(alias) == norm:
            return normalize_geo_text(canonical)
    return norm


def cities_equivalent(want: str, got: str) -> bool:
    a = canonical_neighborhood_name(want) or normalize_geo_text(want)
    b = canonical_neighborhood_name(got) or normalize_geo_text(got)
    if not a or not b:
        return True
    if a == b:
        return True
    return a in b or b in a


def location_tokens_equivalent(preferred: str, location: str) -> bool:
    """تطبیق محله/منطقه — بدون معادل‌سازی اشتباه دو محله مجاور."""
    token = canonical_neighborhood_name(preferred) or normalize_geo_text(preferred)
    loc = canonical_neighborhood_name(location) or normalize_geo_text(location)
    if not token or not loc:
        return False
    if token == loc:
        return True
    if len(token) < 3 or len(loc) < 3:
        return False
    # زیررشته فقط اگر یکی کاملاً داخل دیگری باشد و طول نزدیک داشته باشند
    if token in loc:
        return len(token) >= max(3, int(len(loc) * 0.45))
    if loc in token:
        return len(loc) >= max(3, int(len(token) * 0.45))
    return False


def match_preferred_locations(
    preferred: List[str],
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> Tuple[bool, str]:
    fields = _location_field_values(neighborhood, city, district)
    if not fields or not preferred:
        return False, ''
    for pref in preferred:
        for raw, _ in fields:
            if not location_tokens_equivalent(pref, raw):
                continue
            if location_tokens_equivalent(pref, neighborhood):
                return True, (neighborhood or raw).strip()
            if location_tokens_equivalent(pref, district):
                return True, (district or raw).strip()
            return True, raw.strip()
    return False, ''


def _location_field_values(
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen = set()
    for raw in (neighborhood, district, city):
        text = (raw or '').strip()
        norm = normalize_geo_text(text)
        if norm and norm not in seen:
            seen.add(norm)
            out.append((text, norm))
    return out


def profile_city_blocks_match(customer_city: str, property_city: str) -> bool:
    """اگر هر دو شهر مشخص و ناسازگار باشند — رد قطعی."""
    want = normalize_geo_text(customer_city or '')
    got = normalize_geo_text(property_city or '')
    if not want or not got:
        return False
    return not cities_equivalent(want, got)


def location_match_quality(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> Tuple[float, str, str]:
    """
    امتیاز نرم موقعیت و برچسب کیفیت: exact | approximate | unknown | mismatch
    """
    areas_text = getattr(profile, 'areas', '') or ''
    areas = [
        p.strip()
        for p in re.split(r'[,،;\n|/]+', areas_text)
        if p.strip()
    ]
    want_district = (getattr(profile, 'district', None) or '').strip()
    customer_city = (getattr(profile, 'city', None) or '').strip()

    if profile_city_blocks_match(customer_city, city):
        return 0.05, 'شهر متفاوت', 'mismatch'

    if not areas and not want_district and not customer_city:
        return 0.5, '', 'unknown'

    fields = _location_field_values(neighborhood, city, district)
    if not fields:
        return 0.15, 'موقعیت ملک نامشخص', 'unknown'

    if areas:
        matched, label = match_preferred_locations(areas, neighborhood, city, district)
        if matched:
            return 1.0, f'محله {label or areas[0]}', 'exact'
    if want_district:
        matched, label = match_preferred_locations([want_district], neighborhood, city, district)
        if matched:
            return 0.85, f'منطقه {label or want_district}', 'approximate'
    if customer_city and cities_equivalent(customer_city, city):
        if areas or want_district:
            return 0.35, f'شهر {city or customer_city}', 'approximate'
        return 0.65, f'شهر {city or customer_city}', 'approximate'

    if areas or want_district:
        return 0.15, 'محله متفاوت', 'mismatch'
    return 0.5, '', 'unknown'
