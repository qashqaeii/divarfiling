"""تشخیص نوع ملک برای آگهی‌های فایلینگ."""
from __future__ import annotations

from typing import Optional

from workspace.models import Listing
from workspace.services.crm_matching_geo import normalize_geo_text

# کلید data / category → نوع استاندارد CRM
_CATEGORY_TYPE_MAP = {
    'apartment': 'آپارتمان',
    'apartment-sell': 'آپارتمان',
    'apartment-rent': 'آپارتمان',
    'villa': 'ویلا',
    'house-villa': 'ویلا',
    'house-villa-sell': 'ویلا',
    'land': 'زمین',
    'plot-old': 'کلنگی',
    'shop': 'مغازه',
    'commercial': 'مغازه',
    'office': 'اداری',
    'office-sell': 'اداری',
}

_TITLE_HINTS = (
    ('زمین', 'زمین'),
    ('باغچه', 'زمین'),
    ('کلنگی', 'کلنگی'),
    ('ویلا', 'ویلا'),
    ('باغ ', 'ویلا'),
    ('مغازه', 'مغازه'),
    ('تجاری', 'مغازه'),
    ('اداری', 'اداری'),
    ('دفتر', 'اداری'),
    ('آپارتمان', 'آپارتمان'),
)


def _data_property_type(listing: Listing) -> Optional[str]:
    data = listing.data or {}
    for key in ('property_type', 'propertyType', 'type', 'category_slug'):
        raw = data.get(key)
        if not raw:
            continue
        norm = normalize_geo_text(str(raw))
        if norm in _CATEGORY_TYPE_MAP:
            return _CATEGORY_TYPE_MAP[norm]
        for token, ptype in _TITLE_HINTS:
            if token in norm:
                return ptype
    category = normalize_geo_text(str(data.get('category', '') or ''))
    if category in _CATEGORY_TYPE_MAP:
        return _CATEGORY_TYPE_MAP[category]
    for token, ptype in _TITLE_HINTS:
        if token in category:
            return ptype
    return None


def _title_property_type(listing: Listing) -> Optional[str]:
    title = normalize_geo_text(listing.title or '')
    if not title:
        return None
    for token, ptype in _TITLE_HINTS:
        if token in title:
            return ptype
    return None


def infer_listing_property_type(listing: Listing) -> str:
    """داده ساختاریافته اولویت دارد؛ بدون شواهد «آپارتمان» فرض نمی‌شود."""
    from_data = _data_property_type(listing)
    if from_data:
        return from_data
    from_title = _title_property_type(listing)
    if from_title:
        return from_title
    return ''
