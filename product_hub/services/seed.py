"""Seed کاتالوگ قابلیت‌ها و چند نسخه نمونه changelog."""
from datetime import timedelta

from django.utils import timezone
from django.utils.text import slugify

from product_hub.models import ProductFeature, ProductRelease, ReleaseChange

FEATURES = [
    # فایلینگ
    ('جستجوی پیشرفته فایل‌ها', 'filing', 'active', 'جستجو و فیلتر فایل‌های استخراج‌شده بر اساس منطقه، قیمت و مشخصات.'),
    ('فایل‌های شخصی', 'filing', 'active', 'افزودن آگهی به پرونده شخصی و مدیریت لیست‌های اختصاصی.'),
    ('نقشه فایل‌ها', 'filing', 'active', 'نمایش مکانی آگهی‌ها روی نقشه.'),
    ('خروجی اکسل', 'filing', 'active', 'خروجی گرفتن از دیتاست‌ها به فرمت اکسل.'),
    ('مقایسه آگهی‌ها', 'filing', 'planned', 'مقایسه چند فایل در یک نمای کنار هم.'),
    # استخراج
    ('استخراج خودکار دیوار', 'extraction', 'active', 'ربات دسکتاپ برای استخراج آگهی‌های دیوار بر اساس فیلتر.'),
    ('به‌روزرسانی دوره‌ای دیتاست', 'extraction', 'active', 'همگام‌سازی مجدد داده‌ها از دیوار.'),
    ('فیلتر منطقه و دسته‌بندی', 'extraction', 'active', 'تعیین محدوده استخراج بر اساس شهر، محله و دسته.'),
    # CRM
    ('داشبورد CRM', 'crm', 'active', 'نمای کلی پیگیری مشتری، یادآور و فعالیت‌های روزانه.'),
    ('یادآور و تقویم', 'crm', 'active', 'زمان‌بندی پیگیری تماس و قرار ملاقات.'),
    ('قالب پیام', 'crm', 'active', 'قالب‌های آماده پیام برای ارتباط با مشتریان.'),
    ('اتوماسیون CRM', 'crm', 'beta', 'قوانین خودکار برای پیگیری و تخصیص.'),
    ('تطبیق فایل دیوار با مشتری', 'crm', 'active', 'پیشنهاد فایل مناسب بر اساس نیاز مشتری.'),
    # مشتریان
    ('مدیریت مخاطبین', 'customers', 'active', 'ثبت و دسته‌بندی مشتریان با بودجه و اولویت.'),
    ('وضعیت و اولویت مشتری', 'customers', 'active', 'پیگیری وضعیت مذاکره و اولویت فروش.'),
    ('ورود گروهی مشتریان', 'customers', 'active', 'ایمپورت مخاطبین از فایل.'),
    # معاملات
    ('پایپلاین معاملات', 'deals', 'active', 'مدیریت مراحل معامله از پیشنهاد تا بستن قرارداد.'),
    ('کمیسیون و تقسیم سود', 'deals', 'active', 'ثبت کمیسیون و تقسیم بین اعضای تیم.'),
    ('چک‌لیست معامله', 'deals', 'active', 'مراحل لازم برای بستن موفق معامله.'),
    # گزارشات
    ('گزارش عملکرد آژانس', 'reports', 'active', 'آمار تیم، تخصیص‌ها و عملکرد مشاوران.'),
    ('خروجی CSV تیم', 'reports', 'active', 'دانلود گزارش تیمی به صورت CSV.'),
    # ابزارها
    ('ارزیابی بازار', 'tools', 'active', 'ابزارهای هوشمند تحلیل قیمت و بازار.'),
    ('جعبه ابزار آگهی', 'tools', 'active', 'ابزارهای کمکی برای کار با فایل‌های استخراج‌شده.'),
    # موبایل
    ('اپ موبایل مشاور', 'mobile', 'in_progress', 'دسترسی به CRM و فایلینگ از موبایل.'),
    ('اعلان‌های موبایل', 'mobile', 'planned', 'دریافت یادآور و هشدار تطبیق روی موبایل.'),
    # ربات دسکتاپ
    ('ربات دسکتاپ فایلینگ', 'desktop_bot', 'active', 'نرم‌افزار ویندوز برای استخراج پایدار آگهی‌ها.'),
    ('فعال‌سازی لایسنس چندصندلی', 'desktop_bot', 'active', 'مدیریت صندلی‌های لایسنس برای اعضای تیم.'),
    ('API رویدادهای کلاینت', 'desktop_bot', 'active', 'گزارش وضعیت ربات و رویدادهای کلاینت به سرور.'),
]

SAMPLE_RELEASES = [
    {
        'version': '2.8.1',
        'title': 'بهبود سرعت و اصلاحات CRM',
        'days_ago': 12,
        'changes': [
            ('performance', 'بهبود سرعت جستجوی فایل‌ها'),
            ('fix', 'رفع مشکل نمایش تصاویر آگهی'),
            ('feature', 'اضافه شدن فیلتر منطقه در لیست فایل‌ها'),
            ('improvement', 'اصلاح اعلان‌های CRM'),
        ],
    },
    {
        'version': '2.8.0',
        'title': 'تقویت آژانس و معاملات',
        'days_ago': 35,
        'changes': [
            ('feature', 'داشبورد تیمی آژانس'),
            ('feature', 'تقسیم کمیسیون معاملات'),
            ('improvement', 'بهبود رابط مخاطبین'),
            ('security', 'تقویت کنترل دسترسی صندلی لایسنس'),
        ],
    },
    {
        'version': '2.7.0',
        'title': 'ابزارهای هوشمند و نقشه',
        'days_ago': 70,
        'changes': [
            ('feature', 'نقشه فایل‌ها'),
            ('feature', 'جعبه ابزار ارزیابی بازار'),
            ('improvement', 'بهبود خروجی اکسل'),
            ('fix', 'رفع خطای همگام‌سازی دیتاست'),
        ],
    },
]


def seed_product_hub(*, reset_features=False, reset_releases=False):
    """ایجاد/به‌روزرسانی کاتالوگ و نسخه‌های نمونه. بدون حذف پیشنهاد/باگ کاربر."""
    created_features = 0
    updated_features = 0

    if reset_features:
        ProductFeature.objects.all().delete()

    for i, (title, category, status, summary) in enumerate(FEATURES):
        slug = slugify(title, allow_unicode=True) or f'feature-{i}'
        obj, created = ProductFeature.objects.update_or_create(
            slug=slug,
            defaults={
                'title': title,
                'summary': summary,
                'category': category,
                'status': status,
                'sort_order': i * 10,
                'is_published': True,
                'last_changed_at': timezone.localdate(),
            },
        )
        if created:
            created_features += 1
        else:
            updated_features += 1

    created_releases = 0
    if reset_releases:
        ProductRelease.objects.all().delete()

    now = timezone.now()
    for rel in SAMPLE_RELEASES:
        release, created = ProductRelease.objects.get_or_create(
            version=rel['version'],
            defaults={
                'title': rel['title'],
                'summary': rel['title'],
                'released_at': now - timedelta(days=rel['days_ago']),
                'is_published': True,
            },
        )
        if created:
            created_releases += 1
            for order, (ctype, text) in enumerate(rel['changes']):
                ReleaseChange.objects.create(
                    release=release,
                    change_type=ctype,
                    text=text,
                    sort_order=order,
                )
        elif not release.changes.exists():
            for order, (ctype, text) in enumerate(rel['changes']):
                ReleaseChange.objects.create(
                    release=release,
                    change_type=ctype,
                    text=text,
                    sort_order=order,
                )

    return {
        'features_created': created_features,
        'features_updated': updated_features,
        'releases_created': created_releases,
    }
