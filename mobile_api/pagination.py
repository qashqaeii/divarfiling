"""ابزارهای صفحه‌بندی امن API موبایل."""
from __future__ import annotations


def clamp_page(value, default: int = 1) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, parsed)


def clamp_page_size(value, default: int = 50, maximum: int = 100) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))
