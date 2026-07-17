"""داده منوی امکانات — فقط صفحات published."""
from __future__ import annotations

from shop.platform.registry import published_pages


def platform_mega_menu() -> dict:
    """منوی مگا — بخش‌های اصلی پلتفرم (فاز ۱)."""
    featured_lines = [
        {
            'title': 'CRM املاک',
            'desc': 'مشتری، معامله و پیگیری — رایگان',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'crm'},
            'icon': 'fa-users',
            'accent': 'rose',
            'tag': 'رایگان',
        },
        {
            'title': 'یادآور و تقویم',
            'desc': 'صف امروز و پیگیری به‌موقع',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'crm/reminders'},
            'icon': 'fa-bell',
            'accent': 'amber',
        },
        {
            'title': 'فایلینگ دیوار',
            'desc': 'بانک Dataset و جستجوی فایل',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'filing'},
            'icon': 'fa-folder-tree',
            'accent': 'sky',
            'tag': 'لایسنس',
        },
        {
            'title': 'تحلیل بازار',
            'desc': 'آمار قیمت، نقشه و Value Score',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'market-intelligence'},
            'icon': 'fa-chart-line',
            'accent': 'amber',
            'tag': 'لایسنس',
        },
        {
            'title': 'مدیریت آژانس',
            'desc': 'نقش‌ها، صندوق سرنخ و Agency TV',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'agency'},
            'icon': 'fa-people-group',
            'accent': 'violet',
            'tag': 'رایگان',
        },
        {
            'title': 'ربات استخراج',
            'desc': 'آگهی دیوار با فیلتر شهر',
            'url_name': 'seo_landing_robot_divar',
            'url_kwargs': {},
            'icon': 'fa-robot',
            'accent': 'cyan',
        },
        {
            'title': 'نرم‌افزار مشاور',
            'desc': 'معرفی کامل پلتفرم',
            'url_name': 'seo_landing_real_estate_software',
            'url_kwargs': {},
            'icon': 'fa-layer-group',
            'accent': 'violet',
        },
    ]

    crm_features = [
        {
            'label': 'جزئیات محصول CRM',
            'desc': '/features/crm/',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'crm'},
        },
        {
            'label': 'یادآور و تقویم',
            'desc': 'پیگیری به‌موقع',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'crm/reminders'},
        },
        {
            'label': 'فایلینگ دیوار',
            'desc': '/features/filing/',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'filing'},
        },
        {
            'label': 'تحلیل بازار',
            'desc': '/features/market-intelligence/',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'market-intelligence'},
        },
        {
            'label': 'مدیریت آژانس',
            'desc': '/features/agency/',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'agency'},
        },
        {
            'label': 'لندینگ معرفی CRM',
            'desc': '/real-estate-crm/ — معرفی تجاری',
            'url_name': 'seo_landing_real_estate_crm',
            'url_kwargs': {},
        },
    ]

    solutions = [
        {
            'label': 'پیگیری مشتری',
            'desc': 'تماس دوم از قلم نیفتد',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'customer-follow-up'},
        },
        {
            'label': 'پیدا کردن سریع فایل',
            'desc': 'جستجو روی Dataset',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'fast-property-search'},
        },
        {
            'label': 'قیمت‌گذاری ملک',
            'desc': 'بازه منطقی از فایل مشابه',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'property-pricing'},
        },
        {
            'label': 'راه‌حل مدیریت آژانس',
            'desc': 'سرنخ، مسئولیت و گزارش تیم',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'agency-management'},
        },
    ]

    quick_links = [
        {
            'label': 'همه امکانات',
            'url_name': 'platform_features_hub',
        },
        {
            'label': 'همه راه‌حل‌ها',
            'url_name': 'platform_solutions_hub',
        },
        {
            'label': 'ربات دیوار',
            'url_name': 'seo_landing_robot_divar',
        },
    ]

    published_count = len(published_pages('features')) + len(published_pages('solutions'))

    return {
        'label': 'امکانات',
        'hub_url_name': 'platform_features_hub',
        'solutions_url_name': 'platform_solutions_hub',
        'featured_product': {
            'title': 'CRM املاک',
            'desc': 'مشتری، معامله، یادآور و تیم — ثبت‌نام رایگان',
            'badge': 'رایگان',
            'url_name': 'platform_features_page',
            'url_kwargs': {'slug_path': 'crm'},
            'image': 'images/help-crm-dashboard.png',
        },
        'product_lines': featured_lines,
        'crm_highlights': crm_features,
        'solution_highlights': solutions,
        'solution_spotlight': {
            'title': 'پیگیری مشتری',
            'outcome': 'تماس دوم از قلم نیفتد',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'customer-follow-up'},
        },
        'quick_links': quick_links,
        'published_page_count': published_count,
    }
