"""بینش rule-based بر اساس داده واقعی."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.utils import timezone

from workspace.models import Ticket


def build_customer_insights(user, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """توضیحات قابل‌استناد؛ بدون عملیات خودکار."""
    now = timezone.now()
    items: List[Dict[str, Any]] = []

    usage = summary.get('usage') or {}
    days_join = int(usage.get('days_since_join') or 0)
    if not days_join and user.date_joined:
        days_join = max(0, (now.date() - user.date_joined.date()).days)
    paid_count = int(summary.get('paid_orders_count') or 0)
    has_access = bool(summary.get('has_active_license'))
    pending_act = bool(summary.get('has_pending_bot_activation'))

    win = summary.get('windows') or {}
    ds_count = int(summary.get('datasets_count') or 0)

    if days_join <= 14 and not win.get('first_launch') and not summary.get('android', {}).get('installed'):
        items.append({
            'severity': 'info',
            'code': 'new_no_usage',
            'title': 'مشتری جدید بدون شروع استفاده',
            'detail': f'از {days_join} روز پس از عضویت، نه اجرای ویندوز و نه اپ اندروید ثبت نشده است.',
            'suggested_action': 'تماس خوش‌آمدگویی یا راهنمایی نصب اولیه',
        })

    if paid_count > 0 and not has_access and pending_act:
        items.append({
            'severity': 'warn',
            'code': 'paid_pending_activation',
            'title': 'خرید موفق با تکمیل ناقص فعال‌سازی',
            'detail': 'سفارش پرداخت‌شده وجود دارد اما دسترسی فعال ربات هنوز برقرار نشده است.',
            'suggested_action': 'بررسی تکمیل سفارش و فعال‌سازی روی دستگاه مشتری',
        })

    if paid_count > 0 and not has_access and not pending_act:
        items.append({
            'severity': 'warn',
            'code': 'paid_no_license',
            'title': 'پرداخت بدون دسترسی فعال',
            'detail': f'{paid_count} سفارش پرداخت‌شده ثبت شده اما دسترسی معتبر ربات تشخیص داده نشد.',
            'suggested_action': 'مرور لایسنس‌ها و سفارش‌های مرتبط در تب لایسنس',
        })

    pending_orders = int(summary.get('pending_orders_count') or 0)
    if pending_orders:
        items.append({
            'severity': 'info',
            'code': 'pending_orders',
            'title': 'سفارش معلق یا در انتظار تأیید',
            'detail': f'{pending_orders} سفارش در وضعیت انتظار ثبت شده است.',
            'suggested_action': 'پیگیری پرداخت یا تأیید کارت‌به‌کارت',
        })

    expires_raw = summary.get('license_expires_at')
    if has_access and expires_raw:
        from django.utils.dateparse import parse_datetime

        exp = parse_datetime(expires_raw) if isinstance(expires_raw, str) else expires_raw
        if exp and (exp - now).days <= 14:
            items.append({
                'severity': 'warn',
                'code': 'license_expiring',
                'title': 'اشتراک نزدیک به انقضا',
                'detail': f'انقضای دسترسی در بازه ۱۴ روز آینده ({summary.get("license_expires_jalali")}).',
                'suggested_action': 'پیشنهاد تمدید یا تماس پیشگیرانه',
            })

    old_open = Ticket.objects.filter(user_id=user.id).exclude(status='closed').filter(
        created_at__lt=now - timedelta(days=3),
    ).count()
    if old_open:
        items.append({
            'severity': 'warn',
            'code': 'stale_tickets',
            'title': 'تیکت باز قدیمی',
            'detail': f'{old_open} تیکت باز بیش از ۳ روز سن دارد.',
            'suggested_action': 'اولویت‌بندی پاسخ پشتیبانی',
        })

    if has_access and win.get('first_launch') and ds_count >= 3:
        items.append({
            'severity': 'ok',
            'code': 'active_user',
            'title': 'مشتری فعال',
            'detail': 'دسترسی فعال، اجرای ویندوز و استفاده از دیتاست ثبت شده است.',
            'suggested_action': 'فرصت تمدید یا ارتقا در صورت نزدیک بودن انقضا',
        })

    if win.get('downloaded') and not win.get('first_launch'):
        items.append({
            'severity': 'info',
            'code': 'download_no_launch',
            'title': 'دانلود بدون اولین اجرا',
            'detail': 'دانلود نرم‌افزار ویندوز ثبت شده، اما اولین اجرای برنامه هنوز گزارش نشده است.',
            'suggested_action': 'راهنمای نصب یا بررسی مشکل اجرا',
        })

    return items
