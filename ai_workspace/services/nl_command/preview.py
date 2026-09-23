"""پیش‌نمایش فرمان‌های nl_command."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ai_workspace.services.nl_command.validators_property import build_nl_property_title
from workspace.services.formatting import format_toman
from workspace.services.jalali_input import to_persian_digits


def mask_phone_display(phone: str) -> str:
    raw = (phone or '').strip()
    if len(raw) < 8:
        return raw or ''
    mid = '•••' if len(raw) > 7 else '•'
    return f'{raw[:4]}{mid}{raw[-4:]}'


def _fa_num(value: Optional[int]) -> str:
    if value is None:
        return ''
    return to_persian_digits(f'{value:,}')


def _format_budget_line(validated: Dict[str, Any]) -> str:
    bmin = validated.get('budget_min')
    bmax = validated.get('budget_max')
    if bmin is not None and bmax is not None:
        return f'{_fa_num(bmin)} تا {_fa_num(bmax)} تومان'
    if bmax is not None:
        return f'تا {_fa_num(bmax)} تومان'
    if bmin is not None:
        return f'از {_fa_num(bmin)} تومان'
    return ''


def _format_area_line(validated: Dict[str, Any]) -> str:
    amin = validated.get('min_area')
    amax = validated.get('max_area')
    if amin is not None and amax is not None:
        return f'{to_persian_digits(str(amin))} تا {to_persian_digits(str(amax))} متر'
    if amax is not None:
        return f'تا {to_persian_digits(str(amax))} متر'
    if amin is not None:
        return f'از {to_persian_digits(str(amin))} متر'
    return ''


def build_contact_preview(validated: Dict[str, Any]) -> Dict[str, Any]:
    phone = validated.get('phone') or ''
    return {
        'name': validated.get('name') or '',
        'phone_display': mask_phone_display(phone) if phone else '',
        'customer_type': validated.get('customer_type') or '',
        'areas_display': validated.get('areas') or '',
        'area_range_display': _format_area_line(validated),
        'budget_display': _format_budget_line(validated),
        'rooms_display': to_persian_digits(str(validated.get('rooms'))) if validated.get('rooms') else '',
        'property_type': validated.get('property_type') or '',
        'source': validated.get('source') or '',
        'notes': validated.get('notes') or '',
    }


def _fa_area(area: Optional[float]) -> str:
    if area is None:
        return ''
    if float(area) == int(area):
        return to_persian_digits(str(int(area)))
    return to_persian_digits(str(area))


def build_property_preview(validated: Dict[str, Any]) -> Dict[str, Any]:
    deal = validated.get('deal_mode') or ''
    ptype = validated.get('property_type') or ''
    type_deal = ' · '.join(x for x in (ptype, deal) if x)

    loc = (
        validated.get('neighborhood')
        or validated.get('district')
        or validated.get('city')
        or validated.get('address')
        or ''
    )

    specs: List[str] = []
    area_s = _fa_area(validated.get('area'))
    if area_s:
        specs.append(f'{area_s} متر')
    rooms = (validated.get('rooms') or '').strip()
    if rooms:
        specs.append(f'{to_persian_digits(rooms)} خواب')
    floor = validated.get('floor')
    if floor is not None:
        specs.append(f'طبقه {to_persian_digits(str(floor))}')

    features_positive: List[str] = []
    features_negative: List[str] = []
    if validated.get('has_parking') is True:
        features_positive.append('پارکینگ')
    elif validated.get('has_parking') is False:
        features_negative.append('بدون پارکینگ')
    if validated.get('has_elevator') is True:
        features_positive.append('آسانسور')
    elif validated.get('has_elevator') is False:
        features_negative.append('بدون آسانسور')
    if validated.get('has_storage') is True:
        features_positive.append('انباری')
    elif validated.get('has_storage') is False:
        features_negative.append('بدون انباری')

    sale_line = ''
    deposit_line = ''
    rent_line = ''
    if validated.get('sale_price') is not None:
        sale_line = format_toman(validated.get('sale_price'))
    if validated.get('deposit') is not None:
        deposit_line = format_toman(validated.get('deposit'))
    if validated.get('monthly_rent') is not None:
        rent_line = format_toman(validated.get('monthly_rent'))

    return {
        'title': build_nl_property_title(validated),
        'type_deal_display': type_deal,
        'location_display': loc,
        'specs_display': ' · '.join(specs),
        'features_positive': features_positive,
        'features_negative': features_negative,
        'sale_price_display': sale_line,
        'deposit_display': deposit_line,
        'rent_display': rent_line,
        'notes': validated.get('notes') or '',
    }


def existing_contact_payload(customer) -> Dict[str, Any]:
    from django.urls import reverse

    phone = customer.phone or ''
    return {
        'id': customer.pk,
        'name': customer.name,
        'masked_phone': mask_phone_display(phone),
        'url': reverse('workspace:crm_detail', kwargs={'customer_id': customer.pk}),
    }
