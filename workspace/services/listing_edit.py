"""داده و ذخیره فرم ویرایش آگهی فایلینگ."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from workspace.constants import (
    LISTING_CORE_AMENITIES,
    LISTING_FEATURE_COLUMNS,
    LISTING_FEATURE_GROUPS,
)
from workspace.services.features import FEATURE_KEYS, extract_listing_features, get_exact_from_data
from workspace.services.listing_features import (
    _collect_raw_features,
    _feature_state,
    feature_details_for_edit,
)
from workspace.services.property_features import CHOICES_OCCUPANCY, FIELDS as CRM_FEATURE_FIELDS

OWNER_PHONE_KEYS = ('شماره تماس', 'owner_phone', 'phone', 'موبایل', 'تلفن', 'تماس')
OWNER_NAME_KEYS = ('نام مالک', 'owner_name', 'نام و نام خانوادگی مالک', 'نام صاحب')
TENANT_PHONE_KEYS = ('شماره مستاجر', 'tenant_phone', 'شماره مستأجر', 'تلفن مستاجر')
TENANT_NAME_KEYS = ('نام مستاجر', 'tenant_name', 'نام مستأجر', 'نام و نام خانوادگی مستاجر')
VACANCY_DATE_KEYS = ('تاریخ تخلیه', 'vacancy_date', 'تاریخ تخلیه یا آماده تحویل')
ADDRESS_KEYS = ('آدرس', 'address', 'مکان_آدرس')
DISTRICT_KEYS = ('منطقه', 'district', 'district_persian', 'مکان_منطقه')

# امکانات اضافه (علاوه بر آسانسور/پارکینگ/انباری)
EXTRA_AMENITY_FIELDS = (
    ('balcony', 'بالکن'),
    ('lobby', 'لابی'),
    ('pool', 'استخر'),
    ('roof_garden', 'روف گاردن'),
    ('jacuzzi', 'جکوزی'),
    ('gym', 'سالن ورزش'),
)

# ویژگی‌هایی که با سلکت سه‌حالته ویرایش می‌شوند
BOOLISH_FEATURE_KEYS = frozenset({
    'بالکن', 'جکوزی', 'سونا', 'حیوان خانگی مجاز', 'قابل معاوضه',
    'بازسازی شده', 'سند', 'مجوز ساخت',
})

CORE_AMENITY_LABELS = frozenset(s['key'] for s in LISTING_CORE_AMENITIES)
# این‌ها فیلد اختصاصی در فرم دارند و نباید دوبار ویرایش شوند
DEDICATED_FEATURE_KEYS = frozenset({
    'تعداد کل طبقات ساختمان',
    'بالکن', 'جکوزی', 'لابی', 'استخر', 'روف گاردن', 'سالن ورزش',
    'آسانسور', 'پارکینگ', 'انباری',
    'وضعیت سکونت',
    'تاریخ تخلیه',
    'vacancy_date',
    'تاریخ تخلیه یا آماده تحویل',
}) | CORE_AMENITY_LABELS

OCCUPANCY_KEYS = ('وضعیت سکونت', 'وضعیت واحد', 'occupancy', 'unit_status')
VACANT_MARKERS = ('تخلیه', 'تخليه', 'خالی', 'خالي', 'vacant', 'empty')

# کلیدهای دیوار که در کاتالوگ CRM نام متفاوت دارند ولی همان گزینه‌ها را می‌گیرند
_LISTING_FEATURE_CHOICE_ALIASES = {
    'وضعیت واحد': CHOICES_OCCUPANCY,
}


def _input_meta_for_feature(key: str, val: str = '') -> Dict[str, Any]:
    """نوع ورودی و گزینه‌های انتخابی — هم‌تراز با فرم ورود ملک CRM."""
    if key in BOOLISH_FEATURE_KEYS:
        return {'input': 'tri', 'choices': []}

    spec = CRM_FEATURE_FIELDS.get(key)
    choices: List[str] = []
    widget = ''
    if spec:
        widget = str(spec.get('widget') or '')
        choices = [str(c).strip() for c in (spec.get('choices') or ()) if str(c).strip()]
        if widget == 'toggle':
            return {'input': 'tri', 'choices': []}
    elif key in _LISTING_FEATURE_CHOICE_ALIASES:
        choices = [str(c).strip() for c in _LISTING_FEATURE_CHOICE_ALIASES[key] if str(c).strip()]

    if choices:
        cleaned_val = str(val or '').strip()
        if cleaned_val and cleaned_val not in choices:
            choices = [cleaned_val] + choices
        return {'input': 'select', 'choices': choices}

    if val and _feature_state(val) in ('yes', 'no'):
        return {'input': 'tri', 'choices': []}
    return {'input': 'text', 'choices': []}


def _make_feature_field(
    key: str,
    val: str,
    *,
    group_id: str,
    group_title: str,
    group_icon: str,
) -> Dict[str, Any]:
    cleaned = '' if val is None else str(val)
    meta = _input_meta_for_feature(key, cleaned)
    return {
        'key': key,
        'label': key,
        'value': cleaned,
        'group_id': group_id,
        'group_title': group_title,
        'group_icon': group_icon,
        'input': meta['input'],
        'choices': meta['choices'],
        'state': _feature_state(cleaned) if cleaned else 'unknown',
    }


def occupancy_status_from_listing(listing) -> str:
    data = listing.data or {}
    for key in OCCUPANCY_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def listing_is_vacant(listing) -> bool:
    """آیا آگهی به‌عنوان تخلیه علامت خورده است."""
    val = occupancy_status_from_listing(listing)
    if not val:
        return False
    low = val.lower()
    return any(marker in val or marker in low for marker in VACANT_MARKERS)


def apply_vacant_flag_to_data(data: dict, is_vacant: bool) -> None:
    """تنظیم/پاک‌کردن وضعیت سکونت بر اساس تیک تخلیه."""
    if is_vacant:
        data['وضعیت سکونت'] = 'تخلیه'
        _clear_tenant_from_data(data)
        return
    current = ''
    for key in OCCUPANCY_KEYS:
        raw = data.get(key)
        if raw is not None and str(raw).strip():
            current = str(raw).strip()
            break
    if current and any(m in current or m in current.lower() for m in VACANT_MARKERS):
        for key in OCCUPANCY_KEYS:
            data.pop(key, None)


def tenant_phone_from_listing(listing) -> str:
    data = listing.data or {}
    for key in TENANT_PHONE_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def tenant_name_from_listing(listing) -> str:
    data = listing.data or {}
    for key in TENANT_NAME_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def vacancy_date_from_listing(listing) -> str:
    """تاریخ تخلیه ذخیره‌شده — شمسی با ارقام فارسی، یا رشته خالی."""
    from workspace.services.property_features import normalize_feature_date_value

    data = listing.data or {}
    for key in VACANCY_DATE_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return normalize_feature_date_value(str(value).strip())
    return ''


def _apply_vacancy_date(listing, raw: str) -> None:
    from workspace.services.property_features import normalize_feature_date_value

    data = dict(listing.data or {})
    cleaned = normalize_feature_date_value((raw or '').strip())
    if cleaned:
        data['تاریخ تخلیه'] = cleaned
        data['vacancy_date'] = cleaned
    else:
        for key in VACANCY_DATE_KEYS:
            data.pop(key, None)
    listing.data = data


def _clear_tenant_from_data(data: dict) -> None:
    for key in TENANT_PHONE_KEYS + TENANT_NAME_KEYS:
        data.pop(key, None)


def _apply_tenant_fields(listing, *, phone: str = '', name: str = '', is_vacant: bool = False) -> None:
    data = dict(listing.data or {})
    if is_vacant:
        _clear_tenant_from_data(data)
        listing.data = data
        return
    phone = (phone or '').strip()
    name = (name or '').strip()
    if phone:
        data['شماره مستاجر'] = phone
        data['tenant_phone'] = phone
    else:
        for key in TENANT_PHONE_KEYS:
            data.pop(key, None)
    if name:
        data['نام مستاجر'] = name
        data['tenant_name'] = name
    else:
        for key in TENANT_NAME_KEYS:
            data.pop(key, None)
    listing.data = data


MAX_LISTING_IMAGES = 24


def owner_phone_from_listing(listing) -> str:
    data = listing.data or {}
    for key in OWNER_PHONE_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def owner_name_from_listing(listing) -> str:
    data = listing.data or {}
    for key in OWNER_NAME_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def address_from_listing(listing) -> str:
    data = listing.data or {}
    for key in ADDRESS_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def district_from_listing(listing) -> str:
    data = listing.data or {}
    for key in DISTRICT_KEYS:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    dataset = getattr(listing, 'dataset', None)
    if dataset is not None:
        ds_district = getattr(dataset, 'district', None)
        if ds_district is not None and str(ds_district).strip():
            return str(ds_district).strip()
    return ''


def total_floors_from_listing(listing, feat: Optional[dict] = None) -> str:
    raw = _collect_raw_features(listing.data or {})
    val = raw.get('تعداد کل طبقات ساختمان')
    if val:
        return str(val).strip()
    data = listing.data or {}
    for key in ('تعداد کل طبقات ساختمان', 'total_floors', 'تعداد طبقات'):
        value = get_exact_from_data(data, key) if key == 'تعداد کل طبقات ساختمان' else data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def _apply_owner_phone(listing, phone: str) -> None:
    data = dict(listing.data or {})
    phone = (phone or '').strip()
    if phone:
        data['شماره تماس'] = phone
        data['owner_phone'] = phone
    else:
        for key in OWNER_PHONE_KEYS:
            data.pop(key, None)
    listing.data = data


def _apply_owner_name(listing, name: str) -> None:
    data = dict(listing.data or {})
    name = (name or '').strip()
    if name:
        data['نام مالک'] = name
        data['owner_name'] = name
    else:
        for key in OWNER_NAME_KEYS:
            data.pop(key, None)
    listing.data = data


def _apply_data_text(listing, keys: tuple, value: str, primary: str) -> None:
    data = dict(listing.data or {})
    value = (value or '').strip()
    if value:
        data[primary] = value
    else:
        for key in keys:
            data.pop(key, None)
    listing.data = data


def apply_owner_fields(listing, *, phone: Optional[str] = None, name: Optional[str] = None) -> None:
    """به‌روزرسانی شماره/نام مالک در Listing.data (None = بدون تغییر)."""
    if phone is not None:
        _apply_owner_phone(listing, phone)
    if name is not None:
        _apply_owner_name(listing, name)


def _tri_payload(value: Any) -> Optional[bool]:
    if value is True or value is False:
        return value
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in ('1', 'true', 'yes', 'دارد'):
        return True
    if raw in ('0', 'false', 'no', 'ندارد'):
        return False
    return None


def _feature_fields_for_edit(listing) -> List[Dict[str, Any]]:
    """همه ستون‌های ویژگی دیوار + ویژگی‌های اضافی — برای فرم ویرایش."""
    raw = _collect_raw_features(listing.data or {})
    fields: List[Dict[str, Any]] = []
    used: set = set()

    for group in LISTING_FEATURE_GROUPS:
        for key in group['keys']:
            if key in DEDICATED_FEATURE_KEYS:
                continue
            used.add(key)
            fields.append(_make_feature_field(
                key,
                raw.get(key, ''),
                group_id=group['id'],
                group_title=group['title'],
                group_icon=group.get('icon', 'fa-list'),
            ))

    # ستون‌های استاندارد که در گروه نیستند
    for key in LISTING_FEATURE_COLUMNS:
        if key in used or key in DEDICATED_FEATURE_KEYS:
            continue
        used.add(key)
        fields.append(_make_feature_field(
            key,
            raw.get(key, ''),
            group_id='extra',
            group_title='سایر جزئیات',
            group_icon='fa-ellipsis-h',
        ))

    for key, val in sorted(raw.items()):
        if key in used or key in DEDICATED_FEATURE_KEYS:
            continue
        fields.append(_make_feature_field(
            key,
            val,
            group_id='extra',
            group_title='سایر جزئیات',
            group_icon='fa-ellipsis-h',
        ))

    return fields


def feature_fields_for_edit(listing) -> List[Dict[str, Any]]:
    """خروجی پایدار برای فرم ویرایش موبایل و داشبورد."""
    return _feature_fields_for_edit(listing)


def listing_edit_payload(listing, feat: Optional[dict] = None) -> Dict[str, Any]:
    """داده کامل برای مودال ویرایش — بدون escape دستی."""
    feat = feat or extract_listing_features(listing)
    biz = (listing.business_type or '').strip()
    if feat.get('is_consultant') and not biz:
        biz = 'مشاور'

    images = []
    for img in (listing.images or []):
        url = str(img or '').strip()
        if url:
            images.append(url)

    amenity_extra = {}
    for field, _label in EXTRA_AMENITY_FIELDS:
        amenity_extra[field] = feat.get(field)

    dataset = getattr(listing, 'dataset', None)
    tx_type = getattr(dataset, 'transaction_type', '') if dataset is not None else ''
    from workspace.services.display import transaction_profile
    tx = transaction_profile(tx_type)
    is_rent = bool(tx.get('is_rent') or tx.get('is_mixed') or listing.deposit or listing.rent)

    return {
        'id': listing.id,
        'dataset_id': str(listing.dataset_id),
        'token': listing.token or '',
        'title': listing.title or '',
        'price': listing.price,
        'deposit': listing.deposit,
        'rent': listing.rent,
        'area': listing.area,
        'rooms': feat.get('rooms') or listing.rooms or '',
        'floor': feat.get('floor') or '',
        'total_floors': total_floors_from_listing(listing, feat),
        'build_year': feat.get('build_year'),
        'elevator': feat.get('elevator'),
        'parking': feat.get('parking'),
        'storage': feat.get('storage'),
        **amenity_extra,
        'neighborhood': listing.neighborhood or '',
        'city': listing.city or '',
        'district': district_from_listing(listing),
        'address': address_from_listing(listing),
        'latitude': listing.latitude,
        'longitude': listing.longitude,
        'business_type': biz or 'شخصی',
        'owner_phone': owner_phone_from_listing(listing),
        'owner_name': owner_name_from_listing(listing),
        'tenant_phone': tenant_phone_from_listing(listing),
        'tenant_name': tenant_name_from_listing(listing),
        'vacancy_date': vacancy_date_from_listing(listing),
        'link': listing.link or '',
        'description': listing.description or '',
        'is_expired': bool(listing.is_expired),
        'is_rent': is_rent,
        'is_vacant': listing_is_vacant(listing),
        'images': images,
        'feature_fields': _feature_fields_for_edit(listing),
        # سازگاری با UI قدیمی
        'feature_details': feature_details_for_edit(listing, limit=40),
        'feature_highlights': feat.get('highlights') or [],
    }


def _tri_state(post, name: str) -> Optional[bool]:
    if name not in post:
        return None
    raw = post.get(name, '').strip()
    if raw == '1':
        return True
    if raw == '0':
        return False
    if raw == '':
        return None
    return _tri_payload(raw)


def _parse_optional_float(raw: str) -> Optional[float]:
    raw = (raw or '').strip().replace(',', '')
    if not raw:
        return None
    return float(raw)


def _parse_optional_int(raw: str) -> Optional[int]:
    raw = (raw or '').strip().replace(',', '')
    if not raw:
        return None
    return int(float(raw))


def _set_or_clear_feature(data: dict, key: str, value: str) -> None:
    value = (value or '').strip()
    if value:
        data[key] = value
    else:
        data.pop(key, None)


def _apply_images(listing, post) -> None:
    if 'images_json' not in post:
        return
    raw = post.get('images_json', '').strip()
    if not raw:
        listing.images = []
        return
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError('لیست تصاویر نامعتبر است.')
    if not isinstance(parsed, list):
        raise ValueError('لیست تصاویر نامعتبر است.')
    cleaned: List[str] = []
    for item in parsed:
        url = str(item or '').strip()
        if not url:
            continue
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('/')):
            continue
        cleaned.append(url)
        if len(cleaned) >= MAX_LISTING_IMAGES:
            break
    listing.images = cleaned


def _apply_feature_post(data: dict, post) -> None:
    """ویژگی‌های تفصیلی از فیلدهای feat__* یا features_json."""
    if 'features_json' in post:
        raw = post.get('features_json', '').strip()
        if raw:
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                raise ValueError('ویژگی‌های آگهی نامعتبر است.')
            if isinstance(parsed, dict):
                for key, val in parsed.items():
                    key = str(key or '').strip()
                    if not key or key in DEDICATED_FEATURE_KEYS:
                        continue
                    if val is None:
                        data.pop(key, None)
                        continue
                    text = str(val).strip()
                    if text:
                        data[key] = text
                    else:
                        data.pop(key, None)
                return

    # فرم HTML: feat__کلید
    for key in list(post.keys()) if hasattr(post, 'keys') else []:
        if not str(key).startswith('feat__'):
            continue
        feature_key = str(key)[6:].strip()
        if not feature_key or feature_key in DEDICATED_FEATURE_KEYS:
            continue
        _set_or_clear_feature(data, feature_key, post.get(key, ''))


def apply_listing_edit_post(listing, post) -> None:
    """فیلدهای مدل + ویژگی‌های داخل data را از POST به‌روز می‌کند."""
    int_fields = ('price', 'deposit', 'rent')
    for field in int_fields:
        if field in post:
            listing.__setattr__(field, _parse_optional_int(post.get(field, '')))

    if 'area' in post:
        listing.area = _parse_optional_float(post.get('area', ''))

    if 'latitude' in post:
        listing.latitude = _parse_optional_float(post.get('latitude', ''))
    if 'longitude' in post:
        listing.longitude = _parse_optional_float(post.get('longitude', ''))

    text_fields = ('title', 'rooms', 'neighborhood', 'city', 'business_type', 'description', 'link')
    for field in text_fields:
        if field in post:
            listing.__setattr__(field, post.get(field, '').strip())

    if 'is_expired' in post:
        raw = post.get('is_expired', '').strip().lower()
        listing.is_expired = raw in ('1', 'true', 'on', 'yes')

    _apply_images(listing, post)

    data = dict(listing.data or {})

    # همگام‌سازی فیلدهای مدل با data — نمایش صفحه جزئیات از data می‌خواند
    if 'title' in post:
        if listing.title:
            data['عنوان'] = listing.title
        else:
            data.pop('عنوان', None)
            data.pop('title', None)
    if 'description' in post:
        for key in list(data.keys()):
            kl = str(key).lower()
            if 'توضیح' in str(key) or kl in ('description', 'desc'):
                data.pop(key, None)
        if listing.description:
            data['توضیحات'] = listing.description
    if 'city' in post:
        if listing.city:
            data['شهر'] = listing.city
            data['مکان_شهر'] = listing.city
        else:
            data.pop('شهر', None)
            data.pop('city', None)
            data.pop('مکان_شهر', None)
    if 'neighborhood' in post:
        if listing.neighborhood:
            data['محله'] = listing.neighborhood
        else:
            data.pop('محله', None)
            data.pop('neighborhood', None)
    if 'link' in post:
        if listing.link:
            data['لینک'] = listing.link
        else:
            data.pop('لینک', None)
            data.pop('link', None)
    if 'rooms' in post:
        if listing.rooms:
            data['اتاق'] = listing.rooms
            data['تعداد اتاق'] = listing.rooms
        else:
            data.pop('اتاق', None)
            data.pop('rooms', None)
            data.pop('تعداد اتاق', None)
    for model_key, data_keys in (
        ('price', ('قیمت', 'price')),
        ('deposit', ('ودیعه', 'deposit', 'رهن')),
        ('rent', ('اجاره', 'اجاره ماهانه', 'rent')),
        ('area', ('متراژ', 'area')),
    ):
        if model_key not in post:
            continue
        value = getattr(listing, model_key, None)
        if value is None or value == '':
            for dk in data_keys:
                data.pop(dk, None)
        else:
            data[data_keys[0]] = value

    if 'floor' in post:
        floor = post.get('floor', '').strip()
        if floor:
            data[FEATURE_KEYS['floor'][0]] = floor
        else:
            for k in FEATURE_KEYS['floor']:
                data.pop(k, None)

    if 'total_floors' in post:
        tf = post.get('total_floors', '').strip()
        if tf:
            data['تعداد کل طبقات ساختمان'] = tf
        else:
            data.pop('تعداد کل طبقات ساختمان', None)
            data.pop('total_floors', None)

    if 'build_year' in post:
        raw = post.get('build_year', '').strip()
        if raw:
            try:
                data[FEATURE_KEYS['build_year'][0]] = int(raw)
            except ValueError:
                data[FEATURE_KEYS['build_year'][0]] = raw
        else:
            for k in FEATURE_KEYS['build_year']:
                data.pop(k, None)

    for field, data_key in (
        ('elevator', FEATURE_KEYS['elevator'][0]),
        ('parking', FEATURE_KEYS['parking'][0]),
        ('storage', FEATURE_KEYS['storage'][0]),
    ):
        if field not in post:
            continue
        state = _tri_state(post, field)
        if state is True:
            data[data_key] = 'دارد'
        elif state is False:
            data[data_key] = 'ندارد'
        else:
            for k in FEATURE_KEYS[field]:
                data.pop(k, None)

    for field, label in EXTRA_AMENITY_FIELDS:
        if field not in post:
            continue
        keys = FEATURE_KEYS.get(field, (label,))
        state = _tri_state(post, field)
        if state is True:
            data[keys[0]] = 'دارد'
        elif state is False:
            data[keys[0]] = 'ندارد'
        else:
            for k in keys:
                data.pop(k, None)

    if 'is_vacant' in post:
        if hasattr(post, 'getlist'):
            raw_vals = post.getlist('is_vacant')
        else:
            raw = post.get('is_vacant', '')
            raw_vals = raw if isinstance(raw, (list, tuple)) else [raw]
        raw = str(raw_vals[-1] if raw_vals else '').strip().lower()
        is_vacant = raw in ('1', 'true', 'on', 'yes')
        apply_vacant_flag_to_data(data, is_vacant)
        listing.data = data
        if 'tenant_phone' in post or 'tenant_name' in post:
            _apply_tenant_fields(
                listing,
                phone=post.get('tenant_phone', '') if 'tenant_phone' in post else tenant_phone_from_listing(listing),
                name=post.get('tenant_name', '') if 'tenant_name' in post else tenant_name_from_listing(listing),
                is_vacant=is_vacant,
            )
            data = dict(listing.data or {})
    elif 'tenant_phone' in post or 'tenant_name' in post:
        _apply_tenant_fields(
            listing,
            phone=post.get('tenant_phone', '') if 'tenant_phone' in post else tenant_phone_from_listing(listing),
            name=post.get('tenant_name', '') if 'tenant_name' in post else tenant_name_from_listing(listing),
            is_vacant=listing_is_vacant(listing),
        )
        data = dict(listing.data or {})

    if 'vacancy_date' in post:
        listing.data = data
        _apply_vacancy_date(listing, post.get('vacancy_date', ''))
        data = dict(listing.data or {})

    _apply_feature_post(data, post)

    listing.data = data

    if 'address' in post:
        _apply_data_text(listing, ADDRESS_KEYS, post.get('address', ''), 'آدرس')
    if 'district' in post:
        _apply_data_text(listing, DISTRICT_KEYS, post.get('district', ''), 'منطقه')

    if 'owner_phone' in post:
        _apply_owner_phone(listing, post.get('owner_phone', ''))
    if 'owner_name' in post:
        _apply_owner_name(listing, post.get('owner_name', ''))

    # همگام‌سازی مختصات در data برای نمایش
    data = dict(listing.data or {})
    if listing.latitude is not None:
        data['عرض جغرافیایی'] = listing.latitude
        data['مکان_مختصات_lat'] = listing.latitude
    elif 'latitude' in post:
        data.pop('عرض جغرافیایی', None)
        data.pop('مکان_مختصات_lat', None)
    if listing.longitude is not None:
        data['طول جغرافیایی'] = listing.longitude
        data['مکان_مختصات_lng'] = listing.longitude
    elif 'longitude' in post:
        data.pop('طول جغرافیایی', None)
        data.pop('مکان_مختصات_lng', None)
    listing.data = data


class _JsonPostAdapter:
    """Map JSON body to the POST-like interface used by apply_listing_edit_post."""

    def __init__(self, payload: Dict[str, Any]):
        self._payload = dict(payload or {})
        # features dict → features_json
        if 'features' in self._payload and isinstance(self._payload['features'], dict):
            self._payload['features_json'] = json.dumps(
                self._payload['features'], ensure_ascii=False,
            )
        if 'images' in self._payload and isinstance(self._payload['images'], list):
            self._payload['images_json'] = json.dumps(self._payload['images'])
        if 'is_expired' in self._payload and isinstance(self._payload['is_expired'], bool):
            self._payload['is_expired'] = '1' if self._payload['is_expired'] else '0'

    def __contains__(self, key: str) -> bool:
        if key not in self._payload:
            return False
        # null در PATCH یعنی «این فیلد را تغییر نده» — نه پاک‌کردن مقدار.
        return self._payload[key] is not None

    def keys(self):
        return self._payload.keys()

    def get(self, key: str, default: str = '') -> str:
        if key not in self._payload:
            return default
        value = self._payload[key]
        if value is None:
            return ''
        if isinstance(value, bool):
            return '1' if value else '0'
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value).strip()


def apply_listing_edit_json(listing, payload: Dict[str, Any]) -> None:
    """Apply listing edits from mobile/API JSON body."""
    apply_listing_edit_post(listing, _JsonPostAdapter(payload))
