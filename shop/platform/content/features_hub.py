"""محتوای کامل Hub امکانات — /features/."""
from __future__ import annotations

from typing import Any


def features_hub_content() -> dict[str, Any]:
    return {
        'hero': {
            'eyebrow': 'پلتفرم · میزکار یکپارچه',
            'lead': (
                'فایلینگ دیوار یک میزکار برای مشاور، مدیر و تیم آژانس است — '
                'نه چند ابزار جدا. CRM رایگان، فایلینگ دیوار، تحلیل بازار و مدیریت تیم '
                'روی یک حساب کاربری و یک زبان مشترک کار می‌کنند.'
            ),
            'promise': (
                'این صفحه نقشه پلتفرم است: هر بخش کجا می‌نشیند، '
                'از کجا شروع کنید و کدام صفحه برای عمیق‌تر رفتن مناسب است.'
            ),
            'screenshot': {
                'image': 'images/help-crm-dashboard.png',
                'caption': 'میزکار — CRM، فایل و گزارش در یک نما',
                'explain': 'داشبورد نقطه شروع روز است؛ از اینجا به مخاطب، فایل، معامله و پیگیری می‌روید.',
                'callouts': [
                    {'text': 'وضعیت CRM', 'x': '20', 'y': '40'},
                    {'text': 'دسترسی سریع', 'x': '72', 'y': '52'},
                ],
            },
            'highlights': [
                {'label': 'CRM رایگان', 'desc': 'مخاطب، معامله، یادآور، تیم'},
                {'label': 'یک میزکار', 'desc': 'فایلینگ + CRM + تحلیل'},
                {'label': 'فارسی', 'desc': 'رابط و پشتیبانی بومی'},
            ],
        },
        'workspace_story': {
            'title': 'چرا «یک میزکار» مهم است؟',
            'paragraphs': [
                (
                    'مشاور املاک معمولاً بین واتساپ، اکسل، دیوار و حافظه جابه‌جا می‌شود. '
                    'هر ابزار برای یک کار خوب است — اما وقتی داده‌ها به هم وصل نیستند، '
                    'تماس دوم، تطبیق فایل و گزارش تیم کند می‌شود.'
                ),
                (
                    'فایلینگ دیوار از CRM شروع می‌کند (رایگان) و در صورت نیاز '
                    'فایلینگ دیوار و تحلیل را روی همان میزکار اضافه می‌کند. '
                    'مشتری، فایل و معامله در یک پرونده دیده می‌شوند — نه در سه اپ جدا.'
                ),
            ],
        },
        'pillars': {
            'title': 'بخش‌های اصلی پلتفرم',
            'lead': 'هر خط محصول یک مسیر مشخص دارد — روی کارت کلیک کنید یا از فهرست کاوش عمیق‌تر بروید.',
            'items': [
                {
                    'title': 'CRM املاک',
                    'desc': (
                        'مخاطب، معامله، یادآور، تقویم، قالب پیام، inbox تیم و pipeline — '
                        'ثبت‌نام رایگان، بدون نیاز به ربات دیوار.'
                    ),
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm'},
                    'icon': 'fa-users',
                    'accent': 'rose',
                    'badge': 'رایگان',
                    'size': 'featured',
                    'sub_links': [
                        {
                            'label': 'یادآور و تقویم',
                            'url_name': 'platform_features_page',
                            'url_kwargs': {'slug_path': 'crm/reminders'},
                        },
                        {
                            'label': 'لندینگ CRM',
                            'url_name': 'seo_landing_real_estate_crm',
                            'url_kwargs': {},
                        },
                    ],
                },
                {
                    'title': 'فایلینگ و استخراج',
                    'desc': 'ربات ویندوز + بانک فایل دیوار — جستجو، فیلتر و تطبیق با مشتری.',
                    'url_name': 'seo_landing_robot_divar',
                    'url_kwargs': {},
                    'icon': 'fa-folder-tree',
                    'accent': 'sky',
                    'badge': 'لایسنس ربات',
                    'size': 'normal',
                },
                {
                    'title': 'تحلیل بازار',
                    'desc': 'قیمت، نقشه، Value Score و بینش محله — برای تصمیم حرفه‌ای.',
                    'url_name': 'seo_landing_real_estate_software',
                    'url_kwargs': {},
                    'icon': 'fa-chart-line',
                    'accent': 'amber',
                    'badge': 'لایسنس',
                    'size': 'normal',
                },
                {
                    'title': 'مدیریت آژانس',
                    'desc': 'تیم، inbox، TV، گزارش معوق و نقش‌ها — برای مدیر و منشی.',
                    'url_name': 'blog:post_detail',
                    'url_kwargs': {'slug': 'crm-team-modiriyat-ajans-rahnama'},
                    'icon': 'fa-people-group',
                    'accent': 'violet',
                    'badge': 'راهنما',
                    'size': 'normal',
                },
            ],
        },
        'crm_spotlight': {
            'title': 'CRM — قلب میزکار',
            'lead': (
                'بیشتر مشاوران از CRM شروع می‌کنند. رایگان است، فارسی است '
                'و مستقیماً به پیگیری مشتری و مدیریت معامله وصل می‌شود.'
            ),
            'points': [
                {
                    'title': 'خط محصول CRM',
                    'text': '۸ ماژول اصلی — از مخاطب تا اتوماسیون Beta.',
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm'},
                },
                {
                    'title': 'یادآور و صف امروز',
                    'text': 'جزئیات Feature پیگیری — برای کسی که می‌خواهد عمیق برود.',
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm/reminders'},
                },
                {
                    'title': 'راه‌حل پیگیری مشتری',
                    'text': 'از مشکل «فراموشی تماس» شروع می‌کند — نه از نام ماژول.',
                    'url_name': 'platform_solutions_page',
                    'url_kwargs': {'slug': 'customer-follow-up'},
                },
            ],
            'screenshot': {
                'image': 'images/help-crm-contacts.png',
                'caption': 'CRM — مخاطبین و وضعیت در یک لیست',
                'explain': 'فیلتر نوع مخاطب و وضعیت برای صف تماس روزانه.',
                'callouts': [
                    {'text': 'نوع مخاطب', 'x': '24', 'y': '28'},
                    {'text': 'وضعیت قیف', 'x': '58', 'y': '28'},
                ],
            },
        },
        'lifecycle': {
            'title': 'از استخراج تا تصمیم',
            'lead': 'چهار مرحله که در میزکار به هم وصل می‌شوند — نه چهار نرم‌افزار جدا.',
            'steps': [
                {
                    'title': 'استخراج',
                    'text': 'ربات دیوار آگهی محله هدف را با فیلتر شهر می‌گیرد.',
                    'icon': 'fa-robot',
                    'tone': 'sky',
                },
                {
                    'title': 'فایلینگ',
                    'text': 'فایل‌ها در بانک منظم، قابل جستجو و قابل اشتراک با تیم.',
                    'icon': 'fa-database',
                    'tone': 'cyan',
                },
                {
                    'title': 'CRM',
                    'text': 'مشتری ثبت، پیگیری زمان‌دار و تطبیق فایل با نیاز.',
                    'icon': 'fa-users',
                    'tone': 'rose',
                },
                {
                    'title': 'تحلیل',
                    'text': 'قیمت، نقشه و Value Score برای پیشنهاد حرفه‌ای.',
                    'icon': 'fa-chart-pie',
                    'tone': 'amber',
                },
            ],
        },
        'audience': {
            'title': 'برای چه کسی ساخته شده؟',
            'items': [
                {
                    'title': 'مشاور مستقل',
                    'text': (
                        'CRM رایگان برای مخاطب و پیگیری — بدون هزینه اولیه. '
                        'وقتی روی دیوار کار می‌کنید، ربات و فایلینگ را اضافه کنید.'
                    ),
                    'start': 'platform_features_page',
                    'start_kwargs': {'slug_path': 'crm'},
                    'start_label': 'شروع با CRM',
                },
                {
                    'title': 'مدیر آژانس',
                    'text': (
                        'تیم، inbox، گزارش معوق و نقش‌ها — بدون خواندن محتوای خصوصی تماس. '
                        'CRM تیمی رایگان است.'
                    ),
                    'start': 'blog:post_detail',
                    'start_kwargs': {'slug': 'crm-team-modiriyat-ajans-rahnama'},
                    'start_label': 'راهنمای مدیریت تیم',
                },
                {
                    'title': 'منشی و پذیرش',
                    'text': (
                        'ثبت سرنخ inbox، مخاطب اولیه و یادآور برای مشاور — '
                        'بدون گروه واتساپ شلوغ.'
                    ),
                    'start': 'platform_solutions_page',
                    'start_kwargs': {'slug': 'customer-follow-up'},
                    'start_label': 'راه‌حل پیگیری',
                },
            ],
        },
        'access_tiers': {
            'title': 'چه چیز رایگان است، چه چیز لایسنس می‌خواهد؟',
            'lead': 'بدون ابهام — فقط آنچه واقعاً در محصول وجود دارد.',
            'free': [
                'CRM: مخاطب، معامله، یادآور، تقویم، قالب پیام',
                'صف کار امروز و inbox تیم',
                'تیم آژانس و نقش‌ها (مشاور، منشی، مدیر)',
                'اتوماسیون CRM (Beta)',
            ],
            'licensed': [
                'ربات استخراج دیوار (ویندوز)',
                'بانک فایل Dataset و تطبیق',
                'تحلیل بازار، نقشه و Value Score',
                'برخی امکانات پیشرفته فایلینگ',
            ],
            'note': 'می‌توانید فقط CRM را رایگان استفاده کنید — لایسنس ربات اجباری نیست.',
        },
        'explore': {
            'title': 'کاوش عمیق‌تر',
            'lead': 'صفحات منتشرشده فاز ۱ — هر کدام یک intent جدا برای SEO.',
            'pages': [
                {
                    'title': 'خط محصول CRM',
                    'type': 'Feature Line',
                    'desc': '۸ ماژول CRM با screenshot و FAQ',
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm'},
                },
                {
                    'title': 'یادآور CRM',
                    'type': 'Feature',
                    'desc': 'جزئیات یادآور، تقویم و صف امروز',
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm/reminders'},
                },
                {
                    'title': 'پیگیری مشتری',
                    'type': 'Solution',
                    'desc': 'راه‌حل فراموشی تماس — framework عملی',
                    'url_name': 'platform_solutions_page',
                    'url_kwargs': {'slug': 'customer-follow-up'},
                },
                {
                    'title': 'راه‌حل‌ها',
                    'type': 'Hub',
                    'desc': 'جستجو بر اساس نتیجه، نه ماژول',
                    'url_name': 'platform_solutions_hub',
                    'url_kwargs': {},
                },
            ],
        },
        'solutions_bridge': {
            'title': 'دنبال حل یک مشکل مشخص هستید؟',
            'lead': 'راه‌حل‌ها از نتیجه شروع می‌کنند — نه از نام ماژول.',
            'items': [
                {
                    'title': 'پیگیری مشتری',
                    'outcome': 'تماس دوم از قلم نیفتد',
                    'desc': 'یادآور، صف امروز، تقویم و framework پیگیری.',
                    'url_name': 'platform_solutions_page',
                    'url_kwargs': {'slug': 'customer-follow-up'},
                },
            ],
        },
        'faq': [
            {
                'q': 'CRM فایلینگ دیوار واقعاً رایگان است؟',
                'a': (
                    'بله — CRM، مخاطب، معامله، یادآور، تقویم، قالب پیام، تیم آژانس '
                    'و بسیاری از امکانات بدون لایسنس ربات در دسترس است. '
                    'فایلینگ Dataset، ربات استخراج و تحلیل بازار لایسنس جدا می‌خواهند.'
                ),
            },
            {
                'q': 'از کجا شروع کنم؟',
                'a': (
                    'اگر تازه‌کار هستید: CRM رایگان. '
                    'اگر روی دیوار کار می‌کنید: ربات + CRM. '
                    'اگر مشکل مشخص دارید (مثلاً فراموشی پیگیری): از راه‌حل‌ها شروع کنید.'
                ),
            },
            {
                'q': 'تفاوت این صفحه با صفحه اصلی سایت چیست؟',
                'a': (
                    'صفحه اصلی معرفی کلی برند است. '
                    'اینجا نقشه هر بخش پلتفرم با لینک به جزئیات و راه‌حل‌هاست.'
                ),
            },
            {
                'q': 'تفاوت امکانات و راه‌حل چیست؟',
                'a': (
                    'امکانات معرفی ماژول محصول — مثلاً یادآور CRM. '
                    'راه‌حل از مشکل شما شروع می‌کند — مثلاً فراموشی پیگیری مشتری.'
                ),
            },
            {
                'q': 'تفاوت /features/crm/ با /real-estate-crm/ چیست؟',
                'a': (
                    'لندینگ SEO تجاری CRM است. '
                    'صفحه خط محصول CRM جزئیات ماژول‌ها، screenshot و FAQ فنی دارد.'
                ),
            },
            {
                'q': 'آیا اپ موبایل هم دارید؟',
                'a': (
                    'بله — اپ موبایل برای دسترسی به میزکار وجود دارد. '
                    'CRM و پیگیری از موبایل هم در دسترس است.'
                ),
            },
        ],
        'final_cta': {
            'title': 'میزکار خود را بسازید',
            'lead': 'CRM رایگان است — کمتر از یک دقیقه ثبت‌نام کنید و اولین مخاطب را اضافه کنید.',
        },
        'cta': {
            'primary': 'register',
            'secondary': 'solutions_hub',
        },
    }
