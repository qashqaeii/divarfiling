"""ویژگی‌ها و امکانات تفصیلی آگهی — هماهنگ با خروجی اکسل ربات."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from workspace.constants import (
    LISTING_CORE_AMENITIES,
    LISTING_FEATURE_COLUMNS,
    LISTING_FEATURE_COMBINED_KEYS,
    LISTING_FEATURE_GROUPS,
)
from workspace.services.features import (
    NEGATIVE,
    POSITIVE,
    _NEGATIVE_EXACT,
    _POSITIVE_EXACT,
    _get_from_data,
    get_exact_from_data,
    parse_bool_feature,
)

_CHIP_SPLIT = re.compile(r'\s*[،,|]\s*')
_COMBINED_SPLIT = re.compile(r'\s*\|\s*')
_YEAR_ONLY_RE = re.compile(r'^(13|14|19|20)\d{2}$')

# کلیدهای متادیتا/مالی/مکان — نباید در پنل «ویژگی‌های ملک» نمایش داده شوند
LISTING_METADATA_DATA_KEYS = frozenset({
    'شناسه', 'token', 'عنوان', 'title', 'لینک', 'link', 'url', 'share_link',
    'قیمت', 'price', 'price_text', 'ودیعه', 'deposit', 'رهن', 'اجاره', 'rent', 'اجاره ماهانه',
    'ودیعه و اجاره', 'قیمت هر متر', 'متراژ', 'area', 'اتاق', 'rooms', 'تعداد اتاق',
    'شهر', 'city', 'city_persian', 'محله', 'neighborhood', 'منطقه', 'district', 'district_persian',
    'مکان_شهر', 'مکان_منطقه', 'مکان_آدرس', 'مکان_مختصات_lat', 'مکان_مختصات_lng',
    'normalized_city', 'normalized_district', 'آدرس', 'address',
    'نوع آگهی دهنده', 'نوع آگهی‌دهنده', 'business_type', 'فروشنده_business_type',
    'فروشنده_نوع', 'فروشنده_تخفیف', 'status', 'دسته‌بندی', 'category', 'category_slug',
    'دسته‌بندی_سطح۱', 'دسته‌بندی_سطح۲', 'دسته‌بندی_سطح۳', 'دسته‌بندی_عنوان',
    'توضیحات', 'description', 'زیرعنوان', 'متن آگهی', 'متن کامل', 'شرح', 'شرح آگهی',
    'ایجاد آگهی', 'انقضا آگهی', 'published_at', 'expires_at', 'created_at',
    'انتشار_تاریخ_شمسی', 'انتشار_تاریخ_میلادی', 'انتشار_unavailable_after',
    'عرض جغرافیایی', 'طول جغرافیایی', 'latitude', 'longitude', 'lat', 'lng',
    'نوع مختصات', 'در شعاع (متر)', 'نقشه_نوع', 'نقشه_شعاع_محدوده_متر', 'نقشه_تصویر',
    'تعداد تصاویر', 'تصاویر', 'images', 'رسانه_تصاویر', 'رسانه_تعداد_تصویر',
    'ویدیو دارد؟', 'video', 'رسانه_ویدیو', 'video_url',
    'اصالت تصویر', 'رسانه_اصالت_تصویر_برای_همین_ملک', 'تصویر نقشه', 'mapimage',
    'شماره تماس', 'phone', 'phone_text', 'تماس', 'تلفن', 'موبایل', 'owner_phone',
    'نام مالک', 'owner_name', 'نام و نام خانوادگی مالک', 'نام صاحب',
    'تماس_چت_فعال', 'تماس_تماس_ایمن', 'تماس_contact_uuid',
    'ویژگی‌ها و امکانات', 'ویژگی_ها_و_امکانات', 'attributes', 'features', 'tags', 'برچسب‌ها',
    'مشاور_نام', 'مشاور_آگهی_فعال', 'مشاور_business_ref', 'نام مشاور / آژانس',
    'consultant_name', 'مالی_قیمت_کل_نمایش', 'مالی_قیمت_کل_عدد', 'مالی_قیمت_هر_متر_نمایش',
    'مالی_قیمت_هر_متر_عدد', 'مالی_ارز', 'مالی_منبع_قیمت_وب‌انگیج',
    'اجاره_ودیعه_نمایش', 'اجاره_ودیعه_عدد', 'اجاره_ماهانه_نمایش', 'اجاره_ماهانه_عدد',
    'اجاره_قابل_تبدیل', 'rent_convertibility',
    'سیستمی_webengage_category', 'سیستمی_webengage_city', 'سیستمی_webengage_district',
    'سیستمی_webengage_price', 'سیستمی_webengage_image_count',
    'سیستمی_analytics_cat1', 'سیستمی_analytics_cat2', 'سیستمی_analytics_cat3',
    'سیستمی_city_meta_city_id', 'سیستمی_city_meta_name',
    'raw', 'widget_list', 'business_lazy_widget_list', 'sections',
    'ساخت', 'سال ساخت', 'build_year', 'طبقه', 'floor',
})

_METADATA_KEY_MARKERS = (
    'قیمت', 'price', 'ودیعه', 'اجاره', 'rent', 'deposit',
    'متراژ', 'area', 'latitude', 'longitude', 'عرض جغرافیایی', 'طول جغرافیایی',
    'توضیح', 'description', 'متن آگهی', 'متن کامل', 'شرح', 'لینک', 'link', 'http', 'تاریخ', 'ایجاد', 'انقضا',
    'تصویر', 'ویدیو', 'video', 'image', 'تماس', 'phone', 'شناسه', 'token',
    'دسته', 'category', 'شهر', 'city', 'محله', 'neighborhood',
    'مالک', 'owner_name', 'owner_phone',
)


def is_listing_metadata_key(key: str) -> bool:
    """آیا این کلید متادیتای آگهی است (نه ویژگی ملک)؟"""
    k = str(key or '').strip()
    if not k:
        return True
    if k in LISTING_METADATA_DATA_KEYS:
        return True
    kl = k.lower()
    if any(m in k or m in kl for m in _METADATA_KEY_MARKERS):
        return True
    if k.startswith('ویژگی'):
        return True
    return False


def is_listing_feature_key(key: str) -> bool:
    return not is_listing_metadata_key(key)


def listing_feature_data_keys() -> set:
    return set(LISTING_FEATURE_COLUMNS) | set(LISTING_FEATURE_COMBINED_KEYS)


def _clean_value(value: Any) -> str:
    if value is None:
        return ''
    s = str(value).strip()
    if not s or s.lower() in ('nan', 'none', '-', '—'):
        return ''
    return s


_COUNT_FEATURE_KEYS = frozenset({
    'تعداد پارکینگ', 'تعداد حمام', 'تعداد سرویس بهداشتی',
    'تعداد واحد در طبقه', 'تعداد کل طبقات ساختمان',
})
_BUILD_YEAR_KEYS = frozenset({
    'ساخت', 'سال ساخت', 'build_year', 'سن بنا', 'سال ساخت بنا', 'بازسازی شده',
})
_BOOLISH = frozenset({'دارد', 'ندارد', 'بله', 'خیر', 'yes', 'no'})


def _value_plausible_for_key(key: str, value: str) -> bool:
    """رد مقادیر ناسازگار — مثلاً سال ساخت در «جهت ساختمان»."""
    v = _clean_value(value)
    if not v:
        return False
    if key in _COUNT_FEATURE_KEYS and v.lower() in _BOOLISH:
        return False
    if _YEAR_ONLY_RE.match(v.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))):
        if key not in _BUILD_YEAR_KEYS:
            return False
    return True


def _store_feature(raw: Dict[str, str], key: str, value: Any) -> None:
    cleaned = _clean_value(value)
    if cleaned and _value_plausible_for_key(key, cleaned):
        raw[key] = cleaned


def _feature_state(value: str) -> str:
    """yes | no | neutral"""
    if not value:
        return 'unknown'
    low = value.strip().lower()
    if low in ('-', '—'):
        return 'unknown'
    if low in _NEGATIVE_EXACT or any(n in low for n in NEGATIVE if n not in ('-', '—')):
        return 'no'
    if low in _POSITIVE_EXACT or any(p in low for p in POSITIVE):
        return 'yes'
    if low in ('بله', 'yes', 'true'):
        return 'yes'
    if low in ('خیر', 'no', 'false'):
        return 'no'
    return 'neutral'


def _parse_combined_features(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not text:
        return out
    for part in _COMBINED_SPLIT.split(str(text).strip()):
        piece = part.strip()
        if not piece:
            continue
        if ':' in piece:
            key, val = piece.split(':', 1)
            key, val = key.strip(), val.strip()
            if key and val:
                out[key] = val
            continue
        if piece.endswith(' ندارد'):
            out[piece[:-len(' ندارد')].strip()] = 'ندارد'
        elif piece.endswith(' دارد'):
            out[piece[:-len(' دارد')].strip()] = 'دارد'
        else:
            out[piece] = 'دارد'
    return out


def _collect_raw_features(data: dict) -> Dict[str, str]:
    raw: Dict[str, str] = {}
    for key in LISTING_FEATURE_COLUMNS:
        _store_feature(raw, key, get_exact_from_data(data, key))
    for combined_key in LISTING_FEATURE_COMBINED_KEYS:
        combined = _clean_value(_get_from_data(data, (combined_key,)))
        if combined:
            for k, v in _parse_combined_features(combined).items():
                if k and k not in raw:
                    _store_feature(raw, k, v)
    for key, val in (data or {}).items():
        if key in raw or is_listing_metadata_key(key):
            continue
        if isinstance(val, (dict, list)):
            continue
        text = _clean_value(val)
        if text.startswith('{') or text.startswith('['):
            continue
        _store_feature(raw, str(key), val)
    return raw


def _icon_for_key(key: str) -> str:
    icons = {
        'تعداد واحد در طبقه': 'fa-door-open',
        'تعداد کل طبقات ساختمان': 'fa-layer-group',
        'جهت ساختمان': 'fa-compass',
        'حیوان خانگی مجاز': 'fa-paw',
        'نوع آشپزخانه': 'fa-utensils',
        'مناسب برای': 'fa-user-friends',
        'جنس کابینت': 'fa-box',
        'بازسازی شده': 'fa-hammer',
        'وضعیت واحد': 'fa-home',
        'حداقل مدت قرارداد': 'fa-calendar',
        'جنس کف': 'fa-th-large',
        'بالکن': 'fa-sun',
        'سرویس بهداشتی': 'fa-bath',
        'سرمایش': 'fa-snowflake',
        'گرمایش': 'fa-fire',
        'تأمین‌کننده آب گرم': 'fa-tint',
        'آسانسور': 'fa-arrows-alt-v',
        'پارکینگ': 'fa-car',
        'انباری': 'fa-archive',
        'تعداد پارکینگ': 'fa-car-side',
        'تعداد حمام': 'fa-shower',
        'تعداد سرویس بهداشتی': 'fa-toilet',
        'سند': 'fa-file-signature',
        'وضعیت سند': 'fa-file-contract',
        'مجوز ساخت': 'fa-hard-hat',
        'قابل معاوضه': 'fa-exchange-alt',
        'جکوزی': 'fa-hot-tub',
        'سونا': 'fa-fire-alt',
        'نمای ساختمان': 'fa-building',
        'عرض ملک': 'fa-ruler-horizontal',
        'وضعیت سکونت': 'fa-key',
    }
    return icons.get(key, 'fa-circle')


def _format_item_display(key: str, value: str) -> Dict[str, Any]:
    state = _feature_state(value)
    chips: List[str] = []
    if key == 'مناسب برای' and value:
        chips = [c for c in _CHIP_SPLIT.split(value) if c]
    return {
        'key': key,
        'label': key,
        'value': value,
        'state': state,
        'icon': _icon_for_key(key),
        'chips': chips,
        'is_chip': bool(chips),
    }


_FEATURE_HIGHLIGHT_PRIORITY = (
    'سند', 'وضعیت سند', 'تعداد پارکینگ', 'بالکن', 'گرمایش', 'سرمایش',
    'جنس کف', 'جنس کابینت', 'وضعیت واحد', 'وضعیت سکونت', 'نمای ساختمان',
    'مناسب برای', 'نوع آشپزخانه', 'سرویس بهداشتی', 'تأمین‌کننده آب گرم',
    'جهت ساختمان', 'حیوان خانگی مجاز', 'جکوزی', 'سونا',
)


def feature_highlights_for_listing(listing, limit: int = 4) -> List[str]:
    """برچسب‌های کوتاه ویژگی برای جدول و پیش‌نمایش."""
    raw = _collect_raw_features(listing.data or {})
    highlights: List[str] = []
    seen: set = set()

    def _add(text: str) -> None:
        if text and text not in seen and len(highlights) < limit:
            seen.add(text)
            highlights.append(text)

    for key in _FEATURE_HIGHLIGHT_PRIORITY:
        val = _clean_value(raw.get(key))
        if not val:
            continue
        if key == 'مناسب برای':
            chips = [c for c in _CHIP_SPLIT.split(val) if c]
            _add(f"مناسب: {chips[0]}" + (f" +{len(chips)-1}" if len(chips) > 1 else ''))
        elif _feature_state(val) == 'yes':
            _add(key)
        elif _feature_state(val) == 'no':
            _add(f"{key} ندارد")
        else:
            _add(f"{key}: {val}")

    for key, val in sorted(raw.items()):
        if len(highlights) >= limit:
            break
        if key in seen or key in {s['key'] for s in LISTING_CORE_AMENITIES}:
            continue
        if key in _FEATURE_HIGHLIGHT_PRIORITY:
            continue
        v = _clean_value(val)
        if v:
            _add(f"{key}: {v}")

    return highlights[:limit]


def feature_details_for_edit(listing, limit: int = 12) -> List[Dict[str, str]]:
    """لیست label/value برای نمایش در مودال ویرایش."""
    raw = _collect_raw_features(listing.data or {})
    ordered_keys: List[str] = []
    for key in LISTING_FEATURE_COLUMNS:
        if _clean_value(raw.get(key)):
            ordered_keys.append(key)
    for key in sorted(raw):
        if key not in ordered_keys:
            ordered_keys.append(key)
    rows: List[Dict[str, str]] = []
    for key in ordered_keys:
        val = _clean_value(raw.get(key))
        if not val:
            continue
        rows.append({'label': key, 'value': val})
        if len(rows) >= limit:
            break
    return rows


def build_listing_feature_profile(listing, base_feat: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """پروفایل نمایشی ویژگی‌ها برای صفحه جزئیات آگهی."""
    data = listing.data or {}
    raw = _collect_raw_features(data)
    base_feat = base_feat or {}

    core: List[Dict[str, Any]] = []
    for spec in LISTING_CORE_AMENITIES:
        key = spec['key']
        field = spec['field']
        bool_val = base_feat.get(field)
        raw_text = raw.get(key)
        if bool_val is None:
            bool_val = parse_bool_feature(raw_text)
        elif bool_val is False and parse_bool_feature(raw_text) is True:
            bool_val = True
        if bool_val is True:
            display = 'دارد'
            state = 'yes'
        elif bool_val is False:
            display = 'ندارد'
            state = 'no'
        else:
            display = raw.get(key) or ''
            state = _feature_state(display) if display else 'unknown'
        core.append({
            'key': key,
            'label': key,
            'value': display or ('—' if state == 'unknown' else display),
            'state': state,
            'icon': spec['icon'],
            'known': state != 'unknown',
        })

    groups: List[Dict[str, Any]] = []
    used_keys: set = set()
    for group in LISTING_FEATURE_GROUPS:
        items: List[Dict[str, Any]] = []
        for key in group['keys']:
            val = _clean_value(raw.get(key))
            if not val:
                continue
            used_keys.add(key)
            items.append(_format_item_display(key, val))
        if items:
            groups.append({
                'id': group['id'],
                'title': group['title'],
                'icon': group['icon'],
                'accent': group['accent'],
                'items': items,
            })

    # ویژگی‌های اضافی (ستون‌های داینامیک ربات)
    extra_items: List[Dict[str, Any]] = []
    for key, val in sorted(raw.items()):
        if key in used_keys or key in {s['key'] for s in LISTING_CORE_AMENITIES}:
            continue
        extra_items.append(_format_item_display(key, val))
    if extra_items:
        groups.append({
            'id': 'extra',
            'title': 'سایر جزئیات',
            'icon': 'fa-ellipsis-h',
            'accent': 'amber',
            'items': extra_items,
        })

    detail_count = sum(len(g['items']) for g in groups)
    core_known = sum(1 for c in core if c['known'])
    chip_items = [
        item for g in groups for item in g['items'] if item.get('is_chip')
    ]

    return {
        'core': core,
        'groups': groups,
        'chip_items': chip_items,
        'has_details': bool(groups) or core_known > 0,
        'detail_count': detail_count + core_known,
        'raw': raw,
        'source_label': 'ثبت‌شده از دیوار',
    }
