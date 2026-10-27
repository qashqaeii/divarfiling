"""Property Data Adapter — دادهٔ امن و آمادهٔ استودیو."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMProperty
from workspace.services.display import transaction_profile
from workspace.services.formatting import format_area, format_toman
from workspace.services.property_content_studio.constants import OUTPUT_FORMATS, POSTER_TEMPLATES
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


def _headline(prop: CRMProperty) -> str:
    parts = []
    if prop.area:
        parts.append(f'{format_area(prop.area)}')
    rooms = _rooms_label(prop.rooms or '')
    if rooms:
        parts.append(rooms)
    title = (prop.title or '').strip()
    if parts:
        return '، '.join(parts)
    return title or prop.property_type or 'ملک'


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

    return {
        'id': prop.pk,
        'title': (prop.title or '').strip(),
        'headline': _headline(prop),
        'property_type': prop.property_type or '',
        'deal_mode': prop.deal_mode or '',
        'area': prop.area,
        'area_label': format_area(prop.area) if prop.area else '',
        'rooms': (prop.rooms or '').strip(),
        'rooms_label': _rooms_label(prop.rooms or ''),
        'floor': prop.floor,
        'total_floors': prop.total_floors,
        'neighborhood': (prop.neighborhood or '').strip() if not mask_sensitive else '',
        'city': (prop.city or '').strip(),
        'location_line': _location_line(prop, mask_sensitive=mask_sensitive),
        'price': price,
        'amenities': amenities,
        'images': images,
        'image_count': len(images),
        'cover_image': images[0] if images else '',
        'description_excerpt': _public_description(prop),
        'file_code': f'#{prop.pk}',
        'public_share_url': (public_share_url or '').strip(),
        'has_parking': bool(prop.has_parking),
        'has_storage': bool(prop.has_storage),
        'has_elevator': bool(prop.has_elevator),
        'templates': list(POSTER_TEMPLATES),
        'formats': OUTPUT_FORMATS,
    }


def _public_description(prop: CRMProperty) -> str:
    """متن قابل استفاده برای AI — بدون یادداشت داخلی CRM."""
    notes = (prop.notes or '').strip()
    if len(notes) > 600:
        return notes[:600] + '…'
    return notes


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
    if not visibility.get('amenities', True):
        out['amenities'] = []
    if not visibility.get('file_code', True):
        out['file_code'] = ''
    return out
