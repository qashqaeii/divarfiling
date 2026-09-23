"""اعتبارسنجی خروجی LLM برای create_contact — بدون ORM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from accounts.phone_utils import is_valid_iran_mobile
from workspace.constants import CRM_PROPERTIES, CRM_SOURCES, CRM_TYPES
from workspace.services.crm import normalize_phone

_CRM_TYPE_SET = frozenset(CRM_TYPES)
_CRM_SOURCE_SET = frozenset(CRM_SOURCES)
_CRM_PROPERTY_SET = frozenset(CRM_PROPERTIES)


def _clean_name(name: Optional[str]) -> str:
    return ' '.join((name or '').split())


def _merge_missing(base: List[str], extra: List[str]) -> List[str]:
    seen = set(base)
    out = list(base)
    for field in extra:
        if field not in seen:
            out.append(field)
            seen.add(field)
    return out


def validate_contact_parse(
    data: Dict[str, Any],
    *,
    llm_missing: List[str],
    llm_ambiguous: List[str],
) -> Tuple[Dict[str, Any], List[str], List[str], Optional[str]]:
    """
    برگشت: validated_flat, missing_fields, ambiguous_fields, error_message
    validated_flat فیلدهای مدل Customer (بدون preferences تودرتو).
    """
    missing = list(llm_missing or [])
    ambiguous = list(llm_ambiguous or [])
    error_message: Optional[str] = None

    name = _clean_name(data.get('name'))
    if not name:
        missing = _merge_missing(missing, ['name'])

    phone_raw = data.get('phone')
    phone = ''
    if phone_raw:
        phone = normalize_phone(str(phone_raw))
        if not is_valid_iran_mobile(phone):
            ambiguous = _merge_missing(ambiguous, ['phone'])
            error_message = error_message or 'شماره تماس نامعتبر است.'
            phone = ''

    prefs = data.get('preferences') if isinstance(data.get('preferences'), dict) else {}

    customer_type = (data.get('customer_type') or '').strip()
    if customer_type and customer_type not in _CRM_TYPE_SET:
        ambiguous = _merge_missing(ambiguous, ['customer_type'])
        error_message = error_message or 'نوع مخاطب نامعتبر است.'
        customer_type = ''

    source = (data.get('source') or '').strip()
    if source and source not in _CRM_SOURCE_SET:
        ambiguous = _merge_missing(ambiguous, ['source'])
        error_message = error_message or 'منبع نامعتبر است.'
        source = ''

    property_type = (prefs.get('property_type') or '').strip()
    if property_type and property_type not in _CRM_PROPERTY_SET:
        ambiguous = _merge_missing(ambiguous, ['property_type'])
        error_message = error_message or 'نوع ملک نامعتبر است.'
        property_type = ''

    def _pos_int(key: str) -> Optional[int]:
        val = prefs.get(key)
        if val is None:
            return None
        try:
            num = int(val)
        except (TypeError, ValueError):
            ambiguous.append(key)
            return None
        if num < 0:
            ambiguous.append(key)
            error_message = error_message or 'مقدار منفی مجاز نیست.'
            return None
        return num

    min_area = _pos_int('min_area')
    max_area = _pos_int('max_area')
    if min_area is not None and max_area is not None and min_area > max_area:
        ambiguous = _merge_missing(ambiguous, ['min_area', 'max_area'])
        error_message = error_message or 'بازه متراژ نامعتبر است.'

    def _money(key: str) -> Optional[int]:
        val = prefs.get(key)
        if val is None:
            return None
        try:
            num = int(val)
        except (TypeError, ValueError):
            ambiguous.append(key)
            return None
        if num < 0:
            ambiguous.append(key)
            error_message = error_message or 'مبلغ منفی مجاز نیست.'
            return None
        return num

    budget_min = _money('budget_min')
    budget_max = _money('budget_max')
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        ambiguous = _merge_missing(ambiguous, ['budget_min', 'budget_max'])
        error_message = error_message or 'بازه بودجه نامعتبر است.'

    deposit_min = _money('deposit_min')
    deposit_max = _money('deposit_max')
    if deposit_min is not None and deposit_max is not None and deposit_min > deposit_max:
        ambiguous = _merge_missing(ambiguous, ['deposit_min', 'deposit_max'])
        error_message = error_message or 'بازه ودیعه نامعتبر است.'

    rent_min = _money('rent_min')
    rent_max = _money('rent_max')
    if rent_min is not None and rent_max is not None and rent_min > rent_max:
        ambiguous = _merge_missing(ambiguous, ['rent_min', 'rent_max'])
        error_message = error_message or 'بازه اجاره نامعتبر است.'

    areas_raw = prefs.get('areas')
    if isinstance(areas_raw, list):
        areas = ', '.join(str(x).strip() for x in areas_raw if str(x).strip())
    else:
        areas = (areas_raw or '').strip() if areas_raw else ''

    rooms = (prefs.get('rooms') or '').strip() if prefs.get('rooms') is not None else ''
    if not rooms and prefs.get('rooms') is not None:
        rooms = str(prefs.get('rooms')).strip()

    notes = (data.get('notes') or '').strip()

    validated = {
        'name': name,
        'phone': phone,
        'customer_type': customer_type or 'خریدار',
        'source': source,
        'status': 'جدید',
        'priority': 'متوسط',
        'property_type': property_type,
        'areas': areas,
        'min_area': min_area,
        'max_area': max_area,
        'budget_min': budget_min,
        'budget_max': budget_max,
        'deposit_min': deposit_min,
        'deposit_max': deposit_max,
        'rent_min': rent_min,
        'rent_max': rent_max,
        'rooms': rooms,
        'notes': notes,
    }

    ambiguous = list(dict.fromkeys(ambiguous))
    missing = list(dict.fromkeys(missing))
    return validated, missing, ambiguous, error_message


def hint_for_incomplete_contact(
    *,
    missing_fields: List[str],
    ambiguous_fields: List[str],
    duplicate: bool,
) -> str:
    if duplicate:
        return 'این شماره قبلاً ثبت شده است.'
    if 'phone' in ambiguous_fields:
        return 'شماره تماس را بررسی کنید.'
    if 'name' in missing_fields:
        return 'نام مخاطب را مشخص کنید.'
    if missing_fields:
        field = missing_fields[0]
        if field == 'phone':
            return 'شماره تماس را وارد کنید.'
    if ambiguous_fields:
        return 'برخی فیلدها نامعتبر یا مبهم هستند.'
    return 'برای ثبت، اطلاعات را کامل‌تر بنویسید.'
