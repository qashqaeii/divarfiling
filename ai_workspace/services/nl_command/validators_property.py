"""اعتبارسنجی خروجی LLM برای create_personal_property — بدون ORM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from workspace.constants import CRM_PROPERTIES, PROPERTY_DEAL_MODES
from workspace.services.jalali_input import to_persian_digits

_CRM_PROPERTY_SET = frozenset(CRM_PROPERTIES)
_DEAL_MODE_SET = frozenset(PROPERTY_DEAL_MODES)
_BOOL_KEYS = ('has_parking', 'has_storage', 'has_elevator')
_RENT_DEAL_MODES = frozenset({'اجاره', 'رهن و اجاره'})
_SALE_DEAL_MODES = frozenset({'فروش', 'پیش‌فروش'})


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


def _optional_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in ('true', '1', 'yes'):
        return True
    if text in ('false', '0', 'no'):
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
    num = _pos_int(value)
    if num is None:
        return None
    return num


def _rooms_str(value: Any) -> str:
    if value is None or value == '':
        return ''
    if isinstance(value, (int, float)):
        n = int(value)
        return str(n) if n >= 0 else ''
    return _clean_str(str(value))


def _flatten_location(data: Dict[str, Any]) -> Dict[str, str]:
    loc = data.get('location') if isinstance(data.get('location'), dict) else {}
    return {
        'city': _clean_str(loc.get('city') or data.get('city')),
        'district': _clean_str(loc.get('district') or data.get('district')),
        'neighborhood': _clean_str(loc.get('neighborhood') or data.get('neighborhood')),
        'address': _clean_str(loc.get('address') or data.get('address')),
    }


def _infer_deal_mode(
    *,
    explicit: str,
    sale_price: Optional[int],
    deposit: Optional[int],
    monthly_rent: Optional[int],
) -> Tuple[str, Optional[str]]:
    """برگشت: deal_mode, conflict_reason ('ambiguous' یا None)."""
    has_sale = sale_price is not None and sale_price >= 0
    has_rent_side = (deposit is not None and deposit >= 0) or (monthly_rent is not None and monthly_rent >= 0)
    if explicit and explicit in _DEAL_MODE_SET:
        if has_sale and has_rent_side and explicit in _SALE_DEAL_MODES:
            return explicit, 'ambiguous'
        return explicit, None
    if has_sale and has_rent_side:
        return '', 'ambiguous'
    if has_rent_side:
        return 'اجاره', None
    if has_sale:
        return 'فروش', None
    return '', None


def build_nl_property_title(validated: Dict[str, Any]) -> str:
    """عنوان deterministic — فقط از فیلدهای تأیید‌شده."""
    explicit = _clean_str(validated.get('title'))
    if explicit:
        return explicit[:300]
    parts: List[str] = []
    ptype = validated.get('property_type') or 'آپارتمان'
    area = validated.get('area')
    if area:
        area_display = to_persian_digits(str(int(area)) if float(area) == int(area) else str(area))
        parts.append(f'{ptype} {area_display} متری')
    else:
        parts.append(ptype)
    loc = (
        validated.get('neighborhood')
        or validated.get('district')
        or validated.get('city')
        or ''
    )
    if loc:
        parts.append(loc)
    title = ' '.join(parts).strip()
    return title[:300] if title else ''


def validate_property_parse(
    data: Dict[str, Any],
    *,
    llm_missing: List[str],
    llm_ambiguous: List[str],
) -> Tuple[Dict[str, Any], List[str], List[str], Optional[str]]:
    missing = list(llm_missing or [])
    ambiguous = list(llm_ambiguous or [])
    error_message: Optional[str] = None

    loc = _flatten_location(data)

    property_type = _clean_str(data.get('property_type'))
    if not property_type:
        property_type = ''
    elif property_type not in _CRM_PROPERTY_SET:
        ambiguous = _merge_missing(ambiguous, ['property_type'])
        error_message = error_message or 'نوع ملک نامعتبر است.'
        property_type = ''

    sale_price = _money(data.get('sale_price'))
    deposit = _money(data.get('deposit'))
    monthly_rent = _money(data.get('monthly_rent'))
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

    deal_raw = _clean_str(data.get('deal_mode'))
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

    area_raw = _pos_float(data.get('area'))
    area: Optional[float] = None
    if area_raw is None:
        if data.get('area') is not None and data.get('area') != '':
            ambiguous = _merge_missing(ambiguous, ['area'])
            error_message = error_message or 'متراژ نامعتبر است.'
    elif area_raw <= 0:
        ambiguous = _merge_missing(ambiguous, ['area'])
        error_message = error_message or 'متراژ باید بزرگ‌تر از صفر باشد.'
    else:
        area = area_raw

    if area is None and 'area' not in missing:
        missing = _merge_missing(missing, ['area'])

    if not deal_mode and 'deal_mode' not in missing and 'deal_mode' not in ambiguous:
        missing = _merge_missing(missing, ['deal_mode'])

    floor = _pos_int(data.get('floor'))
    total_floors = _pos_int(data.get('total_floors'))
    if floor is not None and floor < 0:
        ambiguous = _merge_missing(ambiguous, ['floor'])
        floor = None
    if total_floors is not None and total_floors <= 0:
        ambiguous = _merge_missing(ambiguous, ['total_floors'])
        total_floors = None
    if floor is not None and total_floors is not None and floor > total_floors:
        ambiguous = _merge_missing(ambiguous, ['floor', 'total_floors'])
        error_message = error_message or 'طبقه نمی‌تواند بیشتر از تعداد طبقات باشد.'

    build_year = _pos_int(data.get('build_year'))
    if build_year is not None and not (1300 <= build_year <= 2100):
        ambiguous = _merge_missing(ambiguous, ['build_year'])
        build_year = None

    rooms = _rooms_str(data.get('rooms'))

    bools: Dict[str, Optional[bool]] = {}
    for key in _BOOL_KEYS:
        parsed = _optional_bool(data.get(key))
        if data.get(key) is not None and parsed is None:
            ambiguous = _merge_missing(ambiguous, [key])
        bools[key] = parsed

    amenities_raw = data.get('amenities')
    amenities = ''
    if isinstance(amenities_raw, list):
        amenities = '\n'.join(_clean_str(str(x)) for x in amenities_raw if _clean_str(str(x)))
    elif amenities_raw:
        amenities = _clean_str(str(amenities_raw))

    notes = _clean_str(data.get('notes'))
    title = _clean_str(data.get('title'))

    validated = {
        'title': title,
        'property_type': property_type or 'آپارتمان',
        'deal_mode': deal_mode,
        'city': loc['city'],
        'district': loc['district'],
        'neighborhood': loc['neighborhood'],
        'address': loc['address'],
        'area': area,
        'rooms': rooms,
        'floor': floor,
        'total_floors': total_floors,
        'build_year': build_year,
        'has_parking': bools['has_parking'],
        'has_storage': bools['has_storage'],
        'has_elevator': bools['has_elevator'],
        'sale_price': sale_price,
        'deposit': deposit,
        'monthly_rent': monthly_rent,
        'amenities': amenities,
        'notes': notes,
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
    return {
        'title': validated.get('title') or None,
        'property_type': validated.get('property_type'),
        'deal_mode': validated.get('deal_mode'),
        'location': {
            'city': validated.get('city') or None,
            'district': validated.get('district') or None,
            'neighborhood': validated.get('neighborhood') or None,
            'address': validated.get('address') or None,
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
        'amenities': validated.get('amenities') or None,
        'notes': validated.get('notes') or None,
    }
