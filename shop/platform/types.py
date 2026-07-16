"""انواع داده و اعتبارسنجی Registry صفحات پلتفرم."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PageVariant = Literal['hub', 'product_line', 'feature', 'solution']
PublishStatus = Literal['published', 'draft', 'internal']
Marketability = Literal['marketable', 'section_only', 'internal']

REQUIRED_VARIANTS = frozenset({'hub', 'product_line', 'feature', 'solution'})


@dataclass(frozen=True)
class RelatedLink:
    label: str
    url_name: str
    url_kwargs: dict[str, str] = field(default_factory=dict)
    anchor_hint: str = ''


@dataclass(frozen=True)
class PageSEO:
    title: str
    description: str
    keywords: str
    og_title: str = ''
    og_description: str = ''
    h1: str = ''


@dataclass(frozen=True)
class PageSpec:
    """مشخصات یک صفحه بازاریابی — فقط published در URL و Sitemap."""

    section: Literal['features', 'solutions']
    path: str  # '' for hub; 'crm' for product line; 'crm/reminders' for feature
    variant: PageVariant
    status: PublishStatus
    marketability: Marketability
    seo: PageSEO
    accent: str = 'violet'
    icon: str = 'fa-layer-group'
    decor_icon: str = 'layers'
    product_line: str = ''  # e.g. crm
    parent_path: str = ''
    funnel_role: str = ''
    intent: str = ''
    primary_keyword: str = ''
    content_key: str = ''
    related_features: tuple[str, ...] = ()
    related_solutions: tuple[str, ...] = ()
    related_articles: tuple[str, ...] = ()  # blog slugs
    related_seo_landings: tuple[str, ...] = ()  # seo landing slugs
    sitemap_priority: float = 0.75
    sitemap_changefreq: str = 'monthly'

    @property
    def is_published(self) -> bool:
        return self.status == 'published'

    @property
    def url_path(self) -> str:
        base = f'/{self.section}/'
        if not self.path:
            return base
        return f'{base}{self.path}/'

    def validate(self) -> None:
        if self.variant not in REQUIRED_VARIANTS:
            raise ValueError(f'invalid variant: {self.variant}')
        if self.section not in ('features', 'solutions'):
            raise ValueError(f'invalid section: {self.section}')
        if self.status not in ('published', 'draft', 'internal'):
            raise ValueError(f'invalid status: {self.status}')
        if not self.seo.title or not self.seo.description:
            raise ValueError(f'missing SEO for {self.section}/{self.path}')
        if self.variant == 'feature' and not self.product_line:
            raise ValueError(f'feature page needs product_line: {self.path}')
        if self.variant == 'product_line' and self.path != self.product_line:
            raise ValueError(f'product_line path mismatch: {self.path}')


def validate_page_list(pages: list[PageSpec]) -> None:
    seen: set[tuple[str, str]] = set()
    for page in pages:
        page.validate()
        key = (page.section, page.path)
        if key in seen:
            raise ValueError(f'duplicate page: {page.section}/{page.path}')
        seen.add(key)
