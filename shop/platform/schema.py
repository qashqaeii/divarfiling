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
            # Short crumb label (before colon) — matches features crumbs
            items.append({
                'name': page.seo.h1.split(':')[0].strip(),
                'url': page.url_path,
                'active': True,
            })
        else:
            items[-1]['active'] = True
    return items


def _product_line_title(code: str) -> str:
    return {'crm': 'CRM املاک'}.get(code, code)


def _organization_node() -> dict[str, Any]:
    site_url = get_site_url()
    return {
        '@type': 'Organization',
        'name': get_site_name(),
        'url': site_url,
        'logo': {
            '@type': 'ImageObject',
            'url': f'{site_url}/static/logo.png',
        },
    }


def _free_offer(page_url: str) -> dict[str, Any]:
    """Honest free offer for CRM core — price 0, no fake ratings."""
    return {
        '@type': 'Offer',
        'price': '0',
        'priceCurrency': 'IRR',
        'availability': 'https://schema.org/InStock',
        'url': page_url,
        'description': 'هسته CRM رایگان — بدون لایسنس ربات دیوار',
    }


def schema_webpage(
    page: PageSpec,
    page_url: str,
    *,
    image_url: str | None = None,
) -> str:
    site_name = get_site_name()
    site_url = get_site_url()
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
            'url': site_url,
        },
        'publisher': _organization_node(),
    }
    if page.section == 'features' and page.path:
        schema['isPartOf'] = {
            '@type': 'CollectionPage',
            'name': 'امکانات فایلینگ دیوار',
            'url': f'{site_url}/features/',
        }
    if image_url:
        schema['primaryImageOfPage'] = {
            '@type': 'ImageObject',
            'url': image_url,
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


def schema_software_application_for_page(page: PageSpec, page_url: str) -> str:
    """SoftwareApplication tailored to page role — no fake ratings."""
    site_url = get_site_url()
    crm_url = f'{site_url}/features/crm/'
    creator = _organization_node()

    if page.content_key == 'features_hub':
        schema: dict[str, Any] = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'میزکار فایلینگ دیوار',
            'applicationCategory': 'BusinessApplication',
            'operatingSystem': 'Web, Windows',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'offers': _free_offer(page_url),
            'featureList': [
                'CRM املاک رایگان',
                'فایلینگ و استخراج دیوار',
                'تحلیل بازار',
                'مدیریت تیم آژانس',
            ],
        }
    elif page.content_key == 'crm_product_line':
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'CRM املاک فایلینگ دیوار',
            'alternateName': 'CRM املاک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'CRM',
            'operatingSystem': 'Web',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'offers': _free_offer(page_url),
            'featureList': [
                'مخاطب و پرونده مشتری',
                'یادآور و صف کار امروز',
                'معامله و قیف',
                'تقویم و قالب پیام',
                'تیم آژانس و نقش‌ها',
            ],
        }
    elif page.content_key == 'crm_reminders':
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'یادآور و تقویم CRM املاک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'CRM',
            'operatingSystem': 'Web',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isPartOf': {
                '@type': 'SoftwareApplication',
                'name': 'CRM املاک فایلینگ دیوار',
                'url': crm_url,
            },
            'offers': _free_offer(page_url),
            'featureList': [
                'یادآور زمان‌دار روی پرونده',
                'صف کار امروز',
                'تقویم ماهانه',
            ],
        }
    elif page.content_key == 'solutions_hub':
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'راه‌حل‌های فایلینگ دیوار',
            'applicationCategory': 'BusinessApplication',
            'operatingSystem': 'Web',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'offers': _free_offer(f'{site_url}/solutions/customer-follow-up/'),
        }
    elif page.content_key == 'customer_follow_up':
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'راه‌حل پیگیری مشتری املاک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'CRM',
            'operatingSystem': 'Web',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isRelatedTo': {
                '@type': 'SoftwareApplication',
                'name': 'CRM املاک فایلینگ دیوار',
                'url': crm_url,
            },
            'offers': _free_offer(page_url),
            'featureList': [
                'یادآور تماس',
                'صف کار امروز',
                'تقویم بازدید',
                'قالب پیام پیگیری',
            ],
        }
    else:
        return ''

    return json.dumps(schema, ensure_ascii=False)


def schema_product_for_page(page: PageSpec, page_url: str) -> str:
    """
    Product entity for CRM commercial intent pages.
    Free offer only — no AggregateRating / invented reviews.
    """
    if page.content_key not in ('crm_product_line', 'crm_reminders', 'customer_follow_up'):
        return ''

    site_url = get_site_url()
    if page.content_key == 'crm_product_line':
        name = 'CRM املاک فایلینگ دیوار'
        image = f'{site_url}/static/images/help-crm-dashboard.webp'
        product_url = page_url
    elif page.content_key == 'crm_reminders':
        name = 'یادآور و تقویم CRM املاک'
        image = f'{site_url}/static/images/help-crm-today.webp'
        product_url = page_url
    else:
        name = 'راه‌حل پیگیری مشتری املاک'
        image = f'{site_url}/static/images/help-crm-today.webp'
        product_url = page_url

    schema: dict[str, Any] = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': name,
        'description': page.seo.description,
        'url': product_url,
        'image': image,
        'brand': {
            '@type': 'Brand',
            'name': get_site_name(),
        },
        'category': 'نرم‌افزار CRM املاک',
        'offers': _free_offer(product_url),
    }
    return json.dumps(schema, ensure_ascii=False)


def combine_schemas(*parts: str) -> mark_safe:
    scripts = []
    for part in parts:
        if part:
            scripts.append(f'<script type="application/ld+json">{part}</script>')
    return mark_safe('\n'.join(scripts))
