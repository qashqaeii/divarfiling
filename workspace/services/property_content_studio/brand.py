"""Brand Settings — پروفایل کاربر + override پیش‌نویس."""
from __future__ import annotations

import re
from typing import Any, Dict

from django.conf import settings

from workspace.models import WorkspaceSettings
from workspace.services.property_content_studio.constants import DEFAULT_BRAND_COLORS, DEFAULT_VISIBILITY
from workspace.services.public_share_common import get_or_create_settings, profile_consultant_defaults


_HEX_COLOR_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def _normalize_hex(color: str, fallback: str) -> str:
    c = (color or '').strip()
    if _HEX_COLOR_RE.match(c):
        if len(c) == 4:
            return '#' + ''.join(ch * 2 for ch in c[1:])
        return c.lower()
    return fallback


def _logo_url(ws: WorkspaceSettings) -> str:
    if ws.agency_logo:
        try:
            return ws.agency_logo.url
        except (ValueError, AttributeError):
            return ''
    return ''


def default_brand_from_user(user) -> Dict[str, Any]:
    ws = get_or_create_settings(user)
    defaults = dict(ws.content_studio_defaults or {})
    name, phone = profile_consultant_defaults(user)
    agency = (ws.agency_name or '').strip()
    socials = dict(ws.social_links or {})
    instagram = (socials.get('instagram') or socials.get('instagram_handle') or '').strip()

    colors = dict(DEFAULT_BRAND_COLORS)
    stored_colors = defaults.get('colors') if isinstance(defaults.get('colors'), dict) else {}
    colors['primary'] = _normalize_hex(stored_colors.get('primary'), colors['primary'])
    colors['accent'] = _normalize_hex(stored_colors.get('accent'), colors['accent'])

    visibility = dict(DEFAULT_VISIBILITY)
    stored_vis = defaults.get('visibility') if isinstance(defaults.get('visibility'), dict) else {}
    for key in visibility:
        if key in stored_vis:
            visibility[key] = bool(stored_vis[key])

    return {
        'brand_name': (defaults.get('brand_name') or agency or name or '').strip()[:200],
        'consultant_name': (defaults.get('consultant_name') or name or '').strip()[:200],
        'contact_phone': (defaults.get('contact_phone') or phone or '').strip()[:20],
        'instagram': (defaults.get('instagram') or instagram or '').strip()[:120],
        'logo_url': (defaults.get('logo_url') or _logo_url(ws) or '').strip()[:500],
        'colors': colors,
        'visibility': visibility,
    }


def merge_brand(base: Dict[str, Any], override: Dict[str, Any] | None) -> Dict[str, Any]:
    if not override:
        return dict(base)
    merged = dict(base)
    for key in ('brand_name', 'consultant_name', 'contact_phone', 'instagram', 'logo_url'):
        if override.get(key):
            merged[key] = str(override[key]).strip()[:500]
    if isinstance(override.get('colors'), dict):
        colors = dict(merged.get('colors') or {})
        for ck in ('primary', 'accent', 'text_on_primary'):
            if override['colors'].get(ck):
                colors[ck] = _normalize_hex(override['colors'][ck], colors.get(ck, '#7c3aed'))
        merged['colors'] = colors
    if isinstance(override.get('visibility'), dict):
        vis = dict(merged.get('visibility') or {})
        for k, v in override['visibility'].items():
            if k in vis:
                vis[k] = bool(v)
        merged['visibility'] = vis
    return merged


def save_user_brand_defaults(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    ws = get_or_create_settings(user)
    current = dict(ws.content_studio_defaults or {})
    for key in ('brand_name', 'consultant_name', 'contact_phone', 'instagram'):
        if key in payload:
            current[key] = str(payload.get(key) or '').strip()[:500]
    if 'colors' in payload and isinstance(payload['colors'], dict):
        colors = dict(current.get('colors') or {})
        for ck in ('primary', 'accent'):
            if payload['colors'].get(ck):
                colors[ck] = _normalize_hex(payload['colors'][ck], colors.get(ck, '#7c3aed'))
        current['colors'] = colors
    if 'visibility' in payload and isinstance(payload['visibility'], dict):
        vis = dict(current.get('visibility') or DEFAULT_VISIBILITY)
        for k in vis:
            if k in payload['visibility']:
                vis[k] = bool(payload['visibility'][k])
        current['visibility'] = vis
    ws.content_studio_defaults = current
    ws.save(update_fields=['content_studio_defaults', 'updated_at'])
    return default_brand_from_user(user)
