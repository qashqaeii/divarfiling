"""اعتبارسنجی و flatten خروجی LLM برای create_contact."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from accounts.phone_utils import is_valid_iran_mobile
from ai_workspace.services.nl_command.contact_areas import map_area_names, parse_areas_input
from ai_workspace.services.nl_command.datetime_parser import _local_now, _resolve_relative_date
from workspace.constants import CRM_PRIORITIES, CRM_PROPERTIES, CRM_SOURCES, CRM_STATUSES, CRM_TYPES
from workspace.services.crm import normalize_phone
from workspace.services.filters import get_user_dataset_neighborhoods

_CRM_TYPE_SET = frozenset(CRM_TYPES)
_CRM_SOURCE_SET = frozenset(CRM_SOURCES)
_CRM_PROPERTY_SET = frozenset(CRM_PROPERTIES)
_CRM_STATUS_SET = frozenset(CRM_STATUSES)
_CRM_PRIORITY_SET = frozenset(CRM_PRIORITIES)

_AMENITY_KEYS = {
    'parking': 'want_parking',
    'پارکینگ': 'want_parking',
    'want_parking': 'want_parking',
    'storage': 'want_storage',
    'انباری': 'want_storage',
    'want_storage': 'want_storage',
    'elevator': 'want_elevator',
    'آسانسور': 'want_elevator',
    'want_elevator': 'want_elevator',
}

_SENSITIVE_NL_KEYS = frozenset({'national_id', 'social_links', 'active_channels'})


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


def _subdict(d: Any) -> Dict[str, Any]:
    return dict(d) if isinstance(d, dict) else {}


def _collect_explicit_paths(data: Dict[str, Any], prefix: str = '') -> Set[str]:
    """مسیرهایی که مقدار غیرخالی دارند — برای پیش‌نمایش."""
    explicit: Set[str] = set()
    if not isinstance(data, dict):
        return explicit
    for key, val in data.items():
        if key in _SENSITIVE_NL_KEYS:
            continue
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(val, dict):
            explicit.update(_collect_explicit_paths(val, path))
        elif isinstance(val, list):
            if val:
                explicit.add(path)
        elif val is not None and val != '':
            explicit.add(path)
    return explicit


def _flat_model_keys() -> Set[str]:
    return {
        'name', 'phone', 'phone_alt', 'email', 'city', 'district', 'job',
        'is_legal_entity', 'company_name',
        'customer_type', 'status', 'priority', 'source', 'property_type',
        'budget_min', 'budget_max', 'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
        'min_area', 'max_area', 'rooms_min', 'rooms_max', 'year_min', 'year_max',
        'floor_min', 'floor_max', 'areas', 'rooms',
        'want_parking', 'want_storage', 'want_elevator',
        'tags', 'notes', 'next_follow_up',
        'builder_buy_budget_min', 'builder_buy_budget_max',
        'builder_buy_min_area', 'builder_buy_max_area', 'builder_buy_areas',
        'builder_buy_property_types',
    }


def flatten_contact_llm_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """ساختار nested جدید + flat قدیمی را به یک dict مدل نزدیک تبدیل می‌کند."""
    contact = _subdict(data.get('contact'))
    location = _subdict(data.get('location'))
    profile = _subdict(data.get('profile'))
    financial = _subdict(data.get('financial'))
    prefs = _subdict(data.get('preferences'))
    crm = _subdict(data.get('crm'))
    legacy_prefs = _subdict(data.get('preferences')) if data.get('preferences') else prefs

    flat: Dict[str, Any] = {
        'name': data.get('name'),
        'phone': data.get('phone') if data.get('phone') is not None else contact.get('phone'),
        'phone_alt': contact.get('phone_alt'),
        'email': contact.get('email'),
        'city': location.get('city'),
        'district': location.get('district'),
        'job': profile.get('job'),
        'is_legal_entity': profile.get('is_legal_entity'),
        'company_name': profile.get('company_name'),
        'customer_type': data.get('customer_type'),
        'source': data.get('source') if data.get('source') is not None else crm.get('source'),
        'status': crm.get('status'),
        'priority': crm.get('priority'),
        'notes': data.get('notes'),
        'tags': crm.get('tags'),
        'next_followup_date_text': crm.get('next_followup_date_text') or crm.get('next_followup'),
        'property_type': legacy_prefs.get('property_type'),
        'min_area': legacy_prefs.get('min_area') or legacy_prefs.get('area_min'),
        'max_area': legacy_prefs.get('max_area') or legacy_prefs.get('area_max'),
        'rooms_min': legacy_prefs.get('rooms_min'),
        'rooms_max': legacy_prefs.get('rooms_max'),
        'year_min': legacy_prefs.get('year_min') or legacy_prefs.get('build_year_min'),
        'year_max': legacy_prefs.get('year_max') or legacy_prefs.get('build_year_max'),
        'floor_min': legacy_prefs.get('floor_min'),
        'floor_max': legacy_prefs.get('floor_max'),
        'budget_min': financial.get('budget_min') if financial.get('budget_min') is not None else legacy_prefs.get('budget_min'),
        'budget_max': financial.get('budget_max') if financial.get('budget_max') is not None else legacy_prefs.get('budget_max'),
        'deposit_min': financial.get('deposit_min') if financial.get('deposit_min') is not None else legacy_prefs.get('deposit_min'),
        'deposit_max': financial.get('deposit_max') if financial.get('deposit_max') is not None else legacy_prefs.get('deposit_max'),
        'rent_min': financial.get('rent_min') if financial.get('rent_min') is not None else legacy_prefs.get('rent_min'),
        'rent_max': financial.get('rent_max') if financial.get('rent_max') is not None else legacy_prefs.get('rent_max'),
        'areas': legacy_prefs.get('areas'),
        'rooms': legacy_prefs.get('rooms'),
        'required_amenities': legacy_prefs.get('required_amenities'),
    }
    return flat


def _explicit_to_model_fields(explicit_paths: Set[str]) -> Set[str]:
    """نگاشت مسیر nested به نام فیلد مدل برای پیش‌نمایش."""
    mapping = {
        'name': 'name',
        'phone': 'phone',
        'contact.phone': 'phone',
        'contact.phone_alt': 'phone_alt',
        'contact.email': 'email',
        'location.city': 'city',
        'location.district': 'district',
        'profile.job': 'job',
        'profile.is_legal_entity': 'is_legal_entity',
        'profile.company_name': 'company_name',
        'customer_type': 'customer_type',
        'source': 'source',
        'crm.source': 'source',
        'crm.status': 'status',
        'crm.priority': 'priority',
        'crm.tags': 'tags',
        'crm.next_followup_date_text': 'next_follow_up',
        'crm.next_followup': 'next_follow_up',
        'notes': 'notes',
        'preferences.property_type': 'property_type',
        'preferences.areas': 'areas',
        'preferences.min_area': 'min_area',
        'preferences.max_area': 'max_area',
        'preferences.area_min': 'min_area',
        'preferences.area_max': 'max_area',
        'preferences.rooms_min': 'rooms_min',
        'preferences.rooms_max': 'rooms_max',
        'preferences.rooms': 'rooms',
        'preferences.year_min': 'year_min',
        'preferences.year_max': 'year_max',
        'preferences.build_year_min': 'year_min',
        'preferences.build_year_max': 'year_max',
        'preferences.floor_min': 'floor_min',
        'preferences.floor_max': 'floor_max',
        'preferences.required_amenities': 'want_amenities',
        'financial.budget_min': 'budget_min',
        'financial.budget_max': 'budget_max',
        'financial.deposit_min': 'deposit_min',
        'financial.deposit_max': 'deposit_max',
        'financial.rent_min': 'rent_min',
        'financial.rent_max': 'rent_max',
    }
    out: Set[str] = set()
    for path in explicit_paths:
        if path in mapping:
            out.add(mapping[path])
        elif path.startswith('preferences.'):
            tail = path.split('.', 1)[1]
            if tail in _flat_model_keys():
                out.add(tail)
        elif path in _flat_model_keys():
            out.add(path)
    return out


def _parse_rooms_legacy(rooms_raw: Any) -> Tuple[Optional[int], Optional[int]]:
    if rooms_raw is None or rooms_raw == '':
        return None, None
    s = str(rooms_raw).strip()
    m = re.match(r'^(\d+)\s*[-–]\s*(\d+)$', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    digits = ''.join(ch for ch in s if ch.isdigit())
    if digits:
        n = int(digits)
        return n, n
    return None, None


def _parse_followup_date(date_text: Optional[str], tz_name: str) -> Optional[date]:
    if not (date_text or '').strip():
        return None
    now_local = _local_now(tz_name or 'Asia/Tehran')
    resolved = _resolve_relative_date(date_text or '', now_local)
    return resolved


def _amenities_to_flags(raw_list: Any) -> Dict[str, bool]:
    flags = {'want_parking': False, 'want_storage': False, 'want_elevator': False}
    if not isinstance(raw_list, list):
        return flags
    for item in raw_list:
        key = _AMENITY_KEYS.get(str(item).strip().lower()) or _AMENITY_KEYS.get(str(item).strip())
        if key:
            flags[key] = True
    return flags


def validate_contact_parse(
    data: Dict[str, Any],
    *,
    llm_missing: List[str],
    llm_ambiguous: List[str],
    user=None,
    tz_name: str = 'Asia/Tehran',
    prior_explicit: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], List[str], List[str], Optional[str]]:
    ambiguous = list(llm_ambiguous or [])
    error_message: Optional[str] = None
    phone_was_invalid = False

    explicit_paths = _collect_explicit_paths(data)
    if prior_explicit:
        explicit_paths.update(prior_explicit)
    if data.get('_prior_explicit'):
        explicit_paths.update(data.get('_prior_explicit') or [])
    explicit_model = _explicit_to_model_fields(explicit_paths)

    flat_in = flatten_contact_llm_data(data)

    name = _clean_name(flat_in.get('name'))

    phone_raw = flat_in.get('phone')
    phone = ''
    if phone_raw:
        phone = normalize_phone(str(phone_raw))
        if not is_valid_iran_mobile(phone):
            ambiguous = _merge_missing(ambiguous, ['phone'])
            error_message = error_message or 'شماره تماس واردشده معتبر نیست.'
            phone_was_invalid = True
            phone = ''

    phone_alt = ''
    if flat_in.get('phone_alt'):
        phone_alt = normalize_phone(str(flat_in.get('phone_alt')))
        if phone_alt and not is_valid_iran_mobile(phone_alt):
            ambiguous = _merge_missing(ambiguous, ['phone_alt'])
            error_message = error_message or 'شماره دوم نامعتبر است.'
            phone_alt = ''

    email = (flat_in.get('email') or '').strip()
    if email:
        try:
            validate_email(email)
        except ValidationError:
            ambiguous = _merge_missing(ambiguous, ['email'])
            error_message = error_message or 'ایمیل نامعتبر است.'
            email = ''

    customer_type = (flat_in.get('customer_type') or '').strip()
    if customer_type and customer_type not in _CRM_TYPE_SET:
        ambiguous = _merge_missing(ambiguous, ['customer_type'])
        error_message = error_message or 'نوع مخاطب نامعتبر است.'
        customer_type = ''

    source = (flat_in.get('source') or '').strip()
    if source and source not in _CRM_SOURCE_SET:
        ambiguous = _merge_missing(ambiguous, ['source'])
        error_message = error_message or 'منبع نامعتبر است.'
        source = ''

    status = (flat_in.get('status') or '').strip()
    if status and status not in _CRM_STATUS_SET:
        ambiguous = _merge_missing(ambiguous, ['status'])
        error_message = error_message or 'وضعیت نامعتبر است.'
        status = ''

    priority = (flat_in.get('priority') or '').strip()
    if priority and priority not in _CRM_PRIORITY_SET:
        ambiguous = _merge_missing(ambiguous, ['priority'])
        error_message = error_message or 'اولویت نامعتبر است.'
        priority = ''

    property_type = (flat_in.get('property_type') or '').strip()
    if property_type and property_type not in _CRM_PROPERTY_SET:
        ambiguous = _merge_missing(ambiguous, ['property_type'])
        error_message = error_message or 'نوع ملک نامعتبر است.'
        property_type = ''

    def _pos_int(val, field: str) -> Optional[int]:
        nonlocal error_message
        if val is None:
            return None
        try:
            num = int(val)
        except (TypeError, ValueError):
            ambiguous.append(field)
            return None
        if num < 0:
            ambiguous.append(field)
            error_message = error_message or 'مقدار منفی مجاز نیست.'
            return None
        return num

    min_area = _pos_int(flat_in.get('min_area'), 'min_area')
    max_area = _pos_int(flat_in.get('max_area'), 'max_area')
    if min_area is not None and max_area is not None and min_area > max_area:
        ambiguous = _merge_missing(ambiguous, ['min_area', 'max_area'])
        error_message = error_message or 'بازه متراژ نامعتبر است.'

    rooms_min = _pos_int(flat_in.get('rooms_min'), 'rooms_min')
    rooms_max = _pos_int(flat_in.get('rooms_max'), 'rooms_max')
    if rooms_min is None and rooms_max is None and flat_in.get('rooms') is not None:
        rooms_min, rooms_max = _parse_rooms_legacy(flat_in.get('rooms'))
        if rooms_min is not None:
            explicit_model.add('rooms_min')
        if rooms_max is not None:
            explicit_model.add('rooms_max')
    if rooms_min is not None and rooms_max is not None and rooms_min > rooms_max:
        ambiguous = _merge_missing(ambiguous, ['rooms_min', 'rooms_max'])
        error_message = error_message or 'بازه اتاق نامعتبر است.'

    year_min = _pos_int(flat_in.get('year_min'), 'year_min')
    year_max = _pos_int(flat_in.get('year_max'), 'year_max')
    if year_min is not None and year_max is not None and year_min > year_max:
        ambiguous = _merge_missing(ambiguous, ['year_min', 'year_max'])
        error_message = error_message or 'بازه سال ساخت نامعتبر است.'

    floor_min = _pos_int(flat_in.get('floor_min'), 'floor_min')
    floor_max = _pos_int(flat_in.get('floor_max'), 'floor_max')
    if floor_min is not None and floor_max is not None and floor_min > floor_max:
        ambiguous = _merge_missing(ambiguous, ['floor_min', 'floor_max'])
        error_message = error_message or 'بازه طبقه نامعتبر است.'

    def _money(val, field: str) -> Optional[int]:
        nonlocal error_message
        if val is None:
            return None
        try:
            num = int(val)
        except (TypeError, ValueError):
            ambiguous.append(field)
            return None
        if num < 0:
            ambiguous.append(field)
            error_message = error_message or 'مبلغ منفی مجاز نیست.'
            return None
        return num

    budget_min = _money(flat_in.get('budget_min'), 'budget_min')
    budget_max = _money(flat_in.get('budget_max'), 'budget_max')
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        ambiguous = _merge_missing(ambiguous, ['budget_min', 'budget_max'])
        error_message = error_message or 'بازه بودجه نامعتبر است.'

    deposit_min = _money(flat_in.get('deposit_min'), 'deposit_min')
    deposit_max = _money(flat_in.get('deposit_max'), 'deposit_max')
    if deposit_min is not None and deposit_max is not None and deposit_min > deposit_max:
        ambiguous = _merge_missing(ambiguous, ['deposit_min', 'deposit_max'])
        error_message = error_message or 'بازه ودیعه نامعتبر است.'

    rent_min = _money(flat_in.get('rent_min'), 'rent_min')
    rent_max = _money(flat_in.get('rent_max'), 'rent_max')
    if rent_min is not None and rent_max is not None and rent_min > rent_max:
        ambiguous = _merge_missing(ambiguous, ['rent_min', 'rent_max'])
        error_message = error_message or 'بازه اجاره نامعتبر است.'

    dataset = get_user_dataset_neighborhoods(user) if user else []
    area_names = map_area_names(parse_areas_input(flat_in.get('areas')), dataset)
    areas = ', '.join(area_names)

    amenity_flags = _amenities_to_flags(flat_in.get('required_amenities'))
    if 'want_amenities' in explicit_model:
        for k, v in amenity_flags.items():
            if v:
                explicit_model.add(k)

    tags_raw = flat_in.get('tags')
    tags = ''
    if isinstance(tags_raw, list):
        tags = ', '.join(str(x).strip() for x in tags_raw if str(x).strip())
    elif tags_raw:
        tags = str(tags_raw).strip()

    next_follow_up = None
    if flat_in.get('next_followup_date_text'):
        next_follow_up = _parse_followup_date(str(flat_in.get('next_followup_date_text')), tz_name)
        if next_follow_up is None:
            ambiguous = _merge_missing(ambiguous, ['next_follow_up'])
            error_message = error_message or 'تاریخ پیگیری نامعتبر است.'
        else:
            explicit_model.add('next_follow_up')

    is_legal = flat_in.get('is_legal_entity')
    if is_legal is not None and not isinstance(is_legal, bool):
        ambiguous = _merge_missing(ambiguous, ['is_legal_entity'])
        is_legal = None

    rooms_display = ''
    if rooms_min is not None and rooms_max is not None:
        if rooms_min == rooms_max:
            rooms_display = str(rooms_min)
        else:
            rooms_display = f'{rooms_min}-{rooms_max}'
    elif rooms_min is not None:
        rooms_display = str(rooms_min)
    elif rooms_max is not None:
        rooms_display = str(rooms_max)

    validated = {
        'name': name,
        'phone': phone,
        'phone_alt': phone_alt,
        'email': email,
        'city': (flat_in.get('city') or '').strip()[:100],
        'district': (flat_in.get('district') or '').strip()[:100],
        'job': (flat_in.get('job') or '').strip()[:120],
        'is_legal_entity': bool(is_legal) if is_legal is not None else None,
        'company_name': (flat_in.get('company_name') or '').strip()[:200],
        'customer_type': customer_type,
        'source': source,
        'status': status,
        'priority': priority,
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
        'rooms_min': rooms_min,
        'rooms_max': rooms_max,
        'rooms': rooms_display,
        'year_min': year_min,
        'year_max': year_max,
        'floor_min': floor_min,
        'floor_max': floor_max,
        'want_parking': amenity_flags['want_parking'] or None,
        'want_storage': amenity_flags['want_storage'] or None,
        'want_elevator': amenity_flags['want_elevator'] or None,
        'tags': tags,
        'notes': (flat_in.get('notes') or '').strip(),
        'next_follow_up': next_follow_up,
        '_explicit_fields': sorted(explicit_model),
    }

    ambiguous = [f for f in dict.fromkeys(ambiguous) if f not in ('name',)]
    required_missing: List[str] = []
    if not name:
        required_missing.append('name')
    if not phone and not phone_was_invalid:
        required_missing.append('phone')
    missing = required_missing
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
        return 'شماره تماس واردشده معتبر نیست.'
    name_missing = 'name' in missing_fields
    phone_missing = 'phone' in missing_fields
    if name_missing and phone_missing:
        return 'نام و شماره تماس مخاطب را وارد کنید.'
    if name_missing:
        return 'نام مخاطب را هم وارد کنید.'
    if phone_missing:
        return 'شماره تماس مخاطب را هم وارد کنید.'
    if ambiguous_fields:
        return 'برخی فیلدها نامعتبر یا مبهم هستند.'
    return 'برای ثبت، اطلاعات را کامل‌تر بنویسید.'


def validated_as_llm_shape(validated: Dict[str, Any]) -> Dict[str, Any]:
    """برای revalidate روی confirm."""
    explicit = validated.get('_explicit_fields') or []
    prefs: Dict[str, Any] = {
        'areas': validated.get('areas') or None,
        'property_type': validated.get('property_type') or None,
        'min_area': validated.get('min_area'),
        'max_area': validated.get('max_area'),
        'budget_min': validated.get('budget_min'),
        'budget_max': validated.get('budget_max'),
        'deposit_min': validated.get('deposit_min'),
        'deposit_max': validated.get('deposit_max'),
        'rent_min': validated.get('rent_min'),
        'rent_max': validated.get('rent_max'),
        'rooms': validated.get('rooms') or None,
        'rooms_min': validated.get('rooms_min'),
        'rooms_max': validated.get('rooms_max'),
        'year_min': validated.get('year_min'),
        'year_max': validated.get('year_max'),
        'floor_min': validated.get('floor_min'),
        'floor_max': validated.get('floor_max'),
    }
    req_amenities = []
    if validated.get('want_parking'):
        req_amenities.append('parking')
    if validated.get('want_storage'):
        req_amenities.append('storage')
    if validated.get('want_elevator'):
        req_amenities.append('elevator')
    if req_amenities:
        prefs['required_amenities'] = req_amenities
    return {
        'name': validated.get('name'),
        'phone': validated.get('phone'),
        'customer_type': validated.get('customer_type'),
        'contact': {
            'phone': validated.get('phone'),
            'phone_alt': validated.get('phone_alt'),
            'email': validated.get('email'),
        },
        'location': {
            'city': validated.get('city'),
            'district': validated.get('district'),
        },
        'profile': {
            'job': validated.get('job'),
            'is_legal_entity': validated.get('is_legal_entity'),
            'company_name': validated.get('company_name'),
        },
        'financial': {
            'budget_min': validated.get('budget_min'),
            'budget_max': validated.get('budget_max'),
            'deposit_min': validated.get('deposit_min'),
            'deposit_max': validated.get('deposit_max'),
            'rent_min': validated.get('rent_min'),
            'rent_max': validated.get('rent_max'),
        },
        'preferences': prefs,
        'crm': {
            'status': validated.get('status'),
            'priority': validated.get('priority'),
            'source': validated.get('source'),
            'tags': validated.get('tags').split(', ') if validated.get('tags') else None,
            'next_followup_date_text': None,
        },
        'source': validated.get('source'),
        'notes': validated.get('notes'),
        '_prior_explicit': explicit,
    }


def inner_from_validated(validated: Dict[str, Any]) -> Dict[str, Any]:
    shape = validated_as_llm_shape(validated)
    shape.pop('_prior_explicit', None)
    return shape
