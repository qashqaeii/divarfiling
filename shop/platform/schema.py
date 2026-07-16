"""Schema.org helpers for platform pages."""
from __future__ import annotations

import json
from typing import Any

from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from shop.platform.types import PageSpec
from shop.templatetags.seo_tags import get_site_name, get_site_url


def build_breadcrumbs(page: PageSpec) -> list[dict[str, str]]:
    items = [{'name': 'خانه', 'url': '/'}]
    if page.section == 'features':
        items.append({'name': 'امکانات', 'url': '/features/'})
        if page.variant == 'product_line':
            items.append({'name': page.seo.h1.split(':')[0].strip(), 'url': page.url_path, 'active': True})
        elif page.variant == 'feature':
            line_title = _product_line_title(page.product_line)
            items.append({'name': line_title, 'url': f'/features/{page.product_line}/'})
            items.append({'name': page.seo.h1.split(':')[0].strip(), 'url': page.url_path, 'active': True})
        else:
            items[-1]['active'] = True
    elif page.section == 'solutions':
        items.append({'name': 'راه‌حل‌ها', 'url': '/solutions/'})
        if page.path:
            items.append({'name': page.seo.h1, 'url': page.url_path, 'active': True})
        else:
            items[-1]['active'] = True
    return items


def _product_line_title(code: str) -> str:
    return {'crm': 'CRM املاک'}.get(code, code)


def schema_webpage(page: PageSpec, page_url: str) -> str:
    site_name = get_site_name()
    schema: dict[str, Any] = {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'name': page.seo.title,
        'description': page.seo.description,
        'url': page_url,
        'inLanguage': 'fa-IR',
        'isPartOf': {
            '@type': 'WebSite',
            'name': site_name,
            'url': get_site_url(),
        },
    }
    if page.section == 'features' and page.path:
        schema['isPartOf'] = {
            '@type': 'CollectionPage',
            'name': 'امکانات فایلینگ دیوار',
            'url': f'{get_site_url()}/features/',
        }
    return json.dumps(schema, ensure_ascii=False)


def schema_faq_from_pairs(pairs: list[dict[str, str]], page: PageSpec, page_url: str) -> str:
    if not pairs:
        return ''
    schema = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'name': page.seo.title,
        'description': page.seo.description,
        'url': page_url,
        'inLanguage': 'fa-IR',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': p['q'],
                'acceptedAnswer': {'@type': 'Answer', 'text': strip_tags(p['a'])},
            }
            for p in pairs
        ],
    }
    return json.dumps(schema, ensure_ascii=False)


def combine_schemas(*parts: str) -> mark_safe:
    scripts = []
    for part in parts:
        if part:
            scripts.append(f'<script type="application/ld+json">{part}</script>')
    return mark_safe('\n'.join(scripts))
