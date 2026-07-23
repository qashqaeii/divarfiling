"""
Template tags برای تاریخ شمسی و تبدیل‌های فارسی
"""
import re

from django import template
from django.utils import timezone
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import jdatetime

register = template.Library()


_EN_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


@register.filter
def to_persian_digits(value):
    """تبدیل اعداد لاتین به فارسی."""
    if value is None:
        return ''
    return str(value).translate(_EN_TO_FA)


@register.filter
def to_jalali_fa(value, format_string="%Y/%m/%d %H:%M"):
    """تبدیل تاریخ میلادی به شمسی با ارقام فارسی."""
    if not value:
        return ''

    try:
        if isinstance(value, str):
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(value.replace('Z', '+00:00'))
            if parsed is None:
                from datetime import datetime
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            value = parsed
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        jdt = jdatetime.datetime.fromgregorian(datetime=value)
        return jdt.strftime(format_string).translate(_EN_TO_FA)
    except Exception:
        return str(value).translate(_EN_TO_FA)


@register.filter
def to_jalali(value):
    """
    تبدیل تاریخ میلادی به شمسی
    
    Usage:
        {{ order.created_at|to_jalali }}
        {{ order.created_at|to_jalali:"%Y/%m/%d" }}
    """
    if not value:
        return ''
    
    try:
        # اگر timezone aware است، به local time تبدیل کن
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        # تبدیل به تاریخ شمسی
        jdt = jdatetime.datetime.fromgregorian(datetime=value)
        return jdt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        return value


@register.filter
def to_jalali_date(value, format_string="%Y/%m/%d"):
    """
    تبدیل تاریخ میلادی به شمسی با فرمت دلخواه
    
    Usage:
        {{ order.created_at|to_jalali_date }}
        {{ order.created_at|to_jalali_date:"%Y/%m/%d %H:%M" }}
    """
    if not value:
        return ''
    
    try:
        # اگر timezone aware است، به local time تبدیل کن
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        # تبدیل به تاریخ شمسی
        jdt = jdatetime.datetime.fromgregorian(datetime=value)
        return jdt.strftime(format_string)
    except Exception:
        return value


TXN_STATUS_LABELS = {
    'paid': 'پرداخت شده',
    'success': 'پرداخت شده',
    'pending': 'در انتظار پرداخت',
    'failed': 'ناموفق',
    'cancelled': 'لغو شده',
}

TXN_STATUS_TONES = {
    'paid': 'success',
    'success': 'success',
    'pending': 'pending',
    'failed': 'failed',
    'cancelled': 'cancelled',
}


def _normalize_txn_status(value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    return raw.lower()


@register.filter
def transaction_status_fa(value):
    """
    تبدیل وضعیت تراکنش به فارسی

    Usage:
        {{ transaction.status|transaction_status_fa }}
    """
    key = _normalize_txn_status(value)
    if key in TXN_STATUS_LABELS:
        return TXN_STATUS_LABELS[key]
    upper_key = key.upper()
    legacy = {
        'SUCCESS': 'پرداخت شده',
        'FAILED': 'ناموفق',
        'PENDING': 'در انتظار پرداخت',
        'CANCELLED': 'لغو شده',
    }
    return legacy.get(upper_key, raw if (raw := str(value or '')) else '—')


@register.filter
def transaction_status_tone(value):
    """کلاس رنگ وضعیت تراکنش — success / pending / failed / cancelled / unknown"""
    key = _normalize_txn_status(value)
    return TXN_STATUS_TONES.get(key, 'unknown')


@register.filter
def highlight_promo_codes(value):
    """برجسته‌کردن کدهای تخفیف لاتین داخل متن اطلاعیه."""
    if not value:
        return ''

    escaped = conditional_escape(value)
    highlighted = re.sub(
        r'([A-Z][A-Z0-9]{3,15})',
        r'<code class="mk-announce-code">\1</code>',
        str(escaped),
    )
    return mark_safe(highlighted)

