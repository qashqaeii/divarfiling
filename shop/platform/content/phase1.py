"""محتوای صفحات فاز ۱ — فارسی، مبتنی بر قابلیت واقعی."""
from __future__ import annotations

from typing import Any

from shop.platform.content.crm_hub import crm_product_line_content
from shop.platform.content.customer_follow_up import customer_follow_up_content
from shop.platform.content.features_hub import features_hub_content
from shop.platform.content.reminders_feature import crm_reminders_content


def build_page_content(content_key: str) -> dict[str, Any]:
    builders = {
        'features_hub': _features_hub_content,
        'crm_product_line': _crm_product_line_content,
        'crm_reminders': _crm_reminders_content,
        'solutions_hub': _solutions_hub_content,
        'customer_follow_up': _customer_follow_up_content,
    }
    builder = builders.get(content_key)
    if not builder:
        raise KeyError(f'unknown content_key: {content_key}')
    return builder()


def _cta_block(primary: str = 'register', secondary: str = 'crm_landing') -> dict:
    return {
        'primary': primary,
        'secondary': secondary,
    }


def _features_hub_content() -> dict[str, Any]:
    return features_hub_content()


def _crm_product_line_content() -> dict[str, Any]:
    return crm_product_line_content()


def _crm_reminders_content() -> dict[str, Any]:
    return crm_reminders_content()


def _solutions_hub_content() -> dict[str, Any]:
    return {
        'hero': {
            'layout': 'centered',
            'eyebrow': 'راه‌حل‌ها',
            'lead': (
                'اینجا بر اساس نتیجه‌ای که می‌خواهید جستجو کنید — نه نام ماژول نرم‌افزار. '
                'هر راه‌حل به امکانات واقعی فایلینگ دیوار وصل است.'
            ),
        },
        'how_to_choose': {
            'title': 'چطور راه‌حل مناسب را پیدا کنید؟',
            'items': [
                {'title': 'مشکل را نام ببرید', 'text': 'مثلاً «مشتری را فراموش می‌کنم» نه «یادآور می‌خواهم».'},
                {'title': 'راه‌حل را بخوانید', 'text': 'سناریو و امکانات درگیر را ببینید.'},
                {'title': 'به جزئیات بروید', 'text': 'از راه‌حل به صفحه Feature مرتبط لینک بگیرید.'},
            ],
        },
        'solutions': [
            {
                'title': 'پیگیری مشتری',
                'outcome': 'هیچ مشتری‌ای فراموش نشود',
                'desc': 'یادآور، صف امروز، تقویم و اتوماسیون CRM — برای مشاور و تیم آژانس.',
                'url_name': 'platform_solutions_page',
                'url_kwargs': {'slug': 'customer-follow-up'},
                'accent': 'rose',
                'features': ['یادآور CRM', 'صف کار امروز', 'تقویم'],
            },
        ],
        'faq': [
            {
                'q': 'تفاوت راه‌حل و امکانات چیست؟',
                'a': 'راه‌حل از مشکل شما شروع می‌کند — مثلاً فراموشی پیگیری. امکانات معرفی ماژول محصول — مثلاً یادآور CRM.',
            },
            {
                'q': 'آیا همه راه‌حل‌ها رایگان هستند؟',
                'a': 'راه‌حل پیگیری مشتری با CRM رایگان پوشش داده می‌شود. برخی امکانات مثل تطبیق دیوار لایسنس جدا می‌خواهند.',
            },
        ],
        'cta': _cta_block(secondary='crm_landing'),
    }


def _customer_follow_up_content() -> dict[str, Any]:
    return customer_follow_up_content()
