"""CARTO raster basemap URL helpers — key from settings, never hard-coded."""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_CARTO_STYLE_PATHS = {
    'street': 'rastertiles/voyager',
    'voyager': 'rastertiles/voyager',
    'light': 'light_all',
    'dark': 'dark_all',
}

OSM_TILE_TEMPLATE = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
OSM_TILE_SUBDOMAINS = 'abc'


def get_carto_basemap_api_key() -> str:
    return (getattr(settings, 'CARTO_BASEMAP_API_KEY', '') or '').strip()


def carto_tile_template(style: str) -> str | None:
    """Tile URL template with {s},{z},{x},{y} — None when key or style is missing."""
    key = get_carto_basemap_api_key()
    path = _CARTO_STYLE_PATHS.get(style)
    if not key or not path:
        return None
    return f'https://{{s}}.basemaps.cartocdn.com/{path}/{{z}}/{{x}}/{{y}}.png?key={key}'


def carto_tile_url(
    style: str,
    *,
    sub: str,
    z: int,
    x: int,
    y: int,
) -> str | None:
    tmpl = carto_tile_template(style)
    if not tmpl:
        return None
    return tmpl.format(s=sub, z=z, x=x, y=y)


def warn_if_carto_key_missing() -> None:
    if get_carto_basemap_api_key():
        return
    logger.warning(
        'CARTO_BASEMAP_API_KEY is empty — CARTO raster basemaps fall back to OpenStreetMap '
        'in the browser and in server-side article map renders.'
    )
