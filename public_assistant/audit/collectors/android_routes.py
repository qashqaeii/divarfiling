"""استخراج مسیرهای Navigation اندروید از کد — بدون Gradle."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ROUTE_CONST_RE = re.compile(r'const val (\w+) = "([^"]+)"')


@dataclass(frozen=True)
class AndroidRoute:
    const_name: str
    route: str


def collect_android_routes(nav_host_path: Path) -> tuple[list[AndroidRoute], str]:
    """
    برمی‌گرداند: (routes, availability_note)
    """
    if not nav_host_path.is_file():
        return [], 'android_repo_not_found'
    text = nav_host_path.read_text(encoding='utf-8')
    # فقط بلوک object Routes
    start = text.find('object Routes {')
    if start < 0:
        return [], 'routes_block_not_found'
    end = text.find('\n}\n', start)
    block = text[start:end] if end > start else text[start:]
    routes: list[AndroidRoute] = []
    for m in _ROUTE_CONST_RE.finditer(block):
        routes.append(AndroidRoute(const_name=m.group(1), route=m.group(2)))
    return routes, 'ok'
