"""محتوای صفحات فاز ۱ — فارسی، مبتنی بر قابلیت واقعی."""
from __future__ import annotations

from typing import Any


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
            'eyebrow': 'پلتفرم تکنولوژی املاک',
            'lead': (
                'فایلینگ دیوار یک میزکار یکپارچه برای مشاوران، مدیران و مالکان آژانس است — '
                'از CRM رایگان تا فایلینگ دیوار، تحلیل بازار و مدیریت تیم. '
                'هر بخش برای حل یک بخش از کار روزمره شما ساخته شده، نه صرفاً یک فهرست ابزار.'
            ),
        },
        'platform_pillars': [
            {
                'title': 'CRM املاک',
                'desc': 'مشتری، معامله، یادآور و پیگیری — ثبت‌نام رایگان',
                'url_name': 'platform_features_page',
                'url_kwargs': {'slug_path': 'crm'},
                'icon': 'fa-users',
                'accent': 'rose',
                'status': 'active',
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
        ],
        'cta': _cta_block(),
    }


def _crm_product_line_content() -> dict[str, Any]:
    return {
        'hero': {
            'eyebrow': 'خط محصول · CRM',
            'lead': (
                'دیگر مشتری گرم را در واتساپ گم نکنید. CRM املاک فایلینگ دیوار '
                'مشتری، معامله، فایل شخصی و پیگیری را در یک میزکار فارسی نگه می‌دارد — '
                'با یادآور، تقویم و اتصال به آگهی‌های دیوار.'
            ),
        },
        'problem': {
            'title': 'بدون CRM، هر روز مشتری از دست می‌رود',
            'paragraphs': [
                'تماس‌ها در واتساپ، یادداشت‌ها روی کاغذ، فایل‌ها در اکسل — تا وقتی حجم کار کم است جواب می‌دهد. '
                'وقتی روزی چند بازدید و چند پیشنهاد ملک دارید، «فردا زنگ می‌زنم» فراموش می‌شود.',
                'CRM یعنی هر خریدار و فروشنده یک پرونده دارد، هر تماس ثبت می‌شود و سیستم می‌گوید امروز اول به کی زنگ بزنید.',
            ],
        },
        'capabilities': [
            {'icon': 'fa-address-book', 'title': 'پرونده مشتری', 'text': 'نیاز، بودجه، محله و تاریخچه'},
            {'icon': 'fa-filter', 'title': 'قیف معامله', 'text': 'مراحل از سرنخ تا قرارداد'},
            {'icon': 'fa-bell', 'title': 'یادآور و تقویم', 'text': 'صف امروز + برنامه هفتگی'},
            {'icon': 'fa-building', 'title': 'فایل شخصی', 'text': 'ملک‌های خودتان با عکس و موقعیت'},
            {'icon': 'fa-wand-magic-sparkles', 'title': 'تطبیق هوشمند', 'text': 'پیشنهاد فایل دیوار به مشتری'},
            {'icon': 'fa-users-cog', 'title': 'تیم آژانس', 'text': 'inbox، گزارش و TV — رایگان'},
        ],
        'deep_features': [
            {
                'title': 'یادآور و تقویم',
                'desc': 'تماس، بازدید و قرار — با صف کار امروز',
                'url_name': 'platform_features_page',
                'url_kwargs': {'slug_path': 'crm/reminders'},
            },
        ],
        'screenshot': {
            'image': 'images/help-crm-dashboard.png',
            'caption': 'داشبورد CRM — وضعیت مشتریان و پیگیری‌های معوق',
        },
        'audience': ['مشاور مستقل', 'مدیر آژانس', 'منشی پذیرش سرنخ'],
        'faq': [
            {
                'q': 'CRM بدون ربات دیوار هم کار می‌کند؟',
                'a': 'بله. CRM، مخاطب، معامله، یادآور، تقویم، قالب پیام و تیم آژانس رایگان است. تطبیق با آگهی دیوار به لایسنس ربات نیاز دارد.',
            },
            {
                'q': 'تفاوت با لندینگ CRM سایت چیست؟',
                'a': 'صفحه /real-estate-crm/ معرفی تجاری CRM است. این صفحه نمای محصول و خط CRM در پلتفرم را نشان می‌دهد.',
            },
        ],
        'cta': _cta_block(primary='register', secondary='seo_crm'),
    }


def _crm_reminders_content() -> dict[str, Any]:
    return {
        'hero': {
            'eyebrow': 'CRM · یادآور و تقویم',
            'lead': (
                'بعد از بازدید ملک، مشتری می‌گوید «فردا تصمیم می‌گیرم». '
                'یادآور CRM فایلینگ دیوار همان لحظه یادآوری ثبت می‌کند — '
                'و فردا صبح در صف کار امروز می‌بینید: اول به این شماره زنگ بزنید.'
            ),
        },
        'problem': {
            'title': 'تماس دوم مهم‌تر از اول است — ولی بیشتر فراموش می‌شود',
            'paragraphs': [
                'مشاور حرفه‌ای می‌داند پیگیری منظم فروش را می‌برد. اما در شلوغی روز، '
                'یادداشت ذهنی یا پیام واتساپ کافی نیست.',
                'یادآور و تقویم CRM یعنی هر پیگیری زمان مشخص دارد، در صف امروز دیده می‌شود '
                'و مدیر آژانس می‌تواند پیگیری‌های معوق تیم را ببیند — بدون دسترسی به محتوای تماس.',
            ],
        },
        'how_it_works': [
            {'title': 'ثبت یادآور', 'text': 'روی مخاطب یا معامله — تاریخ و ساعت تماس یا بازدید'},
            {'title': 'صف کار امروز', 'text': 'لیست کوتاه کارهای همین روز در /workspace/crm/today/'},
            {'title': 'تقویم', 'text': 'نمای ماه و هفته — بازدیدها و قرارها یک‌جا'},
            {'title': 'تکرار دوره‌ای', 'text': 'یادآور هفتگی یا ماهانه برای مشتریان بلندمدت'},
        ],
        'screenshots': [
            {'image': 'images/help-crm-reminders.png', 'caption': 'یادآور تماس با مشتری'},
            {'image': 'images/help-crm-today.png', 'caption': 'صف کار امروز — اولویت‌بندی تماس‌ها'},
            {'image': 'images/help-crm-calendar.png', 'caption': 'تقویم بازدید و جلسات'},
        ],
        'benefits': [
            'کاهش از دست رفتن مشتری گرم بعد از بازدید',
            'شفافیت برای مدیر: تعداد پیگیری معوق بدون نقض حریم',
            'یکپارچه با معامله و مخاطب — نه اپ جدا',
        ],
        'related_solution': {
            'title': 'راه‌حل: پیگیری مشتری',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'customer-follow-up'},
        },
        'faq': [
            {
                'q': 'یادآور روی موبایل هم می‌آید؟',
                'a': 'اپ اندروید فایلینگ دیوار یادآور و اعلان پشتیبانی می‌کند. CRM وب در مرورگر موبایل هم قابل استفاده است.',
            },
            {
                'q': 'اتوماسیون CRM چطور؟',
                'a': 'قوانین اتوماسیون (Beta) می‌توانند پیگیری را جلو بیندازند. جزئیات در مقاله اتوماسیون CRM.',
            },
            {
                'q': 'آیا رایگان است؟',
                'a': 'بله — یادآور، تقویم و صف امروز بخش CRM رایگان هستند.',
            },
        ],
        'cta': _cta_block(),
    }


def _solutions_hub_content() -> dict[str, Any]:
    return {
        'hero': {
            'eyebrow': 'راه‌حل‌ها',
            'lead': (
                'اینجا بر اساس نتیجه‌ای که می‌خواهید جستجو کنید — نه نام ماژول نرم‌افزار. '
                'هر راه‌حل به امکانات واقعی فایلینگ دیوار وصل است.'
            ),
        },
        'solutions': [
            {
                'title': 'پیگیری مشتری',
                'outcome': 'هیچ مشتری‌ای فراموش نشود',
                'desc': 'یادآور، صف امروز و تقویم CRM',
                'url_name': 'platform_solutions_page',
                'url_kwargs': {'slug': 'customer-follow-up'},
                'accent': 'rose',
            },
        ],
        'faq': [
            {
                'q': 'تفاوت راه‌حل و امکانات چیست؟',
                'a': 'راه‌حل از مشکل شما شروع می‌کند — مثلاً فراموشی پیگیری. امکانات معرفی ماژول محصول — مثلاً یادآور CRM.',
            },
        ],
        'cta': _cta_block(),
    }


def _customer_follow_up_content() -> dict[str, Any]:
    return {
        'hero': {
            'eyebrow': 'راه‌حل · پیگیری مشتری',
            'lead': (
                '۷۰٪ معاملات املاک به پیگیری منظم وابسته است — نه فقط تماس اول. '
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
                'url_kwargs': {'slug_path': 'crm'},
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
        'faq': [
            {
                'q': 'آیا به ربات دیوار نیاز دارم؟',
                'a': 'خیر — پیگیری مشتری بخش CRM رایگان است. تطبیق فایل دیوار جداگانه لایسنس می‌خواهد.',
            },
            {
                'q': 'منشی هم می‌تواند پیگیری ثبت کند؟',
                'a': 'بله — با نقش منشی در آژانس، inbox و مخاطبین در دسترس است.',
            },
        ],
        'cta': _cta_block(),
    }
