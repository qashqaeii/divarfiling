"""نمایش فیلدها بر اساس نوع معامله — قیمت، تاریخ شمسی."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import jdatetime
from django.utils import timezone as dj_tz

from workspace.services.columns import COLUMN_ALIASES
from workspace.services.formatting import format_area, format_toman, format_toman_compact
from workspace.services.jalali_input import to_persian_digits
from workspace.services.listing_features import is_listing_feature_key

RENT_FIELD_MARKERS = ('ودیعه', 'اجاره', 'deposit', 'rent', 'رهن', 'رهن کامل')
SALE_FIELD_MARKERS = ('قیمت', 'price', 'فروش')
PER_SQM_MARKERS = ('هر متر', 'مترمربع', 'sqm', 'price_per')
URL_KEY_MARKERS = ('لینک', 'link', 'url', 'تصویر نقشه', 'mapimage', 'http')
LONG_TEXT_MARKERS = ('توضیح', 'description', 'متن آگهی')

# فیلدهای ساختاری ملک — در تب «ملک» (نه فقط تب ویژگی‌ها)
CORE_PROPERTY_MARKERS = (
    'متراژ', 'area', 'اتاق', 'rooms', 'تعداد اتاق',
    'طبقه', 'floor',
    'تعداد واحد در طبقه', 'تعداد کل طبقات', 'جهت ساختمان',
)

BUILD_YEAR_KEYS = frozenset({
    'ساخت', 'سال ساخت', 'build_year', 'سن بنا', 'سال ساخت بنا',
})

# فیلدهای مکان — در تب «مکان»
CORE_LOCATION_MARKERS = (
    'استان', 'شهر', 'city', 'محله', 'neighborhood', 'خیابان', 'آدرس', 'address',
    'منطقه', 'district', 'عرض جغرافیایی', 'طول جغرافیایی',
    'latitude', 'longitude', 'lat', 'lng', 'مختصات', 'شعاع', 'نوع مختصات',
)

CONTACT_MARKERS = (
    'شماره تماس', 'نام مالک', 'نام و نام خانوادگی مالک', 'نام صاحب',
    'owner_phone', 'owner_name', 'phone_text',
    'تلفن', 'موبایل', 'phone', 'تماس',
)

# برچسب فارسی برای کلیدهای انگلیسی/داخلی
FIELD_LABELS = {
    'owner_phone': 'شماره تماس',
    'owner_name': 'نام مالک',
    'phone': 'شماره تماس',
    'phone_text': 'شماره تماس',
    'title': 'عنوان',
    'token': 'شناسه',
    'link': 'لینک',
    'description': 'توضیحات',
    'city': 'شهر',
    'neighborhood': 'محله',
    'district': 'منطقه',
    'استان': 'استان',
    'خیابان': 'خیابان',
    'area': 'متراژ',
    'rooms': 'اتاق',
    'floor': 'طبقه',
    'price': 'قیمت',
    'deposit': 'ودیعه',
    'rent': 'اجاره',
    'latitude': 'عرض جغرافیایی',
    'longitude': 'طول جغرافیایی',
    'lat': 'عرض جغرافیایی',
    'lng': 'طول جغرافیایی',
    'build_year': 'سال ساخت',
    'business_type': 'نوع آگهی‌دهنده',
}

SECTION_ORDER = ('مالی', 'ملک', 'مکان', 'متن', 'تماس')

PROPERTY_FIELD_ORDER = (
    'متراژ', 'area', 'اتاق', 'rooms', 'تعداد اتاق', 'طبقه', 'floor',
    'سال ساخت', 'ساخت', 'build_year', 'سن بنا',
    'تعداد واحد در طبقه', 'تعداد کل طبقات ساختمان', 'جهت ساختمان',
)

LOCATION_FIELD_ORDER = (
    'استان', 'شهر', 'city', 'منطقه', 'district', 'محله', 'neighborhood',
    'خیابان', 'آدرس', 'address', 'عرض جغرافیایی', 'طول جغرافیایی',
    'latitude', 'longitude', 'نوع مختصات', 'در شعاع (متر)',
)

CONTACT_FIELD_ORDER = (
    'نام مالک', 'owner_name', 'نام و نام خانوادگی مالک', 'نام صاحب',
    'شماره تماس', 'owner_phone', 'phone', 'موبایل', 'تلفن', 'تماس',
)

_EXACT_COORD_MARKERS = frozenset({'EXACT', 'دقیق', 'دقيق'})
_FUZZY_COORD_MARKERS = frozenset({
    'FUZZY', 'تقریبی', 'تقريبي', 'APPROXIMATE', 'APPROX',
})


def _parse_radius_meters(value: Any) -> Optional[int]:
    if value is None or value == '' or value == '-':
        return None
    if isinstance(value, (int, float)):
        v = int(round(float(value)))
        return v if v > 0 else None
    s = str(value).strip().replace('،', ',').replace(',', '')
    m = re.search(r'\d+', s)
    if not m:
        return None
    v = int(m.group())
    return v if v > 0 else None


def _normalize_coord_type(raw: Any) -> str:
    s = str(raw or '').strip()
    s = s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
    return s.upper().replace(' ', '')


def location_accuracy_for_map(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """دقت موقعیت آگهی — برای tooltip نقشه."""
    data = data or {}
    raw_type = str(data.get('نوع مختصات') or data.get('نقشه_نوع') or '').strip()
    norm = _normalize_coord_type(raw_type)
    radius = _parse_radius_meters(
        data.get('در شعاع (متر)') if data.get('در شعاع (متر)') not in (None, '', '-')
        else data.get('نقشه_شعاع_محدوده_متر')
    )

    if norm in _EXACT_COORD_MARKERS or raw_type in _EXACT_COORD_MARKERS:
        return {'label': 'موقعیت دقیق روی نقشه', 'kind': 'exact', 'radius_m': 0}
    if norm in _FUZZY_COORD_MARKERS or raw_type in _FUZZY_COORD_MARKERS or 'تقری' in raw_type or radius:
        if radius:
            return {
                'label': f'موقعیت تقریبی — در شعاع حدود {to_persian_digits(radius)} متر',
                'kind': 'approx',
                'radius_m': radius,
            }
        return {'label': 'موقعیت تقریبی روی نقشه', 'kind': 'approx', 'radius_m': 0}
    return {'label': '', 'kind': '', 'radius_m': 0}


def market_tier_from_score(score: Any) -> str:
    """رده موقعیت قیمتی — زیر بازار / متعارف / بالای بازار."""
    if score is None or score == '':
        return 'unknown'
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 'unknown'
    if s != s:
        return 'unknown'
    if s <= -12:
        return 'under'
    if s >= 12:
        return 'over'
    return 'fair'


KNOWN_TEXT_PRICES = frozenset({'متعارف', 'توافقی', 'رهن کامل', 'رایگان'})


def _parse_text_price(raw: Any) -> str:
    """متن قیمت غیرعددی دیوار — مثل متعارف یا توافقی."""
    if raw is None:
        return ''
    s = str(raw).strip()
    if not s or s in ('-', '—', 'nan', 'None'):
        return ''
    from workspace.services.columns import _safe_int
    if _safe_int(s) is not None:
        return ''
    if 'متعارف' in s:
        return 'متعارف'
    if 'توافقی' in s:
        return 'توافقی'
    if s in KNOWN_TEXT_PRICES:
        return s
    if len(s) <= 32 and not any(ch.isdigit() for ch in s):
        return s
    return ''


def _listing_text_deposit(data: Dict[str, Any]) -> str:
    for key in ('اجاره_ودیعه_نمایش', 'ودیعه', 'رهن', 'deposit'):
        txt = _parse_text_price(data.get(key))
        if txt:
            return txt
    return ''


def _listing_text_rent(data: Dict[str, Any]) -> str:
    for key in ('اجاره_ماهانه_نمایش', 'اجاره', 'اجاره ماهانه', 'rent'):
        txt = _parse_text_price(data.get(key))
        if txt:
            return txt
    return ''


def _listing_text_sale(data: Dict[str, Any]) -> str:
    for key in ('مالی_قیمت_کل_نمایش', 'price_text', 'قیمت', 'price'):
        txt = _parse_text_price(data.get(key))
        if txt:
            return txt
    return ''


def listing_map_price_label(listing, tx: Optional[Dict[str, Any]] = None) -> str:
    """برچسب قیمت نقشه — عددی یا متن (متعارف / توافقی)."""
    tx = tx or transaction_profile(getattr(listing, 'transaction_type', '') or '')
    data = getattr(listing, 'data', None) or {}

    price_val = getattr(listing, 'price', None)
    rent_val = getattr(listing, 'rent', None)
    deposit_val = getattr(listing, 'deposit', None)
    if tx.get('show_price') and price_val is not None:
        return format_toman(price_val)
    if tx.get('show_rent') and rent_val is not None:
        return f'اجاره {format_toman(rent_val)}'
    if tx.get('show_deposit') and deposit_val is not None:
        return f'ودیعه {format_toman(deposit_val)}'

    sale_txt = _listing_text_sale(data)
    dep_txt = _listing_text_deposit(data)
    rent_txt = _listing_text_rent(data)

    if tx.get('show_price') and sale_txt:
        return sale_txt

    if tx.get('show_deposit') or tx.get('show_rent') or tx.get('is_rent'):
        if dep_txt == 'متعارف' and rent_txt == 'متعارف':
            return 'متعارف'
        if dep_txt and rent_txt:
            dep_part = dep_txt if dep_txt in KNOWN_TEXT_PRICES else f'ودیعه {dep_txt}'
            rent_part = rent_txt if rent_txt in KNOWN_TEXT_PRICES else f'اجاره {rent_txt}'
            if dep_part == rent_part:
                return dep_part
            return f'{dep_part} · {rent_part}'
        if dep_txt:
            return dep_txt if dep_txt in KNOWN_TEXT_PRICES else f'ودیعه {dep_txt}'
        if rent_txt:
            return rent_txt if rent_txt in KNOWN_TEXT_PRICES else f'اجاره {rent_txt}'

    if sale_txt:
        return sale_txt
    return '—'


def listing_map_deposit_label(listing) -> str:
    if getattr(listing, 'deposit', None):
        return format_toman(listing.deposit)
    data = getattr(listing, 'data', None)
    return _listing_text_deposit(data if isinstance(data, dict) else {})


def listing_map_rent_label(listing) -> str:
    if getattr(listing, 'rent', None):
        return format_toman(listing.rent)
    data = getattr(listing, 'data', None)
    return _listing_text_rent(data if isinstance(data, dict) else {})


MONEY_FIELD_ORDER = (
    'قیمت', 'price', 'قیمت هر متر', 'قیمت/متر', 'ودیعه', 'deposit',
    'رهن', 'اجاره', 'rent', 'اجاره ماهانه', 'ودیعه و اجاره',
    'ودیعه (شرایط تبدیل)', 'اجاره ماهانه (شرایط تبدیل)',
)

_DOSSIER_INTERNAL_PREFIXES = (
    'مالی_', 'سیستمی_', 'تماس_', 'رسانه_', 'فروشنده_', 'دسته‌بندی_',
    'اجاره_', 'مکان_', 'نقشه_', 'ویژگی_', 'مشاور_business',
)

_DOSSIER_INTERNAL_EXACT_KEYS = frozenset({
    'متراژ_عدد', 'rent_convertibility', 'اجاره_قابل_تبدیل', 'price_text',
    'normalized_city', 'normalized_district', 'published_at_iso',
    'city_persian', 'district_persian', 'مکان_مختصات_اعتبار',
})

_CANONICAL_MONEY_KEYS = frozenset({
    'قیمت', 'price', 'قیمت هر متر', 'قیمت/متر',
    'ودیعه', 'deposit', 'رهن', 'اجاره', 'rent', 'اجاره ماهانه',
    'ودیعه و اجاره',
    'ودیعه (شرایط تبدیل)', 'اجاره ماهانه (شرایط تبدیل)',
})

_RENT_DOSSIER_MONEY_KEYS = frozenset({
    'ودیعه', 'deposit', 'رهن', 'اجاره', 'rent', 'اجاره ماهانه',
    'ودیعه و اجاره', 'ودیعه (شرایط تبدیل)', 'اجاره ماهانه (شرایط تبدیل)',
})

_SALE_DOSSIER_MONEY_KEYS = frozenset({
    'قیمت', 'price', 'قیمت هر متر', 'قیمت/متر',
})

_NON_DISPLAYABLE_RAW_VALUES = frozenset({
    'unknown', 'numeric', 'valid', 'null', 'none', 'nan',
})


def _clean_dossier_label(val: Any) -> str:
    s = str(val or '').strip()
    if not s or s.lower() in ('nan', 'none', '-', '—'):
        return ''
    return s


def _is_dossier_internal_key(key: str) -> bool:
    """کلیدهای فنی JSON/Android — فقط برای ذخیره، نه ردیف پرونده."""
    k = str(key or '').strip()
    if not k:
        return True
    if k in _DOSSIER_INTERNAL_EXACT_KEYS:
        return True
    if any(k.startswith(prefix) for prefix in _DOSSIER_INTERNAL_PREFIXES):
        return True
    if re.search(r'_(وضعیت|عدد|نمایش|برچسب)$', k):
        return True
    return False


def _is_rent_convertible(raw: dict) -> bool:
    conv = str(
        raw.get('اجاره_قابل_تبدیل')
        or raw.get('rent_convertibility')
        or raw.get('ودیعه و اجاره')
        or ''
    ).strip()
    if not conv:
        return False
    if 'غیر' in conv and 'قابل' in conv:
        return False
    low = conv.lower()
    return 'قابل تبدیل' in conv or low in ('convertible', 'convertable')


def _enrich_dossier_financial_fields(data: dict, listing, profile: Dict, raw: dict) -> None:
    from workspace.services.columns import _listing_money_scalar, _safe_int

    merged = {**(raw or {}), **(data or {})}

    if profile.get('is_sale') and not profile.get('is_mixed'):
        for key in list(data.keys()):
            if key in _RENT_DOSSIER_MONEY_KEYS and key != 'ودیعه و اجاره':
                data.pop(key, None)

        price_txt = _listing_text_sale(merged)
        price_num = listing.price if listing.price is not None else _listing_money_scalar(merged, 'price')
        if price_txt:
            data['قیمت'] = price_txt
        elif price_num is not None:
            data['قیمت'] = price_num

        pps_txt = _parse_text_price(merged.get('مالی_قیمت_هر_متر_نمایش'))
        pps_num = _safe_int(merged.get('مالی_قیمت_هر_متر_عدد'))
        if pps_txt:
            data['قیمت هر متر'] = pps_txt
        elif pps_num is not None:
            data['قیمت هر متر'] = pps_num
        return

    if not (profile.get('is_rent') or profile.get('is_mixed')):
        return

    for key in list(data.keys()):
        if key in _SALE_DOSSIER_MONEY_KEYS:
            data.pop(key, None)

    dep_txt = _listing_text_deposit(merged)
    dep_num = listing.deposit if listing.deposit is not None else _listing_money_scalar(merged, 'deposit')
    if dep_txt:
        data['ودیعه'] = dep_txt
    elif dep_num is not None:
        data['ودیعه'] = dep_num

    rent_txt = _listing_text_rent(merged)
    rent_num = listing.rent if listing.rent is not None else _listing_money_scalar(merged, 'rent')
    if rent_txt:
        data['اجاره'] = rent_txt
    elif rent_num is not None:
        data['اجاره'] = rent_num
    elif listing.rent is not None:
        data['اجاره'] = listing.rent

    combined = _clean_dossier_label(merged.get('ودیعه و اجاره'))
    if combined and combined not in ('قابل تبدیل', 'غیر قابل تبدیل'):
        data['ودیعه و اجاره'] = combined

    if _is_rent_convertible(merged):
        conv_dep = _safe_int(merged.get('اجاره_ودیعه_تبدیل_عدد'))
        conv_rent = _safe_int(merged.get('اجاره_ماهانه_تبدیل_عدد'))
        if conv_dep is not None or conv_rent is not None:
            data['ودیعه و اجاره'] = 'قابل تبدیل'
            if conv_dep is not None:
                data['ودیعه (شرایط تبدیل)'] = conv_dep
            if conv_rent is not None:
                data['اجاره ماهانه (شرایط تبدیل)'] = conv_rent


def _promote_dossier_location_alias(data: dict, source_key: str, target_key: str) -> None:
    """کلیدهای مکان_ در JSON را به برچسب پرونده منتقل می‌کند — فقط روی کپی نمایش."""
    val = _clean_dossier_label(data.get(source_key))
    if val and not _clean_dossier_label(data.get(target_key)):
        data[target_key] = val
    data.pop(source_key, None)


def _normalize_dossier_location_fields(data: dict) -> None:
    city = _clean_dossier_label(data.get('شهر'))
    neighborhood = _clean_dossier_label(data.get('محله'))
    address = _clean_dossier_label(data.get('آدرس'))

    _promote_dossier_location_alias(data, 'مکان_استان', 'استان')
    _promote_dossier_location_alias(data, 'مکان_منطقه', 'منطقه')
    _promote_dossier_location_alias(data, 'مکان_محله', 'محله')
    _promote_dossier_location_alias(data, 'مکان_خیابان', 'خیابان')
    _promote_dossier_location_alias(data, 'مکان_آدرس', 'آدرس')

    for alias in (
        'مکان_شهر',
        'city', 'city_persian', 'district', 'district_persian', 'address',
    ):
        data.pop(alias, None)

    raw_acc = str(data.get('مکان_مختصات_اعتبار') or '').strip().lower()
    if raw_acc in ('valid', 'exact'):
        if not _clean_dossier_label(data.get('نوع مختصات')):
            data['نوع مختصات'] = 'دقیق'
    elif raw_acc in ('fuzzy', 'approximate', 'approx'):
        if not _clean_dossier_label(data.get('نوع مختصات')):
            data['نوع مختصات'] = 'تقریبی'
    data.pop('مکان_مختصات_اعتبار', None)

    coord = str(data.get('نوع مختصات') or '').strip()
    if coord:
        norm = _normalize_coord_type(coord)
        if norm in _EXACT_COORD_MARKERS or coord in _EXACT_COORD_MARKERS:
            data['نوع مختصات'] = 'دقیق'
        elif norm in _FUZZY_COORD_MARKERS or 'تقری' in coord:
            data['نوع مختصات'] = 'تقریبی'

    if address:
        if city and address == city:
            data.pop('آدرس', None)
        elif neighborhood and address == neighborhood:
            data.pop('آدرس', None)


def _strip_dossier_internal_keys(data: dict) -> None:
    for key in list(data.keys()):
        if _is_dossier_internal_key(key):
            data.pop(key, None)


def apply_dossier_presentation_rules(
    data: dict,
    listing,
    profile: Dict,
    *,
    raw_data: Optional[dict] = None,
) -> None:
    """قواعد نمایش پرونده — فقط روی کپی نمایش، بدون تغییر Listing.data."""
    raw = raw_data if raw_data is not None else (getattr(listing, 'data', None) or {})
    _enrich_dossier_financial_fields(data, listing, profile, raw if isinstance(raw, dict) else {})
    _normalize_dossier_location_fields(data)
    _strip_dossier_internal_keys(data)
    if _clean_dossier_label(data.get('متراژ')):
        data.pop('متراژ_عدد', None)


def transaction_profile(transaction_type: str = '') -> Dict[str, Any]:
    """پروفایل نمایش بر اساس نوع معامله فایل."""
    tt = (transaction_type or '').strip()
    tl = tt.lower()

    is_sale = tt in ('فروش',) or 'فروش' in tt
    is_rent = tt in ('اجاره',) or ('اجاره' in tt and 'فروش' not in tt)
    is_mixed = tt == 'ترکیبی' or (is_sale and is_rent)

    if is_mixed:
        mode = 'ترکیبی'
    elif is_rent:
        mode = 'اجاره'
    elif is_sale:
        mode = 'فروش'
    else:
        mode = tt or 'فروش'

    return {
        'mode': mode,
        'is_sale': mode == 'فروش',
        'is_rent': mode == 'اجاره',
        'is_mixed': mode == 'ترکیبی',
        'show_price': mode in ('فروش', 'ترکیبی'),
        'show_price_per_sqm': mode in ('فروش', 'ترکیبی'),
        'show_deposit': mode in ('اجاره', 'ترکیبی'),
        'show_rent': mode in ('اجاره', 'ترکیبی'),
        'badge': mode,
    }


def _is_money_key(key: str) -> bool:
    if _is_dossier_internal_key(key):
        return False
    k = str(key or '').strip()
    if k in _CANONICAL_MONEY_KEYS:
        return True
    kl = k.lower()
    if 'قیمت هر متر' in k or 'قیمت/متر' in k:
        return True
    return False


def _is_per_sqm_key(key: str) -> bool:
    kl = key.lower()
    return any(m in key or m in kl for m in PER_SQM_MARKERS)


def _is_rent_field(key: str) -> bool:
    kl = key.lower()
    return any(m in key or m in kl for m in RENT_FIELD_MARKERS)


def _is_sale_price_field(key: str) -> bool:
    if _is_rent_field(key):
        return False
    if _is_per_sqm_key(key):
        return True
    kl = key.lower()
    return any(m in key or m in kl for m in SALE_FIELD_MARKERS)


def field_visible_for_transaction(key: str, profile: Dict) -> bool:
    if _is_dossier_internal_key(key):
        return False
    if profile.get('is_mixed'):
        return True
    if profile.get('is_sale'):
        return key in _SALE_DOSSIER_MONEY_KEYS or not _is_rent_field(key)
    if profile.get('is_rent'):
        if key in _SALE_DOSSIER_MONEY_KEYS:
            return False
        if key.startswith('مالی_'):
            return False
        if _is_sale_price_field(key) and not _is_rent_field(key):
            return False
        return True
    return True


def _try_parse_jalali(s: str) -> Optional[jdatetime.datetime]:
    """تاریخ شمسی خام (۱۳۰۰–۱۵۰۰) — بدون تبدیل اشتباه به میلادی."""
    s = str(s).strip()
    m = re.match(
        r'^(\d{4})[/-](\d{1,2})[/-](\d{1,2})'
        r'(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?',
        s,
    )
    if not m:
        return None
    y = int(m.group(1))
    if not (1300 <= y <= 1500):
        return None
    try:
        return jdatetime.datetime(
            y, int(m.group(2)), int(m.group(3)),
            int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0),
        )
    except (ValueError, TypeError):
        return None


def _try_parse_date(val: Any) -> Optional[datetime]:
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    s = str(val).strip()
    if not s or len(s) < 8:
        return None
    if _try_parse_jalali(s):
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d'):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _format_date_display(value: Any) -> Optional[str]:
    s = str(value).strip()
    if not s:
        return None
    jdt = _try_parse_jalali(s)
    if jdt:
        if jdt.hour or jdt.minute:
            return jdt.strftime('%Y/%m/%d %H:%M')
        return jdt.strftime('%Y/%m/%d')
    dt = _try_parse_date(value)
    if dt:
        try:
            if dj_tz.is_aware(dt):
                dt = dj_tz.localtime(dt)
            jdt = jdatetime.datetime.fromgregorian(datetime=dt)
            if jdt.hour or jdt.minute:
                return jdt.strftime('%Y/%m/%d %H:%M')
            return jdt.strftime('%Y/%m/%d')
        except Exception:
            pass
    return None


def _is_date_key(key: str) -> bool:
    kl = key.lower()
    return any(x in key or x in kl for x in (
        'تاریخ', 'date', 'ایجاد', 'انقضا', 'انتشار', 'published', 'expires', 'created',
        'نردبان', 'به‌روزرسانی', 'بروزرسانی',
    ))


def _looks_like_phone_number(value: Any) -> bool:
    """تشخیص شماره موبایل/تلفن تا به‌عنوان مبلغ فرمت نشود."""
    digits = re.sub(r'\D', '', str(value or ''))
    if not digits:
        return False
    if digits.startswith('98') and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith('0'):
        return len(digits) in (10, 11) and digits.startswith(('09', '021', '026', '031', '041', '051', '061', '071', '081', '011'))
    return len(digits) == 10 and digits.startswith('9')


def format_display_value(key: str, value: Any, profile: Optional[Dict] = None) -> str:
    """فرمت مقدار برای نمایش در جدول/جزئیات."""
    if value is None or str(value).strip() in ('', 'nan', 'None', '-'):
        return '—'

    raw_s = str(value).strip()
    if raw_s.lower() in _NON_DISPLAYABLE_RAW_VALUES:
        return '—'

    if profile and not field_visible_for_transaction(key, profile):
        return '—'

    if _is_date_key(key):
        formatted = _format_date_display(value)
        if formatted:
            return formatted

    if _is_contact_key(key) or _looks_like_phone_number(value):
        return str(value).strip()

    if _is_money_key(key):
        s_money = str(value).strip()
        if s_money in KNOWN_TEXT_PRICES:
            return s_money
        try:
            num = int(float(s_money.replace(',', '').replace('٬', '')))
            if num < 0:
                return '—'
            if num == 0:
                return format_toman(0, per_sqm=_is_per_sqm_key(key))
            return format_toman(num, per_sqm=_is_per_sqm_key(key))
        except (ValueError, TypeError):
            pass

    if any(x in key.lower() for x in ('متراژ', 'area')) and not _is_money_key(key):
        try:
            return format_area(float(value))
        except (ValueError, TypeError):
            pass

    s = str(value).strip()
    # اعداد ۹+ رقمی معمولاً مبلغ‌اند — مگر شماره تماس (۰۹…) یا فیلد تماس
    if re.fullmatch(r'\d{9,}', s) and not s.startswith('0'):
        try:
            return format_toman(int(s), per_sqm=_is_per_sqm_key(key))
        except ValueError:
            pass

    return s


def _marker_in_key(key: str, markers: Tuple[str, ...]) -> bool:
    kl = key.lower()
    return any(m in key or m in kl for m in markers)


def _is_core_property_key(key: str) -> bool:
    k = str(key or '').strip()
    if k in BUILD_YEAR_KEYS:
        return True
    return _marker_in_key(key, CORE_PROPERTY_MARKERS)


def _is_location_key(key: str) -> bool:
    return _marker_in_key(key, CORE_LOCATION_MARKERS)


def _is_contact_key(key: str) -> bool:
    return _marker_in_key(key, CONTACT_MARKERS)


def display_field_label(key: str) -> str:
    """برچسب قابل‌نمایش فیلد — انگلیسی → فارسی."""
    k = str(key or '').strip()
    if not k:
        return k
    if k in FIELD_LABELS:
        return FIELD_LABELS[k]
    mapped = FIELD_LABELS.get(k.lower())
    if mapped:
        return mapped
    return k


def _include_in_sections(key: str) -> bool:
    """آیا فیلد در تب‌های اصلی نمایش داده شود (نه فقط تب ویژگی‌ها)؟"""
    if _is_dossier_internal_key(key):
        return False
    if _is_core_property_key(key) or _is_location_key(key):
        return True
    if _is_money_key(key) or _is_contact_key(key):
        return True
    kl = key.lower()
    if 'توضیح' in key or 'description' in kl:
        return True
    return not is_listing_feature_key(key)


def _resolve_section_name(key: str) -> str:
    """تعیین تب مناسب برای هر فیلد."""
    kl = key.lower()
    if _is_money_key(key):
        return 'مالی'
    if _is_core_property_key(key):
        return 'ملک'
    if _is_location_key(key):
        return 'مکان'
    if _is_contact_key(key):
        return 'تماس'
    if 'توضیح' in key or 'description' in kl:
        return 'متن'
    return 'سایر'


def _field_sort_key(section: str, key: str) -> Tuple[int, str]:
    order_map = {
        'مالی': MONEY_FIELD_ORDER,
        'ملک': PROPERTY_FIELD_ORDER,
        'مکان': LOCATION_FIELD_ORDER,
        'تماس': CONTACT_FIELD_ORDER,
    }
    preferred = order_map.get(section, ())
    kl = key.lower()
    for idx, marker in enumerate(preferred):
        if marker in key or marker in kl:
            return (idx, key)
    return (len(preferred) + 1, key)


def _sort_section_fields(section: str, fields: Dict[str, str]) -> Dict[str, str]:
    ordered = sorted(fields.items(), key=lambda item: _field_sort_key(section, item[0]))
    return dict(ordered)


def _set_if_missing(data: dict, key: str, value: Any) -> None:
    if value is None:
        return
    s = str(value).strip()
    if not s or s.lower() in ('nan', 'none', '-', '—'):
        return
    existing = data.get(key)
    if existing is None or not str(existing).strip() or str(existing).strip().lower() in ('nan', 'none', '-'):
        data[key] = value


def _schedule_field_has_value(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    return bool(s) and s.lower() not in ('nan', 'none', '-', '—')


def _collapse_schedule_fields(data: dict, listing) -> None:
    """یک برچسب نمایشی برای هر مفهوم زمان‌بندی — aliasهای اکسل/ISO در لایه نمایش ادغام می‌شوند."""
    from workspace.services.divar_listing_datetime import (
        DATA_KEY_LAST_BUMPED_AT,
        DATA_KEY_LAST_UPDATED_AT,
        SHAMSI_KEY_LAST_BUMPED,
        SHAMSI_KEY_LAST_UPDATED,
        SHAMSI_KEY_PUBLISH,
        listing_datetime_to_jalali_label,
    )

    if not data:
        return

    publish_aliases = tuple(dict.fromkeys((
        *COLUMN_ALIASES['published_at'],
        SHAMSI_KEY_PUBLISH,
        'published_at_iso',
        'انتشار_تاریخ_میلادی',
    )))
    expire_aliases = tuple(dict.fromkeys((*COLUMN_ALIASES['expires_at'], 'تاریخ انقضا')))
    bump_aliases = tuple(dict.fromkeys((
        *COLUMN_ALIASES['last_bumped_at'],
        DATA_KEY_LAST_BUMPED_AT,
        SHAMSI_KEY_LAST_BUMPED,
    )))
    update_aliases = tuple(dict.fromkeys((
        *COLUMN_ALIASES['last_updated_at'],
        DATA_KEY_LAST_UPDATED_AT,
        SHAMSI_KEY_LAST_UPDATED,
    )))

    def _collapse_model_field(model_attr: str, label: str, aliases: tuple) -> None:
        model_val = getattr(listing, model_attr, None)
        keys_present = [k for k in aliases if k in data]
        if model_val is None and not keys_present:
            return
        value = model_val
        if value is None:
            for key in aliases:
                raw = data.get(key)
                if _schedule_field_has_value(raw):
                    value = raw
                    break
        if value is None:
            for key in aliases:
                data.pop(key, None)
            data.pop(label, None)
            return
        for key in aliases:
            data.pop(key, None)
        data.pop(label, None)
        data[label] = value

    def _collapse_display_only(label: str, aliases: tuple) -> None:
        keys_present = [k for k in aliases if k in data]
        if not keys_present and not _schedule_field_has_value(data.get(label)):
            return
        value = None
        if _schedule_field_has_value(data.get(label)):
            value = data.get(label)
        if value is None:
            for key in aliases:
                raw = data.get(key)
                if _schedule_field_has_value(raw):
                    value = raw
                    break
        if value is None:
            for key in aliases:
                data.pop(key, None)
            data.pop(label, None)
            return
        display_val = value
        if label in ('آخرین نردبان', 'آخرین به‌روزرسانی'):
            jalali = listing_datetime_to_jalali_label(value)
            if jalali:
                display_val = jalali
        for key in aliases:
            data.pop(key, None)
        data.pop(label, None)
        data[label] = display_val

    _collapse_model_field('published_at', 'تاریخ انتشار', publish_aliases)
    _collapse_model_field('expires_at', 'تاریخ انقضا', expire_aliases)
    _collapse_display_only('آخرین نردبان', bump_aliases)
    _collapse_display_only('آخرین به‌روزرسانی', update_aliases)


def _dedupe_listing_data_keys(data: dict) -> dict:
    """حذف کلیدهای تکراری انگلیسی/داخلی وقتی معادل فارسی export وجود دارد."""
    if not data:
        return data
    out = dict(data)
    drop_if_present = {
        'description': ('توضیحات',),
        'city': ('شهر', 'مکان_شهر'),
        'city_persian': ('شهر', 'مکان_شهر'),
        'مکان_شهر': ('شهر',),
        'district': ('محله', 'مکان_منطقه'),
        'district_persian': ('محله', 'مکان_منطقه'),
        'مکان_منطقه': ('محله',),
        'neighborhood': ('محله',),
        'latitude': ('عرض جغرافیایی', 'مکان_مختصات_lat'),
        'longitude': ('طول جغرافیایی', 'مکان_مختصات_lng'),
        'مکان_مختصات_lat': ('عرض جغرافیایی',),
        'مکان_مختصات_lng': ('طول جغرافیایی',),
        'lat': ('عرض جغرافیایی',),
        'lng': ('طول جغرافیایی',),
        'title': ('عنوان',),
        'token': ('شناسه',),
        'link': ('لینک',),
        'deposit': ('ودیعه',),
        'rent': ('اجاره ماهانه', 'اجاره'),
        'area': ('متراژ',),
        'price': ('قیمت',),
        'business_type': ('نوع آگهی دهنده', 'نوع آگهی‌دهنده'),
        'فروشنده_business_type': ('نوع آگهی دهنده', 'نوع آگهی‌دهنده'),
        'owner_phone': ('شماره تماس', 'موبایل', 'تلفن'),
        'phone': ('شماره تماس', 'موبایل', 'تلفن'),
        'phone_text': ('شماره تماس', 'موبایل', 'تلفن'),
        'owner_name': ('نام مالک', 'نام و نام خانوادگی مالک', 'نام صاحب'),
    }
    for key, preferred in drop_if_present.items():
        if key not in out:
            continue
        if any(p in out and out.get(p) not in (None, '', '-', '—') for p in preferred):
            out.pop(key, None)
    return out


def _normalize_contact_fields(data: dict, listing) -> None:
    """یکپارچه‌سازی فیلدهای تماس — فقط برچسب فارسی و مقدار صحیح."""
    from workspace.services.listing_edit import (
        OWNER_NAME_KEYS,
        OWNER_PHONE_KEYS,
        owner_name_from_listing,
        owner_phone_from_listing,
    )

    phone = (owner_phone_from_listing(listing) or '').strip()
    name = (owner_name_from_listing(listing) or '').strip()

    for key in (*OWNER_PHONE_KEYS, *OWNER_NAME_KEYS, 'phone_text'):
        data.pop(key, None)

    for key in list(data.keys()):
        kl = str(key).strip().lower()
        if kl in ('owner_phone', 'owner_name', 'phone', 'phone_text'):
            data.pop(key, None)

    if phone:
        data['شماره تماس'] = phone
    if name:
        data['نام مالک'] = name


def _set_model_field(data: dict, key: str, value: Any, *, clear_keys: tuple = ()) -> None:
    """اولویت با فیلد مدل — برای نمایش پس از ویرایش."""
    if value is None:
        return
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in ('nan', 'none', '-', '—'):
            return
        value = s
    for ck in clear_keys:
        data.pop(ck, None)
    data[key] = value


def build_listing_display_data(
    listing,
    feat: Optional[Dict[str, Any]] = None,
    *,
    transaction_type: str = '',
) -> dict:
    """ادغام فیلدهای مدل و استخراج‌شده در دیکشنری نمایش."""
    raw_stored = dict(listing.data or {})
    data = _dedupe_listing_data_keys(dict(raw_stored))

    # فیلدهای مدل بعد از ویرایش اولویت دارند (نه فقط وقتی data خالی است)
    _set_model_field(data, 'شناسه', listing.token)
    _set_model_field(data, 'عنوان', listing.title, clear_keys=('title',))
    _set_model_field(data, 'لینک', listing.link, clear_keys=('link', 'url'))
    _set_model_field(data, 'متراژ', listing.area, clear_keys=('area',))
    _set_model_field(data, 'اتاق', listing.rooms, clear_keys=('rooms', 'تعداد اتاق'))
    _set_model_field(data, 'شهر', listing.city, clear_keys=('city', 'مکان_شهر', 'city_persian'))
    _set_model_field(data, 'محله', listing.neighborhood, clear_keys=('neighborhood',))
    _set_model_field(data, 'قیمت', listing.price, clear_keys=('price',))
    _set_model_field(data, 'ودیعه', listing.deposit, clear_keys=('deposit', 'رهن'))
    _set_model_field(data, 'اجاره', listing.rent, clear_keys=('rent', 'اجاره ماهانه'))

    desc = (listing.description or '').strip()
    if desc:
        for key in list(data.keys()):
            kl = str(key).lower()
            if key != 'توضیحات' and ('توضیح' in str(key) or kl in ('description', 'desc')):
                data.pop(key, None)
        data['توضیحات'] = desc

    advertiser_label = ''
    if feat and feat.get('advertiser_label'):
        advertiser_label = str(feat['advertiser_label']).strip()
    if not advertiser_label:
        from workspace.services.advertiser_signal import listing_advertiser_display
        advertiser_label = listing_advertiser_display(listing)['label']
    data['نوع آگهی‌دهنده'] = advertiser_label
    data['نوع آگهی دهنده'] = advertiser_label
    _set_model_field(data, 'عرض جغرافیایی', listing.latitude, clear_keys=('latitude', 'lat', 'مکان_مختصات_lat'))
    _set_model_field(data, 'طول جغرافیایی', listing.longitude, clear_keys=('longitude', 'lng', 'مکان_مختصات_lng'))

    from workspace.services.divar_listing_datetime import (
        DATA_KEY_LAST_BUMPED_AT,
        DATA_KEY_LAST_UPDATED_AT,
        listing_datetime_to_jalali_label,
    )

    if listing.published_at:
        _set_if_missing(data, 'تاریخ انتشار', listing.published_at)
    if listing.expires_at:
        _set_if_missing(data, 'تاریخ انقضا', listing.expires_at)
    if data.get(DATA_KEY_LAST_BUMPED_AT):
        _set_if_missing(
            data,
            'آخرین نردبان',
            listing_datetime_to_jalali_label(data.get(DATA_KEY_LAST_BUMPED_AT)),
        )
    if data.get(DATA_KEY_LAST_UPDATED_AT):
        _set_if_missing(
            data,
            'آخرین به‌روزرسانی',
            listing_datetime_to_jalali_label(data.get(DATA_KEY_LAST_UPDATED_AT)),
        )
    _collapse_schedule_fields(data, listing)
    if listing.images:
        data['تعداد تصاویر'] = len(listing.images)

    if feat:
        _set_if_missing(data, 'طبقه', feat.get('floor'))
        if feat.get('rooms'):
            _set_model_field(data, 'اتاق', feat.get('rooms'))
        if feat.get('build_year'):
            _set_if_missing(data, 'سال ساخت', feat['build_year'])

    _normalize_contact_fields(data, listing)
    profile = transaction_profile(transaction_type)
    apply_dossier_presentation_rules(data, listing, profile, raw_data=raw_stored)
    return data


def format_sections(
    data: dict,
    profile: Dict,
) -> Dict[str, Dict[str, str]]:
    """ساخت سکشن‌های فرمت‌شده با فیلتر نوع معامله."""
    sections: Dict[str, Dict[str, str]] = {name: {} for name in SECTION_ORDER}

    for k, v in (data or {}).items():
        if not _include_in_sections(k):
            continue
        if v is None or str(v).strip() in ('', 'nan', 'None'):
            continue
        if not field_visible_for_transaction(k, profile):
            continue

        display = format_display_value(k, v, profile)
        if display == '—':
            continue

        section = _resolve_section_name(k)
        if section not in sections:
            sections[section] = {}
        sections[section][k] = display

    result: Dict[str, Dict[str, str]] = {}
    for name in (*SECTION_ORDER, 'سایر'):
        fields = sections.get(name) or {}
        if fields:
            result[name] = _sort_section_fields(name, fields)
    return result


def format_all_fields(data: dict, profile: Dict) -> List[Tuple[str, str]]:
    rows = []
    for k, v in sorted((data or {}).items(), key=lambda x: x[0]):
        if v is None or str(v).strip() in ('', 'nan', 'None'):
            continue
        if not field_visible_for_transaction(k, profile):
            continue
        display = format_display_value(k, v, profile)
        if display != '—':
            rows.append((k, display))
    return rows


def _is_url_key(key: str) -> bool:
    kl = key.lower()
    return any(m in key or m in kl for m in URL_KEY_MARKERS)


def _is_long_text_key(key: str) -> bool:
    kl = key.lower()
    return any(m in key or m in kl for m in LONG_TEXT_MARKERS)


def _shorten_url(url: str, max_len: int = 40) -> str:
    s = str(url).strip()
    if not s:
        return '—'
    if 'mapimage' in s:
        return 'تصویر نقشه'
    if s.startswith('http'):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(s)
            label = parsed.netloc + (parsed.path[:18] + '…' if len(parsed.path) > 18 else parsed.path)
            if len(label) > max_len:
                return label[: max_len - 1] + '…'
            return label or s[:max_len]
        except Exception:
            pass
    if len(s) > max_len:
        return s[: max_len - 1] + '…'
    return s


def classify_field_for_display(key: str, display: str, raw: Any = None) -> Dict[str, Any]:
    """متادیتای نمایش فیلد — url، متن بلند، عادی."""
    raw_s = str(raw if raw is not None else display).strip()
    disp = display or '—'
    kind = 'normal'
    short = disp

    if raw_s.startswith('http') or _is_url_key(key):
        kind = 'url'
        short = _shorten_url(raw_s)
    elif _is_long_text_key(key) or len(disp) > 140:
        kind = 'long'

    return {
        'key': display_field_label(key),
        'raw_key': key,
        'display': disp,
        'raw': raw_s,
        'short': short,
        'kind': kind,
    }


def format_field_rows(fields: Dict[str, str], data: dict) -> List[Dict[str, Any]]:
    """تبدیل دیکشنری فیلد به ردیف‌های قابل رندر."""
    rows = []
    for key, display in fields.items():
        raw = (data or {}).get(key, display)
        rows.append(classify_field_for_display(key, display, raw))
    return rows


def _normalize_dossier_field_key(key: str) -> str:
    k = str(key or '').strip().lower().replace(' ', '').replace('_', '').replace('‌', '')
    if k in ('سالساخت', 'ساخت', 'buildyear', 'سنبنا'):
        return 'build_year'
    if k in ('متراژعدد', 'area') or (k.startswith('متراژ') and k.endswith('عدد')):
        return 'area'
    if k in ('شهر', 'city', 'مکانشهر'):
        return 'location_city'
    if k in ('آدرس', 'address', 'مکانآدرس'):
        return 'location_address'
    return k


def _dossier_row_preference(norm: str, raw_key: str) -> int:
    preferred = {
        'build_year': ('سال ساخت', 'ساخت', 'build_year'),
        'area': ('متراژ', 'area'),
        'location_city': ('شهر', 'city'),
        'location_address': ('آدرس', 'address'),
    }.get(norm, ())
    for idx, marker in enumerate(preferred):
        if raw_key == marker or marker in raw_key:
            return idx
    return 50


def dedupe_listing_dossier_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """حذف نمایش تکراری فیلدهای هم‌معنا در پرونده آگهی (مثلاً سال ساخت و ساخت)."""
    by_norm: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        raw_key = str(row.get('raw_key') or row.get('key') or '')
        nk = _normalize_dossier_field_key(raw_key)
        if nk not in by_norm:
            by_norm[nk] = row
            order.append(nk)
            continue
        existing = by_norm[nk]
        ex_key = str(existing.get('raw_key') or existing.get('key') or '')
        if _dossier_row_preference(nk, raw_key) < _dossier_row_preference(nk, ex_key):
            by_norm[nk] = row
        elif nk == 'build_year' and 'سال ساخت' in raw_key and 'سال ساخت' not in ex_key:
            by_norm[nk] = row
    return [by_norm[k] for k in order]


def _supplementary_sort_key(key: str) -> Tuple[int, int, str]:
    """اولویت نمایش فیلدهای تکمیلی."""
    priority = [
        ('شناسه', 0), ('token', 0),
        ('عنوان', 1), ('title', 1),
        ('لینک', 2), ('link', 2),
        ('نوع آگهی', 3), ('آگهی دهنده', 3), ('business', 3),
        ('دسته', 4), ('category', 4),
        ('آدرس', 5), ('address', 5),
        ('شهر', 6), ('city', 6),
        ('محله', 7), ('neighborhood', 7),
        ('ایجاد', 8), ('created', 8), ('انتشار', 8),
        ('انقضا', 9), ('expires', 9),
        ('تعداد تصویر', 10), ('تصاویر', 10),
        ('ویدیو', 11), ('video', 11),
        ('اصالت', 12),
        ('ویژگی', 13), ('امکانات', 13),
        ('انباری', 14), ('آسانسور', 14), ('پارکینگ', 14),
    ]
    kl = key.lower()
    for marker, order in priority:
        if marker in key or marker in kl:
            return (0, order, key)
    return (1, 99, key)


def _is_features_supplementary_key(key: str) -> bool:
    """فیلدهای ویژگی/امکانات در تب اختصاصی نمایش داده می‌شوند."""
    kl = key.lower()
    if key in ('ویژگی‌ها و امکانات', 'ویژگی_ها_و_امکانات'):
        return True
    return kl.startswith('ویژگی') or 'امکانات' in key


def _supplementary_group_name(key: str) -> str:
    kl = key.lower()
    if any(x in key or x in kl for x in ('شناسه', 'token', 'عنوان', 'title', 'لینک', 'link', 'دسته', 'نوع آگهی', 'آگهی دهنده', 'business', 'category')):
        return 'شناسایی'
    if any(x in key or x in kl for x in ('نردبان', 'به‌روز', 'بروز')):
        return 'زمان‌بندی'
    if any(x in key or x in kl for x in ('ایجاد', 'انقضا', 'انتشار', 'created', 'expires', 'published', 'تاریخ')):
        return 'زمان‌بندی'
    if any(x in key or x in kl for x in ('تصویر', 'ویدیو', 'اصالت', 'video', 'images')):
        return 'رسانه'
    return 'سایر'


_SUPPLEMENTARY_GROUP_ICONS: Dict[str, str] = {
    'شناسایی': 'fa-fingerprint',
    'زمان‌بندی': 'fa-clock',
    'رسانه': 'fa-photo-film',
    'سایر': 'fa-ellipsis',
}


def _build_schedule_key_sets() -> Tuple[frozenset, frozenset, frozenset, frozenset, frozenset]:
    from workspace.services.divar_listing_datetime import (
        DATA_KEY_LAST_BUMPED_AT,
        DATA_KEY_LAST_UPDATED_AT,
        SHAMSI_KEY_LAST_BUMPED,
        SHAMSI_KEY_LAST_UPDATED,
        SHAMSI_KEY_PUBLISH,
    )

    publish = frozenset((
        *COLUMN_ALIASES['published_at'],
        SHAMSI_KEY_PUBLISH,
        'published_at_iso',
        'انتشار_تاریخ_میلادی',
    ))
    expire = frozenset((*COLUMN_ALIASES['expires_at'], 'تاریخ انقضا'))
    bumped = frozenset((*COLUMN_ALIASES['last_bumped_at'], DATA_KEY_LAST_BUMPED_AT, SHAMSI_KEY_LAST_BUMPED))
    updated = frozenset((
        *COLUMN_ALIASES['last_updated_at'],
        DATA_KEY_LAST_UPDATED_AT,
        SHAMSI_KEY_LAST_UPDATED,
    ))
    internal = frozenset((
        'published_at_iso',
        DATA_KEY_LAST_BUMPED_AT,
        DATA_KEY_LAST_UPDATED_AT,
        SHAMSI_KEY_PUBLISH,
        SHAMSI_KEY_LAST_BUMPED,
        SHAMSI_KEY_LAST_UPDATED,
        'انتشار_تاریخ_میلادی',
    ))
    return publish, expire, bumped, updated, internal


_PUBLISH_SCHEDULE_KEYS, _EXPIRE_SCHEDULE_KEYS, _BUMP_SCHEDULE_KEYS, _UPDATE_SCHEDULE_KEYS, _INTERNAL_SCHEDULE_KEYS = (
    _build_schedule_key_sets()
)

_SUPPLEMENTARY_ROW_PREF: Dict[str, Tuple[str, ...]] = {
    'schedule_published': (
        'تاریخ انتشار', 'ایجاد آگهی', 'انتشار_تاریخ_شمسی', 'published_at', 'created_at', 'published_at_iso',
    ),
    'schedule_expires': ('تاریخ انقضا', 'انقضا آگهی', 'expires_at', 'انتشار_unavailable_after'),
    'schedule_last_bumped': ('آخرین نردبان', 'انتشار_آخرین_نردبان_شمسی', 'last_bumped_at'),
    'schedule_last_updated': ('آخرین به‌روزرسانی', 'انتشار_آخرین_به‌روزرسانی_شمسی', 'last_updated_at'),
}


def _normalize_supplementary_row_key(key: str) -> str:
    k = str(key or '').strip().lower().replace(' ', '').replace('_', '').replace('‌', '')
    if key in _PUBLISH_SCHEDULE_KEYS:
        return 'schedule_published'
    if key in _EXPIRE_SCHEDULE_KEYS:
        return 'schedule_expires'
    if key in _BUMP_SCHEDULE_KEYS:
        return 'schedule_last_bumped'
    if key in _UPDATE_SCHEDULE_KEYS:
        return 'schedule_last_updated'
    if 'نردبان' in key:
        return 'schedule_last_bumped'
    if 'به‌روز' in key or 'بروز' in key:
        return 'schedule_last_updated'
    if any(m in key for m in ('نوع آگهی', 'آگهی دهنده', 'آگهی‌دهنده')) or 'advertiser' in k:
        return 'advertiser_type'
    if 'لینک تصویر اول' in key or k == 'لینکتصویراول':
        return 'first_image_link'
    if 'لینک تصاویر' in key or k == 'لینکتصاویر':
        return 'images_link'
    return k


def _supplementary_row_preference(norm: str, raw_key: str) -> int:
    order = _SUPPLEMENTARY_ROW_PREF.get(norm)
    if not order:
        return 99
    for idx, marker in enumerate(order):
        if raw_key == marker or marker in raw_key:
            return idx
    return 50


def dedupe_supplementary_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """حذف نمایش تکراری فیلدهای هم‌معنا در مشخصات بیشتر."""
    by_norm: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        raw_key = str(row.get('raw_key') or row.get('key') or '')
        nk = _normalize_supplementary_row_key(raw_key)
        if nk not in by_norm:
            by_norm[nk] = row
            order.append(nk)
            continue
        existing = by_norm[nk]
        ex_key = str(existing.get('raw_key') or existing.get('key') or '')
        if _supplementary_row_preference(nk, raw_key) < _supplementary_row_preference(nk, ex_key):
            by_norm[nk] = row
    return [by_norm[k] for k in order]


def _collect_supplementary_rows(
    data: dict,
    profile: Dict,
    sections: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    shown_keys: set = set()
    for sec_fields in sections.values():
        shown_keys.update(sec_fields.keys())

    feature_keys = {k for k in (data or {}) if is_listing_feature_key(k) and not _include_in_sections(k)}
    _skip_supplementary = frozenset({'attributes', 'features', 'raw', 'tags'})
    rows: List[Dict[str, Any]] = []
    for k, v in (data or {}).items():
        if k in shown_keys or k in feature_keys or _is_features_supplementary_key(k):
            continue
        if k in _INTERNAL_SCHEDULE_KEYS:
            continue
        if k.lower() in _skip_supplementary:
            continue
        if isinstance(v, (dict, list)):
            continue
        if v is None or str(v).strip() in ('', 'nan', 'None', '-'):
            continue
        text = str(v).strip()
        if text.startswith('{') or text.startswith('['):
            continue
        if not field_visible_for_transaction(k, profile):
            continue
        display = format_display_value(k, v, profile)
        if display == '—':
            continue
        rows.append(classify_field_for_display(k, display, v))

    rows.sort(key=lambda r: _supplementary_sort_key(r['key']))
    return dedupe_supplementary_rows(rows)


def format_supplementary_fields(
    data: dict,
    profile: Dict,
    sections: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """فیلدهای تکمیلی — مرتب‌شده بر اساس اولویت."""
    return _collect_supplementary_rows(data, profile, sections)


def format_supplementary_groups(
    data: dict,
    profile: Dict,
    sections: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """فیلدهای تکمیلی گروه‌بندی‌شده برای نمایش حرفه‌ای."""
    from workspace.services.listing_features import listing_field_icon

    rows = _collect_supplementary_rows(data, profile, sections)
    group_order = ['شناسایی', 'زمان‌بندی', 'رسانه', 'سایر']
    buckets: Dict[str, List[Dict[str, Any]]] = {g: [] for g in group_order}
    for row in rows:
        buckets[_supplementary_group_name(row['key'])].append({
            **row,
            'icon': listing_field_icon(str(row.get('raw_key') or row.get('key') or '')),
        })
    return [
        {
            'name': name,
            'icon': _SUPPLEMENTARY_GROUP_ICONS.get(name, 'fa-layer-group'),
            'fields': fields,
        }
        for name in group_order
        for fields in [buckets[name]]
        if fields
    ]


def to_jalali_display(value) -> str:
    if not value:
        return '—'
    formatted = _format_date_display(value)
    if formatted:
        return formatted
    try:
        if hasattr(value, 'hour'):
            dt = value
            if isinstance(dt, datetime) and dj_tz.is_aware(dt):
                dt = dj_tz.localtime(dt)
            jdt = jdatetime.datetime.fromgregorian(datetime=dt)
            if jdt.hour or jdt.minute:
                return jdt.strftime('%Y/%m/%d %H:%M')
            return jdt.strftime('%Y/%m/%d')
    except Exception:
        pass
    return str(value)


_CONVERTIBLE_RENT_DOSSIER_KEYS = frozenset({
    'ودیعه', 'deposit', 'رهن', 'اجاره', 'rent', 'اجاره ماهانه',
    'ودیعه و اجاره', 'ودیعه (شرایط تبدیل)', 'اجاره ماهانه (شرایط تبدیل)',
})


def _dossier_money_amount(value: Any) -> Optional[int]:
    from workspace.services.columns import _safe_int

    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    s = str(value).strip().replace('،', ',').replace(',', '')
    if not s or s.lower() in ('nan', 'none', '-', '—'):
        return None
    if s in KNOWN_TEXT_PRICES:
        return None
    parsed = _safe_int(s)
    if parsed is not None:
        return parsed
    return None


def _dossier_rent_label(amount: Optional[int]) -> str:
    if amount is None:
        return '—'
    if amount == 0:
        return 'رایگان'
    return format_toman(amount)


def _dossier_deposit_label(amount: Optional[int]) -> str:
    if amount is None:
        return '—'
    return format_toman(amount)


def _dossier_endpoint_rent_phrase(amount: Optional[int]) -> str:
    if amount is None:
        return '—'
    if amount == 0:
        return 'اجاره رایگان'
    return f'{format_toman_compact(amount)} اجاره'


def _dossier_endpoint_deposit_phrase(amount: Optional[int]) -> str:
    if amount is None:
        return '—'
    return f'{format_toman_compact(amount)} ودیعه'


def effective_convertible_rent_rate(
    base_deposit: int,
    base_rent: int,
    alt_deposit: int,
    alt_rent: int,
) -> Optional[int]:
    """تومان ودیعه به‌ازای هر ۱ میلیون تومان تغییر اجاره — از دو نقطه ثبت‌شده."""
    rent_delta = alt_rent - base_rent
    dep_delta = alt_deposit - base_deposit
    if rent_delta == 0:
        return None
    return int(round(abs(dep_delta) / abs(rent_delta) * 1_000_000))


def is_convertible_slider_compatible(
    base_deposit: int,
    base_rent: int,
    alt_deposit: int,
    alt_rent: int,
) -> bool:
    """اسلایدر پیوسته فقط وقتی تغییر رهن و اجاره هم‌جهت نباشند."""
    dep_delta = alt_deposit - base_deposit
    rent_delta = alt_rent - base_rent
    if dep_delta == 0 and rent_delta == 0:
        return False
    if dep_delta != 0 and rent_delta != 0 and dep_delta * rent_delta > 0:
        return False
    return True


def interpolate_convertible_rent(
    base_deposit: int,
    base_rent: int,
    alt_deposit: int,
    alt_rent: int,
    t: float,
) -> Tuple[int, int]:
    """t∈[0,1] — ۰ پایه، ۱ شرایط تبدیل؛ دو سر بازه دقیق."""
    if t <= 0:
        return base_deposit, base_rent
    if t >= 1:
        return alt_deposit, alt_rent
    dep = int(round(base_deposit + t * (alt_deposit - base_deposit)))
    rent = int(round(base_rent + t * (alt_rent - base_rent)))
    dep = max(0, dep)
    rent = max(0, rent)
    lo_d, hi_d = min(base_deposit, alt_deposit), max(base_deposit, alt_deposit)
    lo_r, hi_r = min(base_rent, alt_rent), max(base_rent, alt_rent)
    return max(lo_d, min(hi_d, dep)), max(lo_r, min(hi_r, rent))


def _resolve_convertible_money_pair(
    listing,
    merged: dict,
    *,
    deposit_keys: Tuple[str, ...],
    rent_keys: Tuple[str, ...],
    deposit_scalar: str = '',
    rent_scalar: str = '',
    use_listing_model: bool = False,
) -> Tuple[Optional[int], Optional[int]]:
    from workspace.services.columns import _listing_money_scalar

    dep: Optional[int] = None
    rent: Optional[int] = None

    if use_listing_model:
        if listing.deposit is not None:
            dep = int(listing.deposit)
        if listing.rent is not None:
            rent = int(listing.rent)

    for key in deposit_keys:
        if dep is not None:
            break
        dep = _dossier_money_amount(merged.get(key))
    if dep is None and deposit_scalar:
        dep = _listing_money_scalar(merged, deposit_scalar)

    for key in rent_keys:
        if rent is not None:
            break
        rent = _dossier_money_amount(merged.get(key))
    if rent is None and rent_scalar:
        rent = _listing_money_scalar(merged, rent_scalar)

    return dep, rent


def resolve_convertible_rent_card(
    listing,
    display_data: dict,
    profile: Dict,
    *,
    raw_data: Optional[dict] = None,
) -> Optional[Dict[str, Any]]:
    """کارت دوحالته رهن/اجاره قابل تبدیل — فقط وقتی هر دو نقطه عددی معتبر داریم."""
    if not (profile.get('is_rent') or profile.get('is_mixed') or profile.get('show_deposit')):
        return None

    raw = raw_data if isinstance(raw_data, dict) else (getattr(listing, 'data', None) or {})
    merged = {**(raw or {}), **(display_data or {})}
    if not _is_rent_convertible(merged):
        return None

    base_dep, base_rent = _resolve_convertible_money_pair(
        listing,
        merged,
        deposit_keys=('ودیعه', 'deposit', 'رهن', 'اجاره_ودیعه_عدد'),
        rent_keys=('اجاره', 'اجاره ماهانه', 'rent', 'اجاره_ماهانه_عدد'),
        deposit_scalar='deposit',
        rent_scalar='rent',
        use_listing_model=True,
    )
    alt_dep, alt_rent = _resolve_convertible_money_pair(
        listing,
        merged,
        deposit_keys=('ودیعه (شرایط تبدیل)', 'اجاره_ودیعه_تبدیل_عدد'),
        rent_keys=('اجاره ماهانه (شرایط تبدیل)', 'اجاره_ماهانه_تبدیل_عدد'),
    )

    if base_dep is None and base_rent is None:
        return {'show_card': False, 'convertible': True, 'badge': 'قابل تبدیل'}
    if alt_dep is None and alt_rent is None:
        return {'show_card': False, 'convertible': True, 'badge': 'قابل تبدیل'}

    if base_dep is None or base_rent is None or alt_dep is None or alt_rent is None:
        return {'show_card': False, 'convertible': True, 'badge': 'قابل تبدیل'}

    state_base = {
        'id': 'base',
        'deposit': base_dep,
        'rent': base_rent,
        'deposit_label': _dossier_deposit_label(base_dep),
        'rent_label': _dossier_rent_label(base_rent),
        'endpoint_deposit': _dossier_endpoint_deposit_phrase(base_dep),
        'endpoint_rent': _dossier_endpoint_rent_phrase(base_rent),
    }
    state_alt = {
        'id': 'alt',
        'deposit': alt_dep,
        'rent': alt_rent,
        'deposit_label': _dossier_deposit_label(alt_dep),
        'rent_label': _dossier_rent_label(alt_rent),
        'endpoint_deposit': _dossier_endpoint_deposit_phrase(alt_dep),
        'endpoint_rent': _dossier_endpoint_rent_phrase(alt_rent),
    }

    default_id = 'base'
    endpoints_rtl = (state_base, state_alt)
    dep_delta = alt_dep - base_dep
    rent_delta = alt_rent - base_rent
    identical = dep_delta == 0 and rent_delta == 0
    slider_ok = is_convertible_slider_compatible(base_dep, base_rent, alt_dep, alt_rent)
    if identical:
        ui_mode = 'static'
    elif slider_ok:
        ui_mode = 'slider'
    else:
        ui_mode = 'dual'

    conv_rate = effective_convertible_rent_rate(base_dep, base_rent, alt_dep, alt_rent)

    return {
        'show_card': True,
        'convertible': True,
        'badge': 'قابل تبدیل',
        'title': 'شرایط رهن و اجاره',
        'hint': 'ودیعه و اجارهٔ این ملک قابل تبدیل است.',
        'mid_note': 'محاسبه بر اساس شرایط آگهی',
        'default_id': default_id,
        'ui_mode': ui_mode,
        'conversion_rate_per_million_rent': conv_rate,
        'states': {
            'base': state_base,
            'alt': state_alt,
        },
        'endpoints_rtl': endpoints_rtl,
        'slider': {
            'base_deposit': base_dep,
            'base_rent': base_rent,
            'alt_deposit': alt_dep,
            'alt_rent': alt_rent,
            'steps': 100,
            'default_step': 0,
        },
    }


def apply_convertible_rent_to_dossier(
    sections: Dict[str, Dict[str, str]],
    section_rows: Dict[str, List[Dict[str, Any]]],
    card: Optional[Dict[str, Any]],
) -> None:
    """حذف ردیف‌های خام مالی وقتی کارت قابل تبدیل فعال است."""
    if not card or not card.get('show_card'):
        return
    money = sections.get('مالی')
    if isinstance(money, dict):
        for key in list(money.keys()):
            if key in _CONVERTIBLE_RENT_DOSSIER_KEYS:
                money.pop(key, None)
    rows = section_rows.get('مالی')
    if rows:
        section_rows['مالی'] = [
            row for row in rows
            if str(row.get('raw_key') or '') not in _CONVERTIBLE_RENT_DOSSIER_KEYS
        ]
