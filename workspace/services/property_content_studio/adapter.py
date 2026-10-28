"""Property Data Adapter — دادهٔ امن و آمادهٔ استودیو."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMProperty
from workspace.services.display import transaction_profile
from workspace.services.formatting import format_area, format_toman
from workspace.services.property_content_studio.constants import (
    DEFAULT_VISIBILITY,
    OUTPUT_FORMATS,
    POSTER_TEMPLATES,
)

_DESCRIPTION_EXCERPT_MAX = 900
from workspace.services.property_features import feature_data_rows_for_display
from workspace.services.property_images import normalize_external_image_url


def _rooms_label(rooms: str) -> str:
    text = (rooms or '').strip()
    if not text:
        return ''
    if 'خواب' in text:
        return text
    return f'{text} خواب'


def _amenity_chips(prop: CRMProperty) -> List[str]:
    chips: List[str] = []
    if prop.has_elevator:
        chips.append('آسانسور')
    if prop.has_parking:
        chips.append('پارکینگ')
    if prop.has_storage:
        chips.append('انباری')
    if prop.has_wardrobe:
        chips.append('کمد دیواری')
    extra = (prop.amenities or '').strip()
    if extra:
        for line in extra.splitlines():
            part = line.strip().lstrip('-•·').strip()
            if part and part not in chips and len(chips) < 8:
                chips.append(part[:40])
    return chips


def _price_display(prop: CRMProperty) -> Dict[str, Any]:
    tx = transaction_profile(prop.deal_mode or 'فروش')
    if tx.get('is_rent') or prop.deal_mode in ('رهن و اجاره', 'اجاره'):
        parts = []
        if prop.deposit:
            parts.append(f'ودیعه {format_toman(prop.deposit)}')
        if prop.monthly_rent:
            parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
        return {
            'show': bool(parts),
            'label': ' · '.join(parts),
            'deal_mode': prop.deal_mode or 'اجاره',
        }
    if prop.sale_price:
        return {
            'show': True,
            'label': format_toman(prop.sale_price),
            'deal_mode': prop.deal_mode or 'فروش',
        }
    return {'show': False, 'label': '', 'deal_mode': prop.deal_mode or ''}


def _headline(prop: CRMProperty, *, mask_sensitive: bool = False) -> str:
    title = (prop.title or '').strip()
    if mask_sensitive:
        return title or prop.property_type or 'ملک'
    parts = []
    if prop.area:
        parts.append(f'{format_area(prop.area)}')
    rooms = _rooms_label(prop.rooms or '')
    if rooms:
        parts.append(rooms)
    if parts:
        return '، '.join(parts)
    return title or prop.property_type or 'ملک'


def _floor_label(prop: CRMProperty) -> str:
    fl = prop.floor
    tf = prop.total_floors
    if fl is None and not tf:
        return ''
    if fl is not None and tf:
        return f'طبقه {fl} از {tf}'
    if fl is not None:
        return f'طبقه {fl}'
    return f'{tf} طبقه'


def _build_year_label(prop: CRMProperty) -> str:
    y = prop.build_year
    return f'ساخت {y}' if y else ''


def _studio_detail_chips(prop: CRMProperty, *, max_items: int = 6) -> List[str]:
    chips: List[str] = []
    for row in feature_data_rows_for_display(prop.feature_data, limit=max_items):
        label = str(row.get('label') or '').strip()
        value = str(row.get('value') or '').strip()
        if not value:
            continue
        if label and label not in value and value not in label:
            piece = f'{label}: {value}'
        else:
            piece = value
        if len(piece) > 44:
            piece = piece[:41] + '…'
        if piece not in chips:
            chips.append(piece)
        if len(chips) >= max_items:
            return chips
    if prop.land_area and prop.area and abs(float(prop.land_area) - float(prop.area)) > 0.01:
        chip = f'زمین {format_area(prop.land_area)}'
        if chip not in chips and len(chips) < max_items:
            chips.append(chip)
    if prop.is_vacant and 'تخلیه' not in chips and len(chips) < max_items:
        chips.append('تخلیه')
    if prop.has_two_corner and len(chips) < max_items:
        chips.append('دو نبش')
    if prop.has_two_access and len(chips) < max_items:
        chips.append('دو معبر')
    return chips


def _description_excerpt(prop: CRMProperty, *, mask_sensitive: bool) -> str:
    """متن توضیحی منتشرشدنی — از امکانات/توضیحات فیلد، نه یادداشت CRM."""
    if mask_sensitive:
        return ''
    text = (prop.amenities or '').strip()
    if not text:
        return ''
    if len(text) <= _DESCRIPTION_EXCERPT_MAX:
        return text
    return text[: _DESCRIPTION_EXCERPT_MAX - 1].rstrip() + '…'


def format_divar_facts_outline(studio: Dict[str, Any]) -> str:
    """چک‌لیست مشخصات برای کپی دیوار — فقط از payload استودیو."""
    if not studio:
        return ''
    lines: List[str] = []
    if studio.get('deal_mode'):
        lines.append(f"نوع معامله: {studio['deal_mode']}")
    price = studio.get('price') or {}
    if price.get('show') and price.get('label'):
        lines.append(f"قیمت: {price['label']}")
    if studio.get('property_type'):
        lines.append(f"نوع ملک: {studio['property_type']}")
    if studio.get('area_label'):
        lines.append(f"متراژ: {studio['area_label']}")
    if studio.get('rooms_label'):
        lines.append(f"اتاق: {studio['rooms_label']}")
    if studio.get('floor_label'):
        lines.append(f"طبقه: {studio['floor_label']}")
    if studio.get('build_year_label'):
        lines.append(studio['build_year_label'])
    loc = (studio.get('location_line') or '').strip()
    if loc:
        lines.append(f"موقعیت: {loc}")
    amenities = studio.get('amenities') or []
    if amenities:
        lines.append('امکانات: ' + ' · '.join(str(a) for a in amenities[:8]))
    for chip in (studio.get('detail_chips') or [])[:8]:
        piece = str(chip).strip()
        if piece and piece not in lines:
            lines.append(piece)
    return '\n'.join(lines)


def _location_line(prop: CRMProperty, *, mask_sensitive: bool) -> str:
    if mask_sensitive:
        city = (prop.city or '').strip()
        return city or 'ایران'
    chunks = []
    if prop.neighborhood:
        chunks.append(prop.neighborhood.strip())
    if prop.city and prop.city not in chunks:
        chunks.append(prop.city.strip())
    return ' — '.join(chunks) if chunks else ''


def build_studio_property_payload(
    prop: CRMProperty,
    *,
    mask_sensitive: bool = False,
    public_share_url: str = '',
) -> Dict[str, Any]:
    images: List[str] = []
    for url in prop.images or []:
        normalized = normalize_external_image_url(str(url or ''))
        if normalized and normalized not in images:
            images.append(normalized)

    price = _price_display(prop)
    amenities = _amenity_chips(prop)

    from workspace.services.property_content_studio.feature_catalog import build_editor_feature_catalog

    return {
        'id': prop.pk,
        'title': (prop.title or '').strip(),
        'headline': _headline(prop, mask_sensitive=mask_sensitive),
        'property_type': prop.property_type or '',
        'deal_mode': prop.deal_mode or '',
        'area': prop.area,
        'area_label': format_area(prop.area) if prop.area else '',
        'rooms': (prop.rooms or '').strip(),
        'rooms_label': _rooms_label(prop.rooms or ''),
        'floor': prop.floor,
        'total_floors': prop.total_floors,
        'floor_label': _floor_label(prop),
        'build_year_label': _build_year_label(prop),
        'detail_chips': _studio_detail_chips(prop),
        'neighborhood': (prop.neighborhood or '').strip() if not mask_sensitive else '',
        'city': (prop.city or '').strip(),
        'location_line': _location_line(prop, mask_sensitive=mask_sensitive),
        'price': price,
        'amenities': amenities,
        'images': images,
        'image_count': len(images),
        'cover_image': images[0] if images else '',
        'description_excerpt': _description_excerpt(prop, mask_sensitive=mask_sensitive),
        'file_code': f'#{prop.pk}',
        'public_share_url': (public_share_url or '').strip(),
        'has_parking': bool(prop.has_parking),
        'has_storage': bool(prop.has_storage),
        'has_elevator': bool(prop.has_elevator),
        'templates': list(POSTER_TEMPLATES),
        'formats': OUTPUT_FORMATS,
        'editor_features': build_editor_feature_catalog(prop, DEFAULT_VISIBILITY),
    }


def apply_visibility(
    payload: Dict[str, Any],
    visibility: Dict[str, bool],
) -> Dict[str, Any]:
    """فیلتر فیلدهای نمایشی بر اساس toggle — برای رندر."""
    out = dict(payload)
    if not visibility.get('price', True):
        out['price'] = {'show': False, 'label': '', 'deal_mode': out.get('deal_mode', '')}
    if not visibility.get('neighborhood', True):
        out['neighborhood'] = ''
        out['location_line'] = out.get('city') or ''
    if not visibility.get('area', True):
        out['area_label'] = ''
    if not visibility.get('bedrooms', True):
        out['rooms_label'] = ''
    if not visibility.get('floor', True):
        out['floor'] = None
        out['floor_label'] = ''
        out['build_year_label'] = ''
    if not visibility.get('amenities', True):
        out['amenities'] = []
        out['detail_chips'] = []
    if not visibility.get('file_code', True):
        out['file_code'] = ''
    return out
