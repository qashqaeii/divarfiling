"""Template tags برای UI قرارداد."""
from __future__ import annotations

from django import template

from contracts.constants import PARTY_ROLES_BY_TYPE
from contracts.services.masking import mask_phone
from contracts.services.money import _toman_words, format_toman, parse_toman_amount

register = template.Library()

ROLE_LABELS = {
    'landlord': 'موجر',
    'tenant': 'مستأجر',
    'seller': 'فروشنده',
    'buyer': 'خریدار',
    'owner': 'مالک',
    'builder': 'سازنده',
    'witness': 'شاهد',
    'other': 'سایر',
}

COST_LABELS = {
    'water': 'آب',
    'electricity': 'برق',
    'gas': 'گاز',
    'phone': 'تلفن',
    'charge': 'شارژ ساختمان',
    'minor_repairs': 'تعمیرات جزئی',
    'major_repairs': 'تعمیرات اساسی',
    'property_tax': 'مالیات ملک',
}


@register.filter
def ct_role_label(role: str) -> str:
    return ROLE_LABELS.get(role or '', role or '')


@register.filter
def ct_mask_phone(phone: str) -> str:
    return mask_phone(phone or '')


@register.filter
def ct_format_toman(value) -> str:
    return format_toman(value)


@register.filter
def ct_toman_words(value) -> str:
    amount = parse_toman_amount(value)
    if amount is None:
        return ''
    return _toman_words(amount)


@register.filter
def ct_format_number(value) -> str:
    amount = parse_toman_amount(value)
    if amount is None:
        return value or ''
    return f'{amount:,}'


@register.filter
def ct_party_roles(contract_type: str):
    return PARTY_ROLES_BY_TYPE.get(contract_type, ())


@register.filter
def ct_cost_label(key: str) -> str:
    return COST_LABELS.get(key or '', key or '')
