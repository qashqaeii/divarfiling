"""Navigation context for platform pages — journey, hub back, location."""
from __future__ import annotations

from typing import Any

from django.urls import reverse

from shop.platform.types import PageSpec


def build_platform_nav(page: PageSpec) -> dict[str, Any]:
    """Where-am-I strip + canonical journey for Phase D."""
    site_trail = _trail_for_page(page)
    hub_back = _hub_back(page)
    journey = _journey_for_page(page)
    crm_vs_landing = None
    if page.content_key in ('crm_product_line', 'crm_reminders'):
        crm_vs_landing = {
            'product_label': 'جزئیات محصول CRM',
            'landing_label': 'معرفی تجاری CRM',
            'landing_url_name': 'seo_landing_real_estate_crm',
            'note': (
                'این صفحه جزئیات محصول و گردش کار است. '
                'برای معرفی کوتاه و جذب ثبت‌نام، لندینگ تجاری را ببینید.'
            ),
        }
    elif page.content_key == 'customer_follow_up':
        crm_vs_landing = {
            'product_label': 'راه‌حل عملی پیگیری',
            'landing_label': 'معرفی تجاری CRM',
            'landing_url_name': 'seo_landing_real_estate_crm',
            'note': (
                'اینجا از مشکل فراموشی تماس شروع می‌کنیم. '
                'اگر فقط معرفی کلی CRM می‌خواهید، لندینگ تجاری مناسب‌تر است.'
            ),
        }

    section_label = 'امکانات' if page.section == 'features' else 'راه‌حل‌ها'
    return {
        'section': page.section,
        'section_label': section_label,
        'location_label': _location_label(page),
        'trail': site_trail,
        'hub_back': hub_back,
        'journey': journey,
        'crm_vs_landing': crm_vs_landing,
        'content_key': page.content_key,
    }


def _location_label(page: PageSpec) -> str:
    labels = {
        'features_hub': 'نقشه امکانات',
        'crm_product_line': 'خط محصول CRM',
        'crm_reminders': 'یادآور CRM',
        'filing_product_line': 'خط محصول فایلینگ',
        'market_intelligence_product_line': 'خط محصول تحلیل بازار',
        'agency_product_line': 'خط محصول مدیریت آژانس',
        'agency_management': 'راه‌حل مدیریت آژانس',
        'extraction_product_line': 'خط محصول ربات استخراج',
        'property_pricing': 'راه‌حل قیمت‌گذاری ملک',
        'fast_property_search': 'راه‌حل پیدا کردن سریع فایل',
        'solutions_hub': 'نقشه راه‌حل‌ها',
        'customer_follow_up': 'راه‌حل پیگیری مشتری',
    }
    return labels.get(page.content_key, page.seo.h1.split(':')[0].strip())


def _hub_back(page: PageSpec) -> dict[str, Any] | None:
    if page.variant == 'hub':
        return None
    if page.content_key == 'crm_reminders':
        return {
            'primary': {
                'label': 'بازگشت به CRM',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'crm'},
            },
            'secondary': {
                'label': 'همه امکانات',
                'url_name': 'platform_features_hub',
                'kwargs': {},
            },
        }
    if page.section == 'features':
        return {
            'primary': {
                'label': 'بازگشت به امکانات',
                'url_name': 'platform_features_hub',
                'kwargs': {},
            },
        }
    return {
        'primary': {
            'label': 'بازگشت به راه‌حل‌ها',
            'url_name': 'platform_solutions_hub',
            'kwargs': {},
        },
    }


def _trail_for_page(page: PageSpec) -> list[dict[str, Any]]:
    """Short chips under breadcrumb — current marked."""
    if page.section == 'features':
        items = [
            {'label': 'امکانات', 'url_name': 'platform_features_hub', 'kwargs': {}, 'current': page.variant == 'hub'},
        ]
        if page.content_key == 'filing_product_line':
            items.append({
                'label': 'فایلینگ',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'filing'},
                'current': True,
            })
            return items
        if page.content_key == 'market_intelligence_product_line':
            items.append({
                'label': 'تحلیل بازار',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'market-intelligence'},
                'current': True,
            })
            return items
        if page.content_key == 'agency_product_line':
            items.append({
                'label': 'CRM',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'crm'},
                'current': False,
            })
            items.append({
                'label': 'مدیریت آژانس',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'agency'},
                'current': True,
            })
            return items
        if page.content_key == 'extraction_product_line':
            items.append({
                'label': 'فایلینگ',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'filing'},
                'current': False,
            })
            items.append({
                'label': 'ربات استخراج',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'extraction'},
                'current': True,
            })
            return items
        if page.path:
            items.append({
                'label': 'CRM',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'crm'},
                'current': page.content_key == 'crm_product_line',
            })
        if page.content_key == 'crm_reminders':
            items.append({
                'label': 'یادآور',
                'url_name': 'platform_features_page',
                'kwargs': {'slug_path': 'crm/reminders'},
                'current': True,
            })
        return items

    items = [
        {'label': 'راه‌حل‌ها', 'url_name': 'platform_solutions_hub', 'kwargs': {}, 'current': page.variant == 'hub'},
    ]
    if page.content_key == 'customer_follow_up':
        items.append({
            'label': 'پیگیری مشتری',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'customer-follow-up'},
            'current': True,
        })
    elif page.content_key == 'fast_property_search':
        items.append({
            'label': 'پیدا کردن سریع فایل',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'fast-property-search'},
            'current': True,
        })
    elif page.content_key == 'property_pricing':
        items.append({
            'label': 'قیمت‌گذاری ملک',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'property-pricing'},
            'current': True,
        })
    elif page.content_key == 'agency_management':
        items.append({
            'label': 'مدیریت آژانس',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'agency-management'},
            'current': True,
        })
    return items


def _journey_for_page(page: PageSpec) -> list[dict[str, Any]]:
    """Canonical funnel — CRM, Filing, Market, Agency, or Extraction path by page family."""
    if page.content_key in ('filing_product_line', 'fast_property_search'):
        return _filing_journey(page.content_key)
    if page.content_key in ('market_intelligence_product_line', 'property_pricing'):
        return _market_journey(page.content_key)
    if page.content_key in ('agency_product_line', 'agency_management'):
        return _agency_journey(page.content_key)
    if page.content_key == 'extraction_product_line':
        return _extraction_journey(page.content_key)
    return _crm_journey(page.content_key)


def _crm_journey(content_key: str) -> list[dict[str, Any]]:
    steps = [
        {
            'id': 'crm',
            'label': 'CRM',
            'hint': 'میزکار مشتری',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'crm'},
        },
        {
            'id': 'reminders',
            'label': 'یادآور',
            'hint': 'صف امروز',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'crm/reminders'},
        },
        {
            'id': 'follow_up',
            'label': 'پیگیری',
            'hint': 'راه‌حل عملی',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'customer-follow-up'},
        },
        {
            'id': 'start',
            'label': 'شروع',
            'hint': 'ثبت‌نام رایگان',
            'url_name': 'register',
            'auth_url_name': 'workspace:home',
            'kwargs': {},
        },
    ]
    current_id = {
        'crm_product_line': 'crm',
        'crm_reminders': 'reminders',
        'customer_follow_up': 'follow_up',
        'features_hub': None,
        'solutions_hub': None,
    }.get(content_key)
    return _annotate_journey(steps, current_id)


def _filing_journey(content_key: str) -> list[dict[str, Any]]:
    steps = [
        {
            'id': 'filing',
            'label': 'فایلینگ',
            'hint': 'بانک Dataset',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'filing'},
        },
        {
            'id': 'fast_search',
            'label': 'جستجوی سریع',
            'hint': 'راه‌حل عملی',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'fast-property-search'},
        },
        {
            'id': 'robot',
            'label': 'استخراج',
            'hint': 'ربات دسکتاپ',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'extraction'},
        },
        {
            'id': 'start',
            'label': 'شروع',
            'hint': 'ثبت‌نام رایگان',
            'url_name': 'register',
            'auth_url_name': 'workspace:home',
            'kwargs': {},
        },
    ]
    current_id = {
        'filing_product_line': 'filing',
        'fast_property_search': 'fast_search',
    }.get(content_key)
    return _annotate_journey(steps, current_id)


def _extraction_journey(content_key: str) -> list[dict[str, Any]]:
    steps = [
        {
            'id': 'extraction',
            'label': 'استخراج',
            'hint': 'ربات دسکتاپ',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'extraction'},
        },
        {
            'id': 'filing',
            'label': 'فایلینگ',
            'hint': 'بانک Dataset',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'filing'},
        },
        {
            'id': 'market',
            'label': 'تحلیل',
            'hint': 'بازار و قیمت',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'market-intelligence'},
        },
        {
            'id': 'start',
            'label': 'شروع',
            'hint': 'لایسنس / میزکار',
            'url_name': 'product_detail',
            'auth_url_name': 'dashboard',
            'kwargs': {'slug': 'divar-extraction-bot'},
        },
    ]
    current_id = {
        'extraction_product_line': 'extraction',
    }.get(content_key)
    return _annotate_journey(steps, current_id)


def _market_journey(content_key: str) -> list[dict[str, Any]]:
    steps = [
        {
            'id': 'filing',
            'label': 'فایلینگ',
            'hint': 'بانک Dataset',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'filing'},
        },
        {
            'id': 'market',
            'label': 'تحلیل بازار',
            'hint': 'آمار و Value Score',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'market-intelligence'},
        },
        {
            'id': 'pricing',
            'label': 'قیمت‌گذاری',
            'hint': 'راه‌حل عملی',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'property-pricing'},
        },
        {
            'id': 'start',
            'label': 'شروع',
            'hint': 'ثبت‌نام رایگان',
            'url_name': 'register',
            'auth_url_name': 'workspace:home',
            'kwargs': {},
        },
    ]
    current_id = {
        'market_intelligence_product_line': 'market',
        'property_pricing': 'pricing',
    }.get(content_key)
    return _annotate_journey(steps, current_id)


def _agency_journey(content_key: str) -> list[dict[str, Any]]:
    steps = [
        {
            'id': 'crm',
            'label': 'CRM',
            'hint': 'مشتری و معامله',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'crm'},
        },
        {
            'id': 'agency',
            'label': 'آژانس',
            'hint': 'نقش و تیم',
            'url_name': 'platform_features_page',
            'kwargs': {'slug_path': 'agency'},
        },
        {
            'id': 'agency_mgmt',
            'label': 'مدیریت دفتر',
            'hint': 'راه‌حل عملی',
            'url_name': 'platform_solutions_page',
            'kwargs': {'slug': 'agency-management'},
        },
        {
            'id': 'start',
            'label': 'شروع',
            'hint': 'ثبت‌نام رایگان',
            'url_name': 'register',
            'auth_url_name': 'workspace:crm_team',
            'kwargs': {},
        },
    ]
    current_id = {
        'agency_product_line': 'agency',
        'agency_management': 'agency_mgmt',
    }.get(content_key)
    return _annotate_journey(steps, current_id)


def _annotate_journey(steps: list[dict[str, Any]], current_id: str | None) -> list[dict[str, Any]]:
    for i, step in enumerate(steps):
        step['state'] = 'upcoming'
        if current_id is None:
            continue
        if step['id'] == current_id:
            step['state'] = 'current'
        elif _step_index(steps, current_id) is not None and i < _step_index(steps, current_id):
            step['state'] = 'done'
    return steps


def _step_index(steps: list[dict], step_id: str | None) -> int | None:
    if not step_id:
        return None
    for i, s in enumerate(steps):
        if s['id'] == step_id:
            return i
    return None


def mark_menu_active(menu: dict, request_path: str) -> dict:
    """Annotate mega-menu entries with is_active from current path."""
    path = (request_path or '').rstrip('/') or '/'

    def match(url: str) -> bool:
        u = (url or '').rstrip('/') or '/'
        return path == u

    def annotate(item: dict, url: str) -> dict:
        out = dict(item)
        out['resolved_url'] = url
        out['is_active'] = match(url)
        return out

    def rev(name: str, kwargs: dict | None = None) -> str:
        return reverse(name, kwargs=kwargs or None)

    fp = menu.get('featured_product')
    if fp:
        url = rev(fp['url_name'], fp.get('url_kwargs') or None)
        menu['featured_product'] = annotate(fp, url)

    menu['product_lines'] = [
        annotate(
            item,
            rev(item['url_name'], item.get('url_kwargs') or None),
        )
        for item in menu.get('product_lines', [])
    ]
    menu['crm_highlights'] = [
        annotate(
            item,
            rev(item['url_name'], item.get('url_kwargs') or None),
        )
        for item in menu.get('crm_highlights', [])
    ]
    menu['solution_highlights'] = [
        annotate(
            item,
            rev(item['url_name'], item.get('url_kwargs') or None),
        )
        for item in menu.get('solution_highlights', [])
    ]
    if menu.get('solution_spotlight'):
        sp = menu['solution_spotlight']
        url = rev(sp['url_name'], sp.get('url_kwargs') or None)
        menu['solution_spotlight'] = annotate(sp, url)

    menu['quick_links'] = [
        annotate(item, rev(item['url_name']))
        for item in menu.get('quick_links', [])
    ]

    hub = rev(menu['hub_url_name'])
    sol_hub = rev(menu['solutions_url_name'])
    menu['hub_is_active'] = match(hub)
    menu['solutions_hub_is_active'] = match(sol_hub)
    menu['features_nav_active'] = (
        path.startswith('/features')
        or path.startswith('/solutions')
        or path.rstrip('/').endswith('real-estate-crm')
        or 'robot' in path
    )
    return menu
