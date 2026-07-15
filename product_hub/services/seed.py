"""Seed فقط کاتالوگ قابلیت‌های واقعی سیستم — بدون داده فیک."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify

from product_hub.models import (
    BugReport,
    FeatureRequest,
    ProductFeature,
    ProductHubNotification,
    ProductRelease,
)

User = get_user_model()

SEED_USERNAMES = ('product_hub_seed',)
# فقط نسخه‌های نمونه قدیمی (دیگر استفاده نمی‌شوند؛ changelog واقعی با build_product_changelog ساخته می‌شود)
LEGACY_SAMPLE_VERSIONS = ()

# کاتالوگ واقعی امکانات موجود در Workspace / محصول
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
    ('مقایسه چند آگهی', 'filing', 'planned', 'مقایسه چند فایل دیوار در یک نمای کنار هم (در مسیر توسعه).', 60),
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
    ('تیکت پشتیبانی میزکار', 'crm', 'active', 'ثبت و پیگیری درخواست پشتیبانی مستقیم از داخل Workspace.', 110),
    ('مرکز توسعه محصول', 'crm', 'active', 'صفحه شفاف قابلیت‌ها، تغییرات نسخه‌ها، پیشنهاد کاربران و roadmap.', 1),
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
]


def purge_fake_seed_data():
    """حذف پیشنهاد/باگ/نسخه‌های نمونه قبلی — بدون حذف User (جلوگیری از cascade به جداول دیگر)."""
    removed = {
        'requests': 0,
        'bugs': 0,
        'releases': 0,
        'users': 0,
        'notifications': 0,
    }
    seed_users = User.objects.filter(username__in=SEED_USERNAMES)
    seed_ids = list(seed_users.values_list('id', flat=True))
    if seed_ids:
        removed['notifications'] = ProductHubNotification.objects.filter(
            user_id__in=seed_ids,
        ).delete()[0]
        # حذف پیشنهادها، رای و follow را هم پاک می‌کند
        removed['requests'] = FeatureRequest.objects.filter(user_id__in=seed_ids).delete()[0]
        removed['bugs'] = BugReport.objects.filter(user_id__in=seed_ids).delete()[0]
        # کاربر مصنوعی را غیرفعال کن؛ حذف کامل به خاطر FKهای دیگر ممکن است fail شود
        updated = seed_users.filter(is_active=True).update(is_active=False)
        removed['users'] = updated

    removed['releases'] = ProductRelease.objects.filter(
        version__in=LEGACY_SAMPLE_VERSIONS,
    ).delete()[0]
    return removed


def seed_product_hub(*, reset_features=False, purge_fake=True):
    """فقط قابلیت‌های واقعی سیستم را sync می‌کند؛ داده فیک نمی‌سازد."""
    purged = purge_fake_seed_data() if purge_fake else {
        'requests': 0, 'bugs': 0, 'releases': 0, 'users': 0, 'notifications': 0,
    }

    created_features = 0
    updated_features = 0
    today = timezone.localdate()

    if reset_features:
        ProductFeature.objects.all().delete()

    keep_slugs = []
    for i, (title, category, status, summary, days_added) in enumerate(FEATURES):
        slug = slugify(title, allow_unicode=True) or f'feature-{i}'
        keep_slugs.append(slug)
        added = today - timedelta(days=days_added)
        last_changed = today if status in ('active', 'beta', 'in_progress') else added
        _, created = ProductFeature.objects.update_or_create(
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

    # قابلیت‌های قدیمی خارج از کاتالوگ فعلی (فقط وقتی reset نیست، orphanهای قبلی را هم پاک کن اگر slug در لیست نباشند و عنوان‌شان از seed قدیمی باشد)
    # برای ایمنی: فقط هنگام reset_features همه‌چیز پاک شده؛ در حالت عادی orphan دستی نمی‌زنیم.

    return {
        'features_created': created_features,
        'features_updated': updated_features,
        'features_total': ProductFeature.objects.filter(is_published=True).count(),
        'releases_total': ProductRelease.objects.filter(is_published=True).count(),
        'purged': purged,
    }
