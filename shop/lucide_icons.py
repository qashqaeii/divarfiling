"""Lucide SVG icon registry — UI icons only; legacy PNG assets remain on disk."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

from shop.decor_icons import ICON_SIZES
from shop.lucide_registry_overrides import REGISTRY_OVERRIDES

# Lucide stroke family: round people, -days/-ring time, chart-* analytics, file/folder uploads.
DECOR_TO_LUCIDE: dict[str, str] = {
    'house': 'layout-dashboard',
    'folder': 'files',
    'users': 'users-round',
    'handshake': 'briefcase',
    'settings': 'settings-2',
    'bell': 'bell',
    'calendar': 'calendar-days',
    'database': 'database',
    'building': 'building-2',
    'tag': 'tag',
    'zap': 'bolt',
    'search': 'search',
    'timer': 'timer',
    'list_todo': 'list-todo',
    'user': 'user-round',
    'trending_up': 'chart-no-axes-combined',
    'filter': 'filter',
    'car': 'car',
    'storage': 'warehouse',
    'elevator': 'arrow-up-down',
    'phone': 'phone-call',
    'external_link': 'external-link',
    'copy': 'copy',
    'file_edit': 'file-pen',
    'calculator': 'calculator',
    'rotate_ccw': 'rotate-ccw',
    'scale': 'scale',
    'percent': 'percent',
    'bar_chart': 'chart-column',
    'layout_grid': 'layout-grid',
    'clipboard_list': 'clipboard-list',
    'coins': 'coins',
    'download': 'download',
    'file_text': 'file-text',
    'layers': 'layers',
    'map_pin': 'map-pin',
    'rocket': 'rocket',
    'ruler': 'ruler',
    'share_2': 'share-2',
    'sparkles': 'sparkles',
    'sticky_note': 'sticky-note',
    'upload': 'cloud-upload',
    'automation': 'workflow',
    'message_template': 'message-square-text',
    'team': 'contact-round',
    'help_center': 'circle-help',
    'api_docs': 'file-code-2',
    'theme_switch': 'sun-moon',
}

EXTRA_TO_LUCIDE: dict[str, str] = {
    'ai': 'bot',
    'ai_wand': 'wand-sparkles',
    'exit': 'log-out',
}

REGISTRY_PATH = Path(__file__).resolve().parent.parent / 'static' / 'icons' / 'lucide-registry.json'

SVG_NS = 'http://www.w3.org/2000/svg'
SVG_VIEWBOX = '0 0 24 24'


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, list[dict[str, Any]]]:
    with REGISTRY_PATH.open(encoding='utf-8') as fh:
        return json.load(fh)


def _icon_exists(lucide_name: str) -> bool:
    return lucide_name in REGISTRY_OVERRIDES or lucide_name in _load_registry()


def _get_icon_nodes(lucide_name: str) -> list[dict[str, Any]]:
    if lucide_name in REGISTRY_OVERRIDES:
        return REGISTRY_OVERRIDES[lucide_name]
    return _load_registry().get(lucide_name, [])


def resolve_lucide_name(name: str) -> str | None:
    """Map a decor/extra icon key to a Lucide registry name."""
    key = (name or '').strip().lower().replace('-', '_')
    lucide = DECOR_TO_LUCIDE.get(key) or EXTRA_TO_LUCIDE.get(key)
    if lucide and _icon_exists(lucide):
        return lucide
    dashed = key.replace('_', '-')
    if _icon_exists(dashed):
        return dashed
    return None


def icon_pixel_size(size: str) -> int:
    return ICON_SIZES.get(size, ICON_SIZES['md'])


def _render_node(node: dict[str, Any]) -> str:
    tag = node.get('tag', 'path')
    attrs = node.get('attrs') or {}
    attr_str = ''.join(
        f' {escape(k)}="{escape(str(v))}"'
        for k, v in attrs.items()
    )
    return f'<{tag}{attr_str} />'


def render_lucide_svg(
    name: str,
    *,
    size: str = 'md',
    class_name: str = '',
    aria_hidden: bool = True,
) -> SafeString | str:
    """Render inline Lucide SVG; sizing/stroke controlled by CSS tokens."""
    lucide_name = resolve_lucide_name(name)
    if not lucide_name:
        return ''

    nodes = _get_icon_nodes(lucide_name)
    inner = ''.join(_render_node(n) for n in nodes)

    svg_class = 'df-lucide-svg'
    if class_name:
        svg_class = f'{svg_class} {class_name}'.strip()

    svg_attrs = {
        'xmlns': SVG_NS,
        'viewBox': SVG_VIEWBOX,
        'class': svg_class,
        'data-lucide': lucide_name,
        'data-icon-size': size,
        'aria-hidden': 'true' if aria_hidden else 'false',
        'role': 'img',
    }

    attr_str = ''.join(
        f' {escape(k)}="{escape(str(v))}"'
        for k, v in svg_attrs.items()
    )
    return mark_safe(f'<svg{attr_str}>{inner}</svg>')
