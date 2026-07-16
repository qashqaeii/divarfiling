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
    return {
        'hero': {
            'layout': 'split',
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
        'feature_modules': [
            {
                'title': 'یادآور و تقویم',
                'icon': 'fa-bell',
                'accent': 'amber',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'بعد از بازدید، تماس دوم فراموش می‌شود.',
                'benefit': 'هر پیگیری زمان مشخص دارد و در صف کار امروز دیده می‌شود.',
                'when': 'بعد از هر بازدید، پیشنهاد یا تماس اول.',
                'image': 'images/help-crm-reminders.png',
                'link': {
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm/reminders'},
                    'label': 'جزئیات یادآور و تقویم',
                },
            },
            {
                'title': 'صف کار امروز',
                'icon': 'fa-list-check',
                'accent': 'rose',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'صبح نمی‌دانید اول به کدام مشتری زنگ بزنید.',
                'benefit': 'لیست کوتاه و اولویت‌بندی‌شده کارهای همین روز.',
                'when': 'هر صبح قبل از شروع تماس‌ها.',
                'image': 'images/help-crm-today.png',
                'link': {
                    'url_name': 'platform_features_page',
                    'url_kwargs': {'slug_path': 'crm/reminders'},
                    'label': 'مرتبط با یادآور CRM',
                },
            },
            {
                'title': 'مخاطبین و پرونده',
                'icon': 'fa-address-book',
                'accent': 'violet',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'نیاز، بودجه و تاریخچه تماس پراکنده است.',
                'benefit': 'هر مشتری یک پرونده با یادداشت و سوابق.',
                'when': 'از اولین تماس تا قرارداد.',
                'image': 'images/help-crm-contacts.png',
                'link': {
                    'url_name': 'seo_landing_real_estate_crm',
                    'url_kwargs': {},
                    'label': 'راهنمای CRM املاک',
                },
            },
            {
                'title': 'قیف معامله',
                'icon': 'fa-filter',
                'accent': 'sky',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'نمی‌دانید هر معامله در چه مرحله‌ای مانده.',
                'benefit': 'مراحل از سرنخ تا قرارداد — قابل پیگیری برای مدیر.',
                'when': 'وقتی چند معامله همزمان در جریان است.',
                'image': 'images/help-crm-deals.png',
                'link': {
                    'url_name': 'blog:post_detail',
                    'url_kwargs': {'slug': 'modiriyat-moamele-amlak-parvande-komision-rahnama'},
                    'label': 'راهنمای مدیریت معامله',
                },
            },
            {
                'title': 'فایل شخصی',
                'icon': 'fa-building',
                'accent': 'emerald',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'ملک‌های خودتان جدا از CRM و فایلینگ است.',
                'benefit': 'ملک با عکس، موقعیت و وضعیت — در همان میزکار.',
                'when': 'برای فایل‌های انحصاری آژانس یا مالک.',
                'image': 'images/help-crm-properties.png',
                'link': {
                    'url_name': 'seo_landing_real_estate_crm',
                    'url_kwargs': {},
                    'label': 'معرفی CRM و فایل شخصی',
                },
            },
            {
                'title': 'قالب پیام',
                'icon': 'fa-message',
                'accent': 'cyan',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'هر بار پیام واتساپ را از نو می‌نویسید.',
                'benefit': 'قالب‌های آماده برای معرفی ملک و پیگیری.',
                'when': 'برای تماس‌های تکراری و پیام گروهی.',
                'image': 'images/help-crm-templates.png',
                'link': {
                    'url_name': 'blog:post_detail',
                    'url_kwargs': {'slug': 'crm-amlak-raygan-rahnama'},
                    'label': 'راهنمای CRM رایگان',
                },
            },
            {
                'title': 'تیم آژانس',
                'icon': 'fa-users-cog',
                'accent': 'violet',
                'badge': {'label': 'رایگان', 'tone': 'free'},
                'problem': 'مدیر نمی‌داند تیم چه کسی را پیگیری کرده.',
                'benefit': 'inbox، گزارش معوق و TV — بدون لو رفتن محتوای تماس.',
                'when': 'آژانس با چند مشاور یا منشی.',
                'image': 'images/help-crm-team.png',
                'link': {
                    'url_name': 'blog:post_detail',
                    'url_kwargs': {'slug': 'crm-team-modiriyat-ajans-rahnama'},
                    'label': 'راهنمای مدیریت تیم',
                },
            },
            {
                'title': 'اتوماسیون پیگیری',
                'icon': 'fa-wand-magic-sparkles',
                'accent': 'amber',
                'badge': {'label': 'Beta', 'tone': 'beta'},
                'problem': 'پیگیری‌های تکراری وقت می‌گیرد.',
                'benefit': 'قوانین خودکار برای یادآور و مرحله بعد.',
                'when': 'الگوی پیگیری ثابت برای انواع مشتری.',
                'image': 'images/help-crm-automation.png',
                'link': {
                    'url_name': 'blog:post_detail',
                    'url_kwargs': {'slug': 'automation-crm-5-ghanon-pigiri-rahnama'},
                    'label': '۵ قانون اتوماسیون CRM',
                },
            },
        ],
        'screenshot': {
            'image': 'images/help-crm-dashboard.png',
            'caption': 'داشبورد CRM — وضعیت مشتریان و پیگیری‌های معوق',
        },
        'pro_tips': [
            'هر تماس را همان لحظه در CRM ثبت کنید — بعداً یادآوری سخت‌تر است.',
            'صف کار امروز را صبح یک‌بار مرور کنید؛ بقیه روز را بر اساس آن برنامه‌ریزی کنید.',
            'برای مشتریان بلندمدت، یادآور تکراری هفتگی تنظیم کنید.',
        ],
        'audience': ['مشاور مستقل', 'مدیر آژانس', 'منشی پذیرش سرنخ'],
        'related_solution': {
            'title': 'راه‌حل: پیگیری مشتری',
            'desc': 'ترکیب یادآور، صف امروز و تقویم',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'customer-follow-up'},
        },
        'faq': [
            {
                'q': 'CRM بدون ربات دیوار هم کار می‌کند؟',
                'a': 'بله. CRM، مخاطب، معامله، یادآور، تقویم، قالب پیام و تیم آژانس رایگان است. تطبیق با آگهی دیوار به لایسنس ربات نیاز دارد.',
            },
            {
                'q': 'تفاوت با لندینگ CRM سایت چیست؟',
                'a': 'صفحه /real-estate-crm/ معرفی تجاری CRM است. این صفحه نمای محصول و تمام ماژول‌های CRM در پلتفرم را نشان می‌دهد.',
            },
            {
                'q': 'کدام بخش CRM را اول فعال کنم؟',
                'a': 'مخاطب + یادآور + صف امروز — سه‌تایی که بیشترین اثر را در کاهش فراموشی پیگیری دارند.',
            },
        ],
        'cta': _cta_block(primary='register', secondary='seo_crm'),
    }


def _crm_reminders_content() -> dict[str, Any]:
    return {
        'hero': {
            'layout': 'feature',
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
        'scenario': {
            'title': 'سناریوی واقعی',
            'steps': [
                'بازدید با خانم احمدی — «با همسرم مشورت می‌کنم».',
                'همان لحظه: یادآور برای دوشنبه ۱۰:۰۰ روی پرونده ثبت می‌شود.',
                'دوشنبه صبح: «صف کار امروز» یادآوری می‌دهد.',
                'بعد از تماس: یادداشت در پرونده — «همسر موافق، بازدید segunda».',
            ],
        },
        'how_it_works': [
            {'title': 'ثبت یادآور', 'text': 'روی مخاطب یا معامله — تاریخ و ساعت تماس یا بازدید'},
            {'title': 'صف کار امروز', 'text': 'لیست کوتاه کارهای همین روز در میزکار CRM'},
            {'title': 'تقویم', 'text': 'نمای ماه و هفته — بازدیدها و قرارها یک‌جا'},
            {'title': 'تکرار دوره‌ای', 'text': 'یادآور هفتگی یا ماهانه برای مشتریان بلندمدت'},
        ],
        'when_to_use': [
            {'title': 'بعد از بازدید', 'text': 'تماس پیگیری ۲۴ تا ۴۸ ساعت بعد'},
            {'title': 'مشتری سرد', 'text': 'یادآور ماهانه برای چک وضعیت'},
            {'title': 'قرار ملاقات', 'text': 'بازدید segunda یا جلسه قرارداد'},
            {'title': 'تیم آژانس', 'text': 'مدیر پیگیری معوق را بدون لو رفتن محتوا می‌بیند'},
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
        'pro_tips': [
            'یادآور را همان لحظه بازدید ثبت کنید — نه شب‌ها.',
            'برای مشتری «فکر می‌کنم»، ۴۸ ساعت بعد تماس بگذارید.',
            'از تقویم برای هماهنگی بازدیدهای چند مشاور استفاده کنید.',
        ],
        'related_solution': {
            'title': 'راه‌حل: پیگیری مشتری',
            'url_name': 'platform_solutions_page',
            'url_kwargs': {'slug': 'customer-follow-up'},
        },
        'related_links': [
            {
                'title': 'خط محصول CRM',
                'url_name': 'platform_features_page',
                'url_kwargs': {'slug_path': 'crm'},
            },
            {
                'title': 'اتوماسیون CRM',
                'url_name': 'blog:post_detail',
                'url_kwargs': {'slug': 'automation-crm-5-ghanon-pigiri-rahnama'},
            },
        ],
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
            {
                'q': 'تفاوت با صفحه CRM چیست؟',
                'a': 'صفحه CRM کل خط محصول را نشان می‌دهد. این صفحه فقط روی یادآور، تقویم و صف امروز تمرکز دارد.',
            },
        ],
        'cta': _cta_block(),
    }


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
