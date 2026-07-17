"""Registry صفحات — بارگذاری، جستجو و منوی عمومی."""
from __future__ import annotations

from shop.platform.registry import pages_phase1 as pages_phase1_module
from shop.platform.registry import pages_phase2 as pages_phase2_module
from shop.platform.types import PageSpec, validate_page_list

_ALL_PAGES: list[PageSpec] | None = None


def all_pages() -> list[PageSpec]:
    global _ALL_PAGES
    if _ALL_PAGES is None:
        _ALL_PAGES = pages_phase1_module.build_pages() + pages_phase2_module.build_pages()
        validate_page_list(_ALL_PAGES)
    return _ALL_PAGES


def get_page(section: str, path: str) -> PageSpec | None:
    path = (path or '').strip('/')
    for page in all_pages():
        if page.section == section and page.path == path and page.is_published:
            return page
    return None


def published_pages(section: str | None = None) -> list[PageSpec]:
    items = [p for p in all_pages() if p.is_published]
    if section:
        items = [p for p in items if p.section == section]
    return items


def sitemap_entries() -> list[PageSpec]:
    return [p for p in all_pages() if p.is_published]


def get_page_by_content_key(key: str) -> PageSpec | None:
    for page in all_pages():
        if page.content_key == key:
            return page
    return None
