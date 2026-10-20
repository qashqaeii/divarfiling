"""استخراج مسیرهای workspace از urls.py — read-only."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PATH_RE = re.compile(
    r"path\(\s*['\"]([^'\"]+)['\"].*?name=['\"]([^'\"]+)['\"]",
    re.DOTALL,
)
_PATH_SIMPLE_RE = re.compile(r"path\(\s*['\"]([^'\"]+)['\"]")

_INCLUDE_RE = re.compile(r"include\(\('([^']+)'")


@dataclass(frozen=True)
class UrlRoute:
    pattern: str
    name: str | None
    line_hint: int


def collect_workspace_routes(urls_path: Path) -> list[UrlRoute]:
    if not urls_path.is_file():
        return []
    text = urls_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    routes: list[UrlRoute] = []
    for i, line in enumerate(lines, start=1):
        if 'path(' not in line:
            continue
        m = _PATH_RE.search(line)
        if m:
            routes.append(UrlRoute(pattern=m.group(1), name=m.group(2), line_hint=i))
            continue
        m2 = _PATH_SIMPLE_RE.search(line)
        if m2:
            routes.append(UrlRoute(pattern=m2.group(1), name=None, line_hint=i))
    return routes


def workspace_url_prefixes(routes: list[UrlRoute]) -> dict[str, list[str]]:
    """گروه‌بندی اولین سگمنت مسیر (بدون پارامتر)."""
    buckets: dict[str, list[str]] = {}
    for r in routes:
        seg = r.pattern.strip('/').split('/')[0] if r.pattern.strip('/') else 'root'
        buckets.setdefault(seg, []).append(r.pattern)
    return buckets
