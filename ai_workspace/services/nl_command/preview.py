"""پیش‌نمایش فرمان create_contact."""
from __future__ import annotations

from typing import Any, Dict, Optional

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


def existing_contact_payload(customer) -> Dict[str, Any]:
    from django.urls import reverse

    phone = customer.phone or ''
    return {
        'id': customer.pk,
        'name': customer.name,
        'masked_phone': mask_phone_display(phone),
        'url': reverse('workspace:crm_detail', kwargs={'customer_id': customer.pk}),
    }
