"""استخراج URL inventory — regex چندخطی + Django resolver."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PATH_BLOCK_RE = re.compile(
    r"path\s*\(\s*['\"]([^'\"]+)['\"][\s\S]*?name\s*=\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_INCLUDE_RE = re.compile(
    r"include\s*\(\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)


@dataclass(frozen=True)
class UrlRoute:
    pattern: str
    name: str | None
    line_hint: int
    source: str
    route_kind: str  # user_page | api | internal | include_mount


def _classify_route(pattern: str, name: str | None) -> str:
    p = pattern.strip('/')
    if p.startswith('api/') or (name or '').startswith('api_'):
        return 'api'
    if '<' in pattern or '{' in pattern:
        if p.startswith('api/'):
            return 'api'
        return 'user_page'
    if name and any(x in name for x in ('action', 'webhook', 'bridge')):
        return 'internal'
    return 'user_page'


def collect_workspace_routes(urls_path: Path) -> list[UrlRoute]:
    """سازگاری عقب‌رو — مسیرهای پارس‌شده از فایل اصلی."""
    inv = collect_url_inventory(urls_path)
    return [
        UrlRoute(
            pattern=r['pattern'],
            name=r.get('name'),
            line_hint=r.get('line_hint', 0),
            source=r.get('source', 'workspace/urls.py'),
            route_kind=r.get('route_kind', 'user_page'),
        )
        for r in inv.get('workspace_routes', [])
    ]


def _parse_urls_py_text(text: str, source_label: str) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for m in _PATH_BLOCK_RE.finditer(text):
        pattern = m.group(1)
        name = m.group(2)
        line = text[: m.start()].count('\n') + 1
        routes.append(
            {
                'pattern': pattern,
                'name': name,
                'line_hint': line,
                'source': source_label,
                'route_kind': _classify_route(pattern, name),
                'has_params': '<' in pattern or '{' in pattern,
            }
        )
    includes = [
        {'mount': m.group(1), 'namespace': m.group(2)}
        for m in _INCLUDE_RE.finditer(text)
    ]
    return routes, includes


def _try_resolver_inventory() -> list[dict[str, Any]]:
    try:
        from django.urls import get_resolver

        resolver = get_resolver()
        found: list[dict[str, Any]] = []

        def walk(patterns, prefix: str = ''):
            for p in patterns:
                if hasattr(p, 'url_patterns'):
                    mount = getattr(p, 'pattern', None)
                    mount_str = str(mount) if mount is not None else ''
                    walk(p.url_patterns, prefix + mount_str)
                    continue
                route = str(getattr(p, 'pattern', ''))
                full = prefix + route
                if not full.startswith('workspace/') and '/workspace/' not in full:
                    if not route.startswith('') and 'workspace' not in prefix:
                        continue
                name = p.name
                if name and (
                    full.find('workspace') >= 0
                    or name.startswith('workspace:')
                    or 'crm_' in name
                    or 'dataset' in name
                ):
                    found.append(
                        {
                            'pattern': full,
                            'name': name,
                            'source': 'django.resolver',
                            'route_kind': _classify_route(full, name),
                            'has_params': '<' in full,
                        }
                    )

        walk(resolver.url_patterns)
        return found[:500]
    except Exception:
        return []


def collect_url_inventory(workspace_urls_path: Path) -> dict[str, Any]:
    inventory: dict[str, Any] = {
        'workspace_routes': [],
        'includes': [],
        'resolver_routes': [],
        'summary': {},
    }
    if workspace_urls_path.is_file():
        text = workspace_urls_path.read_text(encoding='utf-8')
        routes, includes = _parse_urls_py_text(text, 'workspace/urls.py')
        inventory['workspace_routes'] = routes
        inventory['includes'] = includes
        django_root = workspace_urls_path.parent.parent
        for inc in includes:
            app_path = inc['mount'].replace('.', '/') + '/urls.py'
            candidate = django_root / app_path
            if candidate.is_file():
                sub_text = candidate.read_text(encoding='utf-8')
                sub_routes, _ = _parse_urls_py_text(sub_text, app_path)
                for r in sub_routes:
                    r['mount_prefix'] = inc['mount']
                inventory['workspace_routes'].extend(sub_routes)

    inventory['resolver_routes'] = _try_resolver_inventory()

    all_routes = inventory['workspace_routes']
    inventory['summary'] = {
        'total_parsed': len(all_routes),
        'user_page': sum(1 for r in all_routes if r.get('route_kind') == 'user_page'),
        'api': sum(1 for r in all_routes if r.get('route_kind') == 'api'),
        'internal': sum(1 for r in all_routes if r.get('route_kind') == 'internal'),
        'with_params': sum(1 for r in all_routes if r.get('has_params')),
    }
    return inventory
