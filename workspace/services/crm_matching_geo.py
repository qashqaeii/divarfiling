"""نرمال‌سازی و تطبیق موقعیت جغرافیایی برای Matching."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple

# نام‌های جایگزین شناخته‌شده
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

_LOCATION_PREFIXES = (
    'محله ',
    'محدوده ',
    'منطقه ',
    'بخش ',
)

_SEGMENT_SPLIT_RE = re.compile(
    r'[,،؛|\-/–—]+|\s+و\s+',
)


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


def strip_location_prefix(text: str) -> str:
    raw = (text or '').strip()
    for prefix in _LOCATION_PREFIXES:
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
    return raw


def split_location_segments(text: str) -> List[str]:
    """قطعات معنادار از یک رشته موقعیت (شهر، محله ترکیبی، …)."""
    raw = (text or '').strip()
    if not raw:
        return []
    chunks: List[str] = []
    for part in _SEGMENT_SPLIT_RE.split(raw):
        part = strip_location_prefix(part.strip())
        if part:
            chunks.append(part)
    if not chunks:
        chunks = [strip_location_prefix(raw)]
    return chunks


def parse_preferred_areas(areas_text: str) -> List[str]:
    if not areas_text:
        return []
    parts = re.split(r'[,،;\n|/]+', areas_text)
    return [p.strip() for p in parts if p.strip()]


def cities_equivalent(want: str, got: str) -> bool:
    a = canonical_neighborhood_name(want) or normalize_geo_text(want)
    b = canonical_neighborhood_name(got) or normalize_geo_text(got)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4:
        return a in b or b in a
    return False


def _token_pair_equivalent(token: str, loc: str) -> bool:
    if not token or not loc:
        return False
    if token == loc:
        return True
    if len(token) < 3 or len(loc) < 3:
        return False
    if token in loc:
        if len(loc) <= len(token) + 10:
            return True
        return len(token) >= max(3, int(len(loc) * 0.35))
    if loc in token:
        if len(token) <= len(loc) + 10:
            return True
        return len(loc) >= max(3, int(len(token) * 0.35))
    return False


def location_tokens_equivalent(preferred: str, location: str) -> bool:
    """تطبیق محله — با تجزیه رشته‌های ترکیبی مثل «شیراز - محله صیاد»."""
    token = canonical_neighborhood_name(preferred) or normalize_geo_text(preferred)
    if not token:
        return False
    loc_raw = (location or '').strip()
    if not loc_raw:
        return False
    for segment in split_location_segments(loc_raw):
        seg = canonical_neighborhood_name(segment) or normalize_geo_text(segment)
        if _token_pair_equivalent(token, seg):
            return True
    whole = canonical_neighborhood_name(loc_raw) or normalize_geo_text(loc_raw)
    return _token_pair_equivalent(token, whole)


def location_field_values(
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[Sequence[str]] = None,
) -> List[Tuple[str, str]]:
    """جفت (خام، نرمال) برای تمام بخش‌های موقعیت ملک."""
    out: List[Tuple[str, str]] = []
    seen = set()
    candidates: List[str] = []
    for raw in (neighborhood, district, city):
        if raw:
            candidates.extend(split_location_segments(raw))
            candidates.append(raw.strip())
    if extra_values:
        for raw in extra_values:
            if not raw:
                continue
            text = str(raw).strip()
            candidates.extend(split_location_segments(text))
            candidates.append(text)
    for raw in candidates:
        text = (raw or '').strip()
        norm = normalize_geo_text(text)
        if norm and norm not in seen:
            seen.add(norm)
            out.append((text, norm))
    return out


def match_preferred_locations(
    preferred: List[str],
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """OR روی محله‌های ترجیحی — یکی کافی است."""
    fields = location_field_values(
        neighborhood, city, district, extra_values=extra_values,
    )
    if not fields or not preferred:
        return False, ''
    for pref in preferred:
        for raw, _norm in fields:
            if location_tokens_equivalent(pref, raw):
                return True, raw.strip()
    return False, ''


def profile_city_blocks_match(customer_city: str, property_city: str) -> bool:
    """
    Legacy — فقط برای سازگاری import.
    شهر هویتی مخاطب نباید در تطبیق استفاده شود؛ همیشه False.
    """
    return False


def preferred_areas_from_profile(profile) -> List[str]:
    return parse_preferred_areas(getattr(profile, 'areas', '') or '')


def location_match_quality(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[Sequence[str]] = None,
) -> Tuple[float, str, str]:
    """
    امتیاز نرم موقعیت — فقط بر اساس محله‌های ترجیحی (areas)، نه شهر/منطقه هویتی.
    """
    areas = preferred_areas_from_profile(profile)
    if not areas:
        return 0.5, '', 'unknown'

    fields = location_field_values(
        neighborhood, city, district, extra_values=extra_values,
    )
    if not fields:
        return 0.15, 'موقعیت ملک نامشخص', 'unknown'

    matched, label = match_preferred_locations(
        areas, neighborhood, city, district, extra_values=extra_values,
    )
    if matched:
        return 1.0, f'محله {label or areas[0]}', 'exact'
    return 0.15, 'محله متفاوت', 'mismatch'


def listing_data_location_extras(data) -> List[str]:
    if not isinstance(data, dict):
        return []
    out: List[str] = []
    for key in ('محله', 'مکان_محله', 'neighborhood', 'district', 'منطقه', 'مکان'):
        val = data.get(key)
        if val and isinstance(val, str) and val.strip():
            out.append(val.strip())
    return out
