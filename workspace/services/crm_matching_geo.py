"""نرمال‌سازی و تطبیق موقعیت جغرافیایی برای Matching."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

# سطوح تطبیق (برای امتیاز نرم و ممیزی)
GEO_MATCH_EXACT = 'exact'
GEO_MATCH_ALIAS = 'alias'
GEO_MATCH_STRUCTURED = 'structured'
GEO_MATCH_NONE = 'none'
GEO_MATCH_UNKNOWN = 'unknown'

# وضعیت تطبیق جغرافیایی نرم (Matching V3.3)
LOC_STATUS_EXACT = 'exact_neighborhood'
LOC_STATUS_DISTRICT = 'compatible_district'
LOC_STATUS_STREET = 'verified_street'
LOC_STATUS_UNKNOWN = 'location_unknown'
LOC_STATUS_DIFFERENT = 'location_different'
LOC_STATUS_HINT = 'location_unverified_hint'

# نام‌های جایگزین تأییدشده — بدون fuzzy عمومی
_NEIGHBORHOOD_ALIASES = {
    'سعادت آباد': 'سعادت‌آباد',
    'سعادت اباد': 'سعادت‌آباد',
    'پونک': 'پونک',
    'ولنجک': 'ولنجک',
    'زعفرانیه': 'زعفرانیه',
    'نیاوران': 'نیاوران',
    'جردن': 'جردن',
    'آرژانتین': 'جردن',
    # شیراز — املای رایج / برچسب ترکیبی (نه زیررشتهٔ نام محلهٔ دیگر)
    'محله صیاد': 'صیاد',
    'صیاد شیراز': 'صیاد',
    'محله عدالت': 'عدالت',
    'عدالت شیراز': 'عدالت',
    'محله آپادانا': 'آپادانا',
    'آپادانا شیراز': 'آپادانا',
}

_MAJOR_SEARCH_CITIES = frozenset({
    'تهران', 'شیراز', 'اصفهان', 'مشهد', 'تبریز', 'کرج', 'اهواز', 'قم',
    'رشت', 'کرمان', 'یزد', 'همدان', 'اراک', 'قزوین', 'زاهدان', 'کرمانشاه',
})

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

# جداکنندهٔ متن موقعیت — نقطه فقط وقتی جداکننده است، نه اعشار
_SEGMENT_SPLIT_RE = re.compile(
    r'[,،؛|\-/–—\n]+|(?<![0-9۰-۹])\.(?![0-9۰-۹])|\s+و\s+',
)

_AREA_LIST_SPLIT_RE = re.compile(
    r'[,،;\n|/]+|(?<![0-9۰-۹])\.(?![0-9۰-۹])',
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
    # «محدوده ی معلم» / «محدوده‌ی صیاد»
    if raw.startswith('ی '):
        raw = raw[2:].strip()
    elif raw.startswith('ي '):
        raw = raw[2:].strip()
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
    parts = _AREA_LIST_SPLIT_RE.split(areas_text)
    out: List[str] = []
    for p in parts:
        chunk = strip_location_prefix(p.strip())
        if chunk:
            out.append(chunk)
    return out


@dataclass(frozen=True)
class AreaPreference:
    """یک ترجیح محله — با شهر هدف اختیاری (مثلاً شیراز + صیاد)."""
    raw: str
    neighborhood: str
    city_hint: str = ''


def parse_area_preference(area_text: str) -> AreaPreference:
    raw = (area_text or '').strip()
    if not raw:
        return AreaPreference(raw='', neighborhood='')
    segments = split_location_segments(raw)
    if len(segments) >= 2:
        head = normalize_geo_text(segments[0])
        if head in _MAJOR_SEARCH_CITIES:
            tail = strip_location_prefix(segments[-1].strip())
            return AreaPreference(raw=raw, neighborhood=tail or segments[-1].strip(), city_hint=head)
    return AreaPreference(raw=raw, neighborhood=raw)


def area_preferences_from_profile(profile) -> List[AreaPreference]:
    return [parse_area_preference(p) for p in preferred_areas_from_profile(profile)]


def _property_city_matches_hint(city_hint: str, property_city: str) -> bool:
    if not city_hint:
        return True
    got = normalize_geo_text(property_city or '')
    if not got:
        return True
    return cities_equivalent(city_hint, got)


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


def profile_identity_city(profile) -> str:
    """شهر ثبت‌شده روی کارت مخاطب — هویتی؛ در فیلتر سخت محله استفاده نمی‌شود."""
    return normalize_geo_text(getattr(profile, 'city', None) or '')


def profile_search_city_hint(profile) -> str:
    """
    شهر هدف جستجو — فقط وقتی در areas به‌صورت صریح آمده (مثلاً «شیراز - صیاد»).
    city هویتی مخاطب اینجا لحاظ نمی‌شود.
    """
    for pref in area_preferences_from_profile(profile):
        if pref.city_hint:
            return pref.city_hint
    return ''


def property_conflicts_search_city_hint(profile, property_city: str) -> bool:
    """True اگر همه ترجیحات دارای city_hint با شهر ملک ناسازگار باشند."""
    prefs = [p for p in area_preferences_from_profile(profile) if p.city_hint]
    if not prefs:
        return False
    got = normalize_geo_text(property_city or '')
    if not got:
        return False
    return all(not cities_equivalent(p.city_hint, got) for p in prefs)


def _token_pair_match_level(token: str, loc: str) -> str:
    """تطبیق دو توکن نرمال‌شده — بدون substring عمومی."""
    if not token or not loc:
        return GEO_MATCH_NONE
    if len(token) < 3 or len(loc) < 3:
        return GEO_MATCH_NONE
    if loc.startswith(token + ' ') or loc.startswith(token + '-'):
        return GEO_MATCH_NONE
    if token.startswith(loc + ' ') or token.startswith(loc + '-'):
        return GEO_MATCH_NONE
    if token == loc:
        return GEO_MATCH_EXACT
    token_canon = canonical_neighborhood_name(token) or token
    loc_canon = canonical_neighborhood_name(loc) or loc
    if token_canon == loc_canon:
        return GEO_MATCH_ALIAS
    return GEO_MATCH_NONE


def location_token_match_level(preferred: str, location: str) -> Tuple[str, str]:
    """
    بهترین سطح تطبیق برای یک ترجیح و یک رشته موقعیت.
    برمی‌گرداند: (level, برچسب خام)
    """
    token = canonical_neighborhood_name(preferred) or normalize_geo_text(preferred)
    if not token:
        return GEO_MATCH_NONE, ''
    loc_raw = (location or '').strip()
    if not loc_raw:
        return GEO_MATCH_NONE, ''
    best = GEO_MATCH_NONE
    best_label = ''
    segments = split_location_segments(loc_raw)
    multi = len(segments) > 1
    for segment in segments:
        seg = canonical_neighborhood_name(segment) or normalize_geo_text(segment)
        level = _token_pair_match_level(token, seg)
        if level == GEO_MATCH_NONE:
            continue
        if multi and level in (GEO_MATCH_EXACT, GEO_MATCH_ALIAS):
            level = GEO_MATCH_STRUCTURED
        if best == GEO_MATCH_NONE or level == GEO_MATCH_EXACT:
            best = level
            best_label = segment.strip()
            if best == GEO_MATCH_EXACT:
                break
    if best != GEO_MATCH_NONE:
        return best, best_label
    whole = canonical_neighborhood_name(loc_raw) or normalize_geo_text(loc_raw)
    level = _token_pair_match_level(token, whole)
    return level, loc_raw.strip() if level != GEO_MATCH_NONE else ''


def _token_pair_equivalent(token: str, loc: str) -> bool:
    return _token_pair_match_level(token, loc) != GEO_MATCH_NONE


def location_tokens_equivalent(preferred: str, location: str) -> bool:
    """تطبیق محله — با تجزیه رشته‌های ترکیبی مثل «شیراز - محله صیاد»."""
    level, _ = location_token_match_level(preferred, location)
    return level != GEO_MATCH_NONE


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
    """OR روی محله‌های ترجیحی — شهر و محله در ترجیح ترکیبی جداگانه."""
    fields = location_field_values(
        neighborhood, city, district, extra_values=extra_values,
    )
    if not fields or not preferred:
        return False, ''
    for raw_pref in preferred:
        pref = parse_area_preference(raw_pref)
        if not _property_city_matches_hint(pref.city_hint, city):
            continue
        hood = pref.neighborhood or raw_pref
        for raw, _norm in fields:
            if location_tokens_equivalent(hood, raw):
                return True, raw.strip()
    return False, ''


def match_area_preferences_for_property(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """همان منطق فیلتر سخت — OR روی AreaPreference."""
    prefs = area_preferences_from_profile(profile)
    if not prefs:
        return True, ''
    fields = location_field_values(
        neighborhood, city, district, extra_values=extra_values,
    )
    if not fields:
        return False, ''
    for pref in prefs:
        if not _property_city_matches_hint(pref.city_hint, city):
            continue
        hood = pref.neighborhood or pref.raw
        for raw, _norm in fields:
            if location_tokens_equivalent(hood, raw):
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


@dataclass(frozen=True)
class GeographicMatchResult:
    status: str
    confidence: str
    reason: str
    hood_s: float
    geo_level: str


def _best_match_level_for_prefs(
    profile,
    fields: List[Tuple[str, str]],
    *,
    property_city: str,
) -> Tuple[str, str]:
    areas = preferred_areas_from_profile(profile)
    best_level = GEO_MATCH_NONE
    best_label = ''
    for raw_pref in areas:
        pref = parse_area_preference(raw_pref)
        if not _property_city_matches_hint(pref.city_hint, property_city):
            continue
        hood = pref.neighborhood or raw_pref
        for raw, _norm in fields:
            level, label = location_token_match_level(hood, raw)
            if level == GEO_MATCH_NONE:
                continue
            if best_level == GEO_MATCH_NONE or level == GEO_MATCH_EXACT:
                best_level = level
                best_label = label or raw.strip()
                if best_level == GEO_MATCH_EXACT:
                    return best_level, best_label
    return best_level, best_label


def _has_verifiable_neighborhood_evidence(
    neighborhood: str,
    district: str,
    extra_values: Optional[Sequence[str]],
) -> bool:
    if (neighborhood or '').strip():
        return True
    if (district or '').strip():
        return True
    if extra_values:
        return any(str(v).strip() for v in extra_values)
    return False


def evaluate_soft_location_match(
    profile,
    *,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[Sequence[str]] = None,
    trusted_street: str = '',
    unverified_hints: Optional[Sequence[str]] = None,
) -> GeographicMatchResult:
    """
    ترجیح محله نرم — بدون حذف قطعی؛ اولویت در hood_s و status.
    """
    areas = preferred_areas_from_profile(profile)
    if not areas:
        return GeographicMatchResult(
            status='',
            confidence='none',
            reason='',
            hood_s=0.5,
            geo_level=GEO_MATCH_UNKNOWN,
        )

    nb_fields = location_field_values(
        neighborhood, '', '', extra_values=extra_values,
    )
    nb_level, nb_label = _best_match_level_for_prefs(profile, nb_fields, property_city=city)
    if nb_level in (GEO_MATCH_EXACT, GEO_MATCH_ALIAS):
        return GeographicMatchResult(
            status=LOC_STATUS_EXACT,
            confidence='high',
            reason=f'محله {nb_label or areas[0]}',
            hood_s=1.0,
            geo_level=nb_level,
        )
    if nb_level == GEO_MATCH_STRUCTURED:
        return GeographicMatchResult(
            status=LOC_STATUS_DISTRICT,
            confidence='medium',
            reason=f'محدوده {nb_label or district or areas[0]}',
            hood_s=0.82,
            geo_level=GEO_MATCH_STRUCTURED,
        )

    dist_fields = location_field_values('', '', district, extra_values=extra_values)
    dist_level, dist_label = _best_match_level_for_prefs(profile, dist_fields, property_city=city)
    if dist_level in (GEO_MATCH_EXACT, GEO_MATCH_ALIAS, GEO_MATCH_STRUCTURED):
        return GeographicMatchResult(
            status=LOC_STATUS_DISTRICT,
            confidence='medium',
            reason=f'محدوده {dist_label or district or areas[0]}',
            hood_s=0.82,
            geo_level=GEO_MATCH_STRUCTURED,
        )

    street = (trusted_street or '').strip()
    if street:
        street_fields = location_field_values(street, '', '', extra_values=None)
        st_level, st_label = _best_match_level_for_prefs(
            profile, street_fields, property_city=city,
        )
        if st_level in (GEO_MATCH_EXACT, GEO_MATCH_ALIAS):
            return GeographicMatchResult(
                status=LOC_STATUS_STREET,
                confidence='medium',
                reason=f'خیابان {st_label or street}',
                hood_s=0.78,
                geo_level=GEO_MATCH_STRUCTURED,
            )

    hints = [str(h).strip() for h in (unverified_hints or []) if str(h).strip()]
    if hints:
        hint_fields = location_field_values('', '', '', extra_values=hints)
        hint_level, hint_label = _best_match_level_for_prefs(
            profile, hint_fields, property_city=city,
        )
        if hint_level != GEO_MATCH_NONE:
            return GeographicMatchResult(
                status=LOC_STATUS_HINT,
                confidence='low',
                reason='نشانه موقعیت در عنوان — نیاز به بررسی',
                hood_s=0.38,
                geo_level=GEO_MATCH_NONE,
            )

    if _has_verifiable_neighborhood_evidence(neighborhood, district, extra_values):
        return GeographicMatchResult(
            status=LOC_STATUS_DIFFERENT,
            confidence='medium',
            reason='محله متفاوت از ترجیح',
            hood_s=0.22,
            geo_level=GEO_MATCH_NONE,
        )

    return GeographicMatchResult(
        status=LOC_STATUS_UNKNOWN,
        confidence='low',
        reason='موقعیت دقیق نامشخص',
        hood_s=0.5,
        geo_level=GEO_MATCH_UNKNOWN,
    )


def location_match_quality(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[Sequence[str]] = None,
    trusted_street: str = '',
    unverified_hints: Optional[Sequence[str]] = None,
) -> Tuple[float, str, str]:
    """سازگاری قدیمی — خروجی از evaluate_soft_location_match."""
    res = evaluate_soft_location_match(
        profile,
        neighborhood=neighborhood,
        city=city,
        district=district,
        extra_values=extra_values,
        trusted_street=trusted_street,
        unverified_hints=unverified_hints,
    )
    return res.hood_s, res.reason, res.geo_level


def listing_data_location_extras(data) -> List[str]:
    """سازگاری قدیمی — فقط data dict؛ برای تطبیق از listing_structured_location_extras استفاده کنید."""
    if not isinstance(data, dict):
        return []
    return _structured_values_from_data(data, title_neighborhood_untrusted=True)


_TITLE_DERIVED_SOURCES = frozenset({
    'title:expandable_section',
    'title:street',
    'title:neighborhood',
})


def _location_source_parts(data: dict) -> set:
    raw = str(data.get('مکان_منبع_جزئیات') or data.get('location_sources') or '')
    return {p.strip().lower() for p in raw.split(',') if p.strip()}


def _has_title_location_sources(sources: set) -> bool:
    return bool(sources & _TITLE_DERIVED_SOURCES)


def listing_trusted_neighborhood(listing) -> str:
    """
    ستون neighborhood فقط وقتی معتبر است که منبع عنوان‌محور نباشد.
    (row_to_listing_fields گاهی منطقه را در neighborhood می‌گذارد — جداگانه در district.)
    """
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    sources = _location_source_parts(data)
    raw = (getattr(listing, 'neighborhood', None) or '').strip()
    if not raw:
        return ''
    if _has_title_location_sources(sources):
        return ''
    city_norm = normalize_geo_text(getattr(listing, 'city', '') or '')
    if city_norm and normalize_geo_text(raw) == city_norm:
        return ''
    return raw


def listing_trusted_street(listing) -> str:
    """خیابان با منبع غیرعنوان — title:street به‌تنهایی معتبر نیست."""
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    sources = _location_source_parts(data)
    raw = str(data.get('مکان_خیابان') or data.get('خیابان') or '').strip()
    if not raw:
        return ''
    if not sources or sources <= _TITLE_DERIVED_SOURCES:
        return ''
    return raw


def listing_unverified_location_hints(listing) -> List[str]:
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    if not _has_title_location_sources(_location_source_parts(data)):
        return []
    hints: List[str] = []
    for key in ('مکان_محله', 'محله', 'مکان_خیابان', 'خیابان'):
        val = str(data.get(key) or '').strip()
        if val:
            hints.append(val)
    nb_col = (getattr(listing, 'neighborhood', None) or '').strip()
    if nb_col:
        hints.append(nb_col)
    out: List[str] = []
    seen: set = set()
    for h in hints:
        norm = normalize_geo_text(h)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(h)
    return out


def _structured_values_from_data(data: dict, *, title_neighborhood_untrusted: bool) -> List[str]:
    out: List[str] = []
    seen: set = set()
    sources = _location_source_parts(data)

    def add(val) -> None:
        text = (val or '').strip() if isinstance(val, str) else ''
        if not text:
            return
        norm = normalize_geo_text(text)
        if not norm or norm in seen:
            return
        seen.add(norm)
        out.append(text)

    if not title_neighborhood_untrusted:
        for key in ('مکان_محله', 'محله', 'neighborhood'):
            add(data.get(key))

    # منطقه ساختاریافته — نه خیابان (title:street نباید محله تلقی شود)
    for key in ('منطقه', 'مکان_منطقه', 'district', 'district_persian', 'normalized_district'):
        add(data.get(key))

    return out


def listing_structured_location_extras(listing) -> List[str]:
    """
    شواهد ساختاریافته برای فیلتر محله.
    ingest: extract_post_location → apply_location_to_export_record → row_to_listing_fields
    مکان_محله در Listing.data؛ ستون neighborhood اغلب از محله/مکان_منطقه alias.
    """
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    sources = _location_source_parts(data)
    title_nb_untrusted = _has_title_location_sources(sources)
    extras = _structured_values_from_data(data, title_neighborhood_untrusted=title_nb_untrusted)
    if title_nb_untrusted:
        trusted_nb = normalize_geo_text(str(data.get('مکان_محله') or ''))
        if trusted_nb:
            extras = [v for v in extras if normalize_geo_text(v) != trusted_nb]
        for key in ('محله', 'neighborhood'):
            val = normalize_geo_text(str(data.get(key) or ''))
            if val:
                extras = [v for v in extras if normalize_geo_text(v) != val]
    return extras


def listing_matching_district(listing) -> str:
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    for key in ('منطقه', 'مکان_منطقه', 'district', 'district_persian', 'normalized_district'):
        val = data.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ''


def listing_location_evidence_level(listing) -> str:
    """structured | partial | none — برای ممیزی."""
    data = listing.data if isinstance(getattr(listing, 'data', None), dict) else {}
    sources = _location_source_parts(data)
    if listing_trusted_neighborhood(listing):
        return 'structured'
    extras = listing_structured_location_extras(listing)
    if extras:
        return 'structured'
    if sources:
        return 'partial'
    if data.get('مکان_شهر') or data.get('شهر') or (listing.city or '').strip():
        return 'partial'
    return 'none'
