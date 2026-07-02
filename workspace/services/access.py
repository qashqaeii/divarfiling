"""کنترل دسترسی به امکانات ربات و میزکار."""
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from licenses.models import License, LicenseActivation
from shop.models import Order


def _paid_license_qs(user):
    """لایسنس‌های مرتبط با سفارش پرداخت‌شده و معتبر."""
    return License.objects.filter(
        order__user=user,
        order__status='paid',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).exclude(status__in=['suspended', 'expired'])


def _assigned_active_seat_qs(user):
    """اسلات‌های تخصیص‌یافته به عضو تیم — فقط اسلات فعال در ربات."""
    return LicenseActivation.objects.filter(
        assigned_user=user,
        is_active=True,
        license__order__status='paid',
        license__status='active',
    ).filter(
        Q(license__expires_at__isnull=True) | Q(license__expires_at__gt=timezone.now())
    ).exclude(license__status__in=['suspended', 'expired'])


def has_purchased_bot_license(user) -> bool:
    """کاربر ربات را خریده (سفارش paid) — حتی اگر هنوز لایسنس صادر یا فعال نشده."""
    if not user or not user.is_authenticated:
        return False
    return Order.objects.filter(user=user, status='paid').exists()


def has_active_bot_license(user) -> bool:
    """لایسنس فعال ربات — مالک یا عضو تیم با اسلات تخصیص‌یافته."""
    if not user or not user.is_authenticated:
        return False
    if getattr(settings, 'WORKSPACE_LICENSE_STAFF_BYPASS', False) and user.is_staff:
        return True
    if _paid_license_qs(user).filter(status='active').exists():
        return True
    return _assigned_active_seat_qs(user).exists()


def has_pending_bot_activation(user) -> bool:
    """خرید انجام شده اما لایسنس هنوز در ربات فعال نشده."""
    if not user or not user.is_authenticated:
        return False
    if has_active_bot_license(user):
        return False
    if not has_purchased_bot_license(user):
        return False
    return not _paid_license_qs(user).filter(status='active').exists()


def get_bot_access_state(user) -> dict:
    """وضعیت دسترسی ربات برای قالب‌ها."""
    active = has_active_bot_license(user)
    purchased = has_purchased_bot_license(user)
    pending_activation = has_pending_bot_activation(user) and not active
    return {
        'has_bot_license': active,
        'has_purchased_bot': purchased,
        'has_pending_bot_activation': pending_activation,
        'bot_locked': not active,
    }


def get_bot_product_buy_url() -> str:
    """لینک خرید ربات استخراج."""
    from shop.bot_catalog import get_bot_product_buy_url as shop_buy_url

    return shop_buy_url()


BOT_LOCKED_FEATURES = {
    'datasets': {
        'title': 'فایلینگ دیوار',
        'desc': 'آپلود و مدیریت فایل‌های استخراج‌شده از دیوار',
        'icon': 'fa-folder',
        'accent': 'violet',
    },
    'analyze': {
        'title': 'تحلیل بازار',
        'desc': 'نمودارها، آمار و تحلیل قیمت املاک',
        'icon': 'fa-chart-pie',
        'accent': 'sky',
    },
    'compare': {
        'title': 'مقایسه فایل‌ها',
        'desc': 'مقایسه دو مجموعه‌داده و کشف تغییرات بازار',
        'icon': 'fa-arrows-left-right',
        'accent': 'emerald',
    },
    'tools': {
        'title': 'ابزارهای هوشمند',
        'desc': 'قیمت‌گذاری هوشمند و ماشین‌حساب‌های تخصصی',
        'icon': 'fa-wand-magic-sparkles',
        'accent': 'amber',
    },
    'map': {
        'title': 'نقشه آگهی‌ها',
        'desc': 'نمایش جغرافیایی آگهی‌های استخراج‌شده',
        'icon': 'fa-map-location-dot',
        'accent': 'pink',
    },
    'upload': {
        'title': 'آپلود داده',
        'desc': 'وارد کردن خروجی ربات به میزکار',
        'icon': 'fa-cloud-arrow-up',
        'accent': 'cyan',
    },
    'crm_divar': {
        'title': 'تطبیق فایلینگ دیوار در CRM',
        'desc': 'پیشنهاد خودکار آگهی‌های استخراج‌شده دیوار به مشتریان',
        'icon': 'fa-wand-magic-sparkles',
        'accent': 'violet',
    },
}
