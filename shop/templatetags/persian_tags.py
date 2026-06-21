"""
Template tags برای تاریخ شمسی و تبدیل‌های فارسی
"""
from django import template
from django.utils import timezone
import jdatetime

register = template.Library()


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


@register.filter
def transaction_status_fa(value):
    """
    تبدیل وضعیت تراکنش به فارسی
    
    Usage:
        {{ transaction.status|transaction_status_fa }}
    """
    status_map = {
        'SUCCESS': 'موفق',
        'FAILED': 'ناموفق',
        'PENDING': 'در انتظار',
        'CANCELLED': 'لغو شده',
        'success': 'موفق',
        'failed': 'ناموفق',
        'pending': 'در انتظار',
        'cancelled': 'لغو شده',
    }
    return status_map.get(str(value).upper(), str(value))

