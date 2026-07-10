"""داده و ذخیره فرم ویرایش آگهی."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.services.features import FEATURE_KEYS, extract_listing_features
from workspace.services.listing_features import feature_details_for_edit

OWNER_PHONE_KEYS = ('شماره تماس', 'owner_phone', 'phone', 'موبایل', 'تلفن', 'تماس')
OWNER_NAME_KEYS = ('نام مالک', 'owner_name', 'نام و نام خانوادگی مالک', 'نام صاحب')


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


def apply_owner_fields(listing, *, phone: Optional[str] = None, name: Optional[str] = None) -> None:
    """به‌روزرسانی شماره/نام مالک در Listing.data (None = بدون تغییر)."""
    if phone is not None:
        _apply_owner_phone(listing, phone)
    if name is not None:
        _apply_owner_name(listing, name)


def listing_edit_payload(listing, feat: Optional[dict] = None) -> Dict[str, Any]:
    """داده کامل برای مودال ویرایش — بدون escape دستی."""
    feat = feat or extract_listing_features(listing)
    biz = (listing.business_type or '').strip()
    if feat.get('is_consultant') and not biz:
        biz = 'مشاور'
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
        'build_year': feat.get('build_year'),
        'elevator': feat.get('elevator'),
        'parking': feat.get('parking'),
        'storage': feat.get('storage'),
        'neighborhood': listing.neighborhood or '',
        'city': listing.city or '',
        'business_type': biz or 'شخصی',
        'owner_phone': owner_phone_from_listing(listing),
        'owner_name': owner_name_from_listing(listing),
        'link': listing.link or '',
        'description': listing.description or '',
        'feature_details': feature_details_for_edit(listing),
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
    return None


def apply_listing_edit_post(listing, post) -> None:
    """فیلدهای مدل + ویژگی‌های داخل data را از POST به‌روز می‌کند."""
    int_fields = ('price', 'deposit', 'rent')
    for field in int_fields:
        if field in post:
            raw = post.get(field, '').strip().replace(',', '')
            listing.__setattr__(field, int(raw) if raw else None)

    if 'area' in post:
        raw = post.get('area', '').strip().replace(',', '')
        listing.area = float(raw) if raw else None

    text_fields = ('title', 'rooms', 'neighborhood', 'city', 'business_type', 'description', 'link')
    for field in text_fields:
        if field in post:
            listing.__setattr__(field, post.get(field, '').strip())

    data = dict(listing.data or {})

    if 'floor' in post:
        floor = post.get('floor', '').strip()
        if floor:
            data[FEATURE_KEYS['floor'][0]] = floor
        else:
            for k in FEATURE_KEYS['floor']:
                data.pop(k, None)

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
        state = _tri_state(post, field)
        if state is True:
            data[data_key] = 'دارد'
        elif state is False:
            data[data_key] = 'ندارد'

    listing.data = data

    if 'owner_phone' in post:
        _apply_owner_phone(listing, post.get('owner_phone', ''))
    if 'owner_name' in post:
        _apply_owner_name(listing, post.get('owner_name', ''))


class _JsonPostAdapter:
    """Map JSON body to the POST-like interface used by apply_listing_edit_post."""

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def __contains__(self, key: str) -> bool:
        return key in self._payload

    def get(self, key: str, default: str = '') -> str:
        if key not in self._payload:
            return default
        value = self._payload[key]
        if value is None:
            return ''
        if isinstance(value, bool):
            return '1' if value else '0'
        return str(value).strip()


def apply_listing_edit_json(listing, payload: Dict[str, Any]) -> None:
    """Apply listing edits from mobile JSON body."""
    apply_listing_edit_post(listing, _JsonPostAdapter(payload))
