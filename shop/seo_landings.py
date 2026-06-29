"""
لندینگ‌های سئو — Wave 1 و گسترش بعدی.
محتوا: ۱۲۰۰–۱۸۰۰ کلمه با ارزش؛ بدون padding.
"""
from __future__ import annotations

import json
from typing import Any

from django.urls import path, reverse

from shop.templatetags.seo_tags import get_site_name, get_site_url

# slugهای فعال — Wave 1
WAVE1_SLUGS = (
    'real-estate-crm',
    'real-estate-software',
    'robot-divar',
)

LANDING_SLUGS = WAVE1_SLUGS


def landing_url_name(slug: str) -> str:
    return f'seo_landing_{slug.replace("-", "_")}'


def _link(slug: str, label: str, desc: str = '') -> dict[str, str]:
    return {
        'label': label,
        'desc': desc,
        'url_name': landing_url_name(slug),
    }


def _section(title: str, paragraphs: list[str], subsections: list[dict] | None = None) -> dict:
    return {
        'title': title,
        'paragraphs': paragraphs,
        'subsections': subsections or [],
    }


def _subsection(title: str, text: str) -> dict:
    return {'title': title, 'text': text}


def _pill(icon: str, accent: str, text: str) -> dict:
    return {'icon': icon, 'accent': accent, 'text': text}


def _shot(image: str, caption: str, accent: str = 'violet', size: str = 'compact') -> dict:
    return {'image': image, 'caption': caption, 'accent': accent, 'size': size}


def _visuals(
    hero_image: str,
    hero_caption: str,
    hero_pills: list[dict],
    problem_image: str,
    problem_caption: str,
    showcase: dict,
    section_images: list[dict],
) -> dict:
    return {
        'hero_image': hero_image,
        'hero_caption': hero_caption,
        'hero_pills': hero_pills,
        'problem_image': problem_image,
        'problem_caption': problem_caption,
        'showcase': showcase,
        'section_images': section_images,
    }


LANDINGS: dict[str, dict[str, Any]] = {
    'real-estate-crm': {
        'slug': 'real-estate-crm',
        'meta_title': 'CRM مشاور املاک | CRM املاک رایگان آنلاین — فایلینگ دیوار',
        'meta_description': (
            'CRM املاک آنلاین و فارسی برای مشاوران: ثبت مشتری، قیف معامله، '
            'یادآور پیگیری و اتصال به آگهی دیوار. ثبت‌نام رایگان میزکار.'
        ),
        'meta_keywords': (
            'CRM مشاور املاک, CRM املاک آنلاین, CRM املاک رایگان, '
            'مدیریت مشتری مشاور املاک, نرم افزار CRM املاک'
        ),
        'hero': {
            'eyebrow': 'CRM املاک · میزکار فایلینگ دیوار',
            'icon': 'fa-users',
            'decor_icon': 'clipboard_list',
            'accent': 'violet',
            'h1': 'CRM مشاور املاک: مدیریت مشتری، قیف معامله و پیگیری روزانه — رایگان',
            'lead': (
                'دیگر مشتری گرم را در واتساپ گم نکنید. CRM املاک فایلینگ دیوار مشتری، '
                'معامله و فایل را در یک میزکار فارسی نگه می‌دارد — با یادآور پیگیری و '
                'اتصال مستقیم به آگهی‌های دیوار.'
            ),
        },
        'problem': {
            'title': 'بدون CRM، مشاور املاک هر روز مشتری از دست می‌دهد',
            'paragraphs': [
                'بیشتر مشاوران هنوز مشتری را در واتساپ، دفترچه یا فایل اکسل پراکنده نگه می‌دارند. '
                'تا وقتی تماس کم است جواب می‌دهد؛ ولی وقتی روزی ده تماس، پنج بازدید و چند پیشنهاد '
                'ملک دارید، چیزی گم می‌شود — معمولاً همان مشتری که دیروز گفت «فردا تصمیم می‌گیرم».',
                'CRM مشاور املاک یعنی هر خریدار و فروشنده یک پرونده دارد؛ هر تماس ثبت می‌شود؛ '
                'هر معامله مرحله‌به‌مرحله جلو می‌رود؛ و سیستم به شما می‌گوید امروز اول به کی زنگ بزنید.',
            ],
            'bullets': [
                'فراموشی پیگیری بعد از بازدید ملک',
                'نداشتن تصویر واحد از قیف معاملات تیم',
                'جدا بودن مشتری از فایل‌های دیوار',
            ],
        },
        'features': [
            {'icon': 'fa-address-book', 'decor_icon': 'clipboard_list', 'accent': 'violet', 'title': 'پروفایل مشتری', 'text': 'نیاز ملک، بودجه، محله ترجیحی و تاریخچه تماس'},
            {'icon': 'fa-filter', 'decor_icon': 'layers', 'accent': 'rose', 'title': 'قیف معامله', 'text': 'مراحل از سرنخ تا قرارداد با نمای کانبان'},
            {'icon': 'fa-bell', 'decor_icon': 'sticky_note', 'accent': 'amber', 'title': 'یادآور پیگیری', 'text': 'صف کار امروز و تقویم برای تماس به‌موقع'},
            {'icon': 'fa-link', 'decor_icon': 'map_pin', 'accent': 'emerald', 'title': 'اتصال به دیوار', 'text': 'تطبیق مشتری با فایل استخراج‌شده از آگهی'},
            {'icon': 'fa-users-cog', 'decor_icon': 'share_2', 'accent': 'sky', 'title': 'تیم آژانس', 'text': 'سهم فایل و مشتری بین مشاوران'},
            {'icon': 'fa-comment-dots', 'decor_icon': 'file_text', 'accent': 'cyan', 'title': 'قالب پیام', 'text': 'پیام‌های آماده فارسی برای پیگیری سریع'},
        ],
        'comparison': {
            'title': 'CRM فایلینگ دیوار در برابر روش سنتی',
            'headers': ['معیار', 'واتساپ + اکسل', 'CRM فایلینگ دیوار'],
            'rows': [
                ['پیگیری مشتری', 'یادآوری دستی', 'یادآور و صف امروز'],
                ['وضعیت معامله', 'نامشخص', 'قیف شفاف'],
                ['اتصال به آگهی دیوار', 'کپی دستی', 'یکپارچه با فایلینگ'],
                ['هزینه شروع', 'رایگان ولی پرهزینه زمانی', 'میزکار CRM رایگان'],
            ],
        },
        'sections': [
            _section(
                'CRM املاک چیست و چرا برای مشاور ضروری است؟',
                [
                    'نرم‌افزار CRM املاک ابزاری است که روابط با خریدار، فروشنده و سرنخ را '
                    'به‌جای حافظه و پیام پراکنده، در یک سیستم متمرکز نگه می‌دارد. '
                    'برای مشاور مستقل یعنی هیچ تماسی بی‌پاسخ نمی‌ماند؛ برای آژانس یعنی مدیر '
                    'می‌بیند هر معامله کجای قیف است.',
                ],
                [
                    _subsection(
                        'تفاوت CRM املاک با دفترچه تماس',
                        'دفترچه فقط شماره ذخیره می‌کند؛ CRM املاک نیاز ملک، اولویت، مرحله معامله '
                        'و تاریخ پیگیری بعدی را ثبت می‌کند.',
                    ),
                    _subsection(
                        'چرا CRM باید فارسی و بومی باشد',
                        'CRMهای عمومی برای فروشگاه طراحی شده‌اند. مشاور املاک به قیف معامله ملکی، '
                        'یادآور بازدید و زبان فارسی در رابط کاربری نیاز دارد.',
                    ),
                ],
            ),
            _section(
                'امکانات CRM میزکار فایلینگ دیوار',
                [
                    'میزکار فایلینگ دیوار CRM املاک را در کنار فایلینگ و تحلیل بازار قرار داده — '
                    'نه به‌عنوان افزونه جدا. وقتی آگهی جدید از دیوار استخراج می‌شود، می‌توانید '
                    'همان فایل را به مشتری مناسب پیشنهاد دهید.',
                ],
                [
                    _subsection('مدیریت مشتری مشاور املاک', 'ثبت خریدار و فروشنده با برچسب، منبع سرنخ و یادداشت جلسه.'),
                    _subsection('مدیریت معاملات املاک', 'تعریف مراحل معامله، مسئول پرونده و تاریخچه تغییر وضعیت.'),
                    _subsection('CRM املاک رایگان', 'ثبت‌نام میزکار بدون هزینه اولیه — مناسب شروع حرفه‌ای.'),
                ],
            ),
            _section(
                'برای چه کسانی مناسب است؟',
                [
                    'مشاور مستقل که می‌خواهد حرفه‌ای‌تر از رقبای محله عمل کند؛ '
                    'آژانس دو تا ده نفره که به شفافیت قیف نیاز دارد؛ و تیم‌هایی که '
                    'هم‌زمان با فایلینگ دیوار کار می‌کنند و نمی‌خواهند بین پنج ابزار جابه‌جا شوند.',
                ],
            ),
        ],
        'visuals': _visuals(
            hero_image='images/help-crm-dashboard.png',
            hero_caption='داشبورد CRM — خلاصه مشتریان، پیگیری‌های معوق و وضعیت روز',
            hero_pills=[
                _pill('fa-gift', 'emerald', 'CRM رایگان'),
                _pill('fa-filter', 'violet', 'قیف کانبان'),
                _pill('fa-bell', 'amber', 'صف امروز'),
                _pill('fa-link', 'sky', 'اتصال دیوار'),
            ],
            problem_image='images/help-crm-today.png',
            problem_caption='بدون CRM — تماس‌های امروز در حافظه و واتساپ پراکنده می‌مانند',
            showcase={
                'kicker': 'نمای میزکار',
                'title': 'CRM املاک در عمل — نه فقط تبلیغ',
                'desc': 'صف پیگیری، قیف معامله و پرونده مشتری — همان ابزاری که مشاوران حرفه‌ای هر روز باز می‌کنند.',
                'items': [
                    _shot('images/help-crm-deals.png', 'قیف معامله — از بازدید تا قرارداد', 'violet', 'wide'),
                    _shot('images/help-crm-contacts.png', 'پرونده مشتری با بودجه و محله', 'rose'),
                    _shot('images/help-crm-reminders.png', 'یادآور تماس — هیچ پیگیری گم نمی‌شود', 'amber'),
                    _shot('images/help-crm-templates.png', 'قالب پیام آماده برای واتساپ', 'sky'),
                    _shot('images/help-crm-calendar.png', 'تقویم بازدید و قرار', 'emerald'),
                    _shot('images/help-crm-team.png', 'تیم آژانس — مشتری مشخص', 'indigo'),
                ],
            },
            section_images=[
                {'image': 'images/help-crm-contact-detail.png', 'caption': 'تاریخچه تماس و نیاز ملک'},
                {'image': 'images/help-crm-properties.png', 'caption': 'فایل‌های ملک متصل به مشتری'},
                {'image': 'images/help-crm-automation.png', 'caption': 'پیگیری خودکار و قالب پیام'},
            ],
        ),
        'steps': {
            'title': 'شروع در سه قدم',
            'items': [
                {'n': '۱', 'title': 'ثبت‌نام رایگان', 'text': 'میزکار CRM را در کمتر از دو دقیقه بسازید.'},
                {'n': '۲', 'title': 'وارد کردن مشتریان', 'text': 'مشتری فعلی را اضافه کنید یا از سرنخ دیوار شروع کنید.'},
                {'n': '۳', 'title': 'پیگیری روزانه', 'text': 'صف امروز را باز کنید و تماس‌های اولویت‌دار را انجام دهید.'},
            ],
        },
        'faq': [
            ('آیا CRM فایلینگ دیوار واقعاً رایگان است؟', 'بله. میزکار CRM با ثبت‌نام رایگان در دسترس است؛ ربات استخراج و برخی ماژول‌های پیشرفته پلن جدا دارند.'),
            ('چند مشتری می‌توانم ثبت کنم؟', 'محدودیت سخت‌گیرانه‌ای برای شروع نداریم؛ میزکار برای کار روزانه مشاور و تیم کوچک طراحی شده است.'),
            ('آیا یادآور پیگیری دارد؟', 'بله — صف کار امروز، یادآور و تقویم برای پیگیری به‌موقع مشتری.'),
            ('آیا با آگهی‌های دیوار لینک می‌شود؟', 'بله. فایل‌های استخراج‌شده در میزکار قابل تطبیق با نیاز مشتریان CRM است.'),
            ('تفاوت با CRMهای عمومی چیست؟', 'تمرکز بر املاک ایران، فارسی کامل و یکپارچگی با فایلینگ و ربات دیوار.'),
            ('آیا برای تیم چندنفره مناسب است؟', 'بله — امکانات آژانس و سهم فایل بین مشاوران پشتیبانی می‌شود.'),
        ],
        'internal_links': [
            _link('real-estate-software', 'نرم افزار مشاور املاک', 'میزکار جامع شامل CRM'),
            _link('robot-divar', 'ربات دیوار', 'تغذیه CRM از آگهی‌های تازه'),
            {'label': 'مقاله CRM املاک', 'desc': 'راهنمای انتخاب نرم‌افزار', 'url_name': 'blog:post_list'},
        ],
        'cta_mid_title': 'CRM املاک رایگان را همین امروز امتحان کنید',
        'cta_final_title': 'مشتری بعدی را از دست ندهید — میزکار آماده است',
    },
    'real-estate-software': {
        'slug': 'real-estate-software',
        'meta_title': 'نرم افزار مشاور املاک | ابزار ایرانی حرفه‌ای — فایلینگ دیوار',
        'meta_description': (
            'نرم افزار مشاور املاک ایرانی: CRM رایگان، ربات دیوار، فایلینگ، '
            'تحلیل بازار و نقشه — جایگزین ابزارهای پراکنده. شروع رایگان.'
        ),
        'meta_keywords': (
            'نرم افزار مشاور املاک, ابزار مشاور املاک, نرم افزار ایرانی مشاور املاک, '
            'سیستم مدیریت مشاور املاک, نرم افزار املاک'
        ),
        'hero': {
            'eyebrow': 'نرم افزار املاک · پلتفرم یکپارچه',
            'icon': 'fa-laptop-code',
            'decor_icon': 'layers',
            'accent': 'emerald',
            'h1': 'نرم افزار مشاور املاک: میزکار ایرانی برای CRM، فایلینگ، استخراج و تحلیل بازار',
            'lead': (
                'به‌جای پنج ابزار جدا — یک نرم‌افزار مشاور املاک که استخراج دیوار، '
                'مدیریت مشتری، فایلینگ و تحلیل قیمت را در میزکار فارسی جمع می‌کند. '
                'ساخته‌شده برای بازار ایران.'
            ),
        },
        'problem': {
            'title': 'مشاور مدرن گرفتار ابزارهای پراکنده است',
            'paragraphs': [
                'یک روز در دیوار می‌گردید، فایل را در اکسل می‌ریزید، مشتری را در واتساپ پیگیری می‌کنید '
                'و برای تحلیل قیمت دوباره دستی جستجو می‌زنید. هر سوئیچ بین ابزار، زمان و تمرکز می‌گیرد.',
                'نرم افزار مشاور املاک حرفه‌ای باید کل گردش کار را پوشش دهد — نه فقط یک بخش آن.',
            ],
            'bullets': [
                'هزینه پنهان سوئیچ بین اپ‌ها',
                'ناسازگاری داده بین CRM و فایل',
                'وابستگی به ابزارهای غیرتخصصی املاک',
            ],
        },
        'features': [
            {'icon': 'fa-layer-group', 'decor_icon': 'layers', 'accent': 'violet', 'title': 'میزکار یکپارچه', 'text': 'CRM، فایلینگ، تحلیل و ابزار در یک پنل'},
            {'icon': 'fa-robot', 'decor_icon': 'rocket', 'accent': 'indigo', 'title': 'ربات دیوار', 'text': 'استخراج خودکار آگهی با خروجی ساختاریافته'},
            {'icon': 'fa-chart-line', 'decor_icon': 'sparkles', 'accent': 'amber', 'title': 'تحلیل بازار', 'text': 'میانگین قیمت و روند محله بر اساس داده دیوار'},
            {'icon': 'fa-map', 'decor_icon': 'map_pin', 'accent': 'sky', 'title': 'نقشه Pro', 'text': 'نمایش فایل و قیمت روی نقشه'},
            {'icon': 'fa-gift', 'decor_icon': 'sticky_note', 'accent': 'emerald', 'title': 'شروع رایگان', 'text': 'CRM و میزکار بدون هزینه اولیه'},
            {'icon': 'fa-flag', 'decor_icon': 'share_2', 'accent': 'rose', 'title': 'نرم افزار ایرانی', 'text': 'فارسی، پشتیبانی بومی، مناسب بازار داخل'},
        ],
        'comparison': {
            'title': 'یک نرم‌افزار در برابر ترکیب ابزارهای جدا',
            'headers': ['نیاز روزانه', 'روش پراکنده', 'فایلینگ دیوار'],
            'rows': [
                ['جمع‌آوری آگهی', 'کپی دستی دیوار', 'ربات استخراج'],
                ['مدیریت مشتری', 'واتساپ + دفترچه', 'CRM املاک'],
                ['تحلیل قیمت', 'حدس و تجربه', 'داده زنده دیوار'],
                ['هزینه ماهانه', 'چند اشتراک جدا', 'میزکار رایگان + ربات اختیاری'],
            ],
        },
        'sections': [
            _section(
                'اجزای یک نرم افزار کامل مشاور املاک',
                [
                    'نرم افزار املاک حرفه‌ای چهار لایه دارد: ورود داده (استخراج آگهی)، '
                    'سازماندهی (فایلینگ)، رابطه با مشتری (CRM) و تصمیم‌گیری (تحلیل و قیمت‌گذاری). '
                    'فایلینگ دیوار هر چهار لایه را در یک برند و یک میزکار ادغام کرده است.',
                ],
                [
                    _subsection('سیستم مدیریت مشاور املاک', 'داشبورد روزانه، صف کار، یادآور و گزارش فعالیت تیم.'),
                    _subsection('نرم افزار آژانس املاک', 'مدیریت چند مشاور، سهم فایل و قیف مشترک.'),
                    _subsection('ابزار مشاور املاک روزانه', 'مقایسه فایل، نقشه، قیمت‌گذاری و خروجی برای مشتری.'),
                ],
            ),
            _section(
                'چرا نرم افزار ایرانی مشاور املاک مهم است؟',
                [
                    'بازار املاک ایران زبان، قوانین کاربری و رفتار خریدار خاص خود را دارد. '
                    'دیوار منبع اصلی آگهی است؛ CRM باید فارسی باشد؛ و پشتیبانی باید در همان '
                    'منطقه زمانی پاسخ دهد. نرم‌افزارهای خارجی یا عمومی این بافت را ندارند.',
                ],
            ),
            _section(
                'مسیر پیشنهادی برای شروع',
                [
                    'ابتدا میزکار و CRM رایگان را فعال کنید و مشتریان فعلی را وارد کنید. '
                    'سپس در صورت نیاز به حجم بالای آگهی، ربات استخراج دیوار را اضافه کنید. '
                    'تحلیل بازار و قیمت‌گذاری روی همان دیتاست انجام می‌شود — بدون export مجدد.',
                ],
            ),
        ],
        'visuals': _visuals(
            hero_image='images/help-workspace-home.png',
            hero_caption='میزکار یکپارچه — CRM، فایلینگ، تحلیل و ابزار در یک پنل',
            hero_pills=[
                _pill('fa-layer-group', 'violet', 'پلتفرم یکپارچه'),
                _pill('fa-flag', 'emerald', 'نرم‌افزار ایرانی'),
                _pill('fa-chart-line', 'amber', 'تحلیل بازار'),
                _pill('fa-gift', 'sky', 'شروع رایگان'),
            ],
            problem_image='images/help-tools-panel.png',
            problem_caption='ابزارهای پراکنده — سوئیچ مداوم بین دیوار، اکسل و واتساپ',
            showcase={
                'kicker': 'اکوسیستم میزکار',
                'title': 'هر ماژول، یک تصویر از کار واقعی',
                'desc': 'از آپلود فایل تا تحلیل قیمت و نقشه — همه در یک برند و یک حساب کاربری.',
                'items': [
                    _shot('images/help-analyze-dashboard.png', 'تحلیل قیمت و روند محله', 'amber', 'wide'),
                    _shot('images/help-map-view.png', 'آگهی‌ها روی نقشه', 'sky'),
                    _shot('images/help-dataset-table.png', 'فیلتر و جستجو در فایلینگ', 'emerald'),
                    _shot('images/help-upload-bulk.png', 'آپلود گروهی چند محله', 'violet'),
                    _shot('images/help-compare-files.png', 'مقایسه قیمت بین مناطق', 'rose'),
                    _shot('images/help-crm-dashboard.png', 'CRM در کنار فایل و تحلیل', 'indigo'),
                ],
            },
            section_images=[
                {'image': 'images/help-bot-extract-tab.png', 'caption': 'ورود داده — استخراج از دیوار'},
                {'image': 'images/help-listing-detail.png', 'caption': 'سازماندهی — جزئیات هر آگهی'},
                {'image': 'images/help-crm-deals.png', 'caption': 'تصمیم‌گیری — قیف معامله'},
            ],
        ),
        'steps': {
            'title': 'از ثبت‌نام تا میزکار حرفه‌ای',
            'items': [
                {'n': '۱', 'title': 'ثبت‌نام رایگان', 'text': 'دسترسی فوری به CRM و میزکار.'},
                {'n': '۲', 'title': 'سازماندهی مشتری و فایل', 'text': 'پرونده‌ها را متمرکز کنید.'},
                {'n': '۳', 'title': 'افزودن ربات (اختیاری)', 'text': 'استخراج خودکار برای مقیاس بیشتر.'},
            ],
        },
        'faq': [
            ('آیا جایگزین همه ابزارها می‌شود؟', 'برای گردش کار اصلی مشاور املاک — استخراج، CRM، فایلینگ و تحلیل — بله.'),
            ('فقط آنلاین است یا نرم‌افزار ویندوز هم دارید؟', 'میزکار وب‌بیس است؛ ربات استخراج روی ویندوز نصب می‌شود.'),
            ('تفاوت با نرم‌افزارهای خارجی چیست؟', 'تمرکز بر دیوار، فارسی کامل و قیمت‌گذاری مناسب بازار ایران.'),
            ('آموزش استفاده دارد؟', 'بله — مرکز آموزش و راهنمای نصب ربات در سایت موجود است.'),
            ('پشتیبانی فارسی؟', 'بله — تیم پشتیبانی فارسی‌زبان.'),
        ],
        'internal_links': [
            _link('real-estate-crm', 'CRM مشاور املاک', 'ماژول مدیریت مشتری'),
            _link('robot-divar', 'ربات دیوار', 'استخراج آگهی برای میزکار'),
            {'label': 'مرکز آموزش', 'desc': 'مسیرهای یادگیری', 'url_name': 'education'},
        ],
        'cta_mid_title': 'نرم‌افزار مشاور املاک را رایگان شروع کنید',
        'cta_final_title': 'یک میزکار به‌جای پنج ابزار — همین الان',
    },
    'robot-divar': {
        'slug': 'robot-divar',
        'meta_title': 'ربات دیوار | استخراج آگهی املاک از دیوار — فایلینگ دیوار',
        'meta_description': (
            'ربات استخراج آگهی دیوار برای مشاوران: جمع‌آوری خودکار، فیلتر شهر و محله، '
            'خروجی اکسل و اتصال به CRM رایگان. مشاهده قیمت و فعال‌سازی.'
        ),
        'meta_keywords': (
            'ربات دیوار, ربات استخراج آگهی دیوار, خرید ربات دیوار, '
            'استخراج آگهی دیوار, ربات جمع آوری آگهی دیوار'
        ),
        'hero': {
            'eyebrow': 'ربات استخراج · ویندوز + میزکار',
            'icon': 'fa-robot',
            'decor_icon': 'rocket',
            'accent': 'indigo',
            'h1': 'ربات دیوار: استخراج خودکار آگهی املاک با خروجی اکسل و اتصال به میزکار',
            'lead': (
                'دیگر لازم نیست ساعت‌ها در دیوار بگردید. ربات دیوار فایلینگ، آگهی‌های جدید را '
                'با فیلتر شهر و محله جمع می‌کند، در اکسل یا میزکار ساختاردهی می‌کند و '
                'مستقیم به CRM شما وصل می‌شود.'
            ),
        },
        'problem': {
            'title': 'جمع‌آوری دستی آگهی دیوار وقت طلایی مشاور را می‌گیرد',
            'paragraphs': [
                'هر مشاور حرفه‌ای می‌داند: فایل تازه یعنی تماس زودتر با فروشنده. '
                'ولی جستجوی دستی در دیوار کند است، تکراری است و آگهی‌های تازه '
                'بین جلسات از دست می‌روند.',
                'ربات استخراج آگهی دیوار این حلقه را خودکار می‌کند — با فیلتر دقیق '
                'و خروجی آماده برای فایلینگ و CRM.',
            ],
            'bullets': [
                'ساعت‌ها اسکرول در لیست آگهی',
                'کپی ناقص اطلاعات تماس و متراژ',
                'فایل اکسل که به‌روز نمی‌ماند',
            ],
        },
        'features': [
            {'icon': 'fa-sliders-h', 'decor_icon': 'ruler', 'accent': 'violet', 'title': 'فیلتر پیشرفته', 'text': 'شهر، محله، متراژ، قیمت و نوع ملک'},
            {'icon': 'fa-file-excel', 'decor_icon': 'download', 'accent': 'emerald', 'title': 'خروجی اکسل', 'text': 'داده ساختاریافته برای تحلیل و اشتراک'},
            {'icon': 'fa-sync', 'decor_icon': 'upload', 'accent': 'sky', 'title': 'به‌روزرسانی دوره‌ای', 'text': 'اجرای مجدد برای آگهی‌های تازه'},
            {'icon': 'fa-upload', 'decor_icon': 'layers', 'accent': 'amber', 'title': 'آپلود به میزکار', 'text': 'ورود یک‌کلیکی به فایلینگ و CRM'},
            {'icon': 'fab fa-windows', 'decor_icon': 'rocket', 'accent': 'indigo', 'title': 'نصب ویندوز', 'text': 'ویندوز ۱۰ و ۱۱ — راهنمای نصب فارسی'},
            {'icon': 'fa-key', 'decor_icon': 'coins', 'accent': 'rose', 'title': 'لایسنس شفاف', 'text': 'پلن ماهانه با فعال‌سازی سریع'},
        ],
        'comparison': {
            'title': 'ربات دیوار در برابر روش دستی',
            'headers': ['معیار', 'دستی / اکسل', 'ربات فایلینگ دیوار'],
            'rows': [
                ['زمان جمع‌آوری', 'چند ساعت در روز', 'چند دقیقه در اجرا'],
                ['دقت داده', 'خطای تایپی', 'فیلدهای یکسان'],
                ['اتصال CRM', 'import دستی', 'یکپارچه با میزکار'],
                ['پوشش محله', 'محدود به حوصله', 'فیلتر دقیق منطقه'],
            ],
        },
        'sections': [
            _section(
                'ربات استخراج آگهی دیوار چیست؟',
                [
                    'ربات دیوار نرم‌افزار ویندوزی است که بر اساس فیلترهایی که مشاور تعیین می‌کند، '
                    'آگهی‌های املاک را از دیوار جمع‌آوری و در قالب قابل استفاده — اکسل یا دیتاست میزکار — '
                    'ذخیره می‌کند. هدف اصلی: سرعت تماس با فروشنده قبل از رقبا.',
                ],
                [
                    _subsection('ربات جمع‌آوری آگهی دیوار', 'اجرای زمان‌بندی‌شده یا دستی برای محله‌های هدف.'),
                    _subsection('خروجی اکسل آگهی دیوار', 'ستون‌های استاندارد برای متراژ، قیمت، محله و لینک آگهی.'),
                ],
            ),
            _section(
                'مراحل راه‌اندازی ربات دیوار',
                [
                    'پس از خرید لایسنس، ربات را روی ویندوز نصب می‌کنید، کلید را فعال می‌کنید و '
                    'اولین استخراج را با انتخاب شهر و فیلتر اجرا می‌کنید. راهنمای گام‌به‌گام '
                    'در صفحه راهنمای نصب موجود است.',
                ],
                [
                    _subsection('اتصال به CRM رایگان', 'داده استخراج‌شده بدون کار اضافه در میزکار قابل استفاده است.'),
                    _subsection('قیمت ربات استخراج دیوار', 'پلن‌های ماهانه روی صفحه محصول — شفاف و بدون هزینه پنهان.'),
                ],
            ),
            _section(
                'بعد از استخراج چه کنید؟',
                [
                    'آگهی خام ارزش کامل ندارد تا سازماندهی شود. مسیر حرفه‌ای: استخراج → فایلینگ در میزکار → '
                    'تطبیق با مشتریان CRM → تحلیل قیمت برای مذاکره. '
                    'ربات دیوار نقطه شروع این زنجیره است، نه پایان آن.',
                ],
            ),
        ],
        'visuals': _visuals(
            hero_image='images/help-bot-extract-tab.png',
            hero_caption='ربات دیوار — فیلتر شهر و محله، پیشرفت زنده و خروجی ساختاریافته',
            hero_pills=[
                _pill('fab fa-windows', 'indigo', 'ویندوز ۱۰/۱۱'),
                _pill('fa-file-excel', 'emerald', 'خروجی اکسل'),
                _pill('fa-upload', 'amber', 'آپلود میزکار'),
                _pill('fa-users', 'violet', 'اتصال CRM'),
            ],
            problem_image='images/help-bot-output-folder.png',
            problem_caption='جمع‌آوری دستی — ساعت‌ها کپی و فایل اکسل که به‌روز نمی‌ماند',
            showcase={
                'kicker': 'مسیر استخراج',
                'title': 'از نصب تا فایلینگ — گام‌به‌گام',
                'desc': 'نصب ربات، فعال‌سازی لایسنس، استخراج و ورود داده به میزکار — با تصاویر واقعی محصول.',
                'items': [
                    _shot('images/help-bot-install.png', 'نصب و اولین اجرای ربات', 'indigo', 'wide'),
                    _shot('images/help-bot-license.png', 'فعال‌سازی لایسنس', 'violet'),
                    _shot('images/help-bot-extract-tab.png', 'انتخاب شهر و فیلتر محله', 'sky'),
                    _shot('images/help-bot-output-folder.png', 'پوشه خروجی آماده آپلود', 'emerald'),
                    _shot('images/help-upload-single.png', 'آپلود به فایلینگ میزکار', 'amber'),
                    _shot('images/help-crm-contact-detail.png', 'تطبیق فایل با مشتری CRM', 'rose'),
                ],
            },
            section_images=[
                {'image': 'images/help-bot-license.png', 'caption': 'فعال‌سازی — آماده اولین استخراج'},
                {'image': 'images/help-dataset-table.png', 'caption': 'فایلینگ — لیست آگهی‌های ساختاریافته'},
                {'image': 'images/help-analyze-dashboard.png', 'caption': 'تحلیل — میانگین قیمت برای مذاکره'},
            ],
        ),
        'steps': {
            'title': 'راه‌اندازی در چهار قدم',
            'items': [
                {'n': '۱', 'title': 'ثبت‌نام میزکار', 'text': 'حساب رایگان برای اتصال داده.'},
                {'n': '۲', 'title': 'خرید لایسنس ربات', 'text': 'انتخاب پلن مناسب حجم کار.'},
                {'n': '۳', 'title': 'نصب روی ویندوز', 'text': 'طبق راهنمای فارسی نصب.'},
                {'n': '۴', 'title': 'اولین استخراج', 'text': 'فیلتر شهر و دریافت فایل.'},
            ],
        },
        'faq': [
            ('ربات دیوار چیست؟', 'نرم‌افزار استخراج خودکار آگهی املاک از دیوار با فیلتر و خروجی ساختاریافته.'),
            ('ربات روی چه سیستمی نصب می‌شود؟', 'ویندوز ۱۰ و ۱۱.'),
            ('خروجی چه فرمتی دارد؟', 'اکسل و ورود به دیتاست میزکار.'),
            ('آیا می‌توانم یک محله خاص را استخراج کنم؟', 'بله — فیلتر شهر و محله پشتیبانی می‌شود.'),
            ('قیمت ربات چقدر است؟', 'پلن‌های ماهانه روی صفحه محصول ربات درج شده است.'),
            ('آیا با CRM یکپارچه است؟', 'بله — میزکار CRM رایگان داده را دریافت می‌کند.'),
            ('استفاده از ربات قانونی است؟', 'ابزار برای استفاده حرفه‌ای مشاوران طراحی شده؛ مسئولیت رعایت قوانین دیوار با کاربر است.'),
        ],
        'internal_links': [
            _link('real-estate-crm', 'CRM مشاور املاک', 'مرحله بعدی بعد از استخراج'),
            _link('real-estate-software', 'نرم افزار مشاور املاک', 'پلتفرم کامل'),
            {'label': 'صفحه محصول و خرید', 'desc': 'پلن‌ها و لایسنس', 'url_name': 'product_detail', 'url_kwargs': {'slug': 'divar-extraction-bot'}},
            {'label': 'راهنمای نصب', 'desc': 'گام‌به‌گام فارسی', 'url_name': 'license_guide'},
        ],
        'cta_mid_title': 'ربات استخراج را فعال کنید — زمان را پس بگیرید',
        'cta_final_title': 'آگهی تازه را قبل از رقبا بگیرید',
        'product_cta': True,
    },
}


def get_landing(slug: str) -> dict[str, Any] | None:
    landing = LANDINGS.get(slug)
    if not landing:
        return None
    landing = dict(landing)
    visuals = landing.get('visuals') or {}
    section_images = visuals.get('section_images') or []
    sections = []
    for i, sec in enumerate(landing.get('sections', [])):
        s = dict(sec)
        if i < len(section_images):
            s['image'] = section_images[i]
        sections.append(s)
    landing['sections'] = sections
    return landing


def landing_schema_json(landing: dict[str, Any]) -> str:
    site_url = get_site_url()
    page_url = f'{site_url}/{landing["slug"]}/'
    schema = {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        'name': landing['hero']['h1'][:120],
        'applicationCategory': 'BusinessApplication',
        'operatingSystem': 'Windows, Web',
        'description': landing['meta_description'],
        'url': page_url,
        'inLanguage': 'fa-IR',
        'creator': {'@type': 'Organization', 'name': get_site_name(), 'url': site_url},
        'offers': {
            '@type': 'Offer',
            'priceCurrency': 'IRR',
            'availability': 'https://schema.org/InStock',
        },
    }
    return json.dumps(schema, ensure_ascii=False)


def landing_urlpatterns():
    from shop import views

    return [
        path(
            f'{slug}/',
            views.SeoLandingView.as_view(),
            {'landing_slug': slug},
            name=landing_url_name(slug),
        )
        for slug in LANDING_SLUGS
    ]
