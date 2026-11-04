"""تشخیص نوع ملک برای آگهی‌های فایلینگ."""
from __future__ import annotations

from dataclasses import dataclass
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

_TYPE_CONFIDENCE_HIGH = 'high'
_TYPE_CONFIDENCE_MEDIUM = 'medium'
_TYPE_CONFIDENCE_LOW = 'low'
_TYPE_CONFIDENCE_NONE = 'none'

_SOURCE_STRUCTURED = 'structured_data'
_SOURCE_DATASET = 'dataset_subcategory'
_SOURCE_METADATA = 'extract_metadata'
_SOURCE_TITLE = 'title'
_SOURCE_NONE = 'none'

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

# زیردسته‌های کلی (مثل «خانه و ویلا») عمداً نگاشت نمی‌شوند — نوع مشخص ساخته نمی‌شود.
_DATASET_SUBCATEGORY_HINTS = (
    ('آپارتمان', 'آپارتمان'),
    ('ویلا', 'ویلا'),
    ('زمین', 'زمین'),
    ('کلنگی', 'کلنگی'),
    ('مغازه', 'مغازه'),
    ('غرفه', 'مغازه'),
    ('تجاری', 'مغازه'),
    ('دفتر', 'اداری'),
    ('اداری', 'اداری'),
)


@dataclass(frozen=True)
class PropertyTypeInference:
    property_type: str
    source: str
    confidence: str


def _match_title_hints(text: str) -> Optional[str]:
    norm = normalize_geo_text(text)
    if not norm:
        return None
    for token, ptype in _TITLE_HINTS:
        if token in norm:
            return ptype
    return None


def _structured_data_type(listing: Listing) -> Optional[str]:
    data = listing.data or {}
    for key in ('property_type', 'propertyType', 'type', 'category_slug'):
        raw = data.get(key)
        if not raw:
            continue
        norm = normalize_geo_text(str(raw))
        if norm in _CATEGORY_TYPE_MAP:
            return _CATEGORY_TYPE_MAP[norm]
        hinted = _match_title_hints(norm)
        if hinted:
            return hinted
    category = normalize_geo_text(str(data.get('category', '') or ''))
    if category in _CATEGORY_TYPE_MAP:
        return _CATEGORY_TYPE_MAP[category]
    hinted = _match_title_hints(category)
    if hinted:
        return hinted
    return None


def _dataset_subcategory_type(listing: Listing) -> Optional[str]:
    ds = getattr(listing, 'dataset', None)
    raw_sub = (getattr(ds, 'subcategory', '') or '').strip()
    if not raw_sub:
        return None
    norm = normalize_geo_text(raw_sub)
    if norm in {'خانه و ویلا', 'خانه ويلا'}:
        return None
    for token, ptype in _DATASET_SUBCATEGORY_HINTS:
        if norm == normalize_geo_text(token):
            return ptype
    return None


def _metadata_type(listing: Listing) -> Optional[str]:
    data = listing.data or {}
    for key in ('نوع_ملک', 'property_type_label', 'subcategory', 'دسته'):
        raw = data.get(key)
        if not raw:
            continue
        hinted = _match_title_hints(str(raw))
        if hinted:
            return hinted
    return None


def infer_listing_property_type_detail(listing: Listing) -> PropertyTypeInference:
    """
    ترتیب شواهد: data ساختاریافته → زیردسته dataset → متادیتای data → عنوان.
    """
    from_structured = _structured_data_type(listing)
    if from_structured:
        return PropertyTypeInference(from_structured, _SOURCE_STRUCTURED, _TYPE_CONFIDENCE_HIGH)

    from_dataset = _dataset_subcategory_type(listing)
    if from_dataset:
        return PropertyTypeInference(from_dataset, _SOURCE_DATASET, _TYPE_CONFIDENCE_MEDIUM)

    from_meta = _metadata_type(listing)
    if from_meta:
        return PropertyTypeInference(from_meta, _SOURCE_METADATA, _TYPE_CONFIDENCE_MEDIUM)

    title = listing.title or ''
    from_title = _match_title_hints(title)
    if from_title:
        return PropertyTypeInference(from_title, _SOURCE_TITLE, _TYPE_CONFIDENCE_LOW)

    return PropertyTypeInference('', _SOURCE_NONE, _TYPE_CONFIDENCE_NONE)


def infer_listing_property_type(listing: Listing) -> str:
    """داده ساختاریافته اولویت دارد؛ بدون شواهد «آپارتمان» فرض نمی‌شود."""
    return infer_listing_property_type_detail(listing).property_type
