"""کاتالوگ فیلدهای قابل اتصال در ویرایشگر لایه‌ای استودیو."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMProperty
from workspace.services.formatting import format_area
from workspace.services.property_content_studio.adapter import (
    _amenity_chips,
    _build_year_label,
    _floor_label,
    _location_line,
    _price_display,
    _rooms_label,
)
from workspace.services.property_content_studio.constants import DEFAULT_VISIBILITY
from workspace.services.property_features import (
    FIELDS,
    _format_feature_value_for_display,
    feature_profile_groups_from_data,
    is_internal_feature_data_key,
)

# کلیدهای پایدار برای binding لایه‌ها — فقط این‌ها و کلیدهای FIELDS در کاتالوگ می‌آیند.
EDITOR_FEATURE_STABLE_KEYS = frozenset({
    'location_line',
    'area_label',
    'rooms_label',
    'floor_label',
    'build_year_label',
    'price',
    'deal_mode',
    'property_type',
    'file_code',
}) | frozenset(FIELDS.keys())

def _is_stable_editor_key(key: str) -> bool:
    if key in EDITOR_FEATURE_STABLE_KEYS:
        return True
    if key.startswith('amenity.'):
        suffix = key[8:]
        return suffix.isdigit() and 0 <= int(suffix) <= 7
    return False


def _visibility_enabled(visibility: Dict[str, bool], visibility_key: str) -> bool:
    if not visibility_key:
        return True
    return bool(visibility.get(visibility_key, True))


def _entry(
    *,
    key: str,
    label: str,
    value: str,
    icon: str,
    group: str,
    visibility_key: str = '',
) -> Dict[str, Any]:
    return {
        'id': key,
        'key': key,
        'label': label,
        'value': value,
        'icon': icon,
        'group': group,
        'visibilityKey': visibility_key,
    }


def _masked_value(value: str, visibility: Dict[str, bool], visibility_key: str) -> str:
    if not value:
        return ''
    if visibility_key and not _visibility_enabled(visibility, visibility_key):
        return ''
    return value


def build_editor_feature_catalog(
    prop: CRMProperty,
    visibility: Optional[Dict[str, bool]] = None,
) -> List[Dict[str, Any]]:
    """فهرست فیلدهای ملک برای پنل ویژگی‌های ویرایشگر."""
    vis = dict(DEFAULT_VISIBILITY)
    if isinstance(visibility, dict):
        for key in vis:
            if key in visibility:
                vis[key] = bool(visibility[key])

    items: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    def add(entry: Dict[str, Any]) -> None:
        key = str(entry.get('key') or '')
        if not key or key in seen_keys or not _is_stable_editor_key(key):
            return
        vk = str(entry.get('visibilityKey') or '')
        entry = dict(entry)
        entry['value'] = _masked_value(str(entry.get('value') or ''), vis, vk)
        items.append(entry)
        seen_keys.add(key)

    location = _location_line(prop, mask_sensitive=False)
    add(_entry(
        key='location_line',
        label='موقعیت',
        value=location,
        icon='fa-location-dot',
        group='core',
        visibility_key='neighborhood',
    ))

    area_label = format_area(prop.area) if prop.area else ''
    add(_entry(
        key='area_label',
        label='متراژ',
        value=area_label,
        icon='fa-ruler-combined',
        group='core',
        visibility_key='area',
    ))

    rooms_label = _rooms_label(prop.rooms or '')
    add(_entry(
        key='rooms_label',
        label='اتاق',
        value=rooms_label,
        icon='fa-bed',
        group='core',
        visibility_key='bedrooms',
    ))

    floor_label = _floor_label(prop)
    add(_entry(
        key='floor_label',
        label='طبقه',
        value=floor_label,
        icon='fa-building',
        group='core',
        visibility_key='floor',
    ))

    build_year_label = _build_year_label(prop)
    add(_entry(
        key='build_year_label',
        label='سال ساخت',
        value=build_year_label,
        icon='fa-calendar',
        group='core',
        visibility_key='floor',
    ))

    price = _price_display(prop)
    price_value = str(price.get('label') or '') if price.get('show') else ''
    add(_entry(
        key='price',
        label='قیمت',
        value=price_value,
        icon='fa-tag',
        group='core',
        visibility_key='price',
    ))

    deal_mode = (prop.deal_mode or '').strip()
    add(_entry(
        key='deal_mode',
        label='نوع معامله',
        value=deal_mode,
        icon='fa-handshake',
        group='core',
    ))

    property_type = (prop.property_type or '').strip()
    add(_entry(
        key='property_type',
        label='نوع ملک',
        value=property_type,
        icon='fa-house',
        group='core',
    ))

    file_code = f'#{prop.pk}'
    add(_entry(
        key='file_code',
        label='کد فایل',
        value=file_code,
        icon='fa-hashtag',
        group='core',
        visibility_key='file_code',
    ))

    amenities_visible = _visibility_enabled(vis, 'amenities')
    for idx, chip in enumerate(_amenity_chips(prop)[:8]):
        chip_key = f'amenity.{idx}'
        value = chip if amenities_visible else ''
        items.append(_entry(
            key=chip_key,
            label=chip,
            value=value,
            icon='fa-check',
            group='amenities',
            visibility_key='amenities',
        ))
        seen_keys.add(chip_key)

    feature_count = 0
    for group in feature_profile_groups_from_data(prop.feature_data):
        for item in group.get('items') or []:
            if feature_count >= 40:
                break
            key = str(item.get('key') or '').strip()
            if not key or key.startswith('_') or is_internal_feature_data_key(key):
                continue
            if not _is_stable_editor_key(key) or key in seen_keys:
                continue
            label = str(item.get('label') or key).strip()
            value = _format_feature_value_for_display(key, item.get('value'))
            if not value:
                continue
            if not amenities_visible:
                value = ''
            items.append(_entry(
                key=key,
                label=label,
                value=value,
                icon=str(item.get('icon') or 'fa-circle-dot'),
                group='features',
                visibility_key='amenities',
            ))
            seen_keys.add(key)
            feature_count += 1

    return items
