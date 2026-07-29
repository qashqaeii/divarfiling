"""ساخت changelog قابل‌فهم برای مشاور املاک از تاریخچه Git — بدون جزئیات حساس/فنی."""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.utils import timezone

from product_hub.models import ProductRelease, ReleaseChange

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[2]  # django/

# متن‌ها به زبان ساده مشاور نوشته شده‌اند.
# جزئیات فنی، امنیتی داخلی، ادمین محض و اصطلاحات توسعه‌دهنده در این لیست نمی‌آید.
GIT_RELEASES = [
    {
        'version': '2.0.0',
        'title': 'شروع فایلینگ دیوار',
        'summary': 'راه‌اندازی میزکار، فروشگاه و لایسنس برای مشاوران املاک.',
        'released_at': '2026-06-21T20:00:00+0330',
        'since': '2026-06-21',
        'until': '2026-06-22',
        'changes': [
            ('feature', 'میزکار فایلینگ دیوار آماده استفاده شد'),
            ('feature', 'امکان خرید لایسنس و ورود به حساب کاربری'),
            ('feature', 'داشبورد ساده برای شروع کار روزانه'),
            ('improvement', 'ظاهر صفحات اصلی خواناتر و مرتب‌تر شد'),
        ],
    },
    {
        'version': '2.1.0',
        'title': 'ابزار قیمت‌گذاری و آموزش نصب',
        'summary': 'کمک به برآورد قیمت بازار، آموزش نصب، و مدیریت عکس ملک.',
        'released_at': '2026-06-22T22:00:00+0330',
        'since': '2026-06-22',
        'until': '2026-06-23',
        'changes': [
            ('feature', 'ابزار برآورد قیمت و مقایسه فایل‌ها با بازار'),
            ('feature', 'انتخاب آسان فایل استخراج‌شده برای تحلیل'),
            ('feature', 'ویدیوی آموزش نصب ربات'),
            ('feature', 'افزودن و مدیریت عکس برای ملک شخصی'),
            ('feature', 'مقالات راهنما درباره ربات و مدیریت مشتری'),
            ('improvement', 'کار راحت‌تر با نقشه فایل‌ها'),
            ('improvement', 'ورود ساده‌تر فایل‌های استخراج‌شده به میزکار'),
        ],
    },
    {
        'version': '2.2.0',
        'title': 'سایت راهنما و ترتیب بهتر فایل‌ها',
        'summary': 'صفحات راهنما قوی‌تر شدند و فایل شخصی مشاور بالاتر دیده می‌شود.',
        'released_at': '2026-06-25T18:00:00+0330',
        'since': '2026-06-23',
        'until': '2026-06-26',
        'changes': [
            ('feature', 'صفحات راهنما و معرفی امکانات محصول'),
            ('feature', 'بهبود نمایش مطالب آموزشی در سایت'),
            ('improvement', 'فایل‌های شخصی شما زودتر از فایل مشاوران دیگر دیده می‌شوند'),
            ('improvement', 'ویدیوی آموزشی فایلینگ در بخش آموزش'),
            ('fix', 'بهبود نمایش سایت روی موبایل'),
        ],
    },
    {
        'version': '2.3.0',
        'title': 'اپ موبایل مشاور',
        'summary': 'دسترسی به کار روزانه از موبایل با اعلان و استخراج هماهنگ.',
        'released_at': '2026-06-27T20:00:00+0330',
        'since': '2026-06-25',
        'until': '2026-06-28',
        'changes': [
            ('feature', 'اپ موبایل برای کار با فایل‌ها و مشتریان'),
            ('feature', 'اعلان روی موبایل برای رویدادهای مهم'),
            ('feature', 'داشبورد و نقشه فایل‌ها در موبایل'),
            ('feature', 'استخراج موبایل هم‌راستا با خروجی ربات ویندوز'),
            ('fix', 'پایدارتر شدن داشبورد موبایل'),
            ('fix', 'ورود با شماره موبایل روان‌تر شد'),
            ('performance', 'استخراج‌های نیمه‌کاره دیگر کار بعدی را قفل نمی‌کنند'),
        ],
    },
    {
        'version': '2.4.0',
        'title': 'فعال‌سازی آسان‌تر لایسنس و امکانات موبایل',
        'summary': 'بعد از خرید، لایسنس سریع‌تر آماده می‌شود و خروجی گرفتن از موبایل آسان‌تر است.',
        'released_at': '2026-06-30T21:00:00+0330',
        'since': '2026-06-29',
        'until': '2026-07-01',
        'changes': [
            ('feature', 'بعد از پرداخت موفق، لایسنس خودکار فعال می‌شود'),
            ('feature', 'مدیریت دستگاه‌های متصل به لایسنس شفاف‌تر شد'),
            ('feature', 'ارسال امن فایل‌های ربات به میزکار'),
            ('feature', 'نمایش امکانات ملک (آسانسور، پارکینگ و …) در موبایل'),
            ('feature', 'خروجی گرفتن از مخاطبین و فایل‌ها در موبایل'),
            ('feature', 'مدارک و مخاطبین ملک در اپ موبایل'),
            ('improvement', 'آیکون‌ها و ظاهر بخش‌های مختلف یکدست‌تر شد'),
        ],
    },
    {
        'version': '2.5.0',
        'title': 'اشتراک لینک فایل با مشتری',
        'summary': 'ارسال لینک آگهی یا ملک برای مشتری، و تشخیص بهتر صاحب‌آگهی.',
        'released_at': '2026-07-01T23:00:00+0330',
        'since': '2026-07-01',
        'until': '2026-07-02',
        'changes': [
            ('feature', 'ساخت لینک اشتراک برای آگهی دیوار'),
            ('feature', 'ساخت لینک اشتراک برای ملک شخصی خودتان'),
            ('feature', 'تشخیص بهتر اینکه آگهی مالکان است یا مشاور'),
            ('feature', 'پیام خوش‌آمد هنگام اتصال اپ موبایل'),
            ('feature', 'نمایش واضح‌تر امکانات ملک مثل آسانسور'),
            ('improvement', 'زمان‌بندی استخراج و اعلان‌های موبایل بهتر شد'),
            ('fix', 'نمایش پایدارتر عکس‌ها در موبایل'),
        ],
    },
    {
        'version': '2.6.0',
        'title': 'پیشنهاد فایل مناسب به مشتری',
        'summary': 'سیستم فایل‌های هم‌خوان با نیاز مشتری را پیشنهاد می‌دهد و کمک هوش مصنوعی اضافه شد.',
        'released_at': '2026-07-04T20:00:00+0330',
        'since': '2026-07-02',
        'until': '2026-07-05',
        'changes': [
            ('feature', 'پیشنهاد فایل دیوار مطابق بودجه و نیاز مشتری'),
            ('feature', 'کمک هوش مصنوعی برای خلاصه فایل و متن پیام به مشتری'),
            ('improvement', 'ثبت جزئیات نیاز مشتری کامل‌تر شد'),
            ('improvement', 'پایدارتر شدن پیشنهاد فایل و کار روزانه CRM'),
        ],
    },
    {
        'version': '2.7.0',
        'title': 'پشتیبانی داخل میزکار و ورود با کد پیامک',
        'summary': 'ثبت درخواست پشتیبانی از داخل میزکار و ورود ساده‌تر با کد یکبارمصرف.',
        'released_at': '2026-07-09T22:00:00+0330',
        'since': '2026-07-05',
        'until': '2026-07-10',
        'changes': [
            ('feature', 'ثبت و پیگیری تیکت پشتیبانی داخل میزکار'),
            ('feature', 'ورود و ثبت‌نام با کد پیامکی'),
            ('feature', 'امکان بستن اعلان‌های بالای صفحه'),
            ('improvement', 'صفحه معرفی ربات و اپ اندروید واضح‌تر شد'),
            ('improvement', 'تأیید شماره موبایل هنگام ثبت‌نام'),
        ],
    },
    {
        'version': '2.8.0',
        'title': 'فایل شخصی، گالری عکس و تطبیق دقیق‌تر',
        'summary': 'انتقال آگهی به پرونده شخصی، گالری عکس، و پیشنهاد دقیق‌تر بر اساس بودجه و محله.',
        'released_at': '2026-07-10T23:30:00+0330',
        'since': '2026-07-10',
        'until': '2026-07-11',
        'changes': [
            ('feature', 'انتقال آگهی دیوار به فایل شخصی خودتان با عکس'),
            ('feature', 'گالری عکس و ویرایش راحت‌تر مشخصات آگهی'),
            ('feature', 'مشاهده آگهی‌ها از چند فایل استخراج‌شده با هم'),
            ('feature', 'فیلتر پیشرفته‌تر برای ملک‌های شما'),
            ('feature', 'تنظیم محله، نوع ملک و محدوده بودجه برای تطبیق بهتر'),
            ('feature', 'ثبت شماره تماس مالک روی پرونده ملک'),
            ('improvement', 'کارت‌های فایل دیوار در CRM خواناتر شد'),
            ('improvement', 'پنجره اشتراک لینک برای مشتری ساده‌تر شد'),
        ],
    },
    {
        'version': '2.9.0',
        'title': 'نقشه، امکانات ملک و اشتراک حرفه‌ای',
        'summary': 'لینک اشتراک زیباتر شد؛ امکانات ملک و موقعیت روی نقشه بهتر دیده می‌شود.',
        'released_at': '2026-07-11T23:00:00+0330',
        'since': '2026-07-11',
        'until': '2026-07-12',
        'changes': [
            ('feature', 'نمایش امکانات ملک در پرونده و لینک اشتراک'),
            ('feature', 'موقعیت تقریبی ملک و دفتر روی نقشه'),
            ('feature', 'نمایش مشخصات مشاور و آژانس در لینک اشتراک'),
            ('feature', 'متن آماده اشتراک و پیش‌نمایش قبل از ارسال'),
            ('feature', 'تنظیمات پروفایل مشاور از داخل میزکار'),
            ('improvement', 'نقشه روی موبایل و دسکتاپ روان‌تر شد'),
            ('fix', 'لینک اشتراک پایدارتر و قابل‌اعتمادتر شد'),
        ],
    },
    {
        'version': '2.10.0',
        'title': 'دانلود اپ، شبکه‌های مشتری و جستجوی منطقه',
        'summary': 'دانلود برنامه راحت‌تر شد؛ شبکه‌های مشتری و جستجوی محله بهتر کار می‌کند.',
        'released_at': '2026-07-12T22:00:00+0330',
        'since': '2026-07-12',
        'until': '2026-07-13',
        'changes': [
            ('feature', 'صفحه دانلود و راهنمای نصب اپ'),
            ('feature', 'ثبت شبکه‌های ارتباطی مشتری (مثل واتساپ)'),
            ('feature', 'نمایش نوع آگهی‌دهنده در پیشنهاد فایل به مشتری'),
            ('improvement', 'جستجوی سریع‌تر مناطق و محله‌ها'),
            ('improvement', 'فعال‌سازی لایسنس با جزئیات واضح‌تر وضعیت حساب'),
        ],
    },
    {
        'version': '2.11.0',
        'title': 'مدیریت آژانس و پیام بین مشاوران',
        'summary': 'هماهنگی تیم آژانس، پیام داخلی، اهداف فروش و وضعیت لایسنس در صفحه اول.',
        'released_at': '2026-07-13T23:00:00+0330',
        'since': '2026-07-13',
        'until': '2026-07-14',
        'changes': [
            ('feature', 'میز فرمان آژانس برای مدیریت تیم'),
            ('feature', 'پیام بین اعضای آژانس با نشان پیام جدید'),
            ('feature', 'تعیین اهداف فروش برای تیم'),
            ('feature', 'نمایش وضعیت لایسنس در صفحه اول میزکار'),
            ('feature', 'ورود آزمایشی امن‌تر با تأیید شماره موبایل'),
            ('improvement', 'راهنمای شروع کار (آنبوردینگ) واضح‌تر شد'),
            ('improvement', 'پایدارتر شدن اتصال ربات ویندوز'),
        ],
    },
    {
        'version': '2.12.0',
        'title': 'اطلاعیه تیم و نمایش روی مانیتور دفتر',
        'summary': 'اطلاعیه برای تیم، داشبورد روی تلویزیون دفتر، و ثبت بهتر بازدید ملک.',
        'released_at': '2026-07-14T23:30:00+0330',
        'since': '2026-07-14',
        'until': '2026-07-15',
        'changes': [
            ('feature', 'ارسال اطلاعیه برای اعضای آژانس'),
            ('feature', 'نمایش آمار تیم روی مانیتور بزرگ دفتر'),
            ('feature', 'ثبت بازدید ملک راحت‌تر شد'),
            ('feature', 'اتوماسیون پیگیری مشتری هوشمندتر شد'),
            ('improvement', 'خروج از میزکار و پنجره‌ها دسترس‌پذیرتر شد'),
        ],
    },
    {
        'version': '2.13.0',
        'title': 'مرکز توسعه و به‌روزرسانی ربات ویندوز',
        'summary': 'مشاهده تغییرات محصول، پیشنهاد قابلیت، بهبود موبایل، و خروجی دقیق‌تر ربات ویندوز با سال ساخت، اتاق و طبقه.',
        'released_at': '2026-07-16T10:30:00+0330',
        'since': '2026-07-15',
        'until': '2026-07-16',
        'changes': [
            ('feature', 'مرکز توسعه: ببینید چه قابلیت‌هایی اضافه شده'),
            ('feature', 'ثبت پیشنهاد قابلیت و گزارش مشکل توسط شما'),
            ('feature', 'ربات ویندوز: ستون‌های سال ساخت، تعداد اتاق و طبقه در خروجی اکسل'),
            ('feature', 'نشان کیفیت تصویر آگهی'),
            ('feature', 'اقدام سریع و فیلتر ساده‌تر مخاطبین روی موبایل'),
            ('feature', 'تشخیص بهتر آگهی مالک از مشاورِ مبدل'),
            ('feature', 'فیلتر لیست فایل‌ها و خروجی اکسل بهتر شد'),
            ('improvement', 'یکسان‌سازی خروجی استخراج جدید با فایل‌های اکسل قبلی در ربات ویندوز'),
            ('improvement', 'فیلتر سال ساخت در ربات ویندوز'),
            ('improvement', 'نمایش طبقه ملک واضح‌تر شد'),
            ('improvement', 'منوی CRM روی موبایل روان‌تر شد'),
            ('fix', 'رفع مشکل ناقص بودن ردیف‌ها هنگام ادغام با فایل قبلی در ربات ویندوز'),
            ('fix', 'رفع مشکل نمایش طبقه (همکف، زیر همکف و «۳ از ۵») در خروجی ویندوز'),
            ('fix', 'دقت بهتر موقعیت جغرافیایی در خروجی اکسل ربات ویندوز'),
            ('fix', 'رفع مشکل ورود بعضی فایل‌ها و تشخیص مشاور مبدل'),
        ],
    },
    {
        'version': '2.14.0',
        'title': 'پیشنهاد مخاطب، مقالات بازار و هماهنگی تیم',
        'summary': 'برای هر فایل، مخاطب مناسب پیشنهاد می‌شود؛ مقالات بازار از داده‌های واقعی ساخته می‌شود و تاریخچه انتقال در تیم شفاف‌تر است.',
        'released_at': '2026-07-23T21:00:00+0330',
        'since': '2026-07-16',
        'until': '2026-07-24',
        'changes': [
            ('feature', 'platform', 'پیشنهاد مخاطب مناسب برای فایل شخصی (برعکس پیشنهاد فایل به مشتری)'),
            ('feature', 'platform', 'مقالات بازار بر اساس دیتاست‌های باکیفیت کاربران'),
            ('feature', 'platform', 'تاریخچه انتقال پرونده بین اعضای آژانس'),
            ('improvement', 'platform', 'پایدارتر شدن تطبیق مخاطب و فایل در CRM'),
            ('improvement', 'platform', 'خوانایی بهتر صفحات مخاطب و انتخاب محله'),
        ],
    },
    {
        'version': '2.15.0',
        'title': 'هفته اخیر: اندروید، ویندوز و پلتفرم',
        'summary': 'اپ موبایل برای کار روزانه کامل‌تر شد؛ ربات ویندوز استخراج گروهی و فیلتر آگهی‌دهنده گرفت؛ میزکار پلن یک‌هفته‌ای، راهنمای بعد از خرید و آپلود پایدارتر دارد.',
        'released_at': '2026-07-29T16:30:00+0330',
        'since': '2026-07-24',
        'until': None,
        'changes': [
            # اندروید
            ('feature', 'android', 'تیم آژانس داخل اپ: پیام، اعضا، اطلاعیه و صندوق سرنخ'),
            ('feature', 'android', 'هوش مصنوعی کاربردی: خلاصه آگهی، متن معرفی ملک و پیام پیگیری'),
            ('feature', 'android', 'فیلتر حرفه‌ای فایلینگ و ذخیره فیلترهای پرکاربرد'),
            ('feature', 'android', 'تقویم و یادآور کامل با تکرار و اعلان'),
            ('feature', 'android', 'تیکت پشتیبانی با گفتگو، فایل پیوست و بستن/بازگشایی'),
            ('feature', 'android', 'ویرایش مخاطب و آگهی، ثبت مالک به‌عنوان مخاطب'),
            ('improvement', 'android', 'ظاهر یکدست‌تر صفحه خانه، CRM، معاملات و فایلینگ'),
            ('improvement', 'android', 'به‌روزرسانی مستقیم اپ از داخل برنامه'),
            # ویندوز
            ('feature', 'windows', 'استخراج گروهی پشت‌سرهم همه دسته‌ها و زیردسته‌ها با یک کلیک'),
            ('feature', 'windows', 'انتخاب کامل‌تر نوع آگهی‌دهنده هنگام استخراج'),
            ('improvement', 'windows', 'رابط استخراج، زمان‌بندی و فضای کار مرتب‌تر شد'),
            ('improvement', 'windows', 'تشخیص بهتر مالک واقعی از مشاور مبدل در خروجی'),
            # پلتفرم
            ('feature', 'platform', 'پلن یک‌هفته‌ای به‌جای آزمایش یک‌روزه (با تأیید شماره موبایل)'),
            ('feature', 'platform', 'راهنمای واضح‌تر بعد از خرید تا فعال‌سازی ربات ویندوز'),
            ('fix', 'platform', 'رفع باگ آپلود و ادغام اشتباه دیتاست‌ها روی هم'),
            ('improvement', 'platform', 'صفحات معرفی استخراج و پایگاه فایل خواناتر شد'),
            ('improvement', 'platform', 'پایدارتر شدن ایمپورت فایل به میزکار'),
        ],
    },
]


def normalize_change_item(item):
    """پشتیبانی از (type, text) قدیمی و (type, platform, text) جدید."""
    if len(item) == 2:
        ctype, text = item
        return ctype, 'all', text
    if len(item) == 3:
        ctype, platform, text = item
        return ctype, platform, text
    raise ValueError(f'Invalid change item: {item!r}')


PLATFORM_SECTION_ORDER = (
    ('android', 'اپ اندروید', 'mobile-screen'),
    ('windows', 'ربات ویندوز', 'desktop'),
    ('platform', 'پلتفرم و میزکار', 'globe'),
    ('all', 'عمومی', 'layer-group'),
)


def group_changes_by_platform(changes):
    """گروه‌بندی آیتم‌های تغییر برای نمایش شفاف در مرکز توسعه."""
    buckets = {key: [] for key, _, _ in PLATFORM_SECTION_ORDER}
    for ch in changes:
        key = getattr(ch, 'platform', None) or 'all'
        if key not in buckets:
            key = 'all'
        buckets[key].append(ch)
    sections = []
    for key, label, icon in PLATFORM_SECTION_ORDER:
        items = buckets[key]
        if items:
            sections.append({
                'key': key,
                'label': label,
                'icon': icon,
                'changes': items,
                'count': len(items),
            })
    return sections



def git_available() -> bool:
    try:
        r = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return r.returncode == 0 and 'true' in (r.stdout or '').lower()
    except (OSError, subprocess.SubprocessError):
        return False


def count_commits(since: str, until: str | None = None) -> int:
    since_q = since if ' ' in since or 'T' in since else f'{since} 00:00:00'
    cmd = ['git', 'rev-list', '--count', f'--since={since_q}']
    if until:
        until_q = until if ' ' in until or 'T' in until else f'{until} 00:00:00'
        cmd.append(f'--until={until_q}')
    cmd.append('HEAD')
    try:
        r = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if r.returncode != 0:
            return 0
        return int((r.stdout or '0').strip() or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def _parse_dt(value: str):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z')


def build_changelog_from_codebase(*, phone: str = '09357930033', replace_existing: bool = True):
    """ساخت changelog ساده و عمومی برای مشاور؛ شمارش Git فقط در خروجی فرمان می‌آید."""
    user = User.objects.filter(phone=phone).first()
    if not user:
        raise ValueError(f'کاربر با شماره {phone} یافت نشد.')

    has_git = git_available()
    versions = [r['version'] for r in GIT_RELEASES]

    obsolete = ['1.0.0', '1.1.0', '2.8.1', '2.7.2']
    ProductRelease.objects.filter(version__in=obsolete).delete()

    if replace_existing:
        ProductRelease.objects.filter(version__in=versions).delete()

    created = 0
    updated = 0
    enriched = []

    for rel in GIT_RELEASES:
        released_at = _parse_dt(rel['released_at'])
        if timezone.is_naive(released_at):
            released_at = timezone.make_aware(released_at, timezone.get_current_timezone())

        # خلاصه عمومی — بدون اشاره به Git/کامیت/جزئیات داخلی
        summary = rel['summary']

        commit_count = 0
        if has_git:
            until = None if rel['version'] == GIT_RELEASES[-1]['version'] else rel.get('until')
            commit_count = count_commits(rel['since'], until)

        obj, was_created = ProductRelease.objects.update_or_create(
            version=rel['version'],
            defaults={
                'title': rel['title'],
                'summary': summary,
                'released_at': released_at,
                'is_published': True,
                'created_by': user,
            },
        )
        obj.changes.all().delete()
        for order, raw in enumerate(rel['changes'], start=1):
            ctype, platform, text = normalize_change_item(raw)
            ReleaseChange.objects.create(
                release=obj,
                change_type=ctype,
                platform=platform,
                text=text,
                sort_order=order,
            )
        if was_created:
            created += 1
        else:
            updated += 1
        enriched.append({'version': rel['version'], 'commits': commit_count})

    return {
        'user_id': user.id,
        'username': user.username,
        'phone': user.phone,
        'created': created,
        'updated': updated,
        'total': ProductRelease.objects.filter(version__in=versions, is_published=True).count(),
        'git_available': has_git,
        'enriched': enriched,
    }
