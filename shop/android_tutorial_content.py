"""محتوای آموزش حرفه‌ای اپ اندروید فایلینگ دیوار."""
from __future__ import annotations

import json

from django.urls import reverse

from shop.templatetags.seo_tags import get_site_name, get_site_url
from shop.android_tutorial_video import get_all_android_videos_context


def android_tutorial_content() -> dict:
    content = {
        'hero': {
            'eyebrow': 'آموزش اپ اندروید',
            'title': 'همه‌چیز در جیب شما',
            'title_accent': 'از نصب تا معامله',
            'lead': (
                'اپ فایلینگ دیوار همان میزکار مشاور را روی موبایل می‌آورد: '
                'استخراج آگهی، فایلینگ، CRM، اعلان تطبیق ملک و یادآور مشتری. '
                'این راهنما گام‌به‌گام، با ویدیو و تصویر واقعی از اپ آموزش می‌دهد.'
            ),
            'highlights': [
                {'icon': 'fa-mobile-screen', 'text': 'Android 8.0 و بالاتر'},
                {'icon': 'fa-key', 'text': 'ورود با حساب میزکار — بدون کپی کلید'},
                {'icon': 'fa-bell', 'text': 'اعلان تطبیق ملک و یادآور'},
            ],
        },
        'stats': [
            {'num': '۶', 'label': 'فصل آموزشی'},
            {'num': '۲۴+', 'label': 'درس تصویری'},
            {'num': '۷', 'label': 'ویدیوی آموزشی'},
            {'num': 'رایگان', 'label': 'CRM بدون لایسنس'},
        ],
        'chapters': [
            {
                'id': 'install',
                'num': '۰۱',
                'title': 'نصب و آماده‌سازی',
                'subtitle': 'دانلود APK تا اولین باز کردن',
                'accent': 'emerald',
                'icon': 'fa-download',
                'decor_icon': 'download',
                'video_key': 'install',
                'anchor': 'chapter-install',
            },
            {
                'id': 'login',
                'num': '۰۲',
                'title': 'ورود و فعال‌سازی',
                'subtitle': 'حساب میزکار و دسترسی لایسنس',
                'accent': 'violet',
                'icon': 'fa-right-to-bracket',
                'decor_icon': 'sparkles',
                'video_key': 'login',
                'anchor': 'chapter-login',
            },
            {
                'id': 'extract',
                'num': '۰۳',
                'title': 'استخراج آگهی',
                'subtitle': 'شهر، فیلتر و زمان‌بندی',
                'accent': 'sky',
                'icon': 'fa-robot',
                'decor_icon': 'rocket',
                'video_key': 'extract',
                'anchor': 'chapter-extract',
            },
            {
                'id': 'filing',
                'num': '۰۴',
                'title': 'فایلینگ موبایل',
                'subtitle': 'فایل‌ها، لیست و جزئیات آگهی',
                'accent': 'amber',
                'icon': 'fa-folder-open',
                'decor_icon': 'folder',
                'video_key': 'filing',
                'anchor': 'chapter-filing',
            },
            {
                'id': 'crm',
                'num': '۰۵',
                'title': 'CRM و مشتریان',
                'subtitle': 'مشتری، معامله و ملک',
                'accent': 'rose',
                'icon': 'fa-handshake',
                'decor_icon': 'users',
                'video_key': 'crm',
                'anchor': 'chapter-crm',
            },
            {
                'id': 'notifications',
                'num': '۰۶',
                'title': 'اعلان و امروز',
                'subtitle': 'تطبیق، یادآور و برنامه روز',
                'accent': 'cyan',
                'icon': 'fa-bell',
                'decor_icon': 'bell',
                'video_key': 'notifications',
                'anchor': 'chapter-notifications',
            },
        ],
        'hero_visual': [
            {'image': 'android/android-02-home.png', 'caption': 'داشبورد روزانه', 'accent': 'violet'},
            {'image': 'android/android-03-extract-city.png', 'caption': 'استخراج محله', 'accent': 'sky'},
            {'image': 'android/android-08-crm-contacts.png', 'caption': 'پرونده مشتری', 'accent': 'rose'},
            {'image': 'android/android-12-notifications.png', 'caption': 'اعلان تطبیق', 'accent': 'emerald'},
        ],
        'modules': [],
        'gallery': {
            'title': 'تصاویر واقعی از اپ',
            'subtitle': 'هر اسکرین‌شات دقیقاً همان رابط اپ است — کلیک کنید تا بزرگ شود',
            'categories': [
                {'id': 'all', 'label': 'همه', 'icon': 'fa-grid-2'},
                {'id': 'setup', 'label': 'نصب و ورود', 'icon': 'fa-mobile-screen'},
                {'id': 'extract', 'label': 'استخراج', 'icon': 'fa-robot'},
                {'id': 'filing', 'label': 'فایلینگ', 'icon': 'fa-folder-open'},
                {'id': 'crm', 'label': 'CRM', 'icon': 'fa-handshake'},
                {'id': 'daily', 'label': 'روزانه', 'icon': 'fa-calendar-day'},
            ],
            'items': [],
        },
        'tips': [
            {
                'icon': 'fa-wifi',
                'title': 'اینترنت پایدار',
                'text': 'برای استخراج و همگام‌سازی CRM به اینترنت نیاز دارید. در مترو یا مناطق ضعیف، ابتدا داده‌ها را همگام کنید.',
            },
            {
                'icon': 'fa-battery-three-quarters',
                'title': 'مصرف باتری',
                'text': 'استخراج طولانی در پس‌زمینه انجام می‌شود. گوشی را به شارژ وصل کنید یا از زمان‌بندی شبانه استفاده کنید.',
            },
            {
                'icon': 'fa-shield-halved',
                'title': 'امنیت نصب',
                'text': 'فقط از لینک رسمی divarfiling.ir دانلود کنید. هشدار Play Protect طبیعی است — راهنمای نصب را ببینید.',
            },
        ],
        'faq': [
            {
                'q': 'آیا برای اپ اندروید باید کلید لایسنس را دستی وارد کنم؟',
                'a': 'خیر. پس از خرید، با همان نام کاربری و رمز میزکار وارد شوید. دستگاه شما خودکار ثبت می‌شود. '
                     'کلید فقط برای ربات ویندوز لازم است.',
            },
            {
                'q': 'CRM رایگان است یا نیاز به لایسنس دارد؟',
                'a': 'مدیریت مشتری، ملک و معامله رایگان است. استخراج آگهی و فایلینگ پیشرفته نیاز به لایسنس فعال دارد.',
            },
            {
                'q': 'Play Protect هشدار «App not recognized» می‌دهد',
                'a': 'اپ از Google Play منتشر نشده و مستقیم از سایت رسمی نصب می‌شود. '
                     'روی هشدار بزنید → More details → Install anyway. بخش نصب این صفحه را ببینید.',
            },
            {
                'q': 'اعلان تطبیق ملک کار نمی‌کند',
                'a': 'در تنظیمات اندروید اجازه اعلان را بدهید. در اپ هم از شما پرسیده می‌شود — «Allow» را بزنید. '
                     'برخی گوشی‌ها (شیائومی، سامسونگ) باید Battery optimization را برای اپ غیرفعال کنید.',
            },
            {
                'q': 'می‌توانم همزمان اندروید و ویندوز داشته باشم؟',
                'a': 'بله. هر لایسنس یک اسلات اندروید و یک اسلات ویندوز دارد. در اپ وارد شوید و در ویندوز کلید را فعال کنید.',
            },
            {
                'q': 'فایل استخراج کجا ذخیره می‌شود؟',
                'a': 'در بخش فایلینگ اپ و همزمان در میزکار وب شما. می‌توانید از موبایل لیست آگهی‌ها را ببینید و جزئیات هر ملک را مرور کنید.',
            },
            {
                'q': 'نسخه اندروید چند است و کجا به‌روز می‌شود؟',
                'a': 'نسخه فعلی روی صفحه دانلود نمایش داده می‌شود. APK جدید را از همین سایت بگیرید و روی نسخه قبلی نصب کنید — داده‌ها حفظ می‌شوند.',
            },
        ],
        'sections': {
            'videos': {
                'title': 'ویدیوهای آموزشی',
                'subtitle': 'هر فصل یک ویدیوی اختصاصی — با زیرنویس فارسی',
            },
            'curriculum': {
                'title': 'سرفصل کامل',
                'subtitle': 'از صفر تا حرفه‌ای — هر درس با تصویر و نکته کاربردی',
            },
            'cta': {
                'title': 'آماده شروع هستید؟',
                'subtitle': 'اپ را نصب کنید یا اگر هنوز لایسنس ندارید، CRM رایگان را امتحان کنید.',
            },
        },
    }

    content['modules'] = _build_modules()
    content['gallery']['items'] = _build_gallery_items()
    content['videos'] = get_all_android_videos_context()
    return content


def _lesson(num: str, title: str, desc: str, image: str, caption: str, **extra) -> dict:
    return {
        'num': num,
        'title': title,
        'desc': desc,
        'image': image,
        'image_caption': caption,
        **extra,
    }


def _build_modules() -> list[dict]:
    return [
        {
            'id': 'install',
            'anchor': 'chapter-install',
            'badge': 'فصل ۱',
            'title': 'نصب و آماده‌سازی',
            'desc': 'دانلود APK رسمی، عبور از Play Protect و تنظیم اولیه گوشی',
            'accent': 'emerald',
            'icon': 'fa-download',
            'cover_image': 'android/android-17-play-protect.png',
            'cover_caption': 'عبور از هشدار Play Protect',
            'video_key': 'install',
            'lessons': [
                _lesson('۱', 'دانلود APK از سایت رسمی', 'دکمه «دانلود APK» را بزنید. فایل در پوشه Downloads ذخیره می‌شود.', 'android/android-01-login.png', 'صفحه ورود — بعد از نصب'),
                _lesson('۲', 'فعال‌سازی منابع ناشناخته', 'برای Chrome یا Files اجازه «Install unknown apps» بدهید.', 'android/android-18-permissions.png', 'اجازه نصب از مرورگر'),
                _lesson('۳', 'عبور از Play Protect', 'روی هشدار بزنید → More details → Install anyway.', 'android/android-17-play-protect.png', 'نصب در هر صورت'),
                _lesson('۴', 'اولین باز کردن اپ', 'لوگوی فایلینگ دیوار را ببینید و به صفحه ورود بروید.', 'android/android-01-login.png', 'صفحه ورود'),
            ],
        },
        {
            'id': 'login',
            'anchor': 'chapter-login',
            'badge': 'فصل ۲',
            'title': 'ورود و فعال‌سازی',
            'desc': 'با همان حساب میزکار وارد شوید — لایسنس خودکار فعال می‌شود',
            'accent': 'violet',
            'icon': 'fa-right-to-bracket',
            'cover_image': 'android/android-01-login.png',
            'cover_caption': 'ورود با حساب میزکار',
            'video_key': 'login',
            'lessons': [
                _lesson('۱', 'ورود با نام کاربری و رمز', 'همان اطلاعاتی که در divarfiling.ir ثبت‌نام کردید.', 'android/android-01-login.png', 'فرم ورود'),
                _lesson('۲', 'ثبت خودکار دستگاه', 'نیازی به کپی کلید یا شناسه سخت‌افزار نیست.', 'android/android-02-home.png', 'داشبورد پس از ورود'),
                _lesson('۳', 'اجازه اعلان‌ها', 'برای تطبیق ملک و یادآور حتماً Allow بزنید.', 'android/android-12-notifications.png', 'مرکز اعلان‌ها'),
                _lesson('۴', 'بررسی وضعیت لایسنس', 'در تنظیمات یا داشبورد وضعیت فعال بودن را ببینید.', 'android/android-16-settings.png', 'تنظیمات اپ'),
            ],
        },
        {
            'id': 'extract',
            'anchor': 'chapter-extract',
            'badge': 'فصل ۳',
            'title': 'استخراج آگهی',
            'desc': 'انتخاب شهر و محله، فیلتر نوع معامله و اجرای استخراج',
            'accent': 'sky',
            'icon': 'fa-robot',
            'cover_image': 'android/android-03-extract-city.png',
            'cover_caption': 'انتخاب شهر و محله',
            'video_key': 'extract',
            'lessons': [
                _lesson('۱', 'ورود به بخش استخراج', 'از داشبورد یا منوی پایین «استخراج» را بزنید.', 'android/android-02-home.png', 'میانبر استخراج سریع'),
                _lesson('۲', 'انتخاب شهر و محله', 'شهر را انتخاب کنید و محله‌های هدف را تیک بزنید.', 'android/android-03-extract-city.png', 'فیلتر شهر'),
                _lesson('۳', 'تنظیم فیلترها', 'فروش/اجاره، متراژ، قیمت و نوع ملک را مشخص کنید.', 'android/android-04-extract-filters.png', 'فیلترهای پیشرفته'),
                _lesson('۴', 'شروع و پیگیری استخراج', 'نوار پیشرفت را ببینید. پس از اتمام اعلان می‌گیرید.', 'android/android-05-extract-running.png', 'استخراج در حال اجرا'),
                _lesson('۵', 'زمان‌بندی خودکار', 'استخراج شبانه یا هفتگی تنظیم کنید.', 'android/android-14-extract-schedule.png', 'زمان‌بندی استخراج'),
            ],
        },
        {
            'id': 'filing',
            'anchor': 'chapter-filing',
            'badge': 'فصل ۴',
            'title': 'فایلینگ موبایل',
            'desc': 'مرور فایل‌های استخراج، لیست آگهی و جزئیات هر ملک',
            'accent': 'amber',
            'icon': 'fa-folder-open',
            'cover_image': 'android/android-06-filing-list.png',
            'cover_caption': 'لیست فایل‌های فایلینگ',
            'video_key': 'filing',
            'lessons': [
                _lesson('۱', 'لیست فایل‌ها', 'هر استخراج یک فایل جدا — با تاریخ و محله.', 'android/android-06-filing-list.png', 'فایل‌های من'),
                _lesson('۲', 'مرور آگهی‌ها', 'اسکرول، جستجو و مرتب‌سازی بر اساس قیمت.', 'android/android-06-filing-list.png', 'جدول آگهی‌ها'),
                _lesson('۳', 'جزئیات آگهی', 'قیمت هر متر، تصاویر و توضیحات کامل.', 'android/android-07-listing-detail.png', 'صفحه جزئیات ملک'),
                _lesson('۴', 'اشتراک با مشتری', 'لینک آگهی را برای خریدار بفرستید.', 'android/android-07-listing-detail.png', 'اشتراک‌گذاری'),
            ],
        },
        {
            'id': 'crm',
            'anchor': 'chapter-crm',
            'badge': 'فصل ۵',
            'title': 'CRM و مشتریان',
            'desc': 'ثبت مشتری، پیگیری معامله، فایل ملک و تطبیق هوشمند',
            'accent': 'rose',
            'icon': 'fa-handshake',
            'cover_image': 'android/android-08-crm-contacts.png',
            'cover_caption': 'لیست مشتریان',
            'video_key': 'crm',
            'lessons': [
                _lesson('۱', 'لیست مشتریان', 'خریدار، مالک و سرنخ — با فیلتر و جستجو.', 'android/android-08-crm-contacts.png', 'دفترچه مشتری'),
                _lesson('۲', 'پرونده مشتری', 'تاریخچه تماس، بودجه و ملک‌های پیشنهادی.', 'android/android-09-crm-contact-detail.png', 'جزئیات مشتری'),
                _lesson('۳', 'قیف معامله', 'از بازدید تا قرارداد — هر مرحله را ثبت کنید.', 'android/android-10-deals.png', 'پیگیری معاملات'),
                _lesson('۴', 'فایل‌های ملک', 'ملک‌های آژانس را اضافه و مدیریت کنید.', 'android/android-11-properties.png', 'املاک من'),
                _lesson('۵', 'ابزارهای کارشناسی', 'تبدیل رهن و اجاره، محاسبه سریع.', 'android/android-15-tools.png', 'ابزارهای هوشمند'),
            ],
        },
        {
            'id': 'notifications',
            'anchor': 'chapter-notifications',
            'badge': 'فصل ۶',
            'title': 'اعلان‌ها و کارهای امروز',
            'desc': 'تطبیق ملک با مشتری، یادآور تماس و برنامه روزانه',
            'accent': 'cyan',
            'icon': 'fa-bell',
            'cover_image': 'android/android-13-today-tasks.png',
            'cover_caption': 'کارهای امروز',
            'video_key': 'notifications',
            'lessons': [
                _lesson('۱', 'مرکز اعلان‌ها', 'همه اعلان‌ها در یک جا — تطبیق، استخراج، فایل جدید.', 'android/android-12-notifications.png', 'لیست اعلان‌ها'),
                _lesson('۲', 'تطبیق ملک', 'وقتی آگهی جدید با مشتری هم‌خوان شد اعلان می‌گیرید.', 'android/android-12-notifications.png', 'اعلان تطبیق'),
                _lesson('۳', 'کارهای امروز', 'تماس‌ها، بازدیدها و پیگیری‌های امروز.', 'android/android-13-today-tasks.png', 'برنامه روز'),
                _lesson('۴', 'یادآور تماس و بازدید', 'یادآور را از پرونده مشتری تنظیم کنید.', 'android/android-09-crm-contact-detail.png', 'تنظیم یادآور'),
            ],
        },
    ]


def _build_gallery_items() -> list[dict]:
    items = [
        ('android/android-01-login.png', 'صفحه ورود', 'setup', 'violet'),
        ('android/android-02-home.png', 'داشبورد اصلی', 'setup', 'violet'),
        ('android/android-17-play-protect.png', 'هشدار Play Protect', 'setup', 'emerald'),
        ('android/android-18-permissions.png', 'اجازه نصب APK', 'setup', 'emerald'),
        ('android/android-03-extract-city.png', 'انتخاب شهر', 'extract', 'sky'),
        ('android/android-04-extract-filters.png', 'فیلتر استخراج', 'extract', 'sky'),
        ('android/android-05-extract-running.png', 'استخراج در حال اجرا', 'extract', 'sky'),
        ('android/android-14-extract-schedule.png', 'زمان‌بندی خودکار', 'extract', 'sky'),
        ('android/android-06-filing-list.png', 'لیست فایلینگ', 'filing', 'amber'),
        ('android/android-07-listing-detail.png', 'جزئیات آگهی', 'filing', 'amber'),
        ('android/android-08-crm-contacts.png', 'مشتریان', 'crm', 'rose'),
        ('android/android-09-crm-contact-detail.png', 'پرونده مشتری', 'crm', 'rose'),
        ('android/android-10-deals.png', 'معاملات', 'crm', 'rose'),
        ('android/android-11-properties.png', 'فایل ملک', 'crm', 'rose'),
        ('android/android-15-tools.png', 'ابزار کارشناسی', 'crm', 'amber'),
        ('android/android-12-notifications.png', 'اعلان‌ها', 'daily', 'cyan'),
        ('android/android-13-today-tasks.png', 'کارهای امروز', 'daily', 'cyan'),
        ('android/android-16-settings.png', 'تنظیمات', 'daily', 'emerald'),
    ]
    return [
        {'image': img, 'caption': cap, 'category': cat, 'accent': accent}
        for img, cap, cat, accent in items
    ]


def android_tutorial_schema_json(request=None) -> str:
    """JSON-LD ترکیبی: SoftwareApplication + HowTo + FAQPage + BreadcrumbList."""
    site_url = get_site_url()
    site_name = get_site_name()
    page_path = reverse('android_tutorial')
    page_url = f'{site_url}{page_path}'
    if request:
        page_url = request.build_absolute_uri()

    content = android_tutorial_content()
    howto_steps = []
    for mod in content['modules']:
        for lesson in mod['lessons']:
            howto_steps.append({
                '@type': 'HowToStep',
                'position': len(howto_steps) + 1,
                'name': f"{mod['title']} — {lesson['title']}",
                'text': lesson['desc'],
                'url': f"{page_url}#{mod['anchor']}",
            })

    faq_entities = [
        {
            '@type': 'Question',
            'name': item['q'],
            'acceptedAnswer': {'@type': 'Answer', 'text': item['a']},
        }
        for item in content['faq']
    ]

    graph = [
        {
            '@type': 'WebPage',
            '@id': f'{page_url}#webpage',
            'url': page_url,
            'name': 'آموزش اپ اندروید فایلینگ دیوار',
            'description': (
                'راهنمای کامل نصب، ورود، استخراج آگهی، فایلینگ، CRM و اعلان‌ها '
                'در اپ موبایل فایلینگ دیوار برای مشاوران املاک.'
            ),
            'inLanguage': 'fa-IR',
            'isPartOf': {'@type': 'WebSite', 'name': site_name, 'url': site_url},
        },
        {
            '@type': 'BreadcrumbList',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'خانه', 'item': site_url},
                {'@type': 'ListItem', 'position': 2, 'name': 'آموزش', 'item': f'{site_url}{reverse("education")}'},
                {'@type': 'ListItem', 'position': 3, 'name': 'آموزش اپ اندروید', 'item': page_url},
            ],
        },
        {
            '@type': 'SoftwareApplication',
            'name': 'اپ فایلینگ دیوار — اندروید',
            'applicationCategory': 'BusinessApplication',
            'operatingSystem': 'Android 8.0+',
            'description': content['hero']['lead'],
            'url': page_url,
            'inLanguage': 'fa-IR',
            'offers': {
                '@type': 'Offer',
                'priceCurrency': 'IRR',
                'availability': 'https://schema.org/InStock',
            },
            'creator': {'@type': 'Organization', 'name': site_name, 'url': site_url},
        },
        {
            '@type': 'HowTo',
            'name': 'آموزش کامل اپ اندروید فایلینگ دیوار',
            'description': content['hero']['lead'],
            'inLanguage': 'fa-IR',
            'step': howto_steps[:30],
        },
        {
            '@type': 'FAQPage',
            'mainEntity': faq_entities,
        },
    ]

    payload = {'@context': 'https://schema.org', '@graph': graph}
    return json.dumps(payload, ensure_ascii=False)
