"""ساخت changelog حرفه‌ای از تاریخچه واقعی Git (django/)."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.utils import timezone

from product_hub.models import ProductRelease, ReleaseChange

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[2]  # django/

# نقاط عطف بر اساس خوشه‌بندی واقعی کامیت‌های Git
# (شمارش تقریبی کامیت‌ها از git log --since/--until)
GIT_RELEASES = [
    {
        'version': '2.0.0',
        'title': 'راه‌اندازی پروژه Django فایلینگ دیوار',
        'summary': 'اولین کامیت رسمی ریپوی Django و پایه فروشگاه، لایسنس و میزکار.',
        'released_at': '2026-06-21T20:00:00+0330',
        'since': '2026-06-21',
        'until': '2026-06-22',
        'changes': [
            ('feature', 'شروع رسمی پروژه DivarFiling روی Django'),
            ('feature', 'فروشگاه، لایسنس و حساب کاربری'),
            ('feature', 'داشبورد کاربر و بنرهای اطلاع‌رسانی'),
            ('improvement', 'استایل صفحات عمومی و خانه'),
        ],
    },
    {
        'version': '2.1.0',
        'title': 'ابزارهای هوشمند بازار و محتوای آموزشی',
        'summary': 'جعبه ابزار ارزیابی بازار، ویدیو نصب، نقشه و مقالات SEO.',
        'released_at': '2026-06-22T22:00:00+0330',
        'since': '2026-06-22',
        'until': '2026-06-23',
        'changes': [
            ('feature', 'ابزارهای هوشمند: ارزیابی بازار، باند قیمت P25-P75 و مقایسه'),
            ('feature', 'انتخاب دیتاست و اسلایدر تنظیم قیمت بازار'),
            ('feature', 'ویدیو نصب و بخش آموزشی محصول'),
            ('feature', 'مدیریت تصویر ملک در CRM'),
            ('feature', 'مقالات SEO ربات استخراج و CRM املاک'),
            ('improvement', 'نکته VPN روی نقشه و بهبود رابط ابزارها'),
            ('improvement', 'ایمپورت دیتاست با مسیر /workspace/import/'),
        ],
    },
    {
        'version': '2.2.0',
        'title': 'SEO، بلاگ حرفه‌ای و مرتب‌سازی فایل‌ها',
        'summary': 'لندینگ SEO، صفحه نویسنده، اسکیما و اولویت فایل شخصی روی مشاور.',
        'released_at': '2026-06-25T18:00:00+0330',
        'since': '2026-06-23',
        'until': '2026-06-26',
        'changes': [
            ('feature', 'لندینگ‌های SEO و صفحه نویسنده'),
            ('feature', 'Open Graph / Twitter و اسکیمای FAQ و Breadcrumb'),
            ('feature', 'تصویر شاخص و تگ‌گذاری فارسی بلاگ'),
            ('improvement', 'مرتب‌سازی لیستینگ: اولویت فایل شخصی نسبت به مشاور'),
            ('improvement', 'ویدیوی فایلینگ در بخش آموزش'),
            ('fix', 'بهبود فوتر و ریسپانسیو صفحات عمومی'),
        ],
    },
    {
        'version': '2.3.0',
        'title': 'API موبایل و اعلان پوش',
        'summary': 'بک‌اند کامل اپ همراه، FCM و هم‌راستاسازی استخراج موبایل با خروجی ویندوز.',
        'released_at': '2026-06-27T20:00:00+0330',
        'since': '2026-06-25',
        'until': '2026-06-28',
        'changes': [
            ('feature', 'API موبایل کامل برای اپ مشاور (mobile-first)'),
            ('feature', 'مدل اعلان موبایل و FCM HTTP v1'),
            ('feature', 'داشبورد، نقشه و اینسایت دیتاست برای موبایل'),
            ('feature', 'هم‌راستاسازی ingest استخراج موبایل با خروجی Excel ویندوز'),
            ('fix', 'پایداری داشبورد موبایل و توکن‌های FCM منقضی'),
            ('fix', 'حذف نویز DisallowedHost و نرمال‌سازی تلفن در لاگین'),
            ('performance', 'انقضای خودکار استخراج‌های موبایل متوقف‌مانده'),
        ],
    },
    {
        'version': '2.4.0',
        'title': 'لایسنس خودکار، امکانات ملک و خروجی موبایل',
        'summary': 'صدور خودکار لایسنس، مدیریت صندلی دستگاه، امکانات آگهی و Export موبایل.',
        'released_at': '2026-06-30T21:00:00+0330',
        'since': '2026-06-29',
        'until': '2026-07-01',
        'changes': [
            ('feature', 'صدور خودکار لایسنس پس از سفارش پرداخت‌شده'),
            ('feature', 'مدیریت صندلی دستگاه و راهنمای لایسنس شفاف‌تر'),
            ('feature', 'ایمپورت امن دیتاست از ربات دسکتاپ'),
            ('feature', 'امکانات/amenities آگهی در سریالایزر موبایل'),
            ('feature', 'خروجی CSV مخاطب/ملک/دیتاست از API موبایل'),
            ('feature', 'اسناد و مخاطبین ملک در موبایل'),
            ('improvement', 'یکپارچه‌سازی آیکون‌های تزئینی در UI'),
            ('security', 'تقویت مسیر ایمپورت ربات'),
        ],
    },
    {
        'version': '2.5.0',
        'title': 'اشتراک عمومی و سیگنال آگهی‌دهنده',
        'summary': 'لینک اشتراک آگهی و ملک، تشخیص مشاور مبدل، و پوش خوش‌آمد.',
        'released_at': '2026-07-01T23:00:00+0330',
        'since': '2026-07-01',
        'until': '2026-07-02',
        'changes': [
            ('feature', 'اشتراک عمومی آگهی دیوار'),
            ('feature', 'اشتراک عمومی ملک شخصی CRM'),
            ('feature', 'سیگنال و نمایش نوع آگهی‌دهنده'),
            ('feature', 'پوش خوش‌آمد برای اولین ثبت FCM'),
            ('feature', 'آیکون‌های دکور و آسانسور در جزئیات ملک'),
            ('improvement', 'زمان‌بندی استخراج و اعلان‌های موبایل'),
            ('fix', 'Deduplicate و پایدارسازی URL تصاویر موبایل'),
        ],
    },
    {
        'version': '2.6.0',
        'title': 'تطبیق هوشمند و هوش مصنوعی میزکار',
        'summary': 'هشدار تطبیق فایل با مشتری و ماژول AI برای خلاصه و پیام.',
        'released_at': '2026-07-04T20:00:00+0330',
        'since': '2026-07-02',
        'until': '2026-07-05',
        'changes': [
            ('feature', 'هشدار تطبیق فایل دیوار با نیاز مشتری'),
            ('feature', 'ماژول AI Workspace (خلاصه آگهی/ملک و پیام CRM)'),
            ('feature', 'سهمیه، کش و لاگ مصرف توکن AI'),
            ('improvement', 'پروفایل و جزئیات تکمیلی مشتری'),
            ('improvement', 'پایدارسازی سرویس‌های تطبیق و CRM'),
        ],
    },
    {
        'version': '2.7.0',
        'title': 'پشتیبانی تیکتی، OTP و پنل ادمین',
        'summary': 'تیکت پشتیبانی، ورود با OTP، پنل ادمین و داستان تعاملی لندینگ.',
        'released_at': '2026-07-09T22:00:00+0330',
        'since': '2026-07-05',
        'until': '2026-07-10',
        'changes': [
            ('feature', 'تیکت پشتیبانی داخل Workspace'),
            ('feature', 'ورود و ثبت‌نام با OTP و تأیید تلفن'),
            ('feature', 'پنل ادمین: خروجی، خلاصه سیستم و تاریخ جلالی'),
            ('feature', 'داستان تعاملی و بازطراحی لندینگ محصول ربات'),
            ('feature', 'امکان بستن (dismiss) اعلان‌های سیستمی'),
            ('improvement', 'صفحات محصول ربات و کاتالوگ اپ اندروید'),
            ('security', 'تقویت ثبت‌نام با verification تلفن'),
        ],
    },
    {
        'version': '2.8.0',
        'title': 'تطبیق دقیق‌تر، اشتراک حرفه‌ای و فایل شخصی',
        'summary': 'همسان‌سازی بودجه/متراژ، گالری تصویر، انتقال به فایل شخصی و کمپین SMS.',
        'released_at': '2026-07-10T23:30:00+0330',
        'since': '2026-07-10',
        'until': '2026-07-11',
        'changes': [
            ('feature', 'انتقال آگهی به فایل شخصی با تصویر و یکپارچگی CRM'),
            ('feature', 'گالری تصویر ملک و ویرایش پیشرفته لیستینگ'),
            ('feature', 'مشاهده چنددیتاستی آگهی‌ها'),
            ('feature', 'فیلتر پیشرفته ملک در CRM'),
            ('feature', 'ترجیحات خریدار: محله، نوع ملک و band ±۲۰٪ بودجه/متراژ'),
            ('feature', 'کمپین بازاریابی و نمایش موجودی SMS در ادمین'),
            ('feature', 'اطلاعات تماس مالک روی ملک و لیستینگ'),
            ('improvement', 'کارت پورتفوی دیوار در CRM و قالب پیام'),
            ('improvement', 'بازت طراحی مودال اشتراک عمومی'),
        ],
    },
    {
        'version': '2.9.0',
        'title': 'نقشه، امکانات ملک و پروفایل اشتراک',
        'summary': 'امکانات ملک، موقعیت تقریبی، پروفایل مشاور/آژانس و نقشه فروشنده.',
        'released_at': '2026-07-11T23:00:00+0330',
        'since': '2026-07-11',
        'until': '2026-07-12',
        'changes': [
            ('feature', 'نمایش امکانات ملک (amenities) در پرونده و اشتراک'),
            ('feature', 'موقعیت تقریبی و نقشه دفتر/فروشنده'),
            ('feature', 'پروفایل مشاور و جزئیات آژانس در اشتراک'),
            ('feature', 'قالب پیام پیش‌فرض اشتراک و پیش‌نمایش زنده'),
            ('feature', 'مودال تنظیمات میزکار و مدیریت پروفایل'),
            ('improvement', 'مارکرهای نقشه بر اساس نوع فروشنده'),
            ('improvement', 'ریسپانسیو CRM و میزکار'),
            ('fix', 'پایدارسازی لینک‌ها و پیش‌نمایش اشتراک'),
        ],
    },
    {
        'version': '2.10.0',
        'title': 'لایسنس روزانه، ادمین پیشرفته و شبکه اجتماعی مشتری',
        'summary': 'پلن روزانه، تأیید تلفن برای trial، داشبورد ادمین/افیلیت و کانال‌های اجتماعی.',
        'released_at': '2026-07-12T22:00:00+0330',
        'since': '2026-07-12',
        'until': '2026-07-13',
        'changes': [
            ('feature', 'تب دانلودها و هاب نصب اپ'),
            ('feature', 'همگام‌سازی دفترچه تلفن در ادمین'),
            ('feature', 'داشبورد ادمین با افیلیت و وضعیت تراکنش‌ها'),
            ('feature', 'کانال‌های اجتماعی مشتری'),
            ('feature', 'نمایش آگهی‌دهنده در نتایج تطبیق CRM'),
            ('improvement', 'جزئیات حساب در پاسخ فعال‌سازی لایسنس'),
            ('improvement', 'جستجوی مناطق CRM'),
            ('security', 'سگمنت سفارش‌های معلق بدون لایسنس/پرداخت'),
        ],
    },
    {
        'version': '2.11.0',
        'title': 'هاب آژانس، پیام تیمی و لایسنس روزانه',
        'summary': 'فرماندهی تیم، پیام‌رسانی آژانس، اهداف، و محدودیت خرید پلن روزانه.',
        'released_at': '2026-07-13T23:00:00+0330',
        'since': '2026-07-13',
        'until': '2026-07-14',
        'changes': [
            ('feature', 'هاب آژانس حرفه‌ای و ردیابی عملکرد تیم'),
            ('feature', 'پیام‌رسانی درون‌آژانسی و badge خوانده‌نشده'),
            ('feature', 'اهداف تیمی و مرکز فرمان'),
            ('feature', 'نمایش وضعیت لایسنس ربات در صفحه خانه'),
            ('feature', 'ردیابی اپ ویندوز در ادمین'),
            ('feature', 'تأیید تلفن برای خرید پلن آزمایشی + OTP'),
            ('feature', 'محدودیت خرید پلن روزانه'),
            ('improvement', 'آنبوردینگ و ناوبری میزکار'),
            ('improvement', 'رویداد کلاینت ربات دسکتاپ'),
        ],
    },
    {
        'version': '2.12.0',
        'title': 'اطلاعیه آژانس، TV Mode و آنالیتیکس ادمین',
        'summary': 'برد اطلاعیه، داشبورد TV تیم، لاگ فعالیت و داشبورد فروش پلن.',
        'released_at': '2026-07-14T23:30:00+0330',
        'since': '2026-07-14',
        'until': '2026-07-15',
        'changes': [
            ('feature', 'برد اطلاعیه آژانس با آمار خوانده‌شدن'),
            ('feature', 'حالت TV داشبورد تیم (نمودار دونات و روند)'),
            ('feature', 'لاگ فعالیت CRM و فرم بازدید ملک'),
            ('feature', 'اتوماسیون CRM پیشرفته‌تر در فرم‌ها'),
            ('feature', 'داشبورد ادمین: فروش پلن، بلاگ و مارکتینگ'),
            ('feature', 'تب‌های پین، آنالیتیکس و چارت تعاملی ادمین'),
            ('improvement', 'آیکون خروج سایدبار و دسترس‌پذیری مودال‌ها'),
            ('improvement', 'ممیزی و لاگ به‌روزرسانی آژانس'),
        ],
    },
    {
        'version': '2.13.0',
        'title': 'مرکز توسعه محصول و بهبود تجربه موبایل CRM',
        'summary': 'Product Hub، نشان اصالت تصویر، فیلتر موبایل مخاطبین و سیگنال مالک.',
        'released_at': '2026-07-15T20:00:00+0330',
        'since': '2026-07-15',
        'until': '2026-07-16',
        'changes': [
            ('feature', 'مرکز توسعه فایلینگ دیوار (Product Hub)'),
            ('feature', 'کاتالوگ قابلیت‌ها، پیشنهاد کاربران، باگ و roadmap'),
            ('feature', 'نشان اصالت تصویر آگهی'),
            ('feature', 'دکمه‌های اقدام سریع و فیلتر موبایل مخاطبین'),
            ('feature', 'تقویت سیگنال آگهی‌دهنده و تشخیص مشاور مبدل'),
            ('feature', 'بهبود نوار فیلتر لیستینگ و خروجی Excel لینک'),
            ('improvement', 'نمایش طبقه در قالب‌ها و سرویس‌های ملک'),
            ('improvement', 'ریسپانسیو ناوبری CRM و کارت دیتاست'),
            ('fix', 'تست‌های تشخیص مشاور مبدل و ایمپورت دیتاست'),
        ],
    },
]


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
    """تعداد کامیت‌ها از since تا until (until اختیاری)."""
    # Git روی Windows با تاریخ بدون ساعت گاهی ۰ برمی‌گرداند
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


def sample_commit_subjects(since: str, until: str | None = None, limit: int = 8) -> list[str]:
    since_q = since if ' ' in since or 'T' in since else f'{since} 00:00:00'
    cmd = ['git', 'log', f'--since={since_q}', '--pretty=format:%s', '-n', str(limit), 'HEAD']
    if until:
        until_q = until if ' ' in until or 'T' in until else f'{until} 00:00:00'
        cmd.insert(2, f'--until={until_q}')
    try:
        r = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
            check=False,
        )
        if r.returncode != 0:
            return []
        return [ln.strip() for ln in (r.stdout or '').splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def _parse_dt(value: str):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z')


def build_changelog_from_codebase(*, phone: str = '09357930033', replace_existing: bool = True):
    """
    ساخت changelog از نقاط عطف Git برای کاربر مالک (قشقایی).
    نسخه‌های قدیمی غیرمرتبط با تاریخچه Git فعلی حذف می‌شوند.
    """
    user = User.objects.filter(phone=phone).first()
    if not user:
        raise ValueError(f'کاربر با شماره {phone} یافت نشد.')

    has_git = git_available()
    versions = [r['version'] for r in GIT_RELEASES]

    # نسخه‌های legacy که دیگر نباید بمانند (قبل از همگام‌سازی با Git)
    obsolete = [
        '1.0.0', '1.1.0', '2.8.1', '2.7.2',
    ]
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

        summary = rel['summary']
        commit_count = 0
        if has_git:
            # آخرین نسخه: شمارش تا HEAD (بدون until سخت)
            until = None if rel['version'] == GIT_RELEASES[-1]['version'] else rel.get('until')
            commit_count = count_commits(rel['since'], until)
            if commit_count:
                summary = f'{summary} · بر اساس {commit_count} کامیت Git'

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
        for order, (ctype, text) in enumerate(rel['changes'], start=1):
            ReleaseChange.objects.create(
                release=obj,
                change_type=ctype,
                text=text,
                sort_order=order,
            )
        if was_created:
            created += 1
        else:
            updated += 1
        enriched.append({
            'version': rel['version'],
            'commits': commit_count,
            'samples': sample_commit_subjects(
                rel['since'],
                None if rel['version'] == GIT_RELEASES[-1]['version'] else rel.get('until'),
                3,
            ) if has_git else [],
        })

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
