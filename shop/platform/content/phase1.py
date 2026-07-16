"""محتوای صفحات فاز ۱ — فارسی، مبتنی بر قابلیت واقعی."""
from __future__ import annotations

from typing import Any

from shop.platform.content.crm_hub import crm_product_line_content
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
    return {
        'hero': {
            'layout': 'centered',
            'eyebrow': 'پلتفرم تکنولوژی املاک',
            'lead': (
                'فایلینگ دیوار یک میزکار یکپارچه برای مشاوران، مدیران و مالکان آژانس است — '
                'از CRM رایگان تا فایلینگ دیوار، تحلیل بازار و مدیریت تیم. '
                'هر بخش برای حل یک بخش از کار روزمره شما ساخته شده، نه صرفاً یک فهرست ابزار.'
            ),
        },
        'stats': [
            {'value': 'CRM رایگان', 'label': 'مخاطب، معامله، یادآور و تیم'},
            {'value': 'یک میزکار', 'label': 'فایلینگ، CRM و تحلیل بازار'},
            {'value': 'فارسی', 'label': 'رابط و پشتیبانی بومی'},
        ],
        'platform_pillars': [
            {
                'title': 'CRM املاک',
                'desc': 'مشتری، معامله، یادآور و پیگیری — ثبت‌نام رایگان',
                'url_name': 'platform_features_page',
                'url_kwargs': {'slug_path': 'crm'},
                'icon': 'fa-users',
                'accent': 'rose',
                'status': 'active',
                'size': 'large',
            },
            {
                'title': 'فایلینگ و استخراج',
                'desc': 'بانک فایل دیوار + ربات ویندوز',
                'url_name': 'seo_landing_robot_divar',
                'icon': 'fa-folder-tree',
                'accent': 'sky',
                'status': 'active',
            },
            {
                'title': 'تحلیل بازار',
                'desc': 'قیمت، نقشه و Value Score',
                'url_name': 'seo_landing_real_estate_software',
                'icon': 'fa-chart-line',
                'accent': 'amber',
                'status': 'active',
            },
            {
                'title': 'مدیریت آژانس',
                'desc': 'تیم، inbox، TV و گزارش',
                'url_name': 'blog:post_detail',
                'url_kwargs': {'slug': 'crm-team-modiriyat-ajans-rahnama'},
                'icon': 'fa-people-group',
                'accent': 'violet',
                'status': 'guide',
            },
        ],
        'outcomes_teaser': {
            'title': 'دنبال حل یک مشکل مشخص هستید؟',
            'lead': 'راه‌حل‌ها از نتیجه شروع می‌کنند — نه از نام ماژول.',
            'items': [
                {
                    'title': 'پیگیری مشتری',
                    'desc': 'هیچ تماسی از قلم نیفتد',
                    'url_name': 'platform_solutions_page',
                    'url_kwargs': {'slug': 'customer-follow-up'},
                },
            ],
        },
        'workflow': [
            {'step': '۱', 'title': 'استخراج', 'text': 'ربات دیوار آگهی محله هدف را می‌گیرد'},
            {'step': '۲', 'title': 'فایلینگ', 'text': 'فایل‌ها در میزکار منظم و قابل جستجو می‌شوند'},
            {'step': '۳', 'title': 'CRM', 'text': 'مشتری ثبت، پیگیری و تطبیق با فایل'},
            {'step': '۴', 'title': 'تحلیل', 'text': 'قیمت و نقشه برای تصمیم حرفه‌ای'},
        ],
        'faq': [
            {
                'q': 'CRM فایلینگ دیوار واقعاً رایگان است؟',
                'a': 'بله — CRM، مخاطب، معامله، یادآور، تقویم، قالب پیام، تیم آژانس و بسیاری از امکانات بدون لایسنس ربات در دسترس است. فایلینگ دیوار، تحلیل و نقشه نیاز به لایسنس ربات استخراج دارند.',
            },
            {
                'q': 'تفاوت این صفحه با صفحه اصلی سایت چیست؟',
                'a': 'صفحه اصلی معرفی کلی برند است. اینجا هر بخش پلتفرم را عمیق‌تر می‌بینید — با لینک به راه‌حل‌ها و جزئیات هر خط محصول.',
            },
            {
                'q': 'از کجا شروع کنم؟',
                'a': 'اگر تازه‌کار هستید، با CRM رایگان شروع کنید. اگر روی دیوار کار می‌کنید، ربات استخراج + فایلینگ مسیر اصلی است.',
            },
            {
                'q': 'تفاوت امکانات و راه‌حل چیست؟',
                'a': 'امکانات معرفی ماژول محصول — مثلاً یادآور CRM. راه‌حل از مشکل شما شروع می‌کند — مثلاً فراموشی پیگیری مشتری.',
            },
        ],
        'cta': _cta_block(),
    }


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
    return {
        'hero': {
            'layout': 'story',
            'eyebrow': 'راه‌حل · پیگیری مشتری',
            'lead': (
                'پیگیری منظم بخش بزرگی از موفقیت در املاک است — نه فقط تماس اول. '
                'این راه‌حل ترکیب یادآور، صف کار امروز، تقویم و اتوماسیون CRM '
                'فایلینگ دیوار است تا تماس دوم، سوم و چهارم از قلم نیفتد.'
            ),
        },
        'scenario': {
            'title': 'سناریوی واقعی: بعد از بازدید',
            'steps': [
                'شنبه ۱۱:۰۰ — بازدید ملک با خانم احمدی. او می‌گوید «با همسرم مشورت می‌کنم».',
                'همان لحظه در CRM یادآور برای دوشنبه ۱۰:۰۰ ثبت می‌کنید.',
                'دوشنبه ۹:۵۵ — «صف کار امروز» یادآوری می‌دهد: تماس با خانم احمدی.',
                'بعد از تماس — یادداشت در پرونده: «همسر موافق — بازدید segunda پیشنهاد».',
            ],
        },
        'features_used': [
            {
                'title': 'یادآور CRM',
                'text': 'زمان‌بندی دقیق پیگیری',
                'url_name': 'platform_features_page',
                'url_kwargs': {'slug_path': 'crm/reminders'},
            },
            {
                'title': 'صف کار امروز',
                'text': 'اولویت‌بندی روزانه',
                'url_name': 'platform_features_page',
                'url_kwargs': {'slug_path': 'crm/reminders'},
            },
            {
                'title': 'اتوماسیون',
                'text': 'قوانین پیگیری (Beta)',
                'url_name': 'blog:post_detail',
                'url_kwargs': {'slug': 'automation-crm-5-ghanon-pigiri-rahnama'},
            },
        ],
        'comparison': {
            'title': 'قبل و بعد',
            'before': ['یادداشت روی کاغذ', 'فراموشی تماس دوم', 'مدیر بی‌خبر از پیگیری معوق'],
            'after': ['یادآور زمان‌دار', 'صف امروز هر صبح', 'گزارش معوق تیم بدون لو رفتن محتوا'],
        },
        'when_to_use': [
            'بعد از هر بازدید یا تماس اول',
            'وقتی چند مشتری همزمان در جریان است',
            'برای تیم آژانس با چند مشاور',
        ],
        'pro_tips': [
            'تماس دوم را حداکثر ۴۸ ساعت بعد برنامه‌ریزی کنید.',
            'یادداشت کوتاه بعد از هر تماس — برای تماس بعدی.',
            'مدیر هفتگی گزارش معوق را مرور کند.',
        ],
        'faq': [
            {
                'q': 'آیا به ربات دیوار نیاز دارم؟',
                'a': 'خیر — پیگیری مشتری بخش CRM رایگان است. تطبیق فایل دیوار جداگانه لایسنس می‌خواهد.',
            },
            {
                'q': 'منشی هم می‌تواند پیگیری ثبت کند؟',
                'a': 'بله — با نقش منشی در آژانس، inbox و مخاطبین در دسترس است.',
            },
            {
                'q': 'تفاوت با صفحه یادآور CRM چیست؟',
                'a': 'صفحه یادآور جزئیات یک قابلیت است. این راه‌حل ترکیب چند ابزار برای حل مشکل فراموشی پیگیری است.',
            },
        ],
        'cta': _cta_block(),
    }
