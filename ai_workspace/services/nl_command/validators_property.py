"""اعتبارسنجی خروجی LLM برای create_personal_property — بدون ORM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from accounts.phone_utils import is_valid_iran_mobile
from workspace.constants import (
    CRM_PROPERTIES,
    PROPERTY_DEAL_MODES,
    PROPERTY_PUBLISH_STATUSES,
    PROPERTY_TX_STATUSES,
)
from workspace.services.crm import normalize_phone
from workspace.services.jalali_input import to_persian_digits
from workspace.services.property_public_share import (
    property_amenity_checkbox_labels,
    serialize_amenity_checkboxes,
)

_CRM_PROPERTY_SET = frozenset(CRM_PROPERTIES)
_DEAL_MODE_SET = frozenset(PROPERTY_DEAL_MODES)
_TX_STATUS_SET = frozenset(PROPERTY_TX_STATUSES)
_PUBLISH_STATUS_SET = frozenset(PROPERTY_PUBLISH_STATUSES)
_BOOL_KEYS = ('has_parking', 'has_storage', 'has_elevator', 'is_vacant')
_TRI_STATE_KEYS = ('has_parking', 'has_storage', 'has_elevator', 'is_vacant')
_RENT_DEAL_MODES = frozenset({'اجاره', 'رهن و اجاره'})
_SALE_DEAL_MODES = frozenset({'فروش', 'پیش‌فروش'})
_KNOWN_AMENITY_LABELS = property_amenity_checkbox_labels()
_CORE_AMENITY_TO_FIELD = {
    'پارکینگ': 'has_parking',
    'انباری': 'has_storage',
    'آسانسور': 'has_elevator',
}

_IMPLICIT_DEFAULT_VALUES = {
    'property_type': frozenset({'آپارتمان'}),
    'deal_mode': frozenset({'فروش'}),
    'transaction_status': frozenset({'فعال'}),
    'publish_status': frozenset({'پیش‌نویس'}),
}


def _merge_missing(base: List[str], extra: List[str]) -> List[str]:
    seen = set(base)
    out = list(base)
    for field in extra:
        if field not in seen:
            out.append(field)
            seen.add(field)
    return out


def _clean_str(value: Optional[str]) -> str:
    return ' '.join((value or '').split())


def _subdict(d: Any) -> Dict[str, Any]:
    return dict(d) if isinstance(d, dict) else {}


def _optional_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in ('true', '1', 'yes', 'دارد'):
        return True
    if text in ('false', '0', 'no', 'ندارد', 'نیست'):
        return False
    return None


def _pos_float(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num


def _pos_int(value: Any) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        num = int(value)
    except (TypeError, ValueError):
        return None
    return num


def _money(value: Any) -> Optional[int]:
    return _pos_int(value)


def _rooms_str(value: Any) -> str:
    if value is None or value == '':
        return ''
    if isinstance(value, (int, float)):
        n = int(value)
        return str(n) if n >= 0 else ''
    return _clean_str(str(value))


def _normalize_build_year(raw: Optional[int]) -> Optional[int]:
    if raw is None:
        return None
    year = int(raw)
    if 1300 <= year <= 1500:
        return year
    if 50 <= year <= 99:
        return 1300 + year
    if 1300 <= year <= 2100:
        return year
    return None


def flatten_property_llm_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """ساختار nested جدید + flat قدیمی."""
    location = _subdict(data.get('location'))
    specs = _subdict(data.get('specs'))
    features = _subdict(data.get('features'))
    financial = _subdict(data.get('financial'))
    crm = _subdict(data.get('crm'))
    owner = _subdict(data.get('owner'))

    amenities = data.get('amenities')
    if amenities is None:
        amenities = features.get('amenity_labels')

    flat: Dict[str, Any] = {
        'title': data.get('title'),
        'property_type': data.get('property_type'),
        'deal_mode': data.get('deal_mode'),
        'city': location.get('city') if location.get('city') is not None else data.get('city'),
        'district': location.get('district') if location.get('district') is not None else data.get('district'),
        'neighborhood': (
            location.get('neighborhood')
            if location.get('neighborhood') is not None
            else data.get('neighborhood')
        ),
        'address': location.get('address') if location.get('address') is not None else data.get('address'),
        'area': specs.get('area') if specs.get('area') is not None else data.get('area'),
        'rooms': specs.get('rooms') if specs.get('rooms') is not None else data.get('rooms'),
        'floor': specs.get('floor') if specs.get('floor') is not None else data.get('floor'),
        'total_floors': (
            specs.get('total_floors') if specs.get('total_floors') is not None else data.get('total_floors')
        ),
        'build_year': specs.get('build_year') if specs.get('build_year') is not None else data.get('build_year'),
        'has_parking': (
            features.get('has_parking')
            if features.get('has_parking') is not None
            else data.get('has_parking')
        ),
        'has_storage': (
            features.get('has_storage')
            if features.get('has_storage') is not None
            else data.get('has_storage')
        ),
        'has_elevator': (
            features.get('has_elevator')
            if features.get('has_elevator') is not None
            else data.get('has_elevator')
        ),
        'is_vacant': (
            features.get('is_vacant')
            if features.get('is_vacant') is not None
            else data.get('is_vacant')
        ),
        'sale_price': (
            financial.get('sale_price')
            if financial.get('sale_price') is not None
            else data.get('sale_price')
        ),
        'deposit': financial.get('deposit') if financial.get('deposit') is not None else data.get('deposit'),
        'monthly_rent': (
            financial.get('monthly_rent')
            if financial.get('monthly_rent') is not None
            else data.get('monthly_rent')
        ),
        'transaction_status': crm.get('transaction_status') if crm.get('transaction_status') is not None else data.get('transaction_status'),
        'publish_status': crm.get('publish_status') if crm.get('publish_status') is not None else data.get('publish_status'),
        'business_type': crm.get('business_type') if crm.get('business_type') is not None else data.get('business_type'),
        'phone': owner.get('phone') if owner.get('phone') is not None else data.get('phone'),
        'owner_name': owner.get('owner_name') if owner.get('owner_name') is not None else data.get('owner_name'),
        'amenities': amenities,
        'notes': data.get('notes'),
    }
    return flat


def _collect_explicit_paths(data: Dict[str, Any], prefix: str = '') -> Set[str]:
    explicit: Set[str] = set()
    if not isinstance(data, dict):
        return explicit
    for key, val in data.items():
        if key.startswith('_'):
            continue
        path = f'{prefix}.{key}' if prefix else key
        if key == 'source' or path in ('source', 'crm.source'):
            continue
        if isinstance(val, dict):
            explicit.update(_collect_explicit_paths(val, path))
        elif isinstance(val, list):
            if val:
                explicit.add(path)
        elif val is not None and val != '':
            explicit.add(path)
    return explicit


def _explicit_to_model_fields(explicit_paths: Set[str]) -> Set[str]:
    mapping = {
        'title': 'title',
        'property_type': 'property_type',
        'deal_mode': 'deal_mode',
        'location.city': 'city',
        'location.district': 'district',
        'location.neighborhood': 'neighborhood',
        'location.address': 'address',
        'city': 'city',
        'district': 'district',
        'neighborhood': 'neighborhood',
        'address': 'address',
        'specs.area': 'area',
        'specs.rooms': 'rooms',
        'specs.floor': 'floor',
        'specs.total_floors': 'total_floors',
        'specs.build_year': 'build_year',
        'area': 'area',
        'rooms': 'rooms',
        'floor': 'floor',
        'total_floors': 'total_floors',
        'build_year': 'build_year',
        'features.has_parking': 'has_parking',
        'features.has_storage': 'has_storage',
        'features.has_elevator': 'has_elevator',
        'features.is_vacant': 'is_vacant',
        'features.amenity_labels': 'amenities',
        'has_parking': 'has_parking',
        'has_storage': 'has_storage',
        'has_elevator': 'has_elevator',
        'is_vacant': 'is_vacant',
        'financial.sale_price': 'sale_price',
        'financial.deposit': 'deposit',
        'financial.monthly_rent': 'monthly_rent',
        'sale_price': 'sale_price',
        'deposit': 'deposit',
        'monthly_rent': 'monthly_rent',
        'crm.transaction_status': 'transaction_status',
        'crm.publish_status': 'publish_status',
        'crm.business_type': 'business_type',
        'transaction_status': 'transaction_status',
        'publish_status': 'publish_status',
        'business_type': 'business_type',
        'owner.phone': 'phone',
        'owner.owner_name': 'owner_name',
        'phone': 'phone',
        'owner_name': 'owner_name',
        'amenities': 'amenities',
        'notes': 'notes',
    }
    model: Set[str] = set()
    for path in explicit_paths:
        field = mapping.get(path)
        if field:
            model.add(field)
    return model


def _finalize_implicit_defaults(
    explicit_model: Set[str],
    *,
    property_type: str,
    deal_mode: str,
    transaction_status: str,
    publish_status: str,
) -> Set[str]:
    """حذف defaultهای LLM از explicit — preview فقط گفتار واقعی کاربر."""
    model = set(explicit_model)
    pairs = (
        ('property_type', property_type),
        ('deal_mode', deal_mode),
        ('transaction_status', transaction_status),
        ('publish_status', publish_status),
    )
    for field, value in pairs:
        if field in model and (value or '') in _IMPLICIT_DEFAULT_VALUES.get(field, frozenset()):
            model.discard(field)
    return model


def _apply_amenity_labels(
    labels: Any,
    bools: Dict[str, Optional[bool]],
    explicit_model: Set[str],
) -> Tuple[str, Set[str]]:
    """برچسب‌های امکانات → boolهای اصلی + متن amenities."""
    selected: List[str] = []
    leftover: List[str] = []
    if not isinstance(labels, list):
        return '', explicit_model

    model = set(explicit_model)
    for item in labels:
        label = _clean_str(str(item))
        if not label:
            continue
        field = _CORE_AMENITY_TO_FIELD.get(label)
        if field:
            bools[field] = True
            model.add(field)
            continue
        if label in _KNOWN_AMENITY_LABELS:
            selected.append(label)
        else:
            leftover.append(label)
    amenities_text = serialize_amenity_checkboxes(selected, '، '.join(leftover))
    if amenities_text:
        model.add('amenities')
    return amenities_text, model


def _infer_deal_mode(
    *,
    explicit: str,
    sale_price: Optional[int],
    deposit: Optional[int],
    monthly_rent: Optional[int],
) -> Tuple[str, Optional[str]]:
    has_sale = sale_price is not None and sale_price > 0
    has_rent_side = (deposit is not None and deposit > 0) or (monthly_rent is not None and monthly_rent > 0)
    if explicit and explicit in _DEAL_MODE_SET:
        if has_sale and has_rent_side and explicit in _SALE_DEAL_MODES:
            return explicit, 'ambiguous'
        if has_sale and has_rent_side and explicit in _RENT_DEAL_MODES:
            return explicit, None
        return explicit, None
    if has_sale and has_rent_side:
        return '', 'ambiguous'
    if has_rent_side:
        if deposit is not None and deposit > 0 and (monthly_rent is None or monthly_rent == 0):
            return 'رهن و اجاره', None
        return 'اجاره', None
    if has_sale:
        return 'فروش', None
    return '', None


def build_nl_property_title(validated: Dict[str, Any]) -> str:
    """عنوان deterministic — فقط از فیلدهای verified (نه حدس LLM)."""
    explicit_fields = set(validated.get('_explicit_fields') or [])
    title = _clean_str(validated.get('title'))
    if 'title' in explicit_fields and title:
        return title[:300]

    parts: List[str] = []
    ptype = (validated.get('property_type') or '').strip()
    if 'property_type' in explicit_fields and ptype:
        parts.append(ptype)

    area = validated.get('area')
    if area:
        area_display = to_persian_digits(str(int(area)) if float(area) == int(area) else str(area))
        if parts and ptype:
            parts[0] = f'{ptype} {area_display} متری'
        elif parts:
            parts.append(f'{area_display} متری')
        else:
            parts.append(f'{area_display} متری')

    for loc_key in ('neighborhood', 'district', 'city'):
        if loc_key in explicit_fields:
            loc = (validated.get(loc_key) or '').strip()
            if loc:
                parts.append(loc)
                break

    title = ' '.join(parts).strip()
    return title[:300] if title else ''


def validate_property_parse(
    data: Dict[str, Any],
    *,
    llm_missing: List[str],
    llm_ambiguous: List[str],
    prior_explicit: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], List[str], List[str], Optional[str]]:
    ambiguous = list(llm_ambiguous or [])
    error_message: Optional[str] = None

    explicit_paths = _collect_explicit_paths(data)
    if prior_explicit:
        explicit_paths.update(prior_explicit)
    if data.get('_prior_explicit'):
        explicit_paths.update(data.get('_prior_explicit') or [])
    explicit_model = _explicit_to_model_fields(explicit_paths)

    flat = flatten_property_llm_data(data)

    property_type = _clean_str(flat.get('property_type'))
    if property_type and property_type not in _CRM_PROPERTY_SET:
        ambiguous = _merge_missing(ambiguous, ['property_type'])
        error_message = error_message or 'نوع ملک نامعتبر است.'
        property_type = ''
    elif not property_type:
        property_type = ''

    sale_price = _money(flat.get('sale_price'))
    deposit = _money(flat.get('deposit'))
    monthly_rent = _money(flat.get('monthly_rent'))
    for key, val in (('sale_price', sale_price), ('deposit', deposit), ('monthly_rent', monthly_rent)):
        if val is not None and val < 0:
            ambiguous = _merge_missing(ambiguous, [key])
            error_message = error_message or 'مبلغ منفی مجاز نیست.'
            if key == 'sale_price':
                sale_price = None
            elif key == 'deposit':
                deposit = None
            else:
                monthly_rent = None

    deal_raw = _clean_str(flat.get('deal_mode'))
    deal_mode, deal_conflict = _infer_deal_mode(
        explicit=deal_raw,
        sale_price=sale_price,
        deposit=deposit,
        monthly_rent=monthly_rent,
    )
    if deal_conflict == 'ambiguous' or 'deal_mode' in llm_ambiguous:
        ambiguous = _merge_missing(ambiguous, ['deal_mode'])
        error_message = error_message or 'نوع معامله مبهم است.'
        deal_mode = ''
    elif deal_raw and deal_raw not in _DEAL_MODE_SET:
        ambiguous = _merge_missing(ambiguous, ['deal_mode'])
        error_message = error_message or 'نوع معامله نامعتبر است.'
        deal_mode = ''
    elif deal_mode and not deal_raw:
        if {'sale_price', 'deposit', 'monthly_rent'} & explicit_model:
            explicit_model.add('deal_mode')

    area_raw = _pos_float(flat.get('area'))
    area: Optional[float] = None
    if area_raw is None:
        if flat.get('area') is not None and flat.get('area') != '':
            ambiguous = _merge_missing(ambiguous, ['area'])
            error_message = error_message or 'متراژ نامعتبر است.'
    elif area_raw <= 0:
        ambiguous = _merge_missing(ambiguous, ['area'])
        error_message = error_message or 'متراژ باید بزرگ‌تر از صفر باشد.'
    else:
        area = area_raw

    floor = _pos_int(flat.get('floor'))
    total_floors = _pos_int(flat.get('total_floors'))
    if floor is not None and floor < 0:
        ambiguous = _merge_missing(ambiguous, ['floor'])
        floor = None
    if total_floors is not None and total_floors <= 0:
        ambiguous = _merge_missing(ambiguous, ['total_floors'])
        total_floors = None
    if floor is not None and total_floors is not None and floor > total_floors:
        ambiguous = _merge_missing(ambiguous, ['floor', 'total_floors'])
        error_message = error_message or 'طبقه نمی‌تواند بیشتر از تعداد طبقات باشد.'

    build_year_raw = _pos_int(flat.get('build_year'))
    build_year = _normalize_build_year(build_year_raw)
    if build_year_raw is not None and build_year is None:
        ambiguous = _merge_missing(ambiguous, ['build_year'])

    rooms = _rooms_str(flat.get('rooms'))

    bools: Dict[str, Optional[bool]] = {k: None for k in _TRI_STATE_KEYS}
    for key in _TRI_STATE_KEYS:
        if key in explicit_model or flat.get(key) is not None:
            parsed = _optional_bool(flat.get(key))
            if flat.get(key) is not None and parsed is None:
                ambiguous = _merge_missing(ambiguous, [key])
            bools[key] = parsed
            if parsed is not None:
                explicit_model.add(key)

    amenities_text = ''
    amenities_raw = flat.get('amenities')
    if isinstance(amenities_raw, list):
        amenities_text, explicit_model = _apply_amenity_labels(amenities_raw, bools, explicit_model)
    elif amenities_raw:
        amenities_text = _clean_str(str(amenities_raw))
        if amenities_text:
            explicit_model.add('amenities')

    transaction_status = _clean_str(flat.get('transaction_status'))
    if transaction_status and transaction_status not in _TX_STATUS_SET:
        ambiguous = _merge_missing(ambiguous, ['transaction_status'])
        transaction_status = ''

    publish_status = _clean_str(flat.get('publish_status'))
    if publish_status and publish_status not in _PUBLISH_STATUS_SET:
        ambiguous = _merge_missing(ambiguous, ['publish_status'])
        publish_status = ''

    _BUSINESS_TYPES = frozenset({'شخصی', 'مشاور', 'business'})
    business_type = _clean_str(flat.get('business_type'))
    if business_type and business_type not in _BUSINESS_TYPES:
        ambiguous = _merge_missing(ambiguous, ['business_type'])
        business_type = ''

    phone = ''
    if flat.get('phone'):
        phone = normalize_phone(str(flat.get('phone')))
        if not is_valid_iran_mobile(phone):
            ambiguous = _merge_missing(ambiguous, ['phone'])
            error_message = error_message or 'شماره تماس مالک نامعتبر است.'
            phone = ''

    owner_name = _clean_str(flat.get('owner_name'))
    if owner_name and len(owner_name) > 200:
        owner_name = owner_name[:200]

    notes = _clean_str(flat.get('notes'))
    title = _clean_str(flat.get('title'))

    explicit_model = _finalize_implicit_defaults(
        explicit_model,
        property_type=property_type,
        deal_mode=deal_mode,
        transaction_status=transaction_status,
        publish_status=publish_status,
    )

    if 'property_type' not in explicit_model:
        property_type = ''
    if 'transaction_status' not in explicit_model:
        transaction_status = ''
    if 'publish_status' not in explicit_model:
        publish_status = ''
    if 'business_type' not in explicit_model:
        business_type = ''

    missing: List[str] = []
    if area is None and 'area' not in ambiguous:
        missing.append('area')
    if not deal_mode and 'deal_mode' not in ambiguous:
        missing.append('deal_mode')

    validated = {
        'title': title,
        'property_type': property_type,
        'deal_mode': deal_mode,
        'transaction_status': transaction_status,
        'publish_status': publish_status,
        'business_type': business_type,
        'city': _clean_str(flat.get('city')),
        'district': _clean_str(flat.get('district')),
        'neighborhood': _clean_str(flat.get('neighborhood')),
        'address': _clean_str(flat.get('address')),
        'area': area,
        'rooms': rooms,
        'floor': floor,
        'total_floors': total_floors,
        'build_year': build_year,
        'has_parking': bools['has_parking'],
        'has_storage': bools['has_storage'],
        'has_elevator': bools['has_elevator'],
        'is_vacant': bools['is_vacant'],
        'sale_price': sale_price,
        'deposit': deposit,
        'monthly_rent': monthly_rent,
        'amenities': amenities_text,
        'phone': phone,
        'owner_name': owner_name,
        'notes': notes,
        '_explicit_fields': sorted(explicit_model),
    }

    if deal_mode in _SALE_DEAL_MODES:
        if deposit is not None and deposit > 0:
            ambiguous = _merge_missing(ambiguous, ['deposit'])
        if monthly_rent is not None and monthly_rent > 0:
            ambiguous = _merge_missing(ambiguous, ['monthly_rent'])
    elif deal_mode in _RENT_DEAL_MODES:
        if sale_price is not None and sale_price > 0:
            ambiguous = _merge_missing(ambiguous, ['sale_price'])

    ambiguous = list(dict.fromkeys(ambiguous))
    missing = list(dict.fromkeys(missing))
    return validated, missing, ambiguous, error_message


def hint_for_incomplete_property(
    *,
    missing_fields: List[str],
    ambiguous_fields: List[str],
) -> str:
    if 'deal_mode' in ambiguous_fields:
        return 'نوع معامله را روشن کنید (فروش یا اجاره).'
    if 'area' in ambiguous_fields:
        return 'متراژ را بررسی کنید.'
    if 'floor' in ambiguous_fields or 'total_floors' in ambiguous_fields:
        return 'طبقه یا تعداد طبقات ساختمان نامعتبر است.'
    if 'deal_mode' in missing_fields or 'area' in missing_fields:
        return 'برای ثبت فایل، حداقل متراژ و نوع معامله را مشخص کنید.'
    if ambiguous_fields:
        return 'برخی فیلدها نامعتبر یا مبهم هستند.'
    if missing_fields:
        return 'برای ثبت فایل، اطلاعات را کامل‌تر بنویسید.'
    return 'برای ثبت، اطلاعات را کامل‌تر بنویسید.'


def validated_as_llm_shape(validated: Dict[str, Any]) -> Dict[str, Any]:
    amenities = validated.get('amenities') or None
    amenity_labels = None
    if amenities:
        amenity_labels = [x.strip() for x in str(amenities).replace('\n', '،').split('،') if x.strip()]
    explicit = list(validated.get('_explicit_fields') or [])
    return {
        'title': validated.get('title') or None,
        'property_type': validated.get('property_type') or None,
        'deal_mode': validated.get('deal_mode') or None,
        'location': {
            'city': validated.get('city') or None,
            'district': validated.get('district') or None,
            'neighborhood': validated.get('neighborhood') or None,
            'address': validated.get('address') or None,
        },
        'specs': {
            'area': validated.get('area'),
            'rooms': validated.get('rooms') or None,
            'floor': validated.get('floor'),
            'total_floors': validated.get('total_floors'),
            'build_year': validated.get('build_year'),
        },
        'features': {
            'has_parking': validated.get('has_parking'),
            'has_storage': validated.get('has_storage'),
            'has_elevator': validated.get('has_elevator'),
            'is_vacant': validated.get('is_vacant'),
            'amenity_labels': amenity_labels,
        },
        'financial': {
            'sale_price': validated.get('sale_price'),
            'deposit': validated.get('deposit'),
            'monthly_rent': validated.get('monthly_rent'),
        },
        'crm': {
            'transaction_status': validated.get('transaction_status') or None,
            'publish_status': validated.get('publish_status') or None,
            'business_type': validated.get('business_type') or None,
        },
        'owner': {
            'phone': validated.get('phone') or None,
            'owner_name': validated.get('owner_name') or None,
        },
        'area': validated.get('area'),
        'rooms': validated.get('rooms') or None,
        'floor': validated.get('floor'),
        'total_floors': validated.get('total_floors'),
        'build_year': validated.get('build_year'),
        'has_parking': validated.get('has_parking'),
        'has_storage': validated.get('has_storage'),
        'has_elevator': validated.get('has_elevator'),
        'sale_price': validated.get('sale_price'),
        'deposit': validated.get('deposit'),
        'monthly_rent': validated.get('monthly_rent'),
        'amenities': amenity_labels,
        'notes': validated.get('notes') or None,
        '_prior_explicit': explicit,
    }


def inner_from_validated(validated: Dict[str, Any]) -> Dict[str, Any]:
    shape = validated_as_llm_shape(validated)
    shape.pop('_prior_explicit', None)
    return shape
