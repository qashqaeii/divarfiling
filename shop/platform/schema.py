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
    return {
        'crm': 'CRM املاک',
        'filing': 'فایلینگ',
        'market-intelligence': 'تحلیل بازار',
        'agency': 'مدیریت آژانس',
    }.get(code, code)


def _licensed_offer(page_url: str) -> dict[str, Any]:
    """Honest offer for license-gated product lines — no fake price."""
    return {
        '@type': 'Offer',
        'availability': 'https://schema.org/InStock',
        'url': page_url,
        'description': 'نیاز به لایسنس ربات دیوار — جزئیات در صفحه محصولات',
        'priceCurrency': 'IRR',
    }


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
    elif page.content_key == 'filing_product_line':
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'فایلینگ دیوار',
            'alternateName': 'بانک فایل Dataset',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'Property Dataset',
            'operatingSystem': 'Web, Windows',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'offers': _licensed_offer(page_url),
            'featureList': [
                'آپلود خروجی استخراج',
                'جدول بانک فایل و فیلتر',
                'جزئیات آگهی',
                'نقشه و مقایسه فایل',
            ],
        }
    elif page.content_key == 'fast_property_search':
        filing_url = f'{site_url}/features/filing/'
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'راه‌حل پیدا کردن سریع فایل املاک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'Property Search',
            'operatingSystem': 'Web, Windows',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isRelatedTo': {
                '@type': 'SoftwareApplication',
                'name': 'فایلینگ دیوار',
                'url': filing_url,
            },
            'offers': _licensed_offer(page_url),
            'featureList': [
                'فیلتر پیشرفته Dataset',
                'جستجوی جدولی فایل',
                'نقشه آگهی',
                'مقایسه و کاهش تکراری',
            ],
        }
    elif page.content_key == 'market_intelligence_product_line':
        filing_url = f'{site_url}/features/filing/'
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'تحلیل بازار فایلینگ دیوار',
            'alternateName': 'Market Intelligence',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'Real Estate Market Analytics',
            'operatingSystem': 'Web, Windows',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isRelatedTo': {
                '@type': 'SoftwareApplication',
                'name': 'فایلینگ دیوار',
                'url': filing_url,
            },
            'offers': _licensed_offer(page_url),
            'featureList': [
                'گزارش تحلیل Dataset',
                'نقشه آگهی‌ها',
                'Value Score',
                'مقایسه دوره‌ای فایل‌ها',
            ],
        }
    elif page.content_key == 'property_pricing':
        market_url = f'{site_url}/features/market-intelligence/'
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'راه‌حل قیمت‌گذاری ملک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'Property Pricing',
            'operatingSystem': 'Web, Windows',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isRelatedTo': {
                '@type': 'SoftwareApplication',
                'name': 'تحلیل بازار فایلینگ دیوار',
                'url': market_url,
            },
            'isPartOf': {
                '@type': 'SoftwareApplication',
                'name': 'میزکار فایلینگ دیوار',
                'url': site_url,
            },
            'offers': _licensed_offer(page_url),
            'featureList': [
                'فیلتر فایل‌های مشابه',
                'میانه و بازه قیمت',
                'نقشه و پراکندگی',
                'Value Score نسبی',
            ],
        }
    elif page.content_key == 'agency_product_line':
        crm_url = f'{site_url}/features/crm/'
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'مدیریت آژانس فایلینگ دیوار',
            'alternateName': 'CRM تیمی املاک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'Agency Team CRM',
            'operatingSystem': 'Web',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isPartOf': {
                '@type': 'SoftwareApplication',
                'name': 'میزکار فایلینگ دیوار',
                'url': site_url,
            },
            'isRelatedTo': {
                '@type': 'SoftwareApplication',
                'name': 'CRM املاک فایلینگ دیوار',
                'url': crm_url,
            },
            'offers': _free_offer(page_url),
            'featureList': [
                'نقش‌های مالک، مدیر، منشی و مشاور',
                'صندوق سرنخ و تخصیص',
                'پیام و اطلاعیه تیم',
                'گزارش عملکرد و Agency TV',
            ],
        }
    elif page.content_key == 'agency_management':
        agency_url = f'{site_url}/features/agency/'
        crm_url = f'{site_url}/features/crm/'
        schema = {
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'راه‌حل مدیریت آژانس املاک',
            'applicationCategory': 'BusinessApplication',
            'applicationSubCategory': 'Agency Team Management',
            'operatingSystem': 'Web',
            'description': page.seo.description,
            'url': page_url,
            'inLanguage': 'fa-IR',
            'creator': creator,
            'isPartOf': {
                '@type': 'SoftwareApplication',
                'name': 'میزکار فایلینگ دیوار',
                'url': site_url,
            },
            'isRelatedTo': [
                {
                    '@type': 'SoftwareApplication',
                    'name': 'مدیریت آژانس فایلینگ دیوار',
                    'url': agency_url,
                },
                {
                    '@type': 'SoftwareApplication',
                    'name': 'CRM املاک فایلینگ دیوار',
                    'url': crm_url,
                },
            ],
            'offers': _free_offer(page_url),
            'featureList': [
                'صندوق سرنخ و تخصیص مسئول',
                'پیگیری معوق و گزارش عملکرد',
                'نقش‌ها و کنترل دسترسی',
                'Agency TV به‌عنوان نمایشگر مکمل',
            ],
        }
    else:
        return ''

    return json.dumps(schema, ensure_ascii=False)


def schema_product_for_page(page: PageSpec, page_url: str) -> str:
    """
    Product entity for commercial intent pages.
    CRM/solutions: free offer. Filing: license-gated (no fake price/rating).
    """
    if page.content_key not in (
        'crm_product_line',
        'crm_reminders',
        'customer_follow_up',
        'filing_product_line',
        'fast_property_search',
        'market_intelligence_product_line',
        'property_pricing',
        'agency_product_line',
        'agency_management',
    ):
        return ''

    site_url = get_site_url()
    if page.content_key == 'crm_product_line':
        name = 'CRM املاک فایلینگ دیوار'
        image = f'{site_url}/static/images/help-crm-dashboard.webp'
        product_url = page_url
        offers = _free_offer(product_url)
        category = 'نرم‌افزار CRM املاک'
    elif page.content_key == 'crm_reminders':
        name = 'یادآور و تقویم CRM املاک'
        image = f'{site_url}/static/images/help-crm-today.webp'
        product_url = page_url
        offers = _free_offer(product_url)
        category = 'نرم‌افزار CRM املاک'
    elif page.content_key == 'agency_product_line':
        name = 'مدیریت آژانس فایلینگ دیوار'
        image = f'{site_url}/static/images/help-crm-team.webp'
        product_url = page_url
        offers = _free_offer(product_url)
        category = 'CRM تیمی و مدیریت آژانس املاک'
    elif page.content_key == 'agency_management':
        name = 'راه‌حل مدیریت آژانس املاک'
        image = f'{site_url}/static/images/help-crm-team.webp'
        product_url = page_url
        offers = _free_offer(product_url)
        category = 'مدیریت تیم و دفتر املاک'
    elif page.content_key == 'filing_product_line':
        name = 'فایلینگ دیوار'
        image = f'{site_url}/static/images/help-dataset-table.webp'
        product_url = page_url
        offers = _licensed_offer(product_url)
        category = 'بانک فایل و Dataset املاک'
    elif page.content_key == 'fast_property_search':
        name = 'راه‌حل پیدا کردن سریع فایل املاک'
        image = f'{site_url}/static/images/help-dataset-table.webp'
        product_url = page_url
        offers = _licensed_offer(product_url)
        category = 'جستجوی فایل و Dataset املاک'
    elif page.content_key == 'market_intelligence_product_line':
        name = 'تحلیل بازار فایلینگ دیوار'
        image = f'{site_url}/static/images/help-analyze-dashboard.webp'
        product_url = page_url
        offers = _licensed_offer(product_url)
        category = 'تحلیل بازار و قیمت‌گذاری املاک'
    elif page.content_key == 'property_pricing':
        name = 'راه‌حل قیمت‌گذاری ملک'
        image = f'{site_url}/static/images/help-analyze-dashboard.webp'
        product_url = page_url
        offers = _licensed_offer(product_url)
        category = 'قیمت‌گذاری و تحلیل فایل مشابه'
    else:
        name = 'راه‌حل پیگیری مشتری املاک'
        image = f'{site_url}/static/images/help-crm-today.webp'
        product_url = page_url
        offers = _free_offer(product_url)
        category = 'نرم‌افزار CRM املاک'

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
        'category': category,
        'offers': offers,
    }
    return json.dumps(schema, ensure_ascii=False)


def combine_schemas(*parts: str) -> mark_safe:
    scripts = []
    for part in parts:
        if part:
            scripts.append(f'<script type="application/ld+json">{part}</script>')
    return mark_safe('\n'.join(scripts))
