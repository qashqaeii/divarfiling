"""Masked export of studio payloads for mobile API (does not mutate stored drafts)."""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Set

from workspace.models import CRMProperty
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.constants import DEFAULT_VISIBILITY
from workspace.services.property_content_studio.feature_catalog import build_editor_feature_catalog

_CONFIDENTIAL_VISIBILITY = {
    **DEFAULT_VISIBILITY,
    'neighborhood': False,
    'file_code': False,
}

_SENSITIVE_BINDING_FIELDS = frozenset({
    'location_line',
    'neighborhood',
    'file_code',
})

_STRAY_DOT_SEP = re.compile(r'(?:\s·\s)+$|^(?:\s·\s)+')


def collect_redact_fragments(prop: CRMProperty) -> List[str]:
    """Substrings derived from confidential property fields (not user detached copy).

    Policy: redact draft text that contains these fragments; preserve detached text
    that does not echo neighborhood, address, or full location_line.
    """
    fragments: Set[str] = set()
    if prop.neighborhood:
        fragments.add(str(prop.neighborhood).strip())
    if prop.address:
        fragments.add(str(prop.address).strip())
    full = build_studio_property_payload(prop, mask_sensitive=False)
    masked = build_studio_property_payload(prop, mask_sensitive=True)
    for key in ('neighborhood', 'location_line', 'file_code'):
        a = str(full.get(key) or '').strip()
        b = str(masked.get(key) or '').strip()
        if a and a != b:
            fragments.add(a)
    loc_full = str(full.get('location_line') or '').strip()
    if loc_full:
        fragments.add(loc_full)
    raw_title = (prop.title or '').strip()
    if raw_title and prop.neighborhood and prop.neighborhood in raw_title:
        fragments.add(raw_title)
    unmasked_headline = str(full.get('headline') or '').strip()
    masked_headline = str(masked.get('headline') or '').strip()
    if unmasked_headline and unmasked_headline != masked_headline:
        fragments.add(unmasked_headline)
    fragments.add(f'#{prop.pk}')
    return sorted((f for f in fragments if len(f) >= 2), key=len, reverse=True)


def _text_leaks_sensitive(text: Any, fragments: List[str]) -> bool:
    if not text or not fragments:
        return False
    t = str(text)
    for frag in fragments:
        if frag and frag in t:
            return True
    return False


def _clean_stray_separators(text: str) -> str:
    if not text:
        return ''
    t = _STRAY_DOT_SEP.sub('', text.strip())
    t = t.replace('  ·  ·', ' · ').strip()
    while t.endswith('·') or t.startswith('·'):
        t = t.strip('·').strip()
    return t


def _redact_layer_text(layer: Dict[str, Any], fragments: List[str]) -> None:
    binding = layer.get('binding')
    if isinstance(binding, dict):
        field = binding.get('field') or ''
        source = binding.get('source') or ''
        mode = binding.get('mode') or 'linked'
        if source == 'property' and field in _SENSITIVE_BINDING_FIELDS:
            layer['text'] = ''
            return
        if mode == 'linked':
            layer['text'] = ''
            return
        if mode in ('override', 'detached'):
            text = str(layer.get('text') or '')
            if _text_leaks_sensitive(text, fragments):
                layer['text'] = ''
            else:
                layer['text'] = _clean_stray_separators(text)
            return
    elif layer.get('text') is not None:
        if _text_leaks_sensitive(layer.get('text'), fragments):
            layer['text'] = ''
        else:
            layer['text'] = _clean_stray_separators(str(layer.get('text') or ''))


def _redact_storyboard(storyboard: Any, fragments: List[str]) -> None:
    if not isinstance(storyboard, dict):
        return
    slides = storyboard.get('slides')
    if not isinstance(slides, list):
        return
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        for key in ('title', 'subtitle', 'cta', 'price_label'):
            if key in slide and _text_leaks_sensitive(slide.get(key), fragments):
                slide[key] = ''
        if isinstance(slide.get('lines'), list):
            slide['lines'] = [
                '' if _text_leaks_sensitive(line, fragments) else line
                for line in slide['lines']
            ]


def _redact_ai_section(ai: Any, fragments: List[str]) -> None:
    if not isinstance(ai, dict):
        return
    divar = ai.get('divar')
    if isinstance(divar, dict):
        if _text_leaks_sensitive(divar.get('body'), fragments):
            divar['body'] = ''
        titles = divar.get('titles')
        if isinstance(titles, list):
            divar['titles'] = [
                t if not _text_leaks_sensitive(
                    t.get('text') if isinstance(t, dict) else t,
                    fragments,
                ) else {'text': '', 'style': t.get('style', '') if isinstance(t, dict) else ''}
                for t in titles
            ]
    social = ai.get('social')
    if isinstance(social, dict):
        for key in ('whatsapp_short', 'whatsapp_full', 'telegram'):
            if key in social and _text_leaks_sensitive(social.get(key), fragments):
                social[key] = ''
        if isinstance(social.get('captions'), list):
            social['captions'] = [
                c if not _text_leaks_sensitive(
                    c.get('text') if isinstance(c, dict) else c,
                    fragments,
                ) else {'text': '', 'style': c.get('style', '') if isinstance(c, dict) else ''}
                for c in social['captions']
            ]


def export_draft_payload_for_access(
    payload: Dict[str, Any],
    *,
    mask_sensitive: bool,
    prop: Optional[CRMProperty] = None,
) -> Dict[str, Any]:
    if not mask_sensitive or not payload:
        return payload
    out = copy.deepcopy(payload)
    fragments = collect_redact_fragments(prop) if prop else []

    posters = out.get('posters')
    if isinstance(posters, dict):
        for poster_conf in posters.values():
            if not isinstance(poster_conf, dict):
                continue
            scene = poster_conf.get('scene')
            if not isinstance(scene, dict):
                continue
            for layer in scene.get('layers') or []:
                if isinstance(layer, dict):
                    _redact_layer_text(layer, fragments)
            if isinstance(poster_conf.get('headline'), str) and _text_leaks_sensitive(
                poster_conf['headline'], fragments,
            ):
                poster_conf['headline'] = ''

    _redact_storyboard(out.get('storyboard'), fragments)
    _redact_ai_section(out.get('ai'), fragments)
    return out


def enrich_property_payload_for_mobile_export(
    payload: Dict[str, Any],
    prop: CRMProperty,
    *,
    mask_sensitive: bool,
) -> Dict[str, Any]:
    """Property block for mobile studio APIs — respects confidential share."""
    out = dict(payload)
    if mask_sensitive:
        out['file_code'] = ''
        out['editor_features'] = build_editor_feature_catalog(prop, _CONFIDENTIAL_VISIBILITY)
        for row in out.get('editor_features') or []:
            if not isinstance(row, dict):
                continue
            key = row.get('key') or ''
            if key in _SENSITIVE_BINDING_FIELDS or key == 'file_code':
                row['value'] = ''
    return out


def export_mobile_studio_data(
    data: Dict[str, Any],
    prop: CRMProperty,
    *,
    mask_sensitive: bool,
) -> Dict[str, Any]:
    if not mask_sensitive:
        return data
    out = copy.deepcopy(data)
    if out.get('property'):
        out['property'] = enrich_property_payload_for_mobile_export(
            out['property'],
            prop,
            mask_sensitive=True,
        )
    if out.get('draft'):
        out['draft'] = export_draft_payload_for_access(
            out['draft'],
            mask_sensitive=True,
            prop=prop,
        )
    return out
