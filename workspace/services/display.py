"""نمایش فیلدها بر اساس نوع معامله — قیمت، تاریخ شمسی."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import jdatetime

from workspace.services.formatting import format_area, format_toman
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
    'شهر', 'city', 'محله', 'neighborhood', 'آدرس', 'address',
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
    'شهر', 'city', 'منطقه', 'district', 'محله', 'neighborhood',
    'آدرس', 'address', 'عرض جغرافیایی', 'طول جغرافیایی',
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
    raw_type = str(data.get('نوع مختصات') or '').strip()
    norm = _normalize_coord_type(raw_type)
    radius = _parse_radius_meters(data.get('در شعاع (متر)'))

    if norm in _EXACT_COORD_MARKERS or raw_type in _EXACT_COORD_MARKERS:
        return {'label': 'موقعیت دقیق روی نقشه', 'kind': 'exact', 'radius_m': 0}
    if norm in _FUZZY_COORD_MARKERS or raw_type in _FUZZY_COORD_MARKERS or 'تقری' in raw_type or radius:
        if radius:
            return {
                'label': f'موقعیت تقریبی — در شعاع حدود {to_persian_digits(radius)} متر',
                'kind': 'approx',
                'radius_m': radius,
            }
        return {'label': 'موقعیت تقریبی روی نقشه', 'kind': 'approx', 'radius_m': 500}
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

    if tx.get('show_price') and getattr(listing, 'price', None):
        return format_toman(listing.price)
    if tx.get('show_rent') and getattr(listing, 'rent', None):
        return f'اجاره {format_toman(listing.rent)}'
    if tx.get('show_deposit') and getattr(listing, 'deposit', None):
        return f'ودیعه {format_toman(listing.deposit)}'

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
    return _listing_text_deposit(getattr(listing, 'data', None) or {})


def listing_map_rent_label(listing) -> str:
    if getattr(listing, 'rent', None):
        return format_toman(listing.rent)
    return _listing_text_rent(getattr(listing, 'data', None) or '')


MONEY_FIELD_ORDER = (
    'قیمت', 'price', 'قیمت هر متر', 'قیمت/متر', 'ودیعه', 'deposit',
    'رهن', 'اجاره', 'rent', 'اجاره ماهانه', 'ودیعه و اجاره',
)


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
    kl = key.lower()
    return any(m in key or m in kl for m in (
        'قیمت', 'ودیعه', 'اجاره', 'رهن', 'price', 'deposit', 'rent', 'تومان',
    ))


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
    if profile.get('is_mixed'):
        return True
    if profile.get('is_sale'):
        return not _is_rent_field(key)
    if profile.get('is_rent'):
        if _is_sale_price_field(key) and not _is_rent_field(key):
            if _is_per_sqm_key(key):
                return False
            if key in ('قیمت', 'price') or key.strip() == 'قیمت':
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
    ))


def format_display_value(key: str, value: Any, profile: Optional[Dict] = None) -> str:
    """فرمت مقدار برای نمایش در جدول/جزئیات."""
    if value is None or str(value).strip() in ('', 'nan', 'None', '-'):
        return '—'

    if profile and not field_visible_for_transaction(key, profile):
        return '—'

    if _is_date_key(key):
        formatted = _format_date_display(value)
        if formatted:
            return formatted

    if _is_money_key(key):
        try:
            num = int(float(str(value).replace(',', '').replace('٬', '')))
            if num <= 0:
                return '—'
            return format_toman(num, per_sqm=_is_per_sqm_key(key))
        except (ValueError, TypeError):
            pass

    if any(x in key.lower() for x in ('متراژ', 'area')) and not _is_money_key(key):
        try:
            return format_area(float(value))
        except (ValueError, TypeError):
            pass

    s = str(value).strip()
    if re.fullmatch(r'\d{9,}', s):
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

    # کلیدهای انگلیسی باقی‌ماندهٔ تماس را هم حذف کن
    for key in list(data.keys()):
        kl = str(key).strip().lower()
        if kl in ('owner_phone', 'owner_name', 'phone', 'phone_text'):
            data.pop(key, None)

    if phone:
        data['شماره تماس'] = phone
    if name:
        data['نام مالک'] = name


def build_listing_display_data(listing, feat: Optional[Dict[str, Any]] = None) -> dict:
    """ادغام فیلدهای مدل و استخراج‌شده در دیکشنری نمایش."""
    data = _dedupe_listing_data_keys(dict(listing.data or {}))

    _set_if_missing(data, 'شناسه', listing.token)
    _set_if_missing(data, 'عنوان', listing.title)
    _set_if_missing(data, 'لینک', listing.link)
    _set_if_missing(data, 'متراژ', listing.area)
    _set_if_missing(data, 'اتاق', listing.rooms)
    _set_if_missing(data, 'شهر', listing.city)
    _set_if_missing(data, 'محله', listing.neighborhood)
    _set_if_missing(data, 'قیمت', listing.price)
    _set_if_missing(data, 'ودیعه', listing.deposit)
    _set_if_missing(data, 'اجاره', listing.rent)
    advertiser_label = ''
    if feat and feat.get('advertiser_label'):
        advertiser_label = str(feat['advertiser_label']).strip()
    if not advertiser_label:
        from workspace.services.advertiser_signal import listing_advertiser_display
        advertiser_label = listing_advertiser_display(listing)['label']
    data['نوع آگهی‌دهنده'] = advertiser_label
    data['نوع آگهی دهنده'] = advertiser_label
    _set_if_missing(data, 'عرض جغرافیایی', listing.latitude)
    _set_if_missing(data, 'طول جغرافیایی', listing.longitude)

    if listing.published_at:
        _set_if_missing(data, 'تاریخ انتشار', listing.published_at)
    if listing.expires_at:
        _set_if_missing(data, 'تاریخ انقضا', listing.expires_at)
    if listing.images:
        _set_if_missing(data, 'تعداد تصاویر', len(listing.images))

    if feat:
        _set_if_missing(data, 'طبقه', feat.get('floor'))
        _set_if_missing(data, 'اتاق', feat.get('rooms'))
        if feat.get('build_year'):
            _set_if_missing(data, 'سال ساخت', feat['build_year'])

    _normalize_contact_fields(data, listing)
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
    if any(x in key or x in kl for x in ('ایجاد', 'انقضا', 'انتشار', 'created', 'expires', 'published', 'تاریخ')):
        return 'زمان‌بندی'
    if any(x in key or x in kl for x in ('تصویر', 'ویدیو', 'اصالت', 'video', 'images')):
        return 'رسانه'
    return 'سایر'


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
    return rows


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
    rows = _collect_supplementary_rows(data, profile, sections)
    group_order = ['شناسایی', 'زمان‌بندی', 'رسانه', 'سایر']
    buckets: Dict[str, List[Dict[str, Any]]] = {g: [] for g in group_order}
    for row in rows:
        buckets[_supplementary_group_name(row['key'])].append(row)
    return [
        {'name': name, 'fields': fields}
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
            jdt = jdatetime.datetime.fromgregorian(datetime=value)
            if jdt.hour or jdt.minute:
                return jdt.strftime('%Y/%m/%d %H:%M')
            return jdt.strftime('%Y/%m/%d')
    except Exception:
        pass
    return str(value)
