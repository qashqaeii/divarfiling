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

OWNER_PHONE_KEYS = ('شماره تماس', 'owner_phone', 'phone', 'موبایل', 'تلفن', 'تماس')
OWNER_NAME_KEYS = ('نام مالک', 'owner_name', 'نام و نام خانوادگی مالک', 'نام صاحب')
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
}) | CORE_AMENITY_LABELS

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
            val = raw.get(key, '')
            fields.append({
                'key': key,
                'label': key,
                'value': val,
                'group_id': group['id'],
                'group_title': group['title'],
                'group_icon': group.get('icon', 'fa-list'),
                'input': 'tri' if key in BOOLISH_FEATURE_KEYS else 'text',
                'state': _feature_state(val) if val else 'unknown',
            })

    # ستون‌های استاندارد که در گروه نیستند
    for key in LISTING_FEATURE_COLUMNS:
        if key in used or key in DEDICATED_FEATURE_KEYS:
            continue
        used.add(key)
        val = raw.get(key, '')
        fields.append({
            'key': key,
            'label': key,
            'value': val,
            'group_id': 'extra',
            'group_title': 'سایر جزئیات',
            'group_icon': 'fa-ellipsis-h',
            'input': 'tri' if key in BOOLISH_FEATURE_KEYS else 'text',
            'state': _feature_state(val) if val else 'unknown',
        })

    for key, val in sorted(raw.items()):
        if key in used or key in DEDICATED_FEATURE_KEYS:
            continue
        fields.append({
            'key': key,
            'label': key,
            'value': val,
            'group_id': 'extra',
            'group_title': 'سایر جزئیات',
            'group_icon': 'fa-ellipsis-h',
            'input': 'tri' if key in BOOLISH_FEATURE_KEYS or _feature_state(val) in ('yes', 'no') else 'text',
            'state': _feature_state(val) if val else 'unknown',
        })

    return fields


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
        'link': listing.link or '',
        'description': listing.description or '',
        'is_expired': bool(listing.is_expired),
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
        return key in self._payload

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
