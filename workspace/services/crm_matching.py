"""تطبیق هوشمند مخاطب با املاک CRM و آگهی‌های فایلینگ دیوار."""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models import Q

from workspace.constants import (
    BUILDER_BUY_PROPERTY_TYPES,
    BUILDER_SELL_PROPERTY_TYPES,
    LEAD_TYPES,
)
from workspace.models import CRMProperty, Customer, Listing
from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    listing_advertiser_display,
    listing_advertiser_signal,
    property_advertiser_display,
)
from workspace.services.crm_matching_geo import (
    listing_data_location_extras,
    listing_matching_district,
    listing_structured_location_extras,
    listing_trusted_neighborhood,
    listing_trusted_makan_mahalle,
    listing_trusted_street,
    listing_structured_district_extras,
    listing_unverified_location_hints,
    location_field_values,
    evaluate_soft_location_match,
    location_tokens_equivalent,
    match_preferred_locations,
    preferred_areas_from_profile,
    property_conflicts_search_city_hint,
    match_area_preferences_for_property,
)
from workspace.services.crm_matching_prefilter import (
    apply_area_max_prefilter,
    apply_area_min_prefilter,
    apply_int_max_prefilter,
    apply_int_min_prefilter,
)
from workspace.services.crm_matching_types import (
    infer_listing_property_type,
    infer_listing_property_type_detail,
)
from workspace.services.crm_matching_eval import (
    DimensionScores,
    MATCH_TIER_INSUFFICIENT,
    classify_match_tier,
    compute_match_score,
    contact_meaningful_for_property_suggestion,
    evaluation_to_result_fields,
    index_sort_score,
)
from workspace.services.crm_matching_rank import compute_relevance_rank
from workspace.services.customer_search_property_types import customer_search_property_types_restricted
from workspace.services.formatting import format_toman

MATCH_TYPES = {
    'خریدار', 'مستاجر', 'متقاضی خرید', 'متقاضی اجاره', 'سرنخ', 'سرمایه‌گذار', 'سازنده',
}

# پیش‌فرض انعطاف‌پذیری تطبیق — قابل تنظیم per-contact در matching_tolerance_percent.
DEFAULT_MATCHING_TOLERANCE_PERCENT = 20
MATCHING_TOLERANCE_MIN_PERCENT = 0
MATCHING_TOLERANCE_MAX_PERCENT = 50
MATCHING_TOLERANCE_STEP_PERCENT = 5
# نسبت پیش‌فرض (۲۰٪) — برای سازگاری با کدهای قدیمی.
RANGE_TOLERANCE = DEFAULT_MATCHING_TOLERANCE_PERCENT / 100.0


def normalize_matching_tolerance_percent(
    value,
    *,
    default: int = DEFAULT_MATCHING_TOLERANCE_PERCENT,
) -> int:
    """اعتبارسنجی انعطاف‌پذیری: ۰–۵۰٪ با گام ۵٪."""
    if value is None or value == '':
        return default
    try:
        pct = int(value)
    except (TypeError, ValueError):
        raise ValueError('انعطاف‌پذیری باید عدد باشد.')
    if pct < MATCHING_TOLERANCE_MIN_PERCENT or pct > MATCHING_TOLERANCE_MAX_PERCENT:
        raise ValueError(
            f'انعطاف‌پذیری باید بین {MATCHING_TOLERANCE_MIN_PERCENT} '
            f'تا {MATCHING_TOLERANCE_MAX_PERCENT} درصد باشد.'
        )
    if pct % MATCHING_TOLERANCE_STEP_PERCENT != 0:
        raise ValueError(
            f'انعطاف‌پذیری باید مضرب {MATCHING_TOLERANCE_STEP_PERCENT} درصد باشد.'
        )
    return pct


def profile_tolerance_ratio(profile) -> float:
    """نسبت تلورانس (۰.۰–۰.۵) از پروفایل مخاطب."""
    raw = getattr(profile, 'matching_tolerance_percent', None)
    try:
        pct = normalize_matching_tolerance_percent(raw)
    except ValueError:
        pct = DEFAULT_MATCHING_TOLERANCE_PERCENT
    return pct / 100.0


def customer_matching_tolerance_percent(customer: Customer) -> int:
    try:
        return normalize_matching_tolerance_percent(
            getattr(customer, 'matching_tolerance_percent', None),
        )
    except ValueError:
        return DEFAULT_MATCHING_TOLERANCE_PERCENT


# اندازه صفحه نمایش — نه سقف اسکن کاندیدا
MATCH_PAGE_SIZE_DEFAULT = 24
MATCH_RESULT_LIMIT = MATCH_PAGE_SIZE_DEFAULT
MATCH_RESULT_LIMIT_BROAD = 36
MATCH_CRM_MIN_SCORE = 25
MATCH_DIVAR_MIN_SCORE = 30
MATCH_CRM_MIN_SCORE_BROAD = 18
MATCH_DIVAR_MIN_SCORE_BROAD = 22
BROAD_BUDGET_SPAN_RATIO = 8.0

BUILDER_MATCH_INTENTS = {
    'acquisition': {
        'id': 'acquisition',
        'title': 'تأمین پروژه — خرید زمین و کلنگی',
        'hint': 'ویلا، کلنگی و زمین مناسب توسعه پروژه',
        'intent_label': 'تأمین پروژه',
    },
    'supply': {
        'id': 'supply',
        'title': 'بازار آپارتمان — فروش و مقایسه',
        'hint': 'آپارتمان‌های بازار در محدوده فروش سازنده',
        'intent_label': 'بازار آپارتمان',
    },
}

_PROPERTY_TYPE_MAP = {
    'آپارتمان': {'آپارتمان'},
    'ویلا': {'ویلا'},
    'کلنگی': {'کلنگی'},
    'اداری': {'اداری', 'دفتر'},
    'مغازه': {'مغازه', 'تجاری'},
    'زمین': {'زمین', 'کلنگی'},
}


def parse_builder_buy_types(value: str) -> List[str]:
    if not value:
        return list(BUILDER_BUY_PROPERTY_TYPES)
    return [t.strip() for t in value.replace('،', ',').split(',') if t.strip()]


def is_builder_customer(customer: Customer) -> bool:
    return customer.customer_type == 'سازنده'


def _parse_areas(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r'[,،;\n|/]+', text)
    return [p.strip() for p in parts if p.strip()]


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def _within_range_tolerance(
    value: Optional[float],
    lo: Optional[float],
    hi: Optional[float],
    *,
    tolerance: float = RANGE_TOLERANCE,
) -> bool:
    """True اگر مقدار داخل بازه باشد یا حداکثر به اندازه tolerance خارج از آن."""
    if value is None:
        return True
    if lo is None and hi is None:
        return True
    if lo is not None and value < lo:
        return value >= lo * (1 - tolerance)
    if hi is not None and value > hi:
        return value <= hi * (1 + tolerance)
    return True


def _profile_area_eligible(profile, area: Optional[float]) -> bool:
    if area is None or area <= 0:
        return True
    tol = profile_tolerance_ratio(profile)
    return _within_range_tolerance(area, profile.min_area, profile.max_area, tolerance=tol)


def _profile_budget_eligible(
    profile,
    *,
    sale_price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    is_rent: bool = False,
) -> bool:
    tol = profile_tolerance_ratio(profile)
    if is_rent:
        if not _within_range_tolerance(deposit, profile.deposit_min, profile.deposit_max, tolerance=tol):
            return False
        if not _within_range_tolerance(rent, profile.rent_min, profile.rent_max, tolerance=tol):
            return False
        return True
    return _within_range_tolerance(sale_price, profile.budget_min, profile.budget_max, tolerance=tol)


def _profile_allowed_property_types(profile) -> Optional[Set[str]]:
    """مجموعه نوع‌های مجاز؛ None یعنی محدودیتی از سمت کاربر نیست."""
    allowed: Set[str] = set(getattr(profile, 'allowed_types', None) or [])
    if allowed:
        expanded: Set[str] = set()
        for item in allowed:
            expanded |= _PROPERTY_TYPE_MAP.get(item, {item})
        return expanded
    types_raw = getattr(profile, 'property_types', None)
    if isinstance(types_raw, list) and types_raw:
        expanded: Set[str] = set()
        for item in types_raw:
            text = (item or '').strip()
            if not text or text == 'سایر':
                continue
            expanded |= _PROPERTY_TYPE_MAP.get(text, {text})
        return expanded if expanded else None
    want = (getattr(profile, 'property_type', None) or '').strip()
    if not want or want == 'سایر':
        return None
    return set(_PROPERTY_TYPE_MAP.get(want, {want}))


def _profile_property_type_eligible(profile, prop_type: Optional[str]) -> bool:
    allowed = _profile_allowed_property_types(profile)
    if allowed is None:
        return True
    if not prop_type:
        return False
    return prop_type in allowed


def _location_hay(neighborhood: str = '', city: str = '', district: str = '') -> str:
    return _norm(f'{neighborhood or ""} {city or ""} {district or ""}')


def _location_field_values(
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> List[Tuple[str, str]]:
    """جفت (مقدار خام، نرمال‌شده) برای فیلدهای غیرخالی موقعیت."""
    out: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for raw in (neighborhood, district, city):
        text = (raw or '').strip()
        norm = _norm(text)
        if norm and norm not in seen:
            seen.add(norm)
            out.append((text, norm))
    return out


def _location_tokens_equivalent(preferred: str, location: str) -> bool:
    return location_tokens_equivalent(preferred, location)


def _match_preferred_locations(
    preferred: List[str],
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> Tuple[bool, str]:
    return match_preferred_locations(preferred, neighborhood, city, district)


def _profile_search_city_eligible(profile, city: str = '') -> bool:
    """فیلتر سخت فقط برای شهر هدف صریح در areas — نه city هویتی مخاطب."""
    return not property_conflicts_search_city_hint(profile, city or '')


def _profile_neighborhood_eligible(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[List[str]] = None,
) -> bool:
    """سازگاری API — دیگر فیلتر حذف قطعی نیست؛ همیشه True."""
    return True


def _profile_neighborhood_matches_preference(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    extra_values: Optional[List[str]] = None,
) -> bool:
    """آیا ملک با یکی از محله‌های ترجیحی هم‌پوشانی دارد — برای ممیزی."""
    areas = preferred_areas_from_profile(profile)
    if not areas:
        return True
    matched, _ = match_area_preferences_for_property(
        profile,
        neighborhood=neighborhood,
        city=city,
        district=district,
        extra_values=extra_values,
    )
    return matched


def _parse_int_feature(value) -> Optional[int]:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text or text == '-':
        return None
    if 'همکف' in text or 'هم کف' in text:
        return 0
    digits = re.sub(r'[^\d-]', '', text)
    if not digits or digits == '-':
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _int_range_eligible(value: Optional[int], lo: Optional[int], hi: Optional[int]) -> bool:
    if lo is None and hi is None:
        return True
    if value is None:
        return True
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


def _amenity_required_eligible(want: bool, has: Optional[bool]) -> bool:
    if not want:
        return True
    if has is False:
        return False
    return True


def _profile_rooms_bounds(profile) -> Tuple[Optional[int], Optional[int]]:
    lo = getattr(profile, 'rooms_min', None)
    hi = getattr(profile, 'rooms_max', None)
    if lo is not None or hi is not None:
        return lo, hi
    legacy = _parse_int_feature(getattr(profile, 'rooms', None))
    if legacy is not None:
        return legacy, legacy
    return None, None


def _profile_detail_eligible(
    profile,
    *,
    rooms: Optional[str] = None,
    build_year: Optional[int] = None,
    floor: Optional[int] = None,
    has_parking: Optional[bool] = None,
    has_storage: Optional[bool] = None,
    has_elevator: Optional[bool] = None,
) -> bool:
    rooms_lo, rooms_hi = _profile_rooms_bounds(profile)
    if not _int_range_eligible(_parse_int_feature(rooms), rooms_lo, rooms_hi):
        return False
    if not _int_range_eligible(
        _parse_int_feature(build_year),
        getattr(profile, 'year_min', None),
        getattr(profile, 'year_max', None),
    ):
        return False
    if not _int_range_eligible(
        _parse_int_feature(floor),
        getattr(profile, 'floor_min', None),
        getattr(profile, 'floor_max', None),
    ):
        return False
    if not _amenity_required_eligible(bool(getattr(profile, 'want_parking', False)), has_parking):
        return False
    if not _amenity_required_eligible(bool(getattr(profile, 'want_storage', False)), has_storage):
        return False
    if not _amenity_required_eligible(bool(getattr(profile, 'want_elevator', False)), has_elevator):
        return False
    return True


def _profile_criteria_eligible(
    profile,
    *,
    area: Optional[float],
    prop_type: Optional[str] = None,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
    location_extras: Optional[List[str]] = None,
    rooms: Optional[str] = None,
    build_year: Optional[int] = None,
    floor: Optional[int] = None,
    has_parking: Optional[bool] = None,
    has_storage: Optional[bool] = None,
    has_elevator: Optional[bool] = None,
    sale_price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    is_rent: bool = False,
) -> bool:
    """فیلتر سخت: بودجه، متراژ، نوع، شهر هدف صریح و جزئیات ترجیحات."""
    if not _profile_property_type_eligible(profile, prop_type):
        return False
    if not _profile_search_city_eligible(profile, city):
        return False
    if not _profile_area_eligible(profile, area):
        return False
    if not _profile_detail_eligible(
        profile,
        rooms=rooms,
        build_year=build_year,
        floor=floor,
        has_parking=has_parking,
        has_storage=has_storage,
        has_elevator=has_elevator,
    ):
        return False
    return _profile_budget_eligible(
        profile,
        sale_price=sale_price,
        deposit=deposit,
        rent=rent,
        is_rent=is_rent,
    )


def _area_match_profile(profile, area: Optional[float]) -> Tuple[float, str]:
    if area is None or area <= 0:
        return 0.5, ''
    min_a = profile.min_area
    max_a = profile.max_area
    if min_a is None and max_a is None:
        return 0.5, ''
    if min_a is not None and area < min_a:
        ratio = max(0, 1 - (min_a - area) / max(min_a, 1))
        return ratio * 0.5, f'متراژ کمتر از {min_a}'
    if max_a is not None and area > max_a:
        ratio = max(0, 1 - (area - max_a) / max(max_a, 1))
        return ratio * 0.5, f'متراژ بیشتر از {max_a}'
    return 1.0, f'متراژ {int(area)} متر'


def _neighborhood_match_profile(
    profile,
    neighborhood: str,
    city: str,
    district: str = '',
    extra_values: Optional[List[str]] = None,
    trusted_street: str = '',
    unverified_hints: Optional[List[str]] = None,
) -> Tuple[float, str, 'GeographicMatchResult']:
    geo = evaluate_soft_location_match(
        profile,
        neighborhood=neighborhood,
        city=city,
        district=district,
        extra_values=extra_values,
        trusted_street=trusted_street,
        unverified_hints=unverified_hints,
    )
    return geo.hood_s, geo.reason, geo


def _rooms_match_profile(profile, rooms: str) -> Tuple[float, str]:
    lo, hi = _profile_rooms_bounds(profile)
    got = _parse_int_feature(rooms)
    if lo is None and hi is None:
        return 0.5, ''
    if got is None:
        return 0.4, ''
    if (lo is None or got >= lo) and (hi is None or got <= hi):
        label = f'{got} خواب'
        return 1.0, label
    if lo is not None and got < lo:
        gap = lo - got
    else:
        gap = got - (hi or got)
    if gap == 1:
        return 0.55, f'{got} خواب'
    return 0.15, f'{got} خواب'


def _property_type_match_profile(profile, prop_type: str) -> Tuple[float, str]:
    allowed = _profile_allowed_property_types(profile)
    if allowed is not None:
        if prop_type in allowed:
            return 1.0, prop_type
        return 0.1, prop_type
    if not profile.property_type or not prop_type:
        return 0.5, ''
    if profile.property_type == 'سایر':
        return 0.5, prop_type
    if profile.property_type == prop_type:
        return 1.0, prop_type
    return 0.2, prop_type


def _price_match_sale_profile(profile, price: Optional[int]) -> Tuple[float, str]:
    if not price:
        if _profile_has_sale_criteria(profile):
            return 0.05, ''
        return 0.4, ''
    lo, hi = profile.budget_min, profile.budget_max
    if lo is None and hi is None:
        return 0.5, format_toman(price)
    if lo is not None and price < lo:
        gap = (lo - price) / max(lo, 1)
        return max(0, 1 - gap) * 0.6, f'زیر بودجه — {format_toman(price)}'
    if hi is not None and price > hi:
        gap = (price - hi) / max(hi, 1)
        return max(0, 1 - gap) * 0.6, f'بالای بودجه — {format_toman(price)}'
    return 1.0, format_toman(price)


def _price_match_rent_profile(
    profile,
    deposit: Optional[int],
    rent: Optional[int],
) -> Tuple[float, str]:
    parts = []
    score_parts = []

    if deposit is not None:
        lo, hi = profile.deposit_min, profile.deposit_max
        if lo is None and hi is None:
            score_parts.append(0.5)
        elif lo is not None and deposit < lo:
            score_parts.append(max(0, 1 - (lo - deposit) / max(lo, 1)) * 0.6)
        elif hi is not None and deposit > hi:
            score_parts.append(max(0, 1 - (deposit - hi) / max(hi, 1)) * 0.6)
        else:
            score_parts.append(1.0)
        parts.append(f'رهن {format_toman(deposit)}')

    if rent is not None:
        lo, hi = profile.rent_min, profile.rent_max
        if lo is None and hi is None:
            score_parts.append(0.5)
        elif lo is not None and rent < lo:
            score_parts.append(max(0, 1 - (lo - rent) / max(lo, 1)) * 0.6)
        elif hi is not None and rent > hi:
            score_parts.append(max(0, 1 - (rent - hi) / max(hi, 1)) * 0.6)
        else:
            score_parts.append(1.0)
        parts.append(f'اجاره {format_toman(rent)}')

    if not score_parts:
        if _profile_has_rent_criteria(profile):
            return 0.05, ''
        return 0.5, ''
    return sum(score_parts) / len(score_parts), ' · '.join(parts)


def _area_match(customer: Customer, area: Optional[float]) -> Tuple[float, str]:
    return _area_match_profile(customer, area)


def _neighborhood_match(customer: Customer, neighborhood: str, city: str) -> Tuple[float, str]:
    hood_s, hood_note, _geo = _neighborhood_match_profile(customer, neighborhood, city)
    return hood_s, hood_note


def _rooms_match(customer: Customer, rooms: str) -> Tuple[float, str]:
    return _rooms_match_profile(customer, rooms)


def _property_type_match(customer: Customer, prop_type: str) -> Tuple[float, str]:
    return _property_type_match_profile(customer, prop_type)


def _price_match_sale(customer: Customer, price: Optional[int]) -> Tuple[float, str]:
    return _price_match_sale_profile(customer, price)


def _price_match_rent(
    customer: Customer,
    deposit: Optional[int],
    rent: Optional[int],
) -> Tuple[float, str]:
    return _price_match_rent_profile(customer, deposit, rent)


def _is_rent_customer(customer: Customer) -> bool:
    return customer.customer_type in {'مستاجر', 'متقاضی اجاره', 'موجر'}


def _is_rent_profile(profile) -> bool:
    return getattr(profile, 'customer_type', '') in {'مستاجر', 'متقاضی اجاره', 'موجر'}


def _is_sale_customer(customer: Customer) -> bool:
    return customer.customer_type in {
        'خریدار', 'متقاضی خرید', 'فروشنده', 'فروشنده ملک', 'سرمایه‌گذار',
    }


def _profile_has_rent_criteria(profile) -> bool:
    return any(
        getattr(profile, field, None) is not None
        for field in ('deposit_min', 'deposit_max', 'rent_min', 'rent_max')
    )


def _profile_has_sale_criteria(profile) -> bool:
    return getattr(profile, 'budget_min', None) is not None or getattr(profile, 'budget_max', None) is not None


def _budget_sql_bounds(profile, *, tolerance: float = RANGE_TOLERANCE) -> Tuple[Optional[int], Optional[int]]:
    lo = getattr(profile, 'budget_min', None)
    hi = getattr(profile, 'budget_max', None)
    sql_lo = int(lo * (1 - tolerance)) if lo else None
    sql_hi = int(hi * (1 + tolerance)) if hi else None
    return sql_lo, sql_hi


def _deposit_rent_sql_bounds(profile, *, tolerance: float = RANGE_TOLERANCE) -> Dict[str, Optional[int]]:
    out: Dict[str, Optional[int]] = {}
    for field, sql_key in (
        ('deposit_min', 'deposit_lo'),
        ('deposit_max', 'deposit_hi'),
        ('rent_min', 'rent_lo'),
        ('rent_max', 'rent_hi'),
    ):
        val = getattr(profile, field, None)
        if val is None:
            out[sql_key] = None
        elif sql_key.endswith('_lo'):
            out[sql_key] = int(val * (1 - tolerance))
        else:
            out[sql_key] = int(val * (1 + tolerance))
    return out


def _customer_has_narrow_detail_prefs(customer: Customer) -> bool:
    return any([
        customer.areas,
        customer.want_parking,
        customer.want_storage,
        customer.want_elevator,
        customer.rooms_min is not None,
        customer.rooms_max is not None,
        customer.year_min is not None,
        customer.year_max is not None,
        customer.floor_min is not None,
        customer.floor_max is not None,
    ])


def _customer_budget_span_ratio(customer: Customer) -> Optional[float]:
    lo = customer.budget_min
    hi = customer.budget_max
    if lo and hi and lo > 0:
        return hi / lo
    return None


def _is_broad_seeker_profile(customer: Customer) -> bool:
    """ترجیحات باز — بودجه گسترده و بدون فیلتر سخت محله/امکانات."""
    if is_builder_customer(customer):
        return False
    if _customer_has_narrow_detail_prefs(customer):
        return False
    span = _customer_budget_span_ratio(customer)
    if span is not None and span >= BROAD_BUDGET_SPAN_RATIO:
        return True
    if customer.min_area is None and customer.max_area is None:
        if not customer_search_property_types_restricted(customer):
            if not customer.budget_min and not customer.budget_max:
                return True
    return False


def _match_tuning(customer: Customer) -> Dict[str, int]:
    broad = _is_broad_seeker_profile(customer)
    return {
        'page_size': MATCH_RESULT_LIMIT_BROAD if broad else MATCH_RESULT_LIMIT,
        'crm_min_score': MATCH_CRM_MIN_SCORE_BROAD if broad else MATCH_CRM_MIN_SCORE,
        'divar_min_score': MATCH_DIVAR_MIN_SCORE_BROAD if broad else MATCH_DIVAR_MIN_SCORE,
    }


def _crm_property_is_rent_listing(prop: CRMProperty) -> bool:
    return (
        prop.deal_mode in {'رهن و اجاره', 'اجاره'}
        and (prop.deposit or prop.monthly_rent)
    )


def _crm_property_is_sale_listing(prop: CRMProperty) -> bool:
    return prop.deal_mode in {'فروش', 'پیش‌فروش'} and bool(prop.sale_price)


def _listing_is_rent_listing(listing: Listing) -> bool:
    return bool(listing.deposit or listing.rent)


def _listing_is_sale_listing(listing: Listing) -> bool:
    return bool(listing.price) and not _listing_is_rent_listing(listing)


def _listing_is_genuine_owner(listing: Listing) -> bool:
    """فقط آگهی مالک واقعی فایلینگ — نه مشاور رسمی و نه مشاور پنهان."""
    return listing_advertiser_signal(listing) == ADVERTISER_SIGNAL_GENUINE_PERSONAL


def _crm_match_compatible(customer: Customer, prop: CRMProperty) -> bool:
    if is_builder_customer(customer):
        return True
    # متقاضی خرید/اجاره قبل از LEAD_TYPES — فقط سرنخ برای هر دو معامله آزاد است.
    if _is_rent_customer(customer):
        return _crm_property_is_rent_listing(prop)
    if _is_sale_customer(customer):
        return _crm_property_is_sale_listing(prop)
    if customer.customer_type == 'سرنخ':
        return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)
    if customer.customer_type == 'مالک':
        if _profile_has_rent_criteria(customer):
            return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)
        return _crm_property_is_sale_listing(prop) or _crm_property_is_rent_listing(prop)
    return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)


def _listing_match_compatible(customer: Customer, listing: Listing) -> bool:
    if is_builder_customer(customer):
        return True
    if _is_rent_customer(customer):
        return _listing_is_rent_listing(listing)
    if _is_sale_customer(customer):
        return _listing_is_sale_listing(listing)
    if customer.customer_type == 'سرنخ':
        return _listing_is_rent_listing(listing) or _listing_is_sale_listing(listing)
    if customer.customer_type == 'مالک':
        if _profile_has_rent_criteria(customer):
            return _listing_is_rent_listing(listing) or _listing_is_sale_listing(listing)
        return _listing_is_sale_listing(listing) or _listing_is_rent_listing(listing)
    return _listing_is_rent_listing(listing) or _listing_is_sale_listing(listing)


def _compute_score(*, price_s: float, area_s: float, hood_s: float, type_s: float, room_s: float) -> int:
    return compute_match_score(
        DimensionScores(
            price_s=price_s, area_s=area_s, hood_s=hood_s, type_s=type_s, room_s=room_s,
        ),
    )


def _builder_supply_profile(customer: Customer):
    return SimpleNamespace(
        budget_min=customer.budget_min,
        budget_max=customer.budget_max,
        deposit_min=customer.deposit_min,
        deposit_max=customer.deposit_max,
        rent_min=customer.rent_min,
        rent_max=customer.rent_max,
        min_area=customer.min_area,
        max_area=customer.max_area,
        matching_tolerance_percent=customer_matching_tolerance_percent(customer),
        rooms=customer.rooms,
        rooms_min=customer.rooms_min,
        rooms_max=customer.rooms_max,
        year_min=customer.year_min,
        year_max=customer.year_max,
        floor_min=customer.floor_min,
        floor_max=customer.floor_max,
        want_parking=customer.want_parking,
        want_storage=customer.want_storage,
        want_elevator=customer.want_elevator,
        areas=customer.areas,
        property_type=customer.property_type or 'آپارتمان',
        allowed_types=set(BUILDER_SELL_PROPERTY_TYPES),
        customer_type=customer.customer_type,
    )


def _builder_acquisition_profile(customer: Customer):
    return SimpleNamespace(
        budget_min=customer.builder_buy_budget_min,
        budget_max=customer.builder_buy_budget_max,
        deposit_min=None,
        deposit_max=None,
        rent_min=None,
        rent_max=None,
        min_area=customer.builder_buy_min_area,
        max_area=customer.builder_buy_max_area,
        matching_tolerance_percent=customer_matching_tolerance_percent(customer),
        rooms=customer.rooms,
        rooms_min=None,
        rooms_max=None,
        year_min=None,
        year_max=None,
        floor_min=None,
        floor_max=None,
        want_parking=False,
        want_storage=False,
        want_elevator=False,
        areas=customer.builder_buy_areas or customer.areas,
        property_type='',
        allowed_types=set(parse_builder_buy_types(customer.builder_buy_property_types)),
        customer_type=customer.customer_type,
    )


def _infer_listing_property_type(listing: Listing) -> str:
    return infer_listing_property_type(listing)


def _listing_type_inference(listing: Listing):
    return infer_listing_property_type_detail(listing)


def _score_crm_property_with_profile(
    profile,
    prop: CRMProperty,
    *,
    match_intent: str = '',
    intent_label: str = '',
) -> Optional[Dict[str, Any]]:
    is_rent_listing = _crm_property_is_rent_listing(prop)
    is_sale_listing = _crm_property_is_sale_listing(prop)
    rent_customer = _is_rent_profile(profile)

    use_rent_price = is_rent_listing and (rent_customer or not is_sale_listing)
    if not _profile_criteria_eligible(
        profile,
        area=prop.area,
        prop_type=prop.property_type,
        neighborhood=prop.neighborhood or '',
        city=prop.city or '',
        district=prop.district or '',
        location_extras=None,
        rooms=prop.rooms,
        build_year=prop.build_year,
        floor=prop.floor,
        has_parking=prop.has_parking,
        has_storage=prop.has_storage,
        has_elevator=prop.has_elevator,
        sale_price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        is_rent=use_rent_price,
    ):
        return None

    if rent_customer and not is_rent_listing:
        price_s, price_label = 0.0, ''
    elif not rent_customer and is_rent_listing and not is_sale_listing:
        price_s, price_label = 0.0, ''
    elif use_rent_price:
        price_s, price_label = _price_match_rent_profile(profile, prop.deposit, prop.monthly_rent)
    else:
        price_s, price_label = _price_match_sale_profile(profile, prop.sale_price)

    area_s, area_note = _area_match_profile(profile, prop.area)
    hood_s, hood_note, geo = _neighborhood_match_profile(
        profile,
        prop.neighborhood or '',
        prop.city or '',
        prop.district or '',
        extra_values=None,
    )
    type_s, type_note = _property_type_match_profile(profile, prop.property_type)
    room_s, room_note = _rooms_match_profile(profile, prop.rooms)

    dims = DimensionScores(
        price_s=price_s,
        area_s=area_s,
        hood_s=hood_s,
        type_s=type_s,
        room_s=room_s,
        price_label=price_label,
        area_note=area_note,
        hood_note=hood_note,
        type_note=type_note,
        room_note=room_note,
        geo_level=geo.geo_level,
        location_match_status=geo.status,
        location_confidence=geo.confidence,
    )
    type_required = _profile_allowed_property_types(profile) is not None
    evaluation = classify_match_tier(
        profile,
        dims,
        eligible=True,
        is_rent_deal=use_rent_price,
        prop_type_known=bool((prop.property_type or '').strip()),
        prop_type_required=type_required,
    )
    score = evaluation.score
    reasons = evaluation.reasons
    evaluation.property_type_confidence = 'high' if (prop.property_type or '').strip() else 'none'
    evaluation.property_type_source = 'crm'
    relevance_rank = compute_relevance_rank(
        profile,
        dims,
        evaluation,
        is_rent_deal=use_rent_price,
        sale_price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        area=prop.area,
        property_type_confidence=evaluation.property_type_confidence,
        published_at=getattr(prop, 'updated_at', None),
    )

    result = {
        'source': 'crm',
        'id': prop.pk,
        'property_id': prop.pk,
        'token': prop.token or '',
        'title': prop.title,
        'score': score,
        'reasons': reasons[:4],
        'deal_mode': prop.deal_mode,
        'neighborhood': prop.neighborhood or prop.district or '',
        'city': prop.city or '',
        'area': prop.area,
        'rooms': prop.rooms or '',
        'property_type': prop.property_type or '',
        'price_label': price_label or (
            format_toman(prop.monthly_rent or prop.deposit or prop.sale_price)
            if (prop.monthly_rent or prop.deposit or prop.sale_price) else ''
        ),
        'link': prop.link or '',
        'image': (prop.images or [None])[0] if prop.images else '',
        'advertiser': property_advertiser_display(prop.business_type),
    }
    if match_intent:
        result['match_intent'] = match_intent
        result['intent_label'] = intent_label
    result.update(evaluation_to_result_fields(evaluation))
    result['relevance_rank'] = relevance_rank
    return result


def _score_crm_property(customer: Customer, prop: CRMProperty) -> Optional[Dict[str, Any]]:
    return _score_crm_property_with_profile(customer, prop)


def _score_listing_with_profile(
    profile,
    listing: Listing,
    *,
    prop_type: Optional[str] = None,
    match_intent: str = '',
    intent_label: str = '',
) -> Optional[Dict[str, Any]]:
    type_detail = infer_listing_property_type_detail(listing)
    inferred = (prop_type or type_detail.property_type or '').strip()
    is_rent_listing = _listing_is_rent_listing(listing)
    is_sale_listing = _listing_is_sale_listing(listing)
    rent_customer = _is_rent_profile(profile)

    from workspace.services.features import extract_listing_features
    feats = extract_listing_features(listing)
    listing_floor = _parse_int_feature(feats.get('floor'))
    listing_year = _parse_int_feature(feats.get('build_year'))
    listing_rooms = feats.get('rooms') or listing.rooms
    listing_extras = listing_structured_district_extras(listing)
    listing_district = listing_matching_district(listing)
    trusted_neighborhood = listing_trusted_neighborhood(listing) or listing_trusted_makan_mahalle(listing)
    trusted_street = listing_trusted_street(listing)
    location_hints = listing_unverified_location_hints(listing)

    use_rent_price = is_rent_listing and (rent_customer or not is_sale_listing)
    if not _profile_criteria_eligible(
        profile,
        area=listing.area,
        prop_type=inferred,
        neighborhood=trusted_neighborhood,
        city=listing.city or '',
        district=listing_district,
        location_extras=listing_extras,
        rooms=listing_rooms,
        build_year=listing_year,
        floor=listing_floor,
        has_parking=feats.get('parking'),
        has_storage=feats.get('storage'),
        has_elevator=feats.get('elevator'),
        sale_price=listing.price,
        deposit=listing.deposit,
        rent=listing.rent,
        is_rent=use_rent_price,
    ):
        return None

    if rent_customer and not is_rent_listing:
        price_s, price_label = 0.0, ''
    elif not rent_customer and is_rent_listing and not is_sale_listing:
        price_s, price_label = 0.0, ''
    elif use_rent_price:
        price_s, price_label = _price_match_rent_profile(profile, listing.deposit, listing.rent)
    else:
        price_s, price_label = _price_match_sale_profile(profile, listing.price)

    area_s, area_note = _area_match_profile(profile, listing.area)
    hood_s, hood_note, geo = _neighborhood_match_profile(
        profile,
        trusted_neighborhood,
        listing.city or '',
        listing_district,
        extra_values=listing_extras,
        trusted_street=trusted_street,
        unverified_hints=location_hints,
    )
    type_s, type_note = _property_type_match_profile(profile, inferred)
    room_s, room_note = _rooms_match_profile(profile, listing_rooms)

    dims = DimensionScores(
        price_s=price_s,
        area_s=area_s,
        hood_s=hood_s,
        type_s=type_s,
        room_s=room_s,
        price_label=price_label,
        area_note=area_note,
        hood_note=hood_note,
        type_note=type_note,
        room_note=room_note,
        geo_level=geo.geo_level,
        location_match_status=geo.status,
        location_confidence=geo.confidence,
    )
    type_required = _profile_allowed_property_types(profile) is not None
    evaluation = classify_match_tier(
        profile,
        dims,
        eligible=True,
        is_rent_deal=use_rent_price,
        prop_type_known=bool(inferred),
        prop_type_required=type_required,
    )
    evaluation.property_type_confidence = type_detail.confidence
    evaluation.property_type_source = type_detail.source
    score = evaluation.score
    reasons = evaluation.reasons
    relevance_rank = compute_relevance_rank(
        profile,
        dims,
        evaluation,
        is_rent_deal=use_rent_price,
        sale_price=listing.price,
        deposit=listing.deposit,
        rent=listing.rent,
        area=listing.area,
        property_type_confidence=type_detail.confidence,
        published_at=getattr(listing, 'published_at', None),
    )

    display_neighborhood = listing.neighborhood or ''
    areas_pref = preferred_areas_from_profile(profile)
    if areas_pref:
        matched, label = match_preferred_locations(
            areas_pref,
            listing.neighborhood or '',
            listing.city or '',
            '',
            extra_values=listing_extras,
        )
        if matched and label:
            display_neighborhood = label

    result = {
        'source': 'divar',
        'id': listing.pk,
        'listing_id': listing.pk,
        'dataset_id': str(listing.dataset_id),
        'token': listing.token,
        'title': listing.title or listing.token,
        'score': score,
        'reasons': reasons[:4],
        'deal_mode': 'رهن و اجاره' if listing.deposit else ('اجاره' if listing.rent else 'فروش'),
        'neighborhood': display_neighborhood,
        'city': listing.city or '',
        'area': listing.area,
        'rooms': listing.rooms or '',
        'property_type': inferred,
        'price_label': price_label,
        'link': listing.link or '',
        'image': (listing.images or [None])[0] if listing.images else '',
        'advertiser': listing_advertiser_display(listing),
    }
    if match_intent:
        result['match_intent'] = match_intent
        result['intent_label'] = intent_label
    result.update(evaluation_to_result_fields(evaluation))
    result['relevance_rank'] = relevance_rank
    return result


def _score_listing(customer: Customer, listing: Listing) -> Optional[Dict[str, Any]]:
    return _score_listing_with_profile(customer, listing)


def _crm_properties_qs(user):
    from workspace.services.crm_scope import properties_qs
    return properties_qs(user).filter(
        transaction_status__in=['فعال', 'در مذاکره'],
        archived_at__isnull=True,
    ).exclude(publish_status='بایگانی')


def _sale_budget_target(profile) -> Optional[int]:
    lo = getattr(profile, 'budget_min', None)
    hi = getattr(profile, 'budget_max', None)
    if lo and hi:
        return (int(lo) + int(hi)) // 2
    if lo:
        return int(lo)
    if hi:
        return int(hi)
    return None


def _crm_match_candidates_filtered_qs(customer: Customer, user):
    """پیش‌فیلتر SQL — بدون محدودیت اسکن."""
    qs = _crm_properties_qs(user)
    tol = profile_tolerance_ratio(customer)
    if is_builder_customer(customer):
        return qs

    if _is_rent_customer(customer):
        qs = qs.filter(deal_mode__in=['رهن و اجاره', 'اجاره']).filter(
            Q(deposit__gt=0) | Q(monthly_rent__gt=0),
        )
        bounds = _deposit_rent_sql_bounds(customer, tolerance=tol)
        qs = apply_int_min_prefilter(qs, 'deposit', bounds['deposit_lo'])
        qs = apply_int_max_prefilter(qs, 'deposit', bounds['deposit_hi'])
        qs = apply_int_min_prefilter(qs, 'monthly_rent', bounds['rent_lo'])
        qs = apply_int_max_prefilter(qs, 'monthly_rent', bounds['rent_hi'])
    elif _is_sale_customer(customer):
        qs = qs.filter(deal_mode__in=['فروش', 'پیش‌فروش']).filter(sale_price__gt=0)
        sql_lo, sql_hi = _budget_sql_bounds(customer, tolerance=tol)
        if sql_lo is not None:
            qs = qs.filter(sale_price__gte=sql_lo)
        if sql_hi is not None:
            qs = qs.filter(sale_price__lte=sql_hi)
    elif customer.customer_type in LEAD_TYPES or customer.customer_type == 'سرنخ':
        qs = qs.filter(
            Q(deal_mode__in=['فروش', 'پیش‌فروش'], sale_price__gt=0)
            | Q(deal_mode__in=['رهن و اجاره', 'اجاره'], deposit__gt=0)
            | Q(deal_mode__in=['رهن و اجاره', 'اجاره'], monthly_rent__gt=0)
        )

    allowed = _profile_allowed_property_types(customer)
    if allowed:
        qs = qs.filter(property_type__in=sorted(allowed))

    qs = apply_area_min_prefilter(qs, customer.min_area, tol)
    qs = apply_area_max_prefilter(qs, customer.max_area, tol)

    return qs


def _divar_listings_base_qs(user, *, dataset_id=None):
    qs = Listing.objects.filter(
        dataset__user=user, dataset__is_active=True, is_expired=False,
    ).select_related('dataset')
    if dataset_id:
        qs = qs.filter(dataset_id=dataset_id)
    return qs


def _divar_match_candidates_filtered_qs(customer: Customer, user, *, dataset_id=None):
    qs = _divar_listings_base_qs(user, dataset_id=dataset_id)
    tol = profile_tolerance_ratio(customer)
    if is_builder_customer(customer):
        return qs

    if _is_rent_customer(customer):
        qs = qs.filter(Q(deposit__gt=0) | Q(rent__gt=0))
        bounds = _deposit_rent_sql_bounds(customer, tolerance=tol)
        qs = apply_int_min_prefilter(qs, 'deposit', bounds['deposit_lo'])
        qs = apply_int_max_prefilter(qs, 'deposit', bounds['deposit_hi'])
        qs = apply_int_min_prefilter(qs, 'rent', bounds['rent_lo'])
        qs = apply_int_max_prefilter(qs, 'rent', bounds['rent_hi'])
    elif _is_sale_customer(customer):
        qs = qs.filter(price__gt=0).filter(
            Q(deposit__isnull=True) | Q(deposit=0),
        ).filter(
            Q(rent__isnull=True) | Q(rent=0),
        )
        sql_lo, sql_hi = _budget_sql_bounds(customer, tolerance=tol)
        if sql_lo is not None:
            qs = qs.filter(price__gte=sql_lo)
        if sql_hi is not None:
            qs = qs.filter(price__lte=sql_hi)
    elif customer.customer_type in LEAD_TYPES or customer.customer_type == 'سرنخ':
        qs = qs.filter(
            Q(price__gt=0)
            | Q(deposit__gt=0)
            | Q(rent__gt=0)
        )

    qs = apply_area_min_prefilter(qs, customer.min_area, tol)
    qs = apply_area_max_prefilter(qs, customer.max_area, tol)

    return qs


def _divar_listings_qs(user):
    return _divar_listings_base_qs(user).order_by('-published_at')


def _filter_builder_crm_props(props, allowed_types: Set[str], *, sale_only: bool = True):
    expanded: Set[str] = set()
    for item in allowed_types:
        expanded |= _PROPERTY_TYPE_MAP.get(item, {item})
    for prop in props:
        if sale_only and prop.deal_mode not in {'فروش', 'پیش‌فروش'}:
            continue
        if prop.property_type in expanded:
            yield prop


def _filter_builder_listings(listings, allowed_types: Set[str], *, sale_only: bool = True):
    expanded: Set[str] = set()
    for item in allowed_types:
        expanded |= _PROPERTY_TYPE_MAP.get(item, {item})
    for listing in listings:
        if sale_only and (listing.rent or listing.deposit):
            continue
        inferred = _infer_listing_property_type(listing)
        if inferred in expanded:
            yield listing, inferred


def match_crm_properties(customer: Customer, user, *, limit: int | None = None) -> List[Dict[str, Any]]:
    from workspace.services.crm_matching_retrieval import collect_crm_property_matches

    tuning = _match_tuning(customer)
    all_matches = collect_crm_property_matches(
        customer, user, min_score=tuning['crm_min_score'],
    )
    if limit is None:
        return all_matches
    return all_matches[:limit]


def match_divar_listings(customer: Customer, user, *, limit: int | None = None, dataset_id=None) -> List[Dict[str, Any]]:
    from workspace.services.crm_matching_retrieval import collect_divar_listing_matches

    tuning = _match_tuning(customer)
    all_matches = collect_divar_listing_matches(
        customer, user, min_score=tuning['divar_min_score'], dataset_id=dataset_id,
    )
    if limit is None:
        return all_matches
    return all_matches[:limit]


def _match_builder_group(
    customer: Customer,
    user,
    *,
    intent: str,
    profile,
    allowed_types: Set[str],
    min_score: int = 25,
    divar_enabled: bool = True,
    crm_page: int = 1,
    divar_page: int = 1,
    page_size: int = MATCH_PAGE_SIZE_DEFAULT,
    rebuild_index: bool = False,
) -> Dict[str, Any]:
    from workspace.services.crm_matching_index import (
        MATCH_ITERATOR_CHUNK_SIZE,
        ScoredRef,
        get_or_build_index,
        page_has_more,
        slice_refs,
        user_crm_properties_catalog_extra,
        user_divar_listings_catalog_extra,
        _index_cache_key,
        customer_match_fingerprint,
    )

    meta = BUILDER_MATCH_INTENTS[intent]
    fp = f'{customer_match_fingerprint(customer)}:{intent}'
    user_id = int(user.pk)
    customer_id = int(customer.pk)
    divar_min = max(min_score, 30)

    def _build_crm_refs() -> List[ScoredRef]:
        builder_qs = _crm_properties_qs(user).filter(deal_mode__in=['فروش', 'پیش‌فروش'])
        expanded_types: Set[str] = set()
        for item in allowed_types:
            expanded_types |= _PROPERTY_TYPE_MAP.get(item, {item})
        if expanded_types:
            builder_qs = builder_qs.filter(property_type__in=sorted(expanded_types))
        refs: List[ScoredRef] = []
        for prop in builder_qs.order_by('pk').iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
            item = _score_crm_property_with_profile(
                profile, prop,
                match_intent=intent,
                intent_label=meta['intent_label'],
            )
            if item and int(item.get('score') or 0) >= min_score:
                tier = str(item.get('match_tier') or 'strong')
                refs.append(ScoredRef(
                    index_sort_score(int(item['score']), tier, int(item.get('relevance_rank') or 0)),
                    int(prop.pk),
                ))
        return refs

    crm_key = _index_cache_key(
        user_id=user_id, scope='bldr', scope_id=customer_id,
        source='crm', fingerprint=fp,
        extra=user_crm_properties_catalog_extra(user),
    )
    from workspace.services.crm_matching_index import hydrate_crm_matches

    crm_refs, _ = get_or_build_index(crm_key, _build_crm_refs, rebuild=rebuild_index)
    crm_total = len(crm_refs)
    crm_matches = hydrate_crm_matches(
        customer, user, slice_refs(crm_refs, crm_page, page_size),
        min_score=min_score,
        profile=profile,
        match_intent=intent,
        intent_label=meta['intent_label'],
    )

    divar_matches: List[Dict[str, Any]] = []
    divar_total = 0
    divar_has_more = False
    if divar_enabled:
        def _build_divar_refs() -> List[ScoredRef]:
            refs: List[ScoredRef] = []
            for listing, inferred in _filter_builder_listings(_divar_listings_qs(user), allowed_types):
                if not _listing_is_genuine_owner(listing):
                    continue
                item = _score_listing_with_profile(
                    profile, listing, prop_type=inferred,
                    match_intent=intent,
                    intent_label=meta['intent_label'],
                )
                if item and int(item.get('score') or 0) >= divar_min:
                    tier = str(item.get('match_tier') or 'strong')
                    refs.append(ScoredRef(
                        index_sort_score(int(item['score']), tier, int(item.get('relevance_rank') or 0)),
                        int(listing.pk),
                    ))
            return refs

        divar_key = _index_cache_key(
            user_id=user_id, scope='bldr', scope_id=customer_id,
            source='divar', fingerprint=fp,
            extra=user_divar_listings_catalog_extra(user),
        )
        from workspace.services.crm_matching_index import hydrate_divar_matches

        divar_refs, _ = get_or_build_index(divar_key, _build_divar_refs, rebuild=rebuild_index)
        divar_total = len(divar_refs)
        divar_slice = slice_refs(divar_refs, divar_page, page_size)
        divar_matches = hydrate_divar_matches(
            customer, user, divar_slice,
            min_score=divar_min,
            profile=profile,
            match_intent=intent,
            intent_label=meta['intent_label'],
        )
        divar_has_more = page_has_more(divar_total, divar_page, page_size)

    return {
        **meta,
        'crm_matches': crm_matches,
        'divar_matches': divar_matches,
        'crm_total_count': crm_total,
        'divar_total_count': divar_total,
        'crm_page': crm_page,
        'divar_page': divar_page,
        'crm_has_more': page_has_more(crm_total, crm_page, page_size),
        'divar_has_more': divar_has_more,
        'total_count': crm_total + divar_total,
    }


def compute_match_total_count(data: Dict[str, Any]) -> int:
    """تعداد واقعی نتایج واجد شرایط."""
    if 'total_count' in data and data['total_count'] is not None:
        return int(data['total_count'])
    groups = data.get('match_groups') or []
    if groups:
        total = 0
        for g in groups:
            total += int(g.get('crm_total_count') or len(g.get('crm_matches') or []))
            total += int(g.get('divar_total_count') or len(g.get('divar_matches') or []))
        return total
    crm_t = data.get('crm_total_count')
    divar_t = data.get('divar_total_count')
    if crm_t is not None or divar_t is not None:
        return int(crm_t or 0) + int(divar_t or 0)
    return len(data.get('crm_matches') or []) + len(data.get('divar_matches') or [])


def get_builder_customer_matches(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    crm_page: int = 1,
    divar_page: int = 1,
    page_size: int | None = None,
    rebuild_index: bool = False,
) -> Dict[str, Any]:
    acquisition_types = set(parse_builder_buy_types(customer.builder_buy_property_types))
    supply_types = set(BUILDER_SELL_PROPERTY_TYPES)
    effective_size = page_size or MATCH_PAGE_SIZE_DEFAULT

    acquisition = _match_builder_group(
        customer, user,
        intent='acquisition',
        profile=_builder_acquisition_profile(customer),
        allowed_types=acquisition_types,
        divar_enabled=divar_enabled,
        crm_page=crm_page,
        divar_page=divar_page,
        page_size=effective_size,
        rebuild_index=rebuild_index,
    )
    supply = _match_builder_group(
        customer, user,
        intent='supply',
        profile=_builder_supply_profile(customer),
        allowed_types=supply_types,
        divar_enabled=divar_enabled,
        crm_page=crm_page,
        divar_page=divar_page,
        page_size=effective_size,
        rebuild_index=rebuild_index,
    )

    if not divar_enabled:
        acquisition['divar_matches'] = []
        supply['divar_matches'] = []
        acquisition['divar_total_count'] = 0
        supply['divar_total_count'] = 0
        acquisition['divar_has_more'] = False
        supply['divar_has_more'] = False
        acquisition['total_count'] = int(acquisition['crm_total_count'])
        supply['total_count'] = int(supply['crm_total_count'])

    groups = [acquisition, supply]
    crm_total = int(acquisition.get('crm_total_count') or 0) + int(supply.get('crm_total_count') or 0)
    divar_total = int(acquisition.get('divar_total_count') or 0) + int(supply.get('divar_total_count') or 0)

    return {
        'eligible': True,
        'is_builder': True,
        'match_groups': groups,
        'crm_matches': acquisition['crm_matches'] + supply['crm_matches'],
        'divar_matches': acquisition['divar_matches'] + supply['divar_matches'],
        'crm_total_count': crm_total,
        'divar_total_count': divar_total,
        'divar_locked': not divar_enabled,
        'total_count': crm_total + divar_total,
        'crm_page': crm_page,
        'divar_page': divar_page,
        'match_page_size': effective_size,
        'matching_tolerance_percent': customer_matching_tolerance_percent(customer),
        'message': '',
    }


def _match_payload_with_tolerance(payload: Dict[str, Any], customer: Customer) -> Dict[str, Any]:
    payload['matching_tolerance_percent'] = customer_matching_tolerance_percent(customer)
    return payload


def _finalize_match_payload_for_user(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    from workspace.services.crm_matching_access import sanitize_match_payload_for_viewer

    return sanitize_match_payload_for_viewer(user, payload)


def get_customer_matches(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    dataset_id=None,
    crm_page: int = 1,
    divar_page: int = 1,
    page_size: int | None = None,
    paginate: bool = True,
    rebuild_index: bool = False,
) -> Dict[str, Any]:
    from workspace.services.crm_contact_archive import is_contact_archived

    if is_contact_archived(customer):
        return _match_payload_with_tolerance({
            'eligible': False,
            'is_builder': False,
            'match_groups': [],
            'crm_matches': [],
            'divar_matches': [],
            'divar_locked': not divar_enabled,
            'total_count': 0,
            'message': 'مخاطب بایگانی است؛ پیشنهاد جدید غیرفعال است.',
        }, customer)

    if customer.customer_type not in MATCH_TYPES and customer.customer_type not in LEAD_TYPES:
        return _match_payload_with_tolerance({
            'eligible': False,
            'is_builder': False,
            'match_groups': [],
            'crm_matches': [],
            'divar_matches': [],
            'divar_locked': not divar_enabled,
            'total_count': 0,
            'message': 'تطبیق خودکار برای این نوع مخاطب فعال نیست.',
        }, customer)

    from workspace.services.crm_matching_diagnostics import attach_match_guidance

    if is_builder_customer(customer):
        payload = get_builder_customer_matches(
            customer, user,
            divar_enabled=divar_enabled,
            crm_page=crm_page,
            divar_page=divar_page,
            page_size=page_size,
            rebuild_index=rebuild_index,
        )
        payload = _finalize_match_payload_for_user(user, payload)
        payload = attach_match_guidance(
            payload, customer, user,
            divar_enabled=divar_enabled,
            include_staff_diagnostics=getattr(user, 'is_staff', False),
        )
        return _match_payload_with_tolerance(payload, customer)

    from workspace.services.crm_matching_retrieval import (
        MATCH_PAGE_SIZE_DEFAULT,
        collect_customer_match_results,
    )

    tuning = _match_tuning(customer)
    effective_page_size = page_size or tuning['page_size']
    if not paginate:
        effective_page_size = max(effective_page_size, 1_000_000)
    retrieval = collect_customer_match_results(
        customer,
        user,
        divar_enabled=divar_enabled,
        dataset_id=dataset_id,
        crm_min_score=tuning['crm_min_score'],
        divar_min_score=tuning['divar_min_score'],
        crm_page=crm_page,
        divar_page=divar_page,
        page_size=effective_page_size,
        rebuild_index=rebuild_index,
    )
    divar_locked = not divar_enabled
    payload = {
        'eligible': True,
        'is_builder': False,
        'match_groups': [],
        'crm_matches': retrieval['crm_matches'],
        'divar_matches': retrieval['divar_matches'],
        'crm_total_count': retrieval['crm_total_count'],
        'divar_total_count': retrieval['divar_total_count'],
        'divar_locked': divar_locked,
        'crm_page': retrieval['crm_page'],
        'divar_page': retrieval['divar_page'],
        'match_page_size': retrieval['match_page_size'],
        'crm_has_more': retrieval['crm_has_more'],
        'divar_has_more': retrieval['divar_has_more'],
        'message': '',
    }
    payload['total_count'] = int(retrieval['total_count'])
    payload = _finalize_match_payload_for_user(user, payload)
    payload = attach_match_guidance(
        payload, customer, user,
        divar_enabled=divar_enabled,
        dataset_id=dataset_id,
        include_staff_diagnostics=getattr(user, 'is_staff', False),
    )
    return _match_payload_with_tolerance(payload, customer)


# ---------------------------------------------------------------------------
# تطبیق معکوس: فایل شخصی → مخاطب
# ---------------------------------------------------------------------------

MATCH_ELIGIBLE_CUSTOMER_TYPES = MATCH_TYPES | LEAD_TYPES
# نوع‌های مجاز بر اساس حالت معاملهٔ ملک (متقاضی اجاره فقط اجاره؛ متقاضی خرید فقط فروش)
SALE_CONTACT_MATCH_TYPES = frozenset({
    'خریدار', 'متقاضی خرید', 'سرمایه‌گذار', 'سرنخ', 'سازنده',
})
RENT_CONTACT_MATCH_TYPES = frozenset({
    'مستاجر', 'متقاضی اجاره', 'سرنخ',
})
MATCH_CUSTOMER_RESULT_LIMIT = MATCH_RESULT_LIMIT
MATCH_CUSTOMER_RESULT_LIMIT_BROAD = MATCH_RESULT_LIMIT_BROAD
# پیش‌فیلتر SQL با حداکثر تلورانس مجاز (۰–۵۰٪)
_REVERSE_SQL_TOLERANCE = MATCHING_TOLERANCE_MAX_PERCENT / 100.0


def _property_is_contact_match_eligible(prop: CRMProperty) -> bool:
    from workspace.services.crm_property_archive import is_property_archived

    if getattr(prop, 'deleted_at', None):
        return False
    if is_property_archived(prop):
        return False
    if prop.publish_status == 'بایگانی':
        return False
    if prop.transaction_status not in ('فعال', 'در مذاکره'):
        return False
    return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)


def _property_deal_label(prop: CRMProperty) -> str:
    if _crm_property_is_sale_listing(prop) and _crm_property_is_rent_listing(prop):
        return prop.deal_mode or 'فروش / اجاره'
    if _crm_property_is_sale_listing(prop):
        return prop.deal_mode or 'فروش'
    if _crm_property_is_rent_listing(prop):
        return prop.deal_mode or 'رهن و اجاره'
    return prop.deal_mode or ''


def _customer_budget_label(customer: Customer) -> str:
    if _is_rent_customer(customer):
        parts = []
        if customer.deposit_min or customer.deposit_max:
            lo = format_toman(customer.deposit_min) if customer.deposit_min else '—'
            hi = format_toman(customer.deposit_max) if customer.deposit_max else '—'
            parts.append(f'رهن {lo} تا {hi}')
        if customer.rent_min or customer.rent_max:
            lo = format_toman(customer.rent_min) if customer.rent_min else '—'
            hi = format_toman(customer.rent_max) if customer.rent_max else '—'
            parts.append(f'اجاره {lo} تا {hi}')
        return ' · '.join(parts)
    if customer.budget_min or customer.budget_max:
        lo = format_toman(customer.budget_min) if customer.budget_min else '—'
        hi = format_toman(customer.budget_max) if customer.budget_max else '—'
        return f'بودجه {lo} تا {hi}'
    if is_builder_customer(customer):
        if customer.builder_buy_budget_min or customer.builder_buy_budget_max:
            lo = format_toman(customer.builder_buy_budget_min) if customer.builder_buy_budget_min else '—'
            hi = format_toman(customer.builder_buy_budget_max) if customer.builder_buy_budget_max else '—'
            return f'خرید پروژه {lo} تا {hi}'
    return ''


def _customer_match_card(customer: Customer, score_item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'customer_id': customer.pk,
        'id': customer.pk,
        'name': customer.name,
        'full_name': customer.name,
        'phone': customer.phone or '',
        'customer_type': customer.customer_type or '',
        'score': score_item['score'],
        'reasons': list(score_item.get('reasons') or [])[:4],
        'areas': customer.areas or customer.district or '',
        'budget_label': _customer_budget_label(customer),
        'property_type': customer.property_type or '',
        'intent_label': score_item.get('intent_label') or '',
        'match_intent': score_item.get('match_intent') or '',
        'matching_tolerance_percent': customer_matching_tolerance_percent(customer),
        'status': customer.status or '',
        'active_channels': list(getattr(customer, 'active_channels', None) or []),
        'social_links': dict(getattr(customer, 'social_links', None) or {}),
        'can_suggest': True,
        'match_tier': score_item.get('match_tier') or 'strong',
        'evidence_completeness': score_item.get('evidence_completeness'),
        'location_match_status': score_item.get('location_match_status') or '',
        'location_confidence': score_item.get('location_confidence') or '',
        'location_match_reason': score_item.get('location_match_reason') or '',
    }


def _score_builder_customer_for_property(
    customer: Customer,
    prop: CRMProperty,
) -> Optional[Dict[str, Any]]:
    """بهترین امتیاز سازنده روی پروفایل تأمین پروژه یا بازار آپارتمان."""
    if prop.deal_mode not in {'فروش', 'پیش‌فروش'}:
        return None
    best: Optional[Dict[str, Any]] = None
    candidates = [
        (
            'acquisition',
            BUILDER_MATCH_INTENTS['acquisition'],
            _builder_acquisition_profile(customer),
            set(parse_builder_buy_types(customer.builder_buy_property_types)),
        ),
        (
            'supply',
            BUILDER_MATCH_INTENTS['supply'],
            _builder_supply_profile(customer),
            set(BUILDER_SELL_PROPERTY_TYPES),
        ),
    ]
    for intent, meta, profile, allowed_types in candidates:
        expanded: Set[str] = set()
        for item in allowed_types:
            expanded |= _PROPERTY_TYPE_MAP.get(item, {item})
        if prop.property_type and expanded and prop.property_type not in expanded:
            continue
        scored = _score_crm_property_with_profile(
            profile,
            prop,
            match_intent=intent,
            intent_label=meta['intent_label'],
        )
        if scored and (best is None or scored['score'] > best['score']):
            best = scored
    return best


def _score_customer_for_property(
    customer: Customer,
    prop: CRMProperty,
) -> Optional[Dict[str, Any]]:
    if customer.customer_type not in MATCH_ELIGIBLE_CUSTOMER_TYPES:
        return None
    from workspace.services.crm_contact_archive import is_contact_archived

    if is_contact_archived(customer):
        return None
    # فقط مخاطب متعلق به خود کاربر قابل پیشنهاد/پیوند است
    if getattr(customer, 'user_id', None) is None:
        return None
    if not _crm_match_compatible(customer, prop):
        return None

    if not contact_meaningful_for_property_suggestion(
        customer,
        is_rent_listing=_crm_property_is_rent_listing(prop),
        is_sale_listing=_crm_property_is_sale_listing(prop),
    ):
        return None

    if is_builder_customer(customer):
        scored = _score_builder_customer_for_property(customer, prop)
    else:
        scored = _score_crm_property(customer, prop)
    if not scored:
        return None

    if scored.get('match_tier') == MATCH_TIER_INSUFFICIENT:
        return None

    tuning = _match_tuning(customer)
    if scored['score'] < tuning['crm_min_score']:
        return None
    return _customer_match_card(customer, scored)


def _owned_match_customers_qs(user):
    """فقط مخاطبین خود کاربر — موارد اشتراکی قابل پیوند با نقش پیشنهادی نیستند."""
    return Customer.objects.filter(user=user)


def _customer_match_candidates_filtered_qs(prop: CRMProperty, user):
    """پیش‌فیلتر SQL مخاطبین واجد شرایط برای یک فایل شخصی — بدون سقف اسکن."""
    linked_ids = list(prop.contact_links.values_list('customer_id', flat=True))
    qs = (
        _owned_match_customers_qs(user)
        .filter(customer_type__in=MATCH_ELIGIBLE_CUSTOMER_TYPES)
    )
    from workspace.services.crm_contact_archive import archived_contacts_q

    qs = qs.exclude(archived_contacts_q())
    if linked_ids:
        qs = qs.exclude(pk__in=linked_ids)

    tol = _REVERSE_SQL_TOLERANCE
    is_rent = _crm_property_is_rent_listing(prop)
    is_sale = _crm_property_is_sale_listing(prop)

    if is_rent and not is_sale:
        qs = qs.filter(customer_type__in=sorted(RENT_CONTACT_MATCH_TYPES))
    elif is_sale and not is_rent:
        qs = qs.filter(customer_type__in=sorted(SALE_CONTACT_MATCH_TYPES))
    else:
        # حالت نادر: هر دو سیگنال — اتحاد انواع
        qs = qs.filter(
            customer_type__in=sorted(SALE_CONTACT_MATCH_TYPES | RENT_CONTACT_MATCH_TYPES),
        )

    if is_sale and prop.sale_price:
        price = int(prop.sale_price)
        # سازنده: بودجه خرید پروژه جداست — از فیلتر بودجه فروش عادی معاف.
        # سرنخ فقط وقتی بودجه ندارد معاف است؛ وگرنه همان بازه اعمال می‌شود.
        budget_match = (
            Q(budget_min__isnull=True, budget_max__isnull=True)
            | (
                (Q(budget_min__isnull=True) | Q(budget_min__lte=int(price / max(1e-9, (1 - tol)))))
                & (Q(budget_max__isnull=True) | Q(budget_max__gte=int(price / (1 + tol))))
            )
        )
        qs = qs.filter(
            Q(customer_type='سازنده')
            | (Q(customer_type='سرنخ') & Q(budget_min__isnull=True, budget_max__isnull=True))
            | budget_match
        )

    if is_rent and not is_sale:
        rent_exempt = Q(customer_type='سرنخ') & Q(
            deposit_min__isnull=True,
            deposit_max__isnull=True,
            rent_min__isnull=True,
            rent_max__isnull=True,
        )
        deposit_q = Q(deposit_min__isnull=True, deposit_max__isnull=True)
        rent_q = Q(rent_min__isnull=True, rent_max__isnull=True)
        if prop.deposit:
            d = int(prop.deposit)
            deposit_q = (
                Q(deposit_min__isnull=True, deposit_max__isnull=True)
                | (
                    (Q(deposit_min__isnull=True) | Q(deposit_min__lte=int(d / max(1e-9, (1 - tol)))))
                    & (Q(deposit_max__isnull=True) | Q(deposit_max__gte=int(d / (1 + tol))))
                )
            )
        if prop.monthly_rent:
            r = int(prop.monthly_rent)
            rent_q = (
                Q(rent_min__isnull=True, rent_max__isnull=True)
                | (
                    (Q(rent_min__isnull=True) | Q(rent_min__lte=int(r / max(1e-9, (1 - tol)))))
                    & (Q(rent_max__isnull=True) | Q(rent_max__gte=int(r / (1 + tol))))
                )
            )
        money_q = Q()
        if prop.deposit and prop.monthly_rent:
            money_q = deposit_q & rent_q
        elif prop.deposit:
            money_q = deposit_q
        elif prop.monthly_rent:
            money_q = rent_q
        if money_q:
            qs = qs.filter(rent_exempt | money_q)

    # متراژ: سازنده معاف (acquisition از builder_buy_* استفاده می‌کند)
    if prop.area:
        area = float(prop.area)
        area_ok = (
            Q(min_area__isnull=True) | Q(min_area__lte=area / max(1e-9, (1 - tol)))
        ) & (
            Q(max_area__isnull=True) | Q(max_area__gte=area / (1 + tol))
        )
        qs = qs.filter(Q(customer_type='سازنده') | area_ok)

    return qs


def match_customers_for_property(
    prop: CRMProperty,
    user,
    *,
    limit: int | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> List[Dict[str, Any]]:
    from workspace.services.crm_matching_retrieval import collect_property_contact_matches

    tuning_page = page_size or MATCH_CUSTOMER_RESULT_LIMIT_BROAD
    min_score = MATCH_CRM_MIN_SCORE_BROAD
    data = collect_property_contact_matches(
        prop, user, page=page, page_size=tuning_page,
    )
    matches = data['matches']
    if limit is None:
        return matches
    return matches[:limit]


def get_property_contact_matches(
    prop: CRMProperty,
    user,
    *,
    page: int = 1,
    page_size: int | None = None,
) -> Dict[str, Any]:
    """پیشنهاد مخاطب برای یک فایل شخصی — قرینه get_customer_matches."""
    if not _property_is_contact_match_eligible(prop):
        return {
            'eligible': False,
            'matches': [],
            'total_count': 0,
            'property_id': prop.pk,
            'deal_mode': prop.deal_mode or '',
            'deal_label': _property_deal_label(prop),
            'message': 'تطبیق مخاطب فقط برای فایل‌های فعال فروش یا اجاره در دسترس است.',
        }
    from workspace.services.crm_matching_retrieval import collect_property_contact_matches

    effective_size = page_size or MATCH_CUSTOMER_RESULT_LIMIT_BROAD
    retrieval = collect_property_contact_matches(
        prop,
        user,
        page=page,
        page_size=effective_size,
    )
    matches = retrieval['matches']
    message = ''
    if not retrieval['total_count']:
        message = (
            'مخاطب سازگار در پرونده‌های شما پیدا نشد. '
            'بودجه/محله مخاطبین یا معیارهای این فایل را بازبینی کنید.'
        )
    return {
        'eligible': True,
        'matches': matches,
        'total_count': retrieval['total_count'],
        'match_page': retrieval['match_page'],
        'match_page_size': retrieval['match_page_size'],
        'has_more': retrieval['has_more'],
        'property_id': prop.pk,
        'deal_mode': prop.deal_mode or '',
        'deal_label': _property_deal_label(prop),
        'is_sale': _crm_property_is_sale_listing(prop),
        'is_rent': _crm_property_is_rent_listing(prop),
        'message': message,
    }
