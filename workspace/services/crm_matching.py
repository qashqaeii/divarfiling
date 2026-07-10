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
from workspace.services.formatting import format_toman

MATCH_TYPES = {
    'خریدار', 'مستاجر', 'متقاضی خرید', 'متقاضی اجاره', 'سرنخ', 'سرمایه‌گذار', 'سازنده',
}

# حداکثر فاصله مجاز از بازه بودجه/متراژ (۲۰٪ بیشتر یا کمتر).
# خارج از این باند اصلاً پیشنهاد نمی‌شود؛ داخل باند با امتیاز و برچسب نرم می‌ماند.
RANGE_TOLERANCE = 0.20

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
    return _within_range_tolerance(area, profile.min_area, profile.max_area)


def _profile_budget_eligible(
    profile,
    *,
    sale_price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    is_rent: bool = False,
) -> bool:
    if is_rent:
        if not _within_range_tolerance(deposit, profile.deposit_min, profile.deposit_max):
            return False
        if not _within_range_tolerance(rent, profile.rent_min, profile.rent_max):
            return False
        return True
    return _within_range_tolerance(sale_price, profile.budget_min, profile.budget_max)


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


def _profile_criteria_eligible(
    profile,
    *,
    area: Optional[float],
    prop_type: Optional[str] = None,
    sale_price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    is_rent: bool = False,
) -> bool:
    """فیلتر سخت: بودجه، متراژ و نوع ملک باید با ترجیحات کاربر سازگار باشند."""
    if not _profile_property_type_eligible(profile, prop_type):
        return False
    if not _profile_area_eligible(profile, area):
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


def _neighborhood_match_profile(profile, neighborhood: str, city: str) -> Tuple[float, str]:
    areas = _parse_areas(profile.areas)
    if not areas and not profile.district:
        return 0.5, ''
    hay = _norm(f'{neighborhood} {city} {profile.district}')
    for area in areas:
        if _norm(area) in hay or _norm(area) in _norm(neighborhood):
            return 1.0, f'محله {area}'
    if profile.district and _norm(profile.district) in hay:
        return 0.85, f'منطقه {profile.district}'
    return 0.15, 'محله متفاوت'


def _rooms_match_profile(profile, rooms: str) -> Tuple[float, str]:
    if not profile.rooms or not rooms:
        return 0.5, ''
    want = re.sub(r'\D', '', profile.rooms)
    got = re.sub(r'\D', '', str(rooms))
    if not want or not got:
        return 0.5, ''
    if want == got:
        return 1.0, f'{rooms} خواب'
    try:
        diff = abs(int(want) - int(got))
        if diff == 1:
            return 0.6, f'{rooms} خواب'
        return 0.2, f'{rooms} خواب'
    except ValueError:
        return 0.3, ''


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


def _crm_match_compatible(customer: Customer, prop: CRMProperty) -> bool:
    if is_builder_customer(customer):
        return True
    if customer.customer_type in LEAD_TYPES or customer.customer_type == 'سرنخ':
        return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)
    if customer.customer_type == 'مالک':
        if _profile_has_rent_criteria(customer):
            return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)
        return _crm_property_is_sale_listing(prop) or _crm_property_is_rent_listing(prop)
    if _is_rent_customer(customer):
        return _crm_property_is_rent_listing(prop)
    if _is_sale_customer(customer):
        return _crm_property_is_sale_listing(prop)
    return _crm_property_is_rent_listing(prop) or _crm_property_is_sale_listing(prop)


def _listing_match_compatible(customer: Customer, listing: Listing) -> bool:
    if is_builder_customer(customer):
        return True
    if customer.customer_type in LEAD_TYPES or customer.customer_type == 'سرنخ':
        return _listing_is_rent_listing(listing) or _listing_is_sale_listing(listing)
    if customer.customer_type == 'مالک':
        if _profile_has_rent_criteria(customer):
            return _listing_is_rent_listing(listing) or _listing_is_sale_listing(listing)
        return _listing_is_sale_listing(listing) or _listing_is_rent_listing(listing)
    if _is_rent_customer(customer):
        return _listing_is_rent_listing(listing)
    if _is_sale_customer(customer):
        return _listing_is_sale_listing(listing)
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
        rooms=customer.rooms,
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
        rooms=customer.rooms,
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
        profile, prop.neighborhood or prop.district, prop.city,
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

    use_rent_price = is_rent_listing and (rent_customer or not is_sale_listing)
    if not _profile_criteria_eligible(
        profile,
        area=listing.area,
        prop_type=inferred,
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
    hood_s, hood_note = _neighborhood_match_profile(profile, listing.neighborhood, listing.city)
    type_s, type_note = _property_type_match_profile(profile, inferred)
    room_s, room_note = _rooms_match_profile(profile, listing.rooms)

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


def _divar_listings_qs(user):
    return (
        Listing.objects.filter(dataset__user=user, dataset__is_active=True, is_expired=False)
        .select_related('dataset')
        .order_by('-published_at')[:500]
    )


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


def match_crm_properties(customer: Customer, user, *, limit: int = 12) -> List[Dict[str, Any]]:
    qs = _crm_properties_qs(user)
    scored = []
    for prop in qs[:200]:
        if not _crm_match_compatible(customer, prop):
            continue
        item = _score_crm_property(customer, prop)
        if item and item['score'] >= 25:
            scored.append(item)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:limit]


def match_divar_listings(customer: Customer, user, *, limit: int = 12) -> List[Dict[str, Any]]:
    qs = _divar_listings_qs(user)
    scored = []
    for lst in qs:
        if not _listing_match_compatible(customer, lst):
            continue
        item = _score_listing(customer, lst)
        if item and item['score'] >= 30:
            scored.append(item)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:limit]


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
        'message': '',
    }


def get_customer_matches(customer: Customer, user, *, divar_enabled: bool) -> Dict[str, Any]:
    if customer.customer_type not in MATCH_TYPES and customer.customer_type not in LEAD_TYPES:
        return {
            'eligible': False,
            'is_builder': False,
            'match_groups': [],
            'crm_matches': [],
            'divar_matches': [],
            'divar_locked': not divar_enabled,
            'total_count': 0,
            'message': 'تطبیق خودکار برای این نوع مخاطب فعال نیست.',
        }

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
    return payload
