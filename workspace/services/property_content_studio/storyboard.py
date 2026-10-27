"""Storyboard slide definitions — تطبیق با دادهٔ موجود."""
from __future__ import annotations

from typing import Any, Dict, List, Set

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


def _draft_has_reviewable_ai(payload: Dict[str, Any]) -> bool:
    ai = payload.get('ai') or {}
    divar = ai.get('divar') or {}
    if _clip_text(divar.get('body')):
        return True
    for item in divar.get('titles') or []:
        if isinstance(item, dict) and _clip_text(item.get('text')):
            return True
    social = ai.get('social') or {}
    for key in ('whatsapp_full', 'whatsapp_short', 'telegram'):
        if _clip_text(social.get(key)):
            return True
    for item in social.get('captions') or []:
        if isinstance(item, dict) and _clip_text(item.get('text')):
            return True
    return False


def _clip_text(value: Any) -> str:
    return str(value or '').strip()


def merge_storyboard_with_property(
    existing: Dict[str, Any],
    studio_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """فیلدهای خودکار استوری‌برد را با ملک هماهنگ می‌کند؛ CTA و سفارشی‌سازی‌های دستی حفظ می‌شوند."""
    fresh = build_default_storyboard(None, studio_payload)
    fresh_by_id = {s['id']: s for s in fresh.get('slides') or []}
    slides_out: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for raw in existing.get('slides') or []:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get('id') or '').strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        slide = dict(raw)
        ref = fresh_by_id.get(sid)
        if not ref:
            slides_out.append(slide)
            continue
        if sid == 'cover':
            slide['title'] = ref.get('title', '')
            slide['subtitle'] = ref.get('subtitle', '')
            slide['image_index'] = ref.get('image_index')
        elif sid == 'specs':
            slide['lines'] = list(ref.get('lines') or [])
            slide['image_index'] = ref.get('image_index')
        elif sid == 'gallery_price':
            slide['price_label'] = ref.get('price_label', '')
            slide['image_indices'] = list(ref.get('image_indices') or [])
        slides_out.append(slide)

    for sid, ref in fresh_by_id.items():
        if sid not in seen:
            slides_out.append(dict(ref))
            seen.add(sid)

    order = [x for x in (existing.get('order') or []) if x in seen]
    if not order:
        order = fresh.get('order') or [s['id'] for s in slides_out]
    else:
        for sid in fresh.get('order') or []:
            if sid not in order and sid in seen:
                order.append(sid)

    by_id = {s['id']: s for s in slides_out}
    slides_out = [by_id[sid] for sid in order if sid in by_id]
    return {'slides': slides_out, 'order': order}
