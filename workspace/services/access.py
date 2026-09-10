"""کنترل دسترسی به امکانات ربات و میزکار."""
from __future__ import annotations

from typing import Any, Dict, Optional

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


def _assigned_license_qs(user):
    """کلیدهای تخصیص‌یافته به عضو تیم — هم‌تراز allocated_licenses داشبورد."""
    return License.objects.filter(
        assigned_user=user,
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
    """لایسنس فعال ربات — مالک، عضو با کلید تخصیص‌یافته، یا اسلات دستگاه فعال."""
    if not user or not user.is_authenticated:
        return False
    if getattr(settings, 'WORKSPACE_LICENSE_STAFF_BYPASS', False) and user.is_staff:
        return True
    if _paid_license_qs(user).filter(status='active').exists():
        return True
    if _assigned_license_qs(user).exists():
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


def _user_bot_license(user) -> Optional[License]:
    """لایسنس مرتبط با کاربر — مالک، کلید تخصیص‌یافته، یا اسلات فعال."""
    lic = (
        _paid_license_qs(user)
        .filter(status='active')
        .select_related('plan')
        .order_by('-expires_at')
        .first()
    )
    if lic:
        return lic
    allocated = (
        _assigned_license_qs(user)
        .select_related('plan')
        .order_by('-expires_at')
        .first()
    )
    if allocated:
        return allocated
    activation = (
        _assigned_active_seat_qs(user)
        .select_related('license', 'license__plan')
        .order_by('-license__expires_at')
        .first()
    )
    return activation.license if activation else None


def get_bot_license_display(user) -> Dict[str, Any]:
    """خلاصه نمایشی لایسنس ربات در هدر میزکار."""
    from workspace.services.jalali_input import to_persian_digits

    empty = {
        'has_license': False,
        'active': False,
        'pending': False,
        'expiring_soon': False,
        'days_remaining': None,
        'unlimited': False,
        'label': 'بدون لایسنس',
        'status_key': 'none',
    }
    if not user or not user.is_authenticated:
        return empty

    if getattr(settings, 'WORKSPACE_LICENSE_STAFF_BYPASS', False) and user.is_staff:
        return {
            'has_license': True,
            'active': True,
            'pending': False,
            'expiring_soon': False,
            'days_remaining': None,
            'unlimited': True,
            'label': 'لایسنس فعال',
            'status_key': 'active',
        }

    state = get_bot_access_state(user)
    if state['has_pending_bot_activation']:
        return {
            'has_license': True,
            'active': False,
            'pending': True,
            'expiring_soon': False,
            'days_remaining': None,
            'unlimited': False,
            'label': 'در انتظار فعال‌سازی',
            'status_key': 'pending',
        }

    if not state['has_bot_license']:
        return empty

    lic = _user_bot_license(user)
    if not lic:
        return {
            'has_license': True,
            'active': True,
            'pending': False,
            'expiring_soon': False,
            'days_remaining': None,
            'unlimited': True,
            'label': 'لایسنس فعال',
            'status_key': 'active',
        }

    lic.sync_expiration_status(save=True)
    days_remaining = None
    unlimited = not lic.expires_at
    expiring_soon = False
    if lic.expires_at:
        end_date = timezone.localtime(lic.expires_at).date()
        today = timezone.localtime(timezone.now()).date()
        days_remaining = max(0, (end_date - today).days)
        expiring_soon = days_remaining <= 7

    if unlimited:
        label = 'لایسنس فعال — نامحدود'
    else:
        label = f'لایسنس فعال — {to_persian_digits(days_remaining)} روز تا انقضا'

    return {
        'has_license': True,
        'active': True,
        'pending': False,
        'expiring_soon': expiring_soon,
        'days_remaining': days_remaining,
        'unlimited': unlimited,
        'label': label,
        'status_key': 'active',
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
        'decor_icon': 'folder',
        'accent': 'violet',
    },
    'analyze': {
        'title': 'تحلیل بازار',
        'desc': 'نمودارها، آمار و تحلیل قیمت املاک',
        'icon': 'fa-chart-pie',
        'decor_icon': 'bar_chart',
        'accent': 'sky',
    },
    'compare': {
        'title': 'مقایسه فایل‌ها',
        'desc': 'مقایسه دو مجموعه‌داده و کشف تغییرات بازار',
        'icon': 'fa-arrows-left-right',
        'decor_icon': 'scale',
        'accent': 'emerald',
    },
    'tools': {
        'title': 'ابزارهای هوشمند',
        'desc': 'قیمت‌گذاری هوشمند و ماشین‌حساب‌های تخصصی',
        'icon': 'fa-wand-magic-sparkles',
        'decor_icon': 'calculator',
        'accent': 'amber',
    },
    'map': {
        'title': 'نقشه آگهی‌ها',
        'desc': 'نمایش جغرافیایی آگهی‌های استخراج‌شده',
        'icon': 'fa-map-location-dot',
        'decor_icon': 'map_pin',
        'accent': 'pink',
    },
    'upload': {
        'title': 'آپلود داده',
        'desc': 'وارد کردن خروجی ربات به میزکار',
        'icon': 'fa-cloud-arrow-up',
        'decor_icon': 'upload',
        'accent': 'cyan',
    },
    'crm_divar': {
        'title': 'تطبیق فایلینگ دیوار در CRM',
        'desc': 'پیشنهاد خودکار آگهی‌های استخراج‌شده دیوار به مشتریان',
        'icon': 'fa-wand-magic-sparkles',
        'decor_icon': 'sparkles',
        'accent': 'violet',
    },
    'contracts': {
        'title': 'قراردادهای دیجیتال',
        'desc': 'ایجاد، ارسال، تأیید و مدیریت قراردادهای معاملات',
        'icon': 'fa-file-signature',
        'decor_icon': 'file_edit',
        'accent': 'indigo',
    },
}
