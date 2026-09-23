"""پیش‌نمایش فرمان‌های nl_command."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from ai_workspace.services.nl_command.validators_property import build_nl_property_title
from workspace.services.formatting import format_toman
from workspace.services.jalali_input import format_jalali_date, to_persian_digits


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


def _format_money_range(prefix: str, vmin: Optional[int], vmax: Optional[int]) -> str:
    if vmin is not None and vmax is not None:
        return f'{prefix}: {_fa_num(vmin)} تا {_fa_num(vmax)} تومان'
    if vmax is not None:
        return f'{prefix}: تا {_fa_num(vmax)} تومان'
    if vmin is not None:
        return f'{prefix}: از {_fa_num(vmin)} تومان'
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


def _format_rooms_line(validated: Dict[str, Any]) -> str:
    rmin = validated.get('rooms_min')
    rmax = validated.get('rooms_max')
    if rmin is not None and rmax is not None:
        if rmin == rmax:
            return f'{to_persian_digits(str(rmin))} خواب'
        return f'{to_persian_digits(str(rmin))} تا {to_persian_digits(str(rmax))} خواب'
    if rmax is not None:
        return f'تا {to_persian_digits(str(rmax))} خواب'
    if rmin is not None:
        return f'حداقل {to_persian_digits(str(rmin))} خواب'
    rooms = (validated.get('rooms') or '').strip()
    if rooms:
        return f'{to_persian_digits(rooms)} خواب'
    return ''


def _format_year_line(validated: Dict[str, Any]) -> str:
    ymin = validated.get('year_min')
    ymax = validated.get('year_max')
    if ymin is not None and ymax is not None:
        return f'سال ساخت {to_persian_digits(str(ymin))} تا {to_persian_digits(str(ymax))}'
    if ymax is not None:
        return f'سال ساخت تا {to_persian_digits(str(ymax))}'
    if ymin is not None:
        return f'سال ساخت از {to_persian_digits(str(ymin))}'
    return ''


def _format_floor_line(validated: Dict[str, Any]) -> str:
    fmin = validated.get('floor_min')
    fmax = validated.get('floor_max')
    if fmin is not None and fmax is not None:
        return f'طبقه {to_persian_digits(str(fmin))} تا {to_persian_digits(str(fmax))}'
    if fmax is not None:
        return f'تا طبقه {to_persian_digits(str(fmax))}'
    if fmin is not None:
        return f'از طبقه {to_persian_digits(str(fmin))}'
    return ''


def _explicit(validated: Dict[str, Any], field: str) -> bool:
    explicit = set(validated.get('_explicit_fields') or [])
    return field in explicit


def build_contact_preview(validated: Dict[str, Any]) -> Dict[str, Any]:
    phone = validated.get('phone') or ''
    sections: List[Dict[str, Any]] = []

    header: List[str] = []
    if validated.get('name'):
        header.append(validated['name'])
    if _explicit(validated, 'customer_type') and validated.get('customer_type'):
        header.append(validated['customer_type'])
    if header:
        sections.append({'title': '', 'lines': header})

    contact_lines: List[str] = []
    if _explicit(validated, 'phone') and phone:
        contact_lines.append(mask_phone_display(phone))
    if _explicit(validated, 'phone_alt') and validated.get('phone_alt'):
        contact_lines.append(f'شماره دوم: {mask_phone_display(validated["phone_alt"])}')
    if _explicit(validated, 'email') and validated.get('email'):
        contact_lines.append(validated['email'])
    if _explicit(validated, 'city') and validated.get('city'):
        contact_lines.append(validated['city'])
    if _explicit(validated, 'district') and validated.get('district'):
        contact_lines.append(validated['district'])
    if _explicit(validated, 'job') and validated.get('job'):
        contact_lines.append(f'شغل: {validated["job"]}')
    if _explicit(validated, 'company_name') and validated.get('company_name'):
        contact_lines.append(validated['company_name'])
    if _explicit(validated, 'is_legal_entity') and validated.get('is_legal_entity'):
        contact_lines.append('شخص حقوقی')
    if contact_lines:
        sections.append({'title': 'تماس', 'lines': contact_lines})

    pref_lines: List[str] = []
    if _explicit(validated, 'property_type') and validated.get('property_type'):
        pref_lines.append(validated['property_type'])
    if _explicit(validated, 'areas') and validated.get('areas'):
        pref_lines.append(validated['areas'])
    area_line = _format_area_line(validated) if (
        _explicit(validated, 'min_area') or _explicit(validated, 'max_area')
    ) else ''
    if area_line:
        pref_lines.append(area_line)
    rooms_line = _format_rooms_line(validated) if (
        _explicit(validated, 'rooms_min') or _explicit(validated, 'rooms_max') or _explicit(validated, 'rooms')
    ) else ''
    if rooms_line:
        pref_lines.append(rooms_line)
    year_line = _format_year_line(validated) if (
        _explicit(validated, 'year_min') or _explicit(validated, 'year_max')
    ) else ''
    if year_line:
        pref_lines.append(year_line)
    floor_line = _format_floor_line(validated) if (
        _explicit(validated, 'floor_min') or _explicit(validated, 'floor_max')
    ) else ''
    if floor_line:
        pref_lines.append(floor_line)
    amenities: List[str] = []
    if _explicit(validated, 'want_parking') and validated.get('want_parking'):
        amenities.append('پارکینگ')
    if _explicit(validated, 'want_storage') and validated.get('want_storage'):
        amenities.append('انباری')
    if _explicit(validated, 'want_elevator') and validated.get('want_elevator'):
        amenities.append('آسانسور')
    if amenities:
        pref_lines.append('امکانات ضروری: ' + '، '.join(amenities))
    if pref_lines:
        sections.append({'title': 'ترجیحات', 'lines': pref_lines})

    fin_lines: List[str] = []
    if _explicit(validated, 'budget_min') or _explicit(validated, 'budget_max'):
        line = _format_money_range('بودجه', validated.get('budget_min'), validated.get('budget_max'))
        if line:
            fin_lines.append(line)
    if _explicit(validated, 'deposit_min') or _explicit(validated, 'deposit_max'):
        line = _format_money_range('ودیعه', validated.get('deposit_min'), validated.get('deposit_max'))
        if line:
            fin_lines.append(line)
    if _explicit(validated, 'rent_min') or _explicit(validated, 'rent_max'):
        line = _format_money_range('اجاره', validated.get('rent_min'), validated.get('rent_max'))
        if line:
            fin_lines.append(line)
    if fin_lines:
        sections.append({'title': 'مالی', 'lines': fin_lines})

    crm_lines: List[str] = []
    if _explicit(validated, 'priority') and validated.get('priority'):
        crm_lines.append(f'اولویت: {validated["priority"]}')
    if _explicit(validated, 'source') and validated.get('source'):
        crm_lines.append(f'منبع: {validated["source"]}')
    if _explicit(validated, 'status') and validated.get('status'):
        crm_lines.append(f'وضعیت: {validated["status"]}')
    if _explicit(validated, 'next_follow_up') and validated.get('next_follow_up'):
        nf = validated['next_follow_up']
        if isinstance(nf, date):
            crm_lines.append(f'پیگیری: {format_jalali_date(nf)}')
    if _explicit(validated, 'tags') and validated.get('tags'):
        crm_lines.append(f'برچسب: {validated["tags"]}')
    if crm_lines:
        sections.append({'title': 'سایر', 'lines': crm_lines})

    notes = (validated.get('notes') or '').strip()
    if _explicit(validated, 'notes') and notes:
        sections.append({'title': 'یادداشت', 'lines': [notes]})

    budget_display = _format_money_range('بودجه', validated.get('budget_min'), validated.get('budget_max'))
    if budget_display.startswith('بودجه: '):
        budget_display = budget_display[7:]

    return {
        'sections': sections,
        'name': validated.get('name') or '',
        'phone_display': mask_phone_display(phone) if phone and _explicit(validated, 'phone') else '',
        'customer_type': validated.get('customer_type') or '' if _explicit(validated, 'customer_type') else '',
        'areas_display': validated.get('areas') or '' if _explicit(validated, 'areas') else '',
        'area_range_display': area_line,
        'budget_display': budget_display,
        'rooms_display': rooms_line,
        'property_type': validated.get('property_type') or '' if _explicit(validated, 'property_type') else '',
        'source': validated.get('source') or '' if _explicit(validated, 'source') else '',
        'notes': notes if _explicit(validated, 'notes') else '',
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
