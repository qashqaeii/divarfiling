"""Storyboard slide definitions — تطبیق با دادهٔ موجود."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import CRMProperty


def build_default_storyboard(prop: CRMProperty, studio_payload: Dict[str, Any]) -> Dict[str, Any]:
    images = studio_payload.get('images') or []
    slides: List[Dict[str, Any]] = []

    slides.append({
        'id': 'cover',
        'type': 'cover',
        'title': studio_payload.get('headline') or studio_payload.get('title') or '',
        'subtitle': studio_payload.get('location_line') or '',
        'image_index': 0 if images else None,
    })

    spec_lines = []
    if studio_payload.get('area_label'):
        spec_lines.append(f"متراژ: {studio_payload['area_label']}")
    if studio_payload.get('rooms_label'):
        spec_lines.append(studio_payload['rooms_label'])
    if studio_payload.get('property_type'):
        spec_lines.append(studio_payload['property_type'])
    amenities = studio_payload.get('amenities') or []
    if amenities:
        spec_lines.extend(amenities[:4])

    slides.append({
        'id': 'specs',
        'type': 'specs',
        'lines': spec_lines,
        'image_index': 1 if len(images) > 1 else (0 if images else None),
    })

    price = studio_payload.get('price') or {}
    extra_indices = list(range(min(len(images), 4)))
    slides.append({
        'id': 'gallery_price',
        'type': 'gallery_price',
        'price_label': price.get('label') if price.get('show') else '',
        'image_indices': extra_indices[1:] if len(extra_indices) > 1 else extra_indices,
    })

    slides.append({
        'id': 'contact',
        'type': 'contact',
        'cta': 'برای هماهنگی بازدید پیام دهید',
    })

    return {'slides': slides, 'order': [s['id'] for s in slides]}
