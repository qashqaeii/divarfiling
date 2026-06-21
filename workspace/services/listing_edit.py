"""داده و ذخیره فرم ویرایش آگهی."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.services.features import FEATURE_KEYS, extract_listing_features
from workspace.services.listing_features import feature_details_for_edit


def listing_edit_payload(listing, feat: Optional[dict] = None) -> Dict[str, Any]:
    """داده کامل برای مودال ویرایش — بدون escape دستی."""
    feat = feat or extract_listing_features(listing)
    biz = (listing.business_type or '').strip()
    if feat.get('is_consultant') and not biz:
        biz = 'مشاور'
    return {
        'id': listing.id,
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
