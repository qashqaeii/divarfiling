"""تطبیق هوشمند مخاطب با املاک CRM و آگهی‌های فایلینگ دیوار."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from workspace.constants import LEAD_TYPES
from workspace.models import CRMProperty, Customer, Listing
from workspace.services.formatting import format_toman

MATCH_TYPES = {
    'خریدار', 'مستاجر', 'متقاضی خرید', 'متقاضی اجاره', 'سرنخ', 'سرمایه‌گذار',
}

_PROPERTY_TYPE_MAP = {
    'آپارتمان': {'آپارتمان'},
    'ویلا': {'ویلا'},
    'کلنگی': {'کلنگی'},
    'اداری': {'اداری', 'دفتر'},
    'مغازه': {'مغازه', 'تجاری'},
    'زمین': {'زمین', 'کلنگی'},
}


def _parse_areas(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r'[,،;\n|/]+', text)
    return [p.strip() for p in parts if p.strip()]


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def _area_match(customer: Customer, area: Optional[float]) -> Tuple[float, str]:
    if area is None or area <= 0:
        return 0.5, ''
    min_a = customer.min_area
    max_a = customer.max_area
    if min_a is None and max_a is None:
        return 0.5, ''
    if min_a is not None and area < min_a:
        ratio = max(0, 1 - (min_a - area) / max(min_a, 1))
        return ratio * 0.5, f'متراژ کمتر از {min_a}'
    if max_a is not None and area > max_a:
        ratio = max(0, 1 - (area - max_a) / max(max_a, 1))
        return ratio * 0.5, f'متراژ بیشتر از {max_a}'
    return 1.0, f'متراژ {int(area)} متر'


def _neighborhood_match(customer: Customer, neighborhood: str, city: str) -> Tuple[float, str]:
    areas = _parse_areas(customer.areas)
    if not areas and not customer.district:
        return 0.5, ''
    hay = _norm(f'{neighborhood} {city} {customer.district}')
    for area in areas:
        if _norm(area) in hay or _norm(area) in _norm(neighborhood):
            return 1.0, f'محله {area}'
    if customer.district and _norm(customer.district) in hay:
        return 0.85, f'منطقه {customer.district}'
    return 0.15, 'محله متفاوت'


def _rooms_match(customer: Customer, rooms: str) -> Tuple[float, str]:
    if not customer.rooms or not rooms:
        return 0.5, ''
    want = re.sub(r'\D', '', customer.rooms)
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


def _property_type_match(customer: Customer, prop_type: str) -> Tuple[float, str]:
    if not customer.property_type or not prop_type:
        return 0.5, ''
    allowed = _PROPERTY_TYPE_MAP.get(customer.property_type, {customer.property_type})
    if prop_type in allowed or customer.property_type == prop_type:
        return 1.0, prop_type
    if customer.property_type == 'سایر':
        return 0.5, prop_type
    return 0.2, prop_type


def _price_match_sale(customer: Customer, price: Optional[int]) -> Tuple[float, str]:
    if not price:
        return 0.4, ''
    lo, hi = customer.budget_min, customer.budget_max
    if lo is None and hi is None:
        return 0.5, format_toman(price)
    if lo is not None and price < lo:
        gap = (lo - price) / max(lo, 1)
        return max(0, 1 - gap) * 0.6, f'زیر بودجه — {format_toman(price)}'
    if hi is not None and price > hi:
        gap = (price - hi) / max(hi, 1)
        return max(0, 1 - gap) * 0.6, f'بالای بودجه — {format_toman(price)}'
    return 1.0, format_toman(price)


def _price_match_rent(
    customer: Customer,
    deposit: Optional[int],
    rent: Optional[int],
) -> Tuple[float, str]:
    parts = []
    score_parts = []

    if deposit is not None:
        lo, hi = customer.deposit_min, customer.deposit_max
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
        lo, hi = customer.rent_min, customer.rent_max
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
        return 0.5, ''
    return sum(score_parts) / len(score_parts), ' · '.join(parts)


def _is_rent_customer(customer: Customer) -> bool:
    return customer.customer_type in {'مستاجر', 'متقاضی اجاره', 'موجر'}


def _compute_score(customer: Customer, *, price_s: float, area_s: float, hood_s: float, type_s: float, room_s: float) -> int:
    total = price_s * 0.40 + hood_s * 0.25 + area_s * 0.15 + type_s * 0.10 + room_s * 0.10
    return min(100, max(0, int(round(total * 100))))


def _score_crm_property(customer: Customer, prop: CRMProperty) -> Dict[str, Any]:
    is_rent = prop.deal_mode in {'رهن و اجاره', 'اجاره'}
    if is_rent or _is_rent_customer(customer):
        price_s, price_label = _price_match_rent(customer, prop.deposit, prop.monthly_rent)
        if not price_label and prop.sale_price:
            price_s, price_label = _price_match_sale(customer, prop.sale_price)
    else:
        price_s, price_label = _price_match_sale(customer, prop.sale_price)

    area_s, area_note = _area_match(customer, prop.area)
    hood_s, hood_note = _neighborhood_match(customer, prop.neighborhood or prop.district, prop.city)
    type_s, type_note = _property_type_match(customer, prop.property_type)
    room_s, room_note = _rooms_match(customer, prop.rooms)

    score = _compute_score(
        customer, price_s=price_s, area_s=area_s, hood_s=hood_s, type_s=type_s, room_s=room_s,
    )
    reasons = [n for n in (price_label, area_note, hood_note, type_note, room_note) if n]

    return {
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
        'price_label': price_label or (
            format_toman(prop.sale_price) if prop.sale_price else ''
        ),
        'link': prop.link or '',
        'image': (prop.images or [None])[0] if prop.images else '',
    }


def _score_listing(customer: Customer, listing: Listing) -> Dict[str, Any]:
    is_rent = bool(listing.rent or listing.deposit)
    if is_rent or _is_rent_customer(customer):
        price_s, price_label = _price_match_rent(customer, listing.deposit, listing.rent)
    else:
        price_s, price_label = _price_match_sale(customer, listing.price)

    area_s, area_note = _area_match(customer, listing.area)
    hood_s, hood_note = _neighborhood_match(customer, listing.neighborhood, listing.city)
    type_s, type_note = _property_type_match(customer, 'آپارتمان')
    room_s, room_note = _rooms_match(customer, listing.rooms)

    score = _compute_score(
        customer, price_s=price_s, area_s=area_s, hood_s=hood_s, type_s=type_s, room_s=room_s,
    )
    reasons = [n for n in (price_label, area_note, hood_note, room_note) if n]

    return {
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
        'price_label': price_label,
        'link': listing.link or '',
        'image': (listing.images or [None])[0] if listing.images else '',
    }


def match_crm_properties(customer: Customer, user, *, limit: int = 12) -> List[Dict[str, Any]]:
    from workspace.services.crm_scope import properties_qs
    qs = properties_qs(user).filter(
        transaction_status__in=['فعال', 'در مذاکره'],
    ).exclude(publish_status='بایگانی')

    scored = [_score_crm_property(customer, p) for p in qs[:200]]
    scored.sort(key=lambda x: x['score'], reverse=True)
    return [m for m in scored if m['score'] >= 25][:limit]


def match_divar_listings(customer: Customer, user, *, limit: int = 12) -> List[Dict[str, Any]]:
    qs = (
        Listing.objects.filter(dataset__user=user, dataset__is_active=True, is_expired=False)
        .select_related('dataset')
        .order_by('-published_at')[:500]
    )
    scored = [_score_listing(customer, lst) for lst in qs]
    scored.sort(key=lambda x: x['score'], reverse=True)
    return [m for m in scored if m['score'] >= 30][:limit]


def get_customer_matches(customer: Customer, user, *, divar_enabled: bool) -> Dict[str, Any]:
    if customer.customer_type not in MATCH_TYPES and customer.customer_type not in LEAD_TYPES:
        return {
            'eligible': False,
            'crm_matches': [],
            'divar_matches': [],
            'divar_locked': not divar_enabled,
            'message': 'تطبیق خودکار برای این نوع مخاطب فعال نیست.',
        }

    crm_matches = match_crm_properties(customer, user)
    divar_matches = match_divar_listings(customer, user) if divar_enabled else []
    divar_locked = not divar_enabled

    return {
        'eligible': True,
        'crm_matches': crm_matches,
        'divar_matches': divar_matches,
        'divar_locked': divar_locked,
        'message': '',
    }
