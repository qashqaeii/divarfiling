"""ابزارهای مشترک پرونده ۳۶۰."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

from accounts.services.admin_users_management import (
    _annotate_users_qs,
    _jalali,
    _row_from_user,
    _user_display,
)
from workspace.services.jalali_input import to_persian_digits

User = get_user_model()

TAB_KEYS = (
    'overview',
    'account',
    'commerce',
    'licenses',
    'activity',
    'usage',
    'devices',
    'support',
    'workspace',
    'marketing',
    'agency',
    'admin_log',
)

TAB_LABELS = {
    'overview': 'کلی',
    'account': 'حساب',
    'commerce': 'مالی',
    'licenses': 'لایسنس',
    'activity': 'فعالیت',
    'usage': 'استفاده',
    'devices': 'دستگاه',
    'support': 'پشتیبانی',
    'workspace': 'CRM',
    'marketing': 'پیام',
    'agency': 'آژانس',
    'admin_log': 'تاریخچه',
}

TAB_ICONS = {
    'overview': 'fa-chart-pie',
    'account': 'fa-user-circle',
    'commerce': 'fa-shopping-cart',
    'licenses': 'fa-key',
    'activity': 'fa-stream',
    'usage': 'fa-tachometer-alt',
    'devices': 'fa-laptop',
    'support': 'fa-headset',
    'workspace': 'fa-folder-open',
    'marketing': 'fa-bullhorn',
    'agency': 'fa-building',
    'admin_log': 'fa-history',
}

SMS_PURPOSE_LABELS = {
    'login': 'ورود',
    'register': 'ثبت‌نام',
    'verify_phone': 'تأیید موبایل',
    'password_reset': 'بازیابی رمز',
    'license_renewal': 'تمدید لایسنس',
    'system': 'پیام سیستمی',
    'marketing': 'بازاریابی',
    'recovery': 'بازیابی مشتری',
    'acquisition': 'جذب مشتری',
    'activation': 'فعال‌سازی',
    'licensed_marketing': 'بازاریابی دارای لایسنس',
    'weekly_trial_campaign': 'کمپین آزمایشی هفتگی',
    'lead_acquisition': 'جذب از لید',
    'agency_invite': 'دعوت به آژانس',
    'contract_otp': 'تأیید قرارداد',
    'card_transfer_admin_review': 'بررسی کارت‌به‌کارت',
    'card_transfer_license_activated': 'فعال‌سازی پس از کارت‌به‌کارت',
    'card_transfer_rejected': 'رد کارت‌به‌کارت',
    'handover_acceptance': 'تحویل قرارداد',
    'final_view': 'مشاهده نهایی قرارداد',
}


def sms_purpose_label(raw: Any) -> str:
    """برچسب فارسی هدف پیامک — مقدار ذخیره‌شده در لاگ معمولاً انگلیسی است."""
    key = str(raw or '').strip().lower()
    if not key:
        return '—'
    if key in SMS_PURPOSE_LABELS:
        return SMS_PURPOSE_LABELS[key]
    from accounts.models import OtpRequest

    for choice in OtpRequest.Purpose:
        if choice.value == key:
            return str(choice.label)
    return 'سایر'


def fa_digits(value: Any) -> str:
    return to_persian_digits(str(value if value is not None else ''))


def resolve_panel_activity_days(raw_days: Any = None) -> int:
    """تعداد روز نمودار فعالیت — هم‌راستا با فیلتر globl پنل (`?days=`)."""
    from accounts.services.admin_dashboard import ALL_TIME_DAYS, effective_range_days
    from accounts.services.admin_panel_shell import ADMIN_PANEL_RANGE_ALL, EXTENDED_PANEL_RANGES

    if raw_days is None:
        raw = ADMIN_PANEL_RANGE_ALL
    elif isinstance(raw_days, (list, tuple)):
        raw = raw_days[0] if raw_days else ADMIN_PANEL_RANGE_ALL
    else:
        raw = str(raw_days).strip().lower()
    if raw in ('', ADMIN_PANEL_RANGE_ALL, 'none'):
        return effective_range_days(ALL_TIME_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return effective_range_days(30)
    if days not in EXTENDED_PANEL_RANGES:
        return effective_range_days(30)
    return effective_range_days(days)


def safe_query_int(
    raw: Any,
    default: int,
    *,
    minimum: int = 1,
    maximum: Optional[int] = None,
) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    if maximum is not None:
        value = min(value, maximum)
    return value


def resolve_timeline_days_filter(raw_days: Any = None) -> Optional[int]:
    """فیلتر بازه رویدادها: `all` یا خالی → بدون محدودیت زمانی."""
    from accounts.services.admin_panel_shell import ADMIN_PANEL_RANGE_ALL

    if raw_days is None:
        return None
    if isinstance(raw_days, int):
        return raw_days if raw_days > 0 else None
    raw = str(raw_days).strip().lower()
    if raw in ('', ADMIN_PANEL_RANGE_ALL, 'none', '0'):
        return None
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None
    return days if days > 0 else None


def mask_national_id(raw: str, *, reveal: bool = False) -> str:
    raw = (raw or '').strip()
    if not raw:
        return '—'
    if reveal:
        return fa_digits(raw)
    if len(raw) <= 4:
        return '••••'
    return fa_digits(raw[:3] + '•' * (len(raw) - 5) + raw[-2:])


def mask_phone_for_copy(phone: str) -> str:
    return (phone or '').strip()


def paginate_qs(qs, *, page: int, page_size: int):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 100))
    total = qs.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    return qs[start:start + page_size], {
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1,
    }


def get_user_360_user(user_id: int, *, prefetch_profile: bool = True):
    qs = _annotate_users_qs(User.objects.filter(pk=user_id))
    if prefetch_profile:
        qs = qs.select_related('profile', 'referred_by')
    return qs.first()


def user_summary_row(user) -> Dict[str, Any]:
    return _row_from_user(user)


def safe_profile(user) -> Optional[Any]:
    try:
        return user.profile
    except ObjectDoesNotExist:
        return None


def normalize_phone(phone: str) -> str:
    return re.sub(r'\D+', '', phone or '')
