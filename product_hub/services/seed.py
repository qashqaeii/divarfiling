"""Seed دقیق کاتالوگ قابلیت‌ها و changelog واقعی فایلینگ دیوار."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify

from product_hub.models import (
    BugReport,
    FeatureFollow,
    FeatureRequest,
    FeatureVote,
    ProductFeature,
    ProductRelease,
    ReleaseChange,
)

User = get_user_model()

# (title, category, status, summary, days_since_added)
FEATURES = [
    # فایلینگ
    ('دیتاست‌های استخراج‌شده', 'filing', 'active', 'مدیریت فایل‌های دیوار در دیتاست‌های جداگانه با جستجو، فیلتر و آرشیو.', 400),
    ('جستجو و فیلتر پیشرفته آگهی', 'filing', 'active', 'فیلتر بر اساس منطقه، قیمت، متراژ، نوع معامله و مشخصات آگهی.', 380),
    ('نقشه فایل‌ها', 'filing', 'active', 'نمایش مکانی آگهی‌ها روی نقشه برای انتخاب سریع‌تر فایل مناسب.', 220),
    ('خروجی اکسل دیتاست', 'filing', 'active', 'خروجی گرفتن از فایل‌های انتخاب‌شده به Excel برای استفاده بیرون از سیستم.', 360),
    ('علاقه‌مندی و فایل شخصی از دیوار', 'filing', 'active', 'افزودن آگهی دیوار به لیست شخصی و پیگیری سریع‌تر.', 300),
    ('اشتراک عمومی آگهی', 'filing', 'active', 'لینک اشتراک عمومی آگهی با پروفایل مشاور/آژانس و شبکه‌های اجتماعی.', 90),
    ('تحلیل و بنچمارک آگهی', 'filing', 'active', 'بررسی مقایسه‌ای آگهی نسبت به فایل‌های مشابه در دیتاست.', 200),
    ('مقایسه چند آگهی', 'filing', 'planned', 'مقایسه چند فایل دیوار در یک نمای کنار هم (در roadmap).', 60),
    # استخراج
    ('استخراج خودکار از دیوار', 'extraction', 'active', 'ربات دسکتاپ برای استخراج پایدار آگهی‌ها بر اساس فیلترهای تعریف‌شده.', 420),
    ('فیلتر شهر، محله و دسته', 'extraction', 'active', 'تعیین محدوده استخراج بر اساس منطقه و دسته‌بندی دیوار.', 400),
    ('همگام‌سازی مجدد دیتاست', 'extraction', 'active', 'به‌روزرسانی دوره‌ای داده‌ها بدون از دست رفتن فایل‌های قبلی.', 280),
    ('آپلود گروهی فایل‌ها', 'extraction', 'active', 'ورود گروهی نتایج استخراج به میزکار برای ادامه کار مشاور.', 260),
    # CRM
    ('داشبورد CRM', 'crm', 'active', 'نمای کلی وضعیت مشتریان، پیگیری‌ها، معاملات و فعالیت روزانه.', 350),
    ('صف کار امروز', 'crm', 'active', 'لیست فشرده پیگیری‌ها و کارهای ضروری همان روز.', 320),
    ('یادآور و تقویم', 'crm', 'active', 'زمان‌بندی تماس، بازدید و قرار ملاقات با یادآوری خودکار.', 330),
    ('قالب پیام مشاور', 'crm', 'active', 'قالب‌های آماده پیام برای ارتباط سریع و یکدست با مشتری.', 300),
    ('اتوماسیون CRM', 'crm', 'beta', 'قوانین خودکار برای تخصیص، پیگیری و هشدارهای عملیاتی.', 120),
    ('تطبیق فایل دیوار با مشتری', 'crm', 'active', 'پیشنهاد فایل مناسب از دیوار بر اساس بودجه و نیاز مشتری.', 100),
    ('اشتراک عمومی ملک شخصی', 'crm', 'active', 'ساخت لینک عمومی برای فایل‌های شخصی CRM با تنظیمات نمایش.', 85),
    ('هاب آژانس (تیم)', 'crm', 'active', 'میز فرمان آژانس: اعضا، عملکرد، پیام‌ها، اطلاعیه‌ها و تنظیمات.', 70),
    ('پیام‌رسانی درون‌آژانسی', 'crm', 'active', 'گفتگوی تیمی بین مشاوران داخل میزکار آژانس.', 55),
    ('اطلاعیه‌های آژانس', 'crm', 'active', 'انتشار اطلاعیه برای اعضای تیم با وضعیت خوانده‌شدن.', 50),
    ('نمایش TV آژانس', 'crm', 'active', 'داشبورد بزرگ‌نمایش برای مانیتور فروشگاه/آژانس.', 45),
    # مشتریان
    ('مدیریت مخاطبین', 'customers', 'active', 'ثبت مشتری با بودجه، اولویت، وضعیت مذاکره و تخصیص مشاور.', 350),
    ('ترجیحات و پروفایل نیاز', 'customers', 'active', 'ثبت محله، متراژ، رهن/اجاره/خرید و جزئیات دقیق نیاز مشتری.', 200),
    ('ورود گروهی مشتریان', 'customers', 'active', 'ایمپورت مخاطبین از فایل برای شروع سریع CRM.', 180),
    ('فعالیت‌ها و تاریخچه مشتری', 'customers', 'active', 'ثبت تماس‌ها، یادداشت‌ها و اقدامات روی پرونده مشتری.', 340),
    # معاملات
    ('پایپلاین معاملات', 'deals', 'active', 'مدیریت مراحل معامله از پیشنهاد تا بستن قرارداد.', 280),
    ('چک‌لیست معامله', 'deals', 'active', 'مراحل عملیاتی لازم برای بستن موفق معامله.', 200),
    ('کمیسیون و تقسیم سود', 'deals', 'active', 'ثبت کمیسیون و تقسیم بین اعضای تیم آژانس.', 80),
    # گزارشات
    ('گزارش عملکرد تیم', 'reports', 'active', 'آمار تخصیص، عملکرد مشاوران و خروجی مدیریتی آژانس.', 70),
    ('خروجی CSV تیمی', 'reports', 'active', 'دانلود گزارش تیمی برای بررسی بیرون از سیستم.', 65),
    # ابزارها / AI
    ('ابزارهای هوشمند بازار', 'tools', 'active', 'جعبه ابزار ارزیابی و تحلیل بازار روی فایل‌های استخراج‌شده.', 150),
    ('خلاصه هوشمند آگهی (AI)', 'tools', 'beta', 'تولید خلاصه خوانا از آگهی دیوار با کمک هوش مصنوعی.', 40),
    ('خلاصه ملک شخصی (AI)', 'tools', 'beta', 'خلاصه‌سازی پرونده ملک CRM برای مشاور.', 38),
    ('پیام پیشنهادی CRM (AI)', 'tools', 'beta', 'پیشنهاد متن پیام متناسب با مشتری و لحن انتخابی.', 35),
    ('بریف آپلود هوشمند', 'tools', 'beta', 'راهنمای کوتاه هوشمند هنگام آپلود دیتاست جدید.', 32),
    # موبایل
    ('API موبایل مشاور', 'mobile', 'in_progress', 'دسترسی به فایلینگ و CRM از اپ موبایل از طریق API امن.', 60),
    ('اعلان‌های موبایل', 'mobile', 'in_progress', 'یادآور، هشدار تطبیق و رویدادهای مهم روی موبایل.', 40),
    # ربات دسکتاپ / لایسنس
    ('ربات دسکتاپ فایلینگ', 'desktop_bot', 'active', 'نرم‌افزار ویندوز برای استخراج پایدار و اتصال به لایسنس.', 420),
    ('لایسنس و صندلی تیمی', 'desktop_bot', 'active', 'فعال‌سازی لایسنس، مدیریت صندلی‌ها و دسترسی اعضای تیم.', 250),
    ('رویدادهای کلاینت ربات', 'desktop_bot', 'active', 'گزارش وضعیت و رویدادهای ربات دسکتاپ به سرور برای پشتیبانی بهتر.', 140),
    ('تیکت پشتیبانی میزکار', 'crm', 'active', 'ثبت و پیگیری درخواست پشتیبانی مستقیم از داخل Workspace.', 110),
    ('مرکز توسعه محصول', 'crm', 'active', 'صفحه شفاف قابلیت‌ها، changelog، پیشنهاد کاربران و roadmap.', 1),
]

SAMPLE_RELEASES = [
    {
        'version': '2.9.0',
        'title': 'مرکز توسعه محصول و شفافیت مسیر',
        'summary': 'راه‌اندازی Product Hub برای نمایش قابلیت‌ها، پیشنهاد کاربران، باگ‌ها و Roadmap.',
        'days_ago': 0,
        'hour': 14,
        'changes': [
            ('feature', 'افزوده شدن مرکز توسعه فایلینگ دیوار (Product Hub)'),
            ('feature', 'Timeline نسخه‌ها و کاتالوگ قابلیت‌های واقعی محصول'),
            ('feature', 'ثبت پیشنهاد قابلیت، رای‌دهی و دنبال کردن توسط کاربران لایسنس‌دار'),
            ('feature', 'سیستم گزارش باگ و اطلاع‌رسانی انتشار به دنبال‌کنندگان'),
            ('improvement', 'هم‌راستاسازی تجربه کاربری با Design System میزکار'),
        ],
    },
    {
        'version': '2.8.1',
        'title': 'تقویت CRM، اشتراک و پایداری فایلینگ',
        'summary': 'بهبود سرعت جستجو، اشتراک عمومی و اصلاحات تجربه مشاور.',
        'days_ago': 12,
        'hour': 14,
        'changes': [
            ('performance', 'بهبود سرعت جستجو و فیلتر فایل‌های استخراج‌شده'),
            ('fix', 'رفع مشکل نمایش تصاویر در جزئیات آگهی'),
            ('feature', 'تقویت فیلتر منطقه در لیست فایل‌ها'),
            ('improvement', 'اصلاح اعلان‌ها و یادآورهای CRM'),
            ('improvement', 'پایدارتر شدن لینک اشتراک عمومی آگهی و ملک'),
        ],
    },
    {
        'version': '2.8.0',
        'title': 'هاب آژانس، پیام تیمی و کمیسیون',
        'summary': 'آژانس حرفه‌ای: پیام‌ها، اطلاعیه‌ها، TV و تقسیم کمیسیون.',
        'days_ago': 35,
        'hour': 11,
        'changes': [
            ('feature', 'هاب آژانس با داشبورد فرماندهی تیم'),
            ('feature', 'پیام‌رسانی درون‌آژانسی و اطلاعیه‌ها'),
            ('feature', 'تقسیم کمیسیون معاملات بین اعضا'),
            ('feature', 'نمایش TV آژانس برای مانیتور فروش'),
            ('security', 'تقویت کنترل دسترسی صندلی لایسنس و عضویت تیم'),
            ('improvement', 'بهبود رابط مخاطبین و فایل‌های شخصی'),
        ],
    },
    {
        'version': '2.7.2',
        'title': 'تطبیق فایل، اشتراک عمومی و اتوماسیون',
        'summary': 'پیشنهاد فایل مناسب مشتری و اشتراک‌گذاری حرفه‌ای فایل‌ها.',
        'days_ago': 55,
        'hour': 16,
        'changes': [
            ('feature', 'تطبیق هوشمند فایل دیوار با نیاز مشتری'),
            ('feature', 'اشتراک عمومی ملک شخصی با پروفایل آژانس'),
            ('feature', 'اتوماسیون اولیه CRM برای پیگیری‌ها'),
            ('improvement', 'کامل‌تر شدن ترجیحات و پروفایل مشتری'),
            ('fix', 'رفع خطای همگام‌سازی در آپلود گروهی'),
        ],
    },
    {
        'version': '2.7.0',
        'title': 'نقشه، ابزارهای هوشمند و خروجی حرفه‌ای',
        'summary': 'ابزارهای تحلیل بازار، نقشه فایل‌ها و خروجی اکسل پایدارتر.',
        'days_ago': 90,
        'hour': 10,
        'changes': [
            ('feature', 'نقشه فایل‌های استخراج‌شده'),
            ('feature', 'جعبه ابزار هوشمند ارزیابی بازار'),
            ('improvement', 'خروجی اکسل پایدارتر و خواناتر'),
            ('fix', 'رفع باگ نمایش فیلترهای ترکیبی در لیست آگهی'),
            ('performance', 'کاهش زمان بارگذاری صفحات پرترافیک میزکار'),
        ],
    },
]

DEMO_REQUESTS = [
    {
        'slug_hint': 'send-file-to-customer',
        'title': 'ارسال مستقیم فایل ملک برای مشتری',
        'category': 'crm',
        'problem': 'الان برای فرستادن فایل باید لینک را دستی کپی کنیم. نیاز داریم یک دکمه «ارسال برای مشتری» داشته باشیم.',
        'why_important': 'زمان مشاورها هدر می‌رود و احتمال غلط فرستادن لینک زیاد است.',
        'priority': 'high',
        'status': 'in_development',
        'votes': 18,
    },
    {
        'slug_hint': 'whatsapp-template-share',
        'title': 'اشتراک یک‌کلیکه در واتساپ با قالب آماده',
        'category': 'customers',
        'problem': 'می‌خواهیم فایل و پیام قالب‌شده مستقیم در واتساپ مشتری باز شود.',
        'why_important': 'بیشتر مذاکرات املاک روی واتساپ است.',
        'priority': 'high',
        'status': 'approved',
        'votes': 24,
    },
    {
        'slug_hint': 'bulk-price-alert',
        'title': 'هشدار تغییر قیمت فایل‌های دنبال‌شده',
        'category': 'filing',
        'problem': 'وقتی قیمت آگهی دیوار تغییر می‌کند متوجه نمی‌شویم مگر دستی چک کنیم.',
        'why_important': 'فرصت چانه‌زنی و واکنش سریع از دست می‌رود.',
        'priority': 'medium',
        'status': 'reviewing',
        'votes': 11,
    },
    {
        'slug_hint': 'customer-kanban',
        'title': 'نمای کانبان برای وضعیت مشتریان',
        'category': 'customers',
        'problem': 'لیست جدولی برای جابجایی سریع وضعیت کافی نیست؛ کانبان بصری بهتر است.',
        'why_important': 'مدیر آژانس دید بهتری روی قیف فروش پیدا می‌کند.',
        'priority': 'medium',
        'status': 'submitted',
        'votes': 9,
    },
    {
        'slug_hint': 'offline-bot-queue',
        'title': 'صف استخراج آفلاین هنگام قطع اینترنت',
        'category': 'desktop_bot',
        'problem': 'اگر اینترنت لحظه‌ای قطع شود بخشی از استخراج نیمه‌کاره می‌ماند.',
        'why_important': 'پایداری ربات برای دفاتر با اینترنت ناپایدار حیاتی است.',
        'priority': 'high',
        'status': 'approved',
        'votes': 14,
    },
]

DEMO_BUGS = [
    {
        'title': 'در موبایل، دکمه فیلتر لیست مخاطبین گاهی زیر کیبورد می‌ماند',
        'description': 'در اندروید وقتی جستجو فوکوس دارد، دکمه اعمال فیلتر دیده نمی‌شود و باید کیبورد بسته شود.',
        'severity': 'medium',
        'status': 'resolved',
        'resolution_note': 'با اصلاح لایه fixed در نسخه موبایل CRM برطرف شد.',
    },
    {
        'title': 'پس از آپلود حجیم، نوار پیشرفت گاهی روی ۱۰۰٪ می‌ماند',
        'description': 'در آپلود دیتاست بزرگ، UI پیشرفت کامل می‌شود اما تا رفرش صفحه نتیجه نهایی نشان داده نمی‌شود.',
        'severity': 'high',
        'status': 'fixing',
        'resolution_note': '',
    },
    {
        'title': 'تاریخ یادآور در تم تاریک کنتراست پایینی دارد',
        'description': 'متن تاریخ جلالی در کارت یادآور روی پس‌زمینه تیره سخت خوانده می‌شود.',
        'severity': 'low',
        'status': 'resolved',
        'resolution_note': 'رنگ متن ثانویه در تم تاریک مطابق توکن‌های Design System اصلاح شد.',
    },
]


def _seed_user():
    """کاربر داخلی برای داده نمونه (اگر وجود ندارد ساخته می‌شود)."""
    user, created = User.objects.get_or_create(
        username='product_hub_seed',
        defaults={
            'phone': '09000000001',
            'first_name': 'کاربر',
            'last_name': 'نمونه',
            'is_active': True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    return user


def _sync_release(rel_data, *, force=False):
    now = timezone.now()
    released_at = (now - timedelta(days=rel_data['days_ago'])).replace(
        hour=rel_data.get('hour', 12), minute=30, second=0, microsecond=0,
    )
    release, created = ProductRelease.objects.update_or_create(
        version=rel_data['version'],
        defaults={
            'title': rel_data['title'],
            'summary': rel_data.get('summary') or rel_data['title'],
            'released_at': released_at,
            'is_published': True,
        },
    )
    if created or force or not release.changes.exists():
        release.changes.all().delete()
        for order, (ctype, text) in enumerate(rel_data['changes']):
            ReleaseChange.objects.create(
                release=release,
                change_type=ctype,
                text=text,
                sort_order=order,
            )
    return created


def seed_product_hub(*, reset_features=False, reset_releases=False, sync_releases=True, with_demo=True):
    """ایجاد/به‌روزرسانی کاتالوگ، changelog و در صورت نیاز داده نمونه عمومی."""
    created_features = 0
    updated_features = 0
    today = timezone.localdate()

    if reset_features:
        ProductFeature.objects.all().delete()

    for i, (title, category, status, summary, days_added) in enumerate(FEATURES):
        slug = slugify(title, allow_unicode=True) or f'feature-{i}'
        added = today - timedelta(days=days_added)
        last_changed = today if status in ('active', 'beta', 'in_progress') else added
        obj, created = ProductFeature.objects.update_or_create(
            slug=slug,
            defaults={
                'title': title,
                'summary': summary,
                'category': category,
                'status': status,
                'sort_order': i * 10,
                'is_published': True,
                'added_at': added,
                'last_changed_at': last_changed,
            },
        )
        if created:
            created_features += 1
        else:
            updated_features += 1

    created_releases = 0
    if reset_releases:
        ProductRelease.objects.filter(
            version__in=[r['version'] for r in SAMPLE_RELEASES],
        ).delete()

    for rel in SAMPLE_RELEASES:
        created = _sync_release(rel, force=sync_releases or reset_releases)
        if created:
            created_releases += 1

    demo_requests = 0
    demo_bugs = 0
    if with_demo:
        seed_user = _seed_user()
        for item in DEMO_REQUESTS:
            obj, created = FeatureRequest.objects.get_or_create(
                user=seed_user,
                title=item['title'],
                defaults={
                    'category': item['category'],
                    'problem': item['problem'],
                    'why_important': item['why_important'],
                    'priority': item['priority'],
                    'status': item['status'],
                    'votes_count': item['votes'],
                    'follows_count': max(1, item['votes'] // 3),
                    'is_public': True,
                },
            )
            if created:
                demo_requests += 1
                # synthetic votes/follows ownership for seed user only (counts already set)
                FeatureVote.objects.get_or_create(request=obj, user=seed_user)
                FeatureFollow.objects.get_or_create(request=obj, user=seed_user)
            else:
                # keep titles curated: refresh copy/status lightly
                FeatureRequest.objects.filter(pk=obj.pk).update(
                    problem=item['problem'],
                    why_important=item['why_important'],
                    priority=item['priority'],
                    status=item['status'],
                    votes_count=max(obj.votes_count, item['votes']),
                    is_public=True,
                )

        for item in DEMO_BUGS:
            obj, created = BugReport.objects.get_or_create(
                user=seed_user,
                title=item['title'],
                defaults={
                    'description': item['description'],
                    'severity': item['severity'],
                    'status': item['status'],
                    'resolution_note': item.get('resolution_note') or '',
                    'resolved_at': timezone.now() - timedelta(days=3) if item['status'] == 'resolved' else None,
                    'is_public': True,
                },
            )
            if created:
                demo_bugs += 1
            else:
                BugReport.objects.filter(pk=obj.pk).update(
                    description=item['description'],
                    severity=item['severity'],
                    status=item['status'],
                    resolution_note=item.get('resolution_note') or '',
                    is_public=True,
                )

    return {
        'features_created': created_features,
        'features_updated': updated_features,
        'releases_created': created_releases,
        'demo_requests': demo_requests,
        'demo_bugs': demo_bugs,
        'features_total': ProductFeature.objects.filter(is_published=True).count(),
        'releases_total': ProductRelease.objects.filter(is_published=True).count(),
    }
