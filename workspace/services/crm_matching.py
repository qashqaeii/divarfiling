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


MATCH_CRM_SCAN_LIMIT = 800
MATCH_CRM_SCAN_LIMIT_BROAD = 1200
MATCH_DIVAR_SCAN_LIMIT = 800
MATCH_DIVAR_SCAN_LIMIT_BROAD = 1200
MATCH_RESULT_LIMIT = 24
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
    want = (getattr(profile, 'property_type', None) or '').strip()
    if not want or want == 'سایر':
        return None
    return set(_PROPERTY_TYPE_MAP.get(want, {want}))


def _profile_property_type_eligible(profile, prop_type: Optional[str]) -> bool:
    allowed = _profile_allowed_property_types(profile)
    if allowed is None:
        return True
    if not prop_type:
        return True
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
    """آیا ترجیح مشتری با یکی از فیلدهای موقعیت ملک هم‌پوشانی دارد."""
    token = _norm(preferred)
    loc = _norm(location)
    if not token or not loc:
        return False
    if token == loc:
        return True
    if len(token) < 2 or len(loc) < 2:
        return False
    return token in loc or loc in token


def _match_preferred_locations(
    preferred: List[str],
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> Tuple[bool, str]:
    """تطبیق لیست محله/منطقه ترجیحی با فیلدهای واقعی ملک."""
    fields = _location_field_values(neighborhood, city, district)
    if not fields or not preferred:
        return False, ''
    for pref in preferred:
        for raw, _ in fields:
            if not _location_tokens_equivalent(pref, raw):
                continue
            if _location_tokens_equivalent(pref, neighborhood):
                return True, (neighborhood or raw).strip()
            if _location_tokens_equivalent(pref, district):
                return True, (district or raw).strip()
            return True, raw.strip()
    return False, ''


def _profile_neighborhood_eligible(
    profile,
    neighborhood: str = '',
    city: str = '',
    district: str = '',
) -> bool:
    """اگر کاربر محله/منطقه مشخص کرده، ملک باید در همان محدوده باشد."""
    areas = _parse_areas(getattr(profile, 'areas', '') or '')
    want_district = (getattr(profile, 'district', None) or '').strip()
    if not areas and not want_district:
        return True

    if not _location_field_values(neighborhood, city, district):
        return False

    if areas:
        matched, _ = _match_preferred_locations(areas, neighborhood, city, district)
        if matched:
            return True
    if want_district:
        matched, _ = _match_preferred_locations([want_district], neighborhood, city, district)
        if matched:
            return True
    return False


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
    """فیلتر سخت: بودجه، متراژ، نوع، محله و جزئیات ترجیحات باید سازگار باشند."""
    if not _profile_property_type_eligible(profile, prop_type):
        return False
    if not _profile_neighborhood_eligible(
        profile, neighborhood=neighborhood, city=city, district=district,
    ):
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


def _neighborhood_match_profile(profile, neighborhood: str, city: str, district: str = '') -> Tuple[float, str]:
    areas = _parse_areas(getattr(profile, 'areas', '') or '')
    want_district = (getattr(profile, 'district', None) or '').strip()
    if not areas and not want_district:
        return 0.5, ''
    if areas:
        matched, label = _match_preferred_locations(areas, neighborhood, city, district)
        if matched:
            return 1.0, f'محله {label or areas[0]}'
    if want_district:
        matched, label = _match_preferred_locations([want_district], neighborhood, city, district)
        if matched:
            return 0.85, f'منطقه {label or want_district}'
    if not _location_field_values(neighborhood, city, district):
        return 0.15, 'محله نامشخص'
    return 0.15, 'محله متفاوت'


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
    return _neighborhood_match_profile(customer, neighborhood, city)


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
        customer.district,
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
        if not customer.property_type or customer.property_type == 'سایر':
            if not customer.budget_min and not customer.budget_max:
                return True
    return False


def _match_tuning(customer: Customer) -> Dict[str, int]:
    broad = _is_broad_seeker_profile(customer)
    return {
        'crm_scan_limit': MATCH_CRM_SCAN_LIMIT_BROAD if broad else MATCH_CRM_SCAN_LIMIT,
        'divar_scan_limit': MATCH_DIVAR_SCAN_LIMIT_BROAD if broad else MATCH_DIVAR_SCAN_LIMIT,
        'result_limit': MATCH_RESULT_LIMIT_BROAD if broad else MATCH_RESULT_LIMIT,
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
    total = price_s * 0.40 + hood_s * 0.25 + area_s * 0.15 + type_s * 0.10 + room_s * 0.10
    return min(100, max(0, int(round(total * 100))))


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
        district=customer.district,
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
        district=customer.district,
        property_type='',
        allowed_types=set(parse_builder_buy_types(customer.builder_buy_property_types)),
        customer_type=customer.customer_type,
    )


def _infer_listing_property_type(listing: Listing) -> str:
    title = _norm(listing.title or '')
    category = _norm(str((listing.data or {}).get('category', '')))
    hay = f'{title} {category}'
    if 'زمین' in hay or 'باغچه' in hay:
        return 'زمین'
    if 'کلنگی' in hay:
        return 'کلنگی'
    if 'ویلا' in hay or 'باغ' in hay:
        return 'ویلا'
    if 'مغازه' in hay or 'تجاری' in hay:
        return 'مغازه'
    if 'اداری' in hay or 'دفتر' in hay:
        return 'اداری'
    return 'آپارتمان'


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
    hood_s, hood_note = _neighborhood_match_profile(
        profile,
        prop.neighborhood or '',
        prop.city or '',
        prop.district or '',
    )
    type_s, type_note = _property_type_match_profile(profile, prop.property_type)
    room_s, room_note = _rooms_match_profile(profile, prop.rooms)

    score = _compute_score(
        price_s=price_s, area_s=area_s, hood_s=hood_s, type_s=type_s, room_s=room_s,
    )
    reasons = [n for n in (price_label, area_note, hood_note, type_note, room_note) if n]

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
    inferred = prop_type or _infer_listing_property_type(listing)
    is_rent_listing = _listing_is_rent_listing(listing)
    is_sale_listing = _listing_is_sale_listing(listing)
    rent_customer = _is_rent_profile(profile)

    from workspace.services.features import extract_listing_features
    feats = extract_listing_features(listing)
    listing_floor = _parse_int_feature(feats.get('floor'))
    listing_year = _parse_int_feature(feats.get('build_year'))
    listing_rooms = feats.get('rooms') or listing.rooms

    use_rent_price = is_rent_listing and (rent_customer or not is_sale_listing)
    if not _profile_criteria_eligible(
        profile,
        area=listing.area,
        prop_type=inferred,
        neighborhood=listing.neighborhood or '',
        city=listing.city or '',
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
    hood_s, hood_note = _neighborhood_match_profile(
        profile, listing.neighborhood or '', listing.city or '',
    )
    type_s, type_note = _property_type_match_profile(profile, inferred)
    room_s, room_note = _rooms_match_profile(profile, listing_rooms)

    score = _compute_score(
        price_s=price_s, area_s=area_s, hood_s=hood_s, type_s=type_s, room_s=room_s,
    )
    reasons = [n for n in (price_label, area_note, hood_note, type_note, room_note) if n]

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
        'neighborhood': listing.neighborhood or '',
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
    return result


def _score_listing(customer: Customer, listing: Listing) -> Optional[Dict[str, Any]]:
    return _score_listing_with_profile(customer, listing)


def _crm_properties_qs(user):
    from workspace.services.crm_scope import properties_qs
    return properties_qs(user).filter(
        transaction_status__in=['فعال', 'در مذاکره'],
    ).exclude(publish_status='بایگانی')


def _crm_match_candidates_qs(customer: Customer, user, *, scan_limit: int):
    """پیش‌فیلتر SQL تا فایل‌های داخل بازه بودجه/متراژ از دست نروند."""
    qs = _crm_properties_qs(user)
    tol = profile_tolerance_ratio(customer)
    if is_builder_customer(customer):
        return qs.order_by('-updated_at')[:scan_limit]

    if _is_rent_customer(customer):
        qs = qs.filter(deal_mode__in=['رهن و اجاره', 'اجاره']).filter(
            Q(deposit__gt=0) | Q(monthly_rent__gt=0),
        )
        bounds = _deposit_rent_sql_bounds(customer, tolerance=tol)
        if bounds['deposit_lo'] is not None:
            qs = qs.filter(deposit__gte=bounds['deposit_lo'])
        if bounds['deposit_hi'] is not None:
            qs = qs.filter(deposit__lte=bounds['deposit_hi'])
        if bounds['rent_lo'] is not None:
            qs = qs.filter(monthly_rent__gte=bounds['rent_lo'])
        if bounds['rent_hi'] is not None:
            qs = qs.filter(monthly_rent__lte=bounds['rent_hi'])
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

    if customer.min_area:
        qs = qs.filter(area__gte=customer.min_area * (1 - tol))
    if customer.max_area:
        qs = qs.filter(area__lte=customer.max_area * (1 + tol))

    return qs.order_by('-updated_at')[:scan_limit]


def _divar_listings_base_qs(user):
    return (
        Listing.objects.filter(dataset__user=user, dataset__is_active=True, is_expired=False)
        .select_related('dataset')
        .order_by('-published_at')
    )


def _divar_match_candidates_qs(customer: Customer, user, *, scan_limit: int):
    qs = _divar_listings_base_qs(user)
    tol = profile_tolerance_ratio(customer)
    if is_builder_customer(customer):
        return qs[:scan_limit]

    if _is_rent_customer(customer):
        qs = qs.filter(Q(deposit__gt=0) | Q(rent__gt=0))
        bounds = _deposit_rent_sql_bounds(customer, tolerance=tol)
        if bounds['deposit_lo'] is not None:
            qs = qs.filter(deposit__gte=bounds['deposit_lo'])
        if bounds['deposit_hi'] is not None:
            qs = qs.filter(deposit__lte=bounds['deposit_hi'])
        if bounds['rent_lo'] is not None:
            qs = qs.filter(rent__gte=bounds['rent_lo'])
        if bounds['rent_hi'] is not None:
            qs = qs.filter(rent__lte=bounds['rent_hi'])
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

    if customer.min_area:
        qs = qs.filter(area__gte=customer.min_area * (1 - tol))
    if customer.max_area:
        qs = qs.filter(area__lte=customer.max_area * (1 + tol))

    return qs[:scan_limit]


def _divar_listings_qs(user):
    return _divar_listings_base_qs(user)[:MATCH_DIVAR_SCAN_LIMIT]


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
    tuning = _match_tuning(customer)
    result_limit = limit if limit is not None else tuning['result_limit']
    min_score = tuning['crm_min_score']
    scored = []
    for prop in _crm_match_candidates_qs(customer, user, scan_limit=tuning['crm_scan_limit']):
        if not _crm_match_compatible(customer, prop):
            continue
        item = _score_crm_property(customer, prop)
        if item and item['score'] >= min_score:
            scored.append(item)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:result_limit]


def match_divar_listings(customer: Customer, user, *, limit: int | None = None) -> List[Dict[str, Any]]:
    tuning = _match_tuning(customer)
    result_limit = limit if limit is not None else tuning['result_limit']
    min_score = tuning['divar_min_score']
    # اسکن بیشتر چون فقط مالک واقعی نگه داشته می‌شود.
    scan_limit = min(tuning['divar_scan_limit'] * 2, 2400)
    scored = []
    for lst in _divar_match_candidates_qs(customer, user, scan_limit=scan_limit):
        if not _listing_is_genuine_owner(lst):
            continue
        if not _listing_match_compatible(customer, lst):
            continue
        item = _score_listing(customer, lst)
        if item and item['score'] >= min_score:
            scored.append(item)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:result_limit]


def _match_builder_group(
    customer: Customer,
    user,
    *,
    intent: str,
    profile,
    allowed_types: Set[str],
    limit: int = 8,
    min_score: int = 25,
) -> Dict[str, Any]:
    meta = BUILDER_MATCH_INTENTS[intent]
    crm_props = list(_filter_builder_crm_props(_crm_properties_qs(user)[:250], allowed_types))
    crm_scored = [
        item for item in (
            _score_crm_property_with_profile(
                profile, prop,
                match_intent=intent,
                intent_label=meta['intent_label'],
            )
            for prop in crm_props
        )
        if item
    ]
    crm_scored.sort(key=lambda x: x['score'], reverse=True)
    crm_matches = [m for m in crm_scored if m['score'] >= min_score][:limit]

    divar_scored = []
    for listing, inferred in _filter_builder_listings(_divar_listings_qs(user), allowed_types):
        if not _listing_is_genuine_owner(listing):
            continue
        item = _score_listing_with_profile(
            profile, listing, prop_type=inferred,
            match_intent=intent,
            intent_label=meta['intent_label'],
        )
        if item:
            divar_scored.append(item)
    divar_scored.sort(key=lambda x: x['score'], reverse=True)
    divar_matches = [m for m in divar_scored if m['score'] >= max(min_score, 30)][:limit]

    return {
        **meta,
        'crm_matches': crm_matches,
        'divar_matches': divar_matches,
        'total_count': len(crm_matches) + len(divar_matches),
    }


def compute_match_total_count(data: Dict[str, Any]) -> int:
    """تعداد واقعی آیتم‌های برگشتی — نه مجموع قبل از slice."""
    groups = data.get('match_groups') or []
    if groups:
        total = 0
        for g in groups:
            total += len(g.get('crm_matches') or [])
            total += len(g.get('divar_matches') or [])
        return total
    return len(data.get('crm_matches') or []) + len(data.get('divar_matches') or [])


def get_builder_customer_matches(customer: Customer, user, *, divar_enabled: bool) -> Dict[str, Any]:
    acquisition_types = set(parse_builder_buy_types(customer.builder_buy_property_types))
    supply_types = set(BUILDER_SELL_PROPERTY_TYPES)

    acquisition = _match_builder_group(
        customer, user,
        intent='acquisition',
        profile=_builder_acquisition_profile(customer),
        allowed_types=acquisition_types,
    )
    supply = _match_builder_group(
        customer, user,
        intent='supply',
        profile=_builder_supply_profile(customer),
        allowed_types=supply_types,
    )

    if not divar_enabled:
        acquisition['divar_matches'] = []
        supply['divar_matches'] = []
        acquisition['total_count'] = len(acquisition['crm_matches'])
        supply['total_count'] = len(supply['crm_matches'])

    groups = [acquisition, supply]
    combined = []
    for group in groups:
        combined.extend(group['crm_matches'])
        combined.extend(group['divar_matches'])
    combined.sort(key=lambda x: x['score'], reverse=True)

    crm_matches = [m for m in combined if m['source'] == 'crm'][:12]
    divar_matches = [m for m in combined if m['source'] == 'divar'][:12]

    return {
        'eligible': True,
        'is_builder': True,
        'match_groups': groups,
        'crm_matches': crm_matches,
        'divar_matches': divar_matches,
        'divar_locked': not divar_enabled,
        'total_count': compute_match_total_count({'match_groups': groups}),
        'matching_tolerance_percent': customer_matching_tolerance_percent(customer),
        'message': '',
    }


def _match_payload_with_tolerance(payload: Dict[str, Any], customer: Customer) -> Dict[str, Any]:
    payload['matching_tolerance_percent'] = customer_matching_tolerance_percent(customer)
    return payload


def get_customer_matches(customer: Customer, user, *, divar_enabled: bool) -> Dict[str, Any]:
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

    if is_builder_customer(customer):
        return get_builder_customer_matches(customer, user, divar_enabled=divar_enabled)

    crm_matches = match_crm_properties(customer, user)
    divar_matches = match_divar_listings(customer, user) if divar_enabled else []
    divar_locked = not divar_enabled
    payload = {
        'eligible': True,
        'is_builder': False,
        'match_groups': [],
        'crm_matches': crm_matches,
        'divar_matches': divar_matches,
        'divar_locked': divar_locked,
        'message': '',
    }
    payload['total_count'] = compute_match_total_count(payload)
    return _match_payload_with_tolerance(payload, customer)


# ---------------------------------------------------------------------------
# تطبیق معکوس: فایل شخصی → مخاطب
# ---------------------------------------------------------------------------

MATCH_ELIGIBLE_CUSTOMER_TYPES = MATCH_TYPES | LEAD_TYPES
MATCH_CUSTOMER_SCAN_LIMIT = MATCH_CRM_SCAN_LIMIT
MATCH_CUSTOMER_RESULT_LIMIT = MATCH_RESULT_LIMIT
# پیش‌فیلتر SQL با حداکثر تلورانس مجاز (۰–۵۰٪)
_REVERSE_SQL_TOLERANCE = MATCHING_TOLERANCE_MAX_PERCENT / 100.0


def _property_is_contact_match_eligible(prop: CRMProperty) -> bool:
    if getattr(prop, 'deleted_at', None):
        return False
    if prop.publish_status == 'بایگانی':
        return False
    if prop.transaction_status not in ('فعال', 'در مذاکره'):
        return False
    return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)


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
        'name': customer.name,
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
    }


def _score_builder_customer_for_property(
    customer: Customer,
    prop: CRMProperty,
) -> Optional[Dict[str, Any]]:
    """بهترین امتیاز سازنده روی پروفایل تأمین پروژه یا بازار آپارتمان."""
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
        if prop.deal_mode not in {'فروش', 'پیش‌فروش'}:
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
    if customer.status == 'بایگانی':
        return None
    if not _crm_match_compatible(customer, prop):
        return None

    if is_builder_customer(customer):
        scored = _score_builder_customer_for_property(customer, prop)
    else:
        scored = _score_crm_property(customer, prop)
    if not scored:
        return None

    tuning = _match_tuning(customer)
    if scored['score'] < tuning['crm_min_score']:
        return None
    return _customer_match_card(customer, scored)


def _customer_match_candidates_qs(prop: CRMProperty, user, *, scan_limit: int):
    """پیش‌فیلتر مخاطبین واجد شرایط برای یک فایل شخصی."""
    from workspace.services.crm_scope import customers_qs

    linked_ids = prop.contact_links.values_list('customer_id', flat=True)
    qs = (
        customers_qs(user)
        .filter(customer_type__in=MATCH_ELIGIBLE_CUSTOMER_TYPES)
        .exclude(status='بایگانی')
        .exclude(pk__in=linked_ids)
    )

    tol = _REVERSE_SQL_TOLERANCE
    is_rent = _crm_property_is_rent_listing(prop)
    is_sale = _crm_property_is_sale_listing(prop)

    type_q = Q()
    if is_rent and not is_sale:
        type_q = Q(customer_type__in=[
            'مستاجر', 'متقاضی اجاره', 'سرنخ', 'سازنده',
        ])
    elif is_sale and not is_rent:
        type_q = Q(customer_type__in=[
            'خریدار', 'متقاضی خرید', 'سرمایه‌گذار', 'سرنخ', 'سازنده',
        ])
    if type_q:
        qs = qs.filter(type_q)

    if is_sale and prop.sale_price:
        price = int(prop.sale_price)
        # بودجه مشتری باید بتواند قیمت ملک را با تلورانس حداکثر پوشش دهد.
        # فقط سرنخ/سازنده بدون بودجه خرید از فیلتر بودجه معاف‌اند (نه متقاضی اجاره).
        budget_ok = (
            Q(budget_min__isnull=True, budget_max__isnull=True)
            | (
                (Q(budget_min__isnull=True) | Q(budget_min__lte=int(price / max(1e-9, (1 - tol)))))
                & (Q(budget_max__isnull=True) | Q(budget_max__gte=int(price / (1 + tol))))
            )
            | Q(customer_type__in=['سازنده', 'سرنخ'])
        )
        qs = qs.filter(budget_ok)

    if is_rent:
        rent_ok = Q(customer_type__in=['سرنخ', 'سازنده'])
        deposit_q = Q()
        rent_q = Q()
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
            qs = qs.filter(rent_ok | money_q)

    if prop.area:
        area = float(prop.area)
        qs = qs.filter(
            Q(min_area__isnull=True) | Q(min_area__lte=area / max(1e-9, (1 - tol))),
        ).filter(
            Q(max_area__isnull=True) | Q(max_area__gte=area / (1 + tol)),
        )

    return qs.order_by('-updated_at')[:scan_limit]


def match_customers_for_property(
    prop: CRMProperty,
    user,
    *,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    result_limit = limit if limit is not None else MATCH_CUSTOMER_RESULT_LIMIT
    scored: List[Dict[str, Any]] = []
    for customer in _customer_match_candidates_qs(
        prop, user, scan_limit=MATCH_CUSTOMER_SCAN_LIMIT,
    ):
        item = _score_customer_for_property(customer, prop)
        if item:
            scored.append(item)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:result_limit]


def get_property_contact_matches(prop: CRMProperty, user) -> Dict[str, Any]:
    """پیشنهاد مخاطب برای یک فایل شخصی — قرینه get_customer_matches."""
    if not _property_is_contact_match_eligible(prop):
        return {
            'eligible': False,
            'matches': [],
            'total_count': 0,
            'message': 'تطبیق مخاطب برای این فایل فعال نیست (وضعیت معامله یا بایگانی).',
        }
    matches = match_customers_for_property(prop, user)
    return {
        'eligible': True,
        'matches': matches,
        'total_count': len(matches),
        'message': '',
    }
