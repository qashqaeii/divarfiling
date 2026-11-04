"""Static PCS template manifests for Native Android (derived from pcs-template-scenes.js)."""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.templatetags.static import static

from workspace.services.property_content_studio.constants import (
    OUTPUT_FORMATS,
    POSTER_TEMPLATES,
    STORY_SLIDE_IDENTITIES,
)

logger = logging.getLogger(__name__)

_ACTIVE_TEMPLATE_IDS = frozenset(t['id'] for t in POSTER_TEMPLATES)
_FORMAT_IDS = frozenset(OUTPUT_FORMATS.keys())
_MANIFESTS_ROOT = Path(settings.BASE_DIR) / 'static' / 'workspace' / 'pcs' / 'manifests'


class ManifestNotFoundError(LookupError):
    pass


class ManifestUnavailableError(RuntimeError):
    pass


class ManifestVersionMismatchError(ManifestUnavailableError):
    """File manifest_version differs from index — client must refresh catalog."""
    pass


@lru_cache(maxsize=1)
def _load_index() -> Dict[str, Any]:
    index_path = _MANIFESTS_ROOT / 'index.json'
    if not index_path.is_file():
        raise ManifestUnavailableError('PCS manifest index missing; run scripts/generate_pcs_manifests.mjs')
    try:
        return json.loads(index_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestUnavailableError('PCS manifest index unreadable') from exc


def manifest_version() -> str:
    try:
        return str(_load_index().get('manifest_version') or '')
    except ManifestUnavailableError:
        return ''


def layout_revision() -> str:
    try:
        return str(_load_index().get('layout_revision') or '')
    except ManifestUnavailableError:
        return ''


def manifests_available() -> bool:
    try:
        _load_index()
        return True
    except ManifestUnavailableError:
        return False


def _static_root() -> Path:
    return Path(settings.BASE_DIR) / 'static'


def _cache_bust_static_url(url: str, revision: str) -> str:
    if not url or not revision:
        return url
    sep = '&' if '?' in url else '?'
    return f'{url}{sep}v={revision}'


def absolute_static_url(request, rel_path: str, *, revision: str = '') -> str:
    rel = (rel_path or '').strip().lstrip('/')
    if not rel:
        return ''
    if not (_static_root() / rel).is_file():
        return ''
    url = static(rel)
    if request:
        url = request.build_absolute_uri(url)
    rev = revision or layout_revision()
    return _cache_bust_static_url(url, rev)


def _overlay_rel_for_template(template_id: str) -> str:
    for row in POSTER_TEMPLATES:
        if row['id'] == template_id:
            return str(row.get('overlay') or '').strip()
    return ''


def build_templates_catalog(request) -> List[Dict[str, Any]]:
    """Metadata for all active templates (mobile session)."""
    ver = manifest_version()
    rev = layout_revision()
    out: List[Dict[str, Any]] = []
    for row in POSTER_TEMPLATES:
        tid = row['id']
        overlay_rel = _overlay_rel_for_template(tid)
        entry: Dict[str, Any] = {
            'template_id': tid,
            'label': row.get('label') or '',
            'description': row.get('description') or '',
            'overlay_url': absolute_static_url(request, overlay_rel, revision=rev) if overlay_rel else '',
            'supported_formats': list(_FORMAT_IDS),
            'manifest_version': ver,
        }
        out.append(entry)
    return out


def enrich_property_templates_for_mobile(property_payload: Dict[str, Any], request) -> Dict[str, Any]:
    out = dict(property_payload)
    ver = manifest_version()
    rev = layout_revision()
    templates: List[Dict[str, Any]] = []
    for row in out.get('templates') or []:
        if not isinstance(row, dict):
            continue
        tid = str(row.get('id') or '').strip()
        overlay_rel = str(row.get('overlay') or _overlay_rel_for_template(tid)).strip()
        templates.append({
            **row,
            'template_id': tid,
            'overlay_url': absolute_static_url(request, overlay_rel, revision=rev) if overlay_rel else '',
            'supported_formats': list(_FORMAT_IDS),
            'manifest_version': ver,
        })
    out['templates'] = templates
    out['formats'] = OUTPUT_FORMATS
    out['story_slide_identities'] = STORY_SLIDE_IDENTITIES
    return out


@lru_cache(maxsize=128)
def _load_manifest_file(template_id: str, format_key: str) -> Dict[str, Any]:
    path = _MANIFESTS_ROOT / template_id / f'{format_key}.json'
    if not path.is_file():
        raise ManifestNotFoundError(f'manifest not found: {template_id}/{format_key}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestNotFoundError(f'manifest corrupt: {template_id}/{format_key}') from exc
    if not isinstance(data, dict) or not data.get('scene'):
        raise ManifestNotFoundError(f'manifest invalid: {template_id}/{format_key}')
    return data


def get_template_manifest(
    template_id: str,
    format_key: str,
    request,
) -> Dict[str, Any]:
    tid = (template_id or '').strip()
    fmt = (format_key or 'story').strip()
    if tid not in _ACTIVE_TEMPLATE_IDS:
        raise ManifestNotFoundError('template')
    if fmt not in _FORMAT_IDS:
        raise ManifestNotFoundError('format')
    if not manifests_available():
        raise ManifestUnavailableError('manifests not generated')

    raw = _load_manifest_file(tid, fmt)
    file_version = str(raw.get('manifest_version') or '')
    index_version = manifest_version()
    if index_version and file_version and file_version != index_version:
        raise ManifestVersionMismatchError('manifest version mismatch')
    overlay_rel = _overlay_rel_for_template(tid)
    overlay_url = absolute_static_url(request, overlay_rel, revision=layout_revision()) if overlay_rel else ''

    scene = raw.get('scene')
    if isinstance(scene, dict):
        scene = json.loads(json.dumps(scene))
        for layer in scene.get('layers') or []:
            if not isinstance(layer, dict):
                continue
            ref = layer.get('assetRef')
            if isinstance(ref, str) and ref.startswith('tpl:'):
                layer['assetRef'] = ref
                layer['overlay_url'] = overlay_url

    return {
        'template_id': tid,
        'schema_version': int(raw.get('schema_version') or 2),
        'manifest_version': raw.get('manifest_version') or manifest_version(),
        'layout_revision': raw.get('layout_revision') or layout_revision(),
        'format': fmt,
        'canvas': raw.get('canvas') or OUTPUT_FORMATS.get(fmt, {}),
        'overlay_url': overlay_url,
        'overlay_path': overlay_rel,
        'overlay_asset_ref': raw.get('overlay_asset_ref') or f'tpl:{tid}',
        'background': raw.get('background') or '',
        'scene': scene,
        'dynamic_content': raw.get('dynamic_content') or {},
        'image_slots': raw.get('image_slots') or [],
        'layout_calibration': raw.get('layout_calibration') or {},
    }


def clear_manifest_cache() -> None:
    _load_index.cache_clear()
    _load_manifest_file.cache_clear()
