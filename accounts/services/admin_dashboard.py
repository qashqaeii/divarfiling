"""آمار و داده نمودار برای پنل مدیریت سیستم."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Exists, Max, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from workspace.services.jalali_input import to_persian_digits

from accounts.services.admin_exports import get_export_catalog
from accounts.services.admin_windows_app import (
    get_windows_activations,
    get_windows_app_stats,
    get_windows_download_logs,
    get_windows_first_launches,
    get_windows_user_funnel,
)
from accounts.services.pending_orders import PENDING_ORDER_STATUSES, get_pending_orders_for_display
from accounts.services.sms import get_sms_balance_snapshot

from affiliates.models import Affiliate, AffiliateSale, Withdrawal
from licenses.models import License, LicenseActivation
from shop.models import CardTransferSubmission, Order, Product
from workspace.models import Dataset, Ticket

User = get_user_model()

TABLE_PREVIEW_ROWS = 5
TABLE_FETCH_LIMIT = 20

CHART_COLORS = [
    'rgba(124, 58, 237, 0.85)',
    'rgba(59, 130, 246, 0.8)',
    'rgba(16, 185, 129, 0.8)',
    'rgba(245, 158, 11, 0.85)',
    'rgba(239, 68, 68, 0.75)',
    'rgba(236, 72, 153, 0.75)',
    'rgba(14, 165, 233, 0.8)',
    'rgba(99, 102, 241, 0.8)',
]

ORDER_STATUS_LABELS = dict(Order.STATUS_CHOICES)
LICENSE_STATUS_LABELS = dict(License.STATUS_CHOICES)
PAYMENT_METHOD_LABELS = dict(Order.PAYMENT_METHOD_CHOICES)


def _today():
    return timezone.now().date()


def _date_range(days: int):
    end = _today()
    start = end - timedelta(days=days - 1)
    return start, end


def _chart_day_label(day, total_days: int) -> str:
    """برچسب شمسی برای محور نمودار."""
    j = jdatetime.date.fromgregorian(date=day)
    if total_days <= 7:
        return to_persian_digits(f'{j.day:02d}/{j.month:02d}')
    if total_days <= 31:
        return to_persian_digits(f'{j.day:02d}/{j.month:02d}')
    return to_persian_digits(f'{j.month:02d}/{j.year}')


def _fill_daily_series(start, end, rows, value_key='count', money=False, days: int = 30):
    """سری روزانه با صفر برای روزهای بدون داده."""
    lookup = {row['day']: row[value_key] for row in rows}
    labels, values = [], []
    current = start
    while current <= end:
        labels.append(_chart_day_label(current, days))
        val = lookup.get(current, 0)
        if money:
            val = int(val or 0)
        else:
            val = int(val or 0)
        values.append(val)
        current += timedelta(days=1)
    return labels, values


def _pct_change(current: int | float, previous: int | float) -> float | None:
    if previous in (0, None):
        return None if not current else 100.0
    return round(((current - previous) / previous) * 100, 1)


def get_system_start_at():
    """تاریخ شروع به کار سیستم = اولین لایسنس فعال‌شده."""
    first_active = (
        LicenseActivation.objects.filter(is_active=True)
        .order_by('activated_at')
        .values_list('activated_at', flat=True)
        .first()
    )
    if first_active:
        return first_active
    # اگر فعلاً هیچ اسلات فعالی نیست، اولین ثبت فعال‌سازی
    first_any = (
        LicenseActivation.objects.order_by('activated_at')
        .values_list('activated_at', flat=True)
        .first()
    )
    if first_any:
        return first_any
    # آخرین fallback: اولین لایسنس صادرشده
    return (
        License.objects.order_by('created_at')
        .values_list('created_at', flat=True)
        .first()
    )


def get_overview_stats() -> Dict[str, Any]:
    now = timezone.now()
    today = now.date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    system_start_at = get_system_start_at()
    system_uptime_days = None
    if system_start_at:
        start_local = timezone.localtime(system_start_at) if timezone.is_aware(system_start_at) else system_start_at
        system_uptime_days = max(0, (now.date() - start_local.date()).days)

    users_total = User.objects.count()
    users_active = User.objects.filter(is_active=True).count()
    users_new_week = User.objects.filter(date_joined__date__gte=week_ago).count()
    users_new_month = User.objects.filter(date_joined__date__gte=month_ago).count()

    orders_qs = Order.objects.all()
    orders_total = orders_qs.count()
    orders_paid = orders_qs.filter(status='paid').count()
    revenue_total = orders_qs.filter(status='paid').aggregate(
        total=Sum('amount'),
    )['total'] or Decimal(0)
    revenue_month = orders_qs.filter(
        status='paid', paid_at__date__gte=month_ago,
    ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
    revenue_week = orders_qs.filter(
        status='paid', paid_at__date__gte=week_ago,
    ).aggregate(total=Sum('amount'))['total'] or Decimal(0)
    revenue_prev_month = orders_qs.filter(
        status='paid',
        paid_at__date__gte=month_ago - timedelta(days=30),
        paid_at__date__lt=month_ago,
    ).aggregate(total=Sum('amount'))['total'] or Decimal(0)

    licenses_total = License.objects.count()
    licenses_active = License.objects.filter(status='active').count()
    licenses_expired = License.objects.filter(status='expired').count()
    licenses_expiring_soon = License.objects.filter(
        status='active',
        expires_at__isnull=False,
        expires_at__lte=now + timedelta(days=14),
        expires_at__gt=now,
    ).count()
    activations_total = LicenseActivation.objects.filter(is_active=True).count()

    affiliates_total = Affiliate.objects.filter(is_active=True).count()
    affiliate_sales_total = AffiliateSale.objects.filter(status='paid').aggregate(
        total=Sum('commission_amount'),
    )['total'] or Decimal(0)

    pending_card_transfers = CardTransferSubmission.objects.filter(status='pending').count()
    pending_withdrawals = Withdrawal.objects.filter(status='pending').count()
    open_tickets = Ticket.objects.exclude(status='closed').count()
    unread_tickets = Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count()
    pending_orders = orders_qs.filter(status__in=PENDING_ORDER_STATUSES).count()
    users_pending_payment = User.objects.filter(
        orders__status__in=PENDING_ORDER_STATUSES,
    ).distinct().count()

    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    users_without_license = User.objects.filter(is_active=True).annotate(
        has_active_license=Exists(active_license_q),
    ).filter(has_active_license=False).count()

    datasets_total = Dataset.objects.count()

    return {
        'users_total': users_total,
        'users_active': users_active,
        'users_new_week': users_new_week,
        'users_new_month': users_new_month,
        'orders_total': orders_total,
        'orders_paid': orders_paid,
        'orders_pending': pending_orders,
        'users_pending_payment': users_pending_payment,
        'users_without_license': users_without_license,
        'revenue_total': int(revenue_total),
        'revenue_month': int(revenue_month),
        'revenue_week': int(revenue_week),
        'revenue_month_change': _pct_change(int(revenue_month), int(revenue_prev_month)),
        'licenses_total': licenses_total,
        'licenses_active': licenses_active,
        'licenses_expired': licenses_expired,
        'licenses_expiring_soon': licenses_expiring_soon,
        'activations_total': activations_total,
        'affiliates_total': affiliates_total,
        'affiliate_commissions_total': int(affiliate_sales_total),
        'pending_card_transfers': pending_card_transfers,
        'pending_withdrawals': pending_withdrawals,
        'open_tickets': open_tickets,
        'unread_tickets': unread_tickets,
        'datasets_total': datasets_total,
        'conversion_rate': round((orders_paid / users_total * 100), 1) if users_total else 0,
        'system_start_at': system_start_at,
        'system_uptime_days': system_uptime_days,
    }


def get_revenue_series(days: int = 30) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        Order.objects.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=end)
        .annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, value_key='total', money=True, days=days)
    return {'labels': labels, 'values': values}


def get_user_registration_series(days: int = 30) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        User.objects.filter(date_joined__date__gte=start, date_joined__date__lte=end)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def get_order_status_breakdown() -> List[Dict[str, Any]]:
    rows = Order.objects.values('status').annotate(count=Count('id')).order_by('-count')
    return [
        {
            'key': row['status'],
            'label': ORDER_STATUS_LABELS.get(row['status'], row['status']),
            'count': row['count'],
        }
        for row in rows
    ]


def get_payment_method_breakdown() -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(status='paid')
        .values('payment_method')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')
    )
    return [
        {
            'key': row['payment_method'],
            'label': PAYMENT_METHOD_LABELS.get(row['payment_method'], row['payment_method']),
            'count': row['count'],
            'total': int(row['total'] or 0),
        }
        for row in rows
    ]


def get_license_status_breakdown() -> List[Dict[str, Any]]:
    rows = License.objects.values('status').annotate(count=Count('id')).order_by('-count')
    return [
        {
            'key': row['status'],
            'label': LICENSE_STATUS_LABELS.get(row['status'], row['status']),
            'count': row['count'],
        }
        for row in rows
    ]


def get_plan_sales_breakdown(limit: int = 8) -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(status='paid')
        .values('plan__name', 'plan__product__title')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')[:limit]
    )
    return [
        {
            'label': f"{row['plan__product__title']} — {row['plan__name']}",
            'count': row['count'],
            'total': int(row['total'] or 0),
        }
        for row in rows
    ]


def get_product_revenue() -> List[Dict[str, Any]]:
    rows = (
        Order.objects.filter(status='paid')
        .values('product__title')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')
    )
    return [
        {
            'label': row['product__title'],
            'count': row['count'],
            'total': int(row['total'] or 0),
        }
        for row in rows
    ]


def get_pending_orders(limit: int = TABLE_FETCH_LIMIT):
    return get_pending_orders_for_display(limit=limit)


def get_users_with_pending_orders(limit: int = TABLE_FETCH_LIMIT):
    return (
        User.objects.filter(orders__status__in=PENDING_ORDER_STATUSES)
        .annotate(
            pending_count=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            pending_total=Sum('orders__amount', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            last_pending=Max('orders__created_at', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .distinct()
        .order_by('-last_pending')[:limit]
    )


def get_expiring_licenses(limit: int = TABLE_FETCH_LIMIT):
    now = timezone.now()
    return (
        License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=now + timedelta(days=14),
        )
        .select_related('order__user', 'plan')
        .order_by('expires_at')[:limit]
    )


def get_users_without_license_preview(limit: int = TABLE_FETCH_LIMIT):
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return (
        User.objects.filter(is_active=True)
        .annotate(
            has_active_license=Exists(active_license_q),
            paid_orders=Count('orders', filter=Q(orders__status='paid')),
            pending_orders=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .filter(has_active_license=False)
        .order_by('-date_joined')[:limit]
    )


def get_recent_orders(limit: int = TABLE_FETCH_LIMIT):
    return (
        Order.objects.select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )


def get_recent_users(limit: int = TABLE_FETCH_LIMIT):
    return User.objects.order_by('-date_joined')[:limit]


def get_pending_card_transfers(limit: int = TABLE_FETCH_LIMIT):
    return (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order', 'order__user', 'order__product')
        .order_by('-created_at')[:limit]
    )


def get_open_tickets(limit: int = TABLE_FETCH_LIMIT):
    return (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-staff_has_unread', '-last_message_at', '-created_at')[:limit]
    )


def get_pending_withdrawals(limit: int = TABLE_FETCH_LIMIT):
    return (
        Withdrawal.objects.filter(status='pending')
        .select_related('wallet', 'wallet__user')
        .order_by('-created_at')[:limit]
    )


def build_charts_payload(days: int = 30) -> Dict[str, Any]:
    revenue = get_revenue_series(days)
    signups = get_user_registration_series(days)
    order_status = get_order_status_breakdown()
    license_status = get_license_status_breakdown()
    payment_methods = get_payment_method_breakdown()
    plan_sales = get_plan_sales_breakdown()
    product_revenue = get_product_revenue()

    return {
        'revenue_trend': {
            'type': 'line',
            'labels': revenue['labels'],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': revenue['values'],
                'borderColor': 'rgba(124, 58, 237, 1)',
                'backgroundColor': 'rgba(124, 58, 237, 0.12)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'money',
        },
        'user_signups': {
            'type': 'bar',
            'labels': signups['labels'],
            'datasets': [{
                'label': 'ثبت‌نام جدید',
                'data': signups['values'],
                'backgroundColor': 'rgba(59, 130, 246, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        },
        'order_status': {
            'type': 'doughnut',
            'labels': [item['label'] for item in order_status],
            'datasets': [{
                'data': [item['count'] for item in order_status],
                'backgroundColor': CHART_COLORS[:len(order_status)],
            }],
            'axis': 'count',
        },
        'license_status': {
            'type': 'doughnut',
            'labels': [item['label'] for item in license_status],
            'datasets': [{
                'data': [item['count'] for item in license_status],
                'backgroundColor': CHART_COLORS[:len(license_status)],
            }],
            'axis': 'count',
        },
        'payment_methods': {
            'type': 'bar',
            'labels': [item['label'] for item in payment_methods],
            'datasets': [{
                'label': 'تعداد سفارش',
                'data': [item['count'] for item in payment_methods],
                'backgroundColor': 'rgba(16, 185, 129, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        },
        'plan_sales': {
            'type': 'bar',
            'labels': [item['label'][:28] for item in plan_sales],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': [item['total'] for item in plan_sales],
                'backgroundColor': 'rgba(245, 158, 11, 0.8)',
                'borderRadius': 6,
            }],
            'horizontal': True,
            'axis': 'money',
        },
        'product_revenue': {
            'type': 'bar',
            'labels': [item['label'] for item in product_revenue],
            'datasets': [{
                'label': 'درآمد (تومان)',
                'data': [item['total'] for item in product_revenue],
                'backgroundColor': 'rgba(99, 102, 241, 0.8)',
                'borderRadius': 6,
            }],
            'axis': 'money',
        },
    }


def get_today_stats() -> Dict[str, Any]:
    """آمار امروز برای کارت‌های Spotlight."""
    today = _today()
    orders_paid_today = Order.objects.filter(status='paid', paid_at__date=today)
    return {
        'revenue_today': int(orders_paid_today.aggregate(total=Sum('amount'))['total'] or 0),
        'orders_paid_today': orders_paid_today.count(),
        'signups_today': User.objects.filter(date_joined__date=today).count(),
        'avg_order_value': int(
            Order.objects.filter(status='paid').aggregate(avg=Avg('amount'))['avg'] or 0
        ),
    }


def build_action_queue(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """صف اقدامات فوری — اولویت‌بندی شده."""
    items: List[Dict[str, Any]] = []
    queue = [
        ('pending_card_transfers', 'پرداخت کارت‌به‌کارت', 'fa-money-check', 'amber', '#adm-ops', 'بررسی'),
        ('unread_tickets', 'تیکت خوانده‌نشده', 'fa-headset', 'rose', '#adm-ops', 'پاسخ'),
        ('orders_pending', 'سفارش پرداخت‌نشده', 'fa-clock', 'violet', '#adm-reports', 'پیگیری'),
        ('users_pending_payment', 'کاربر با سفارش معلق', 'fa-user-clock', 'blue', '#adm-reports', 'تماس'),
        ('licenses_expiring_soon', 'لایسنس در شرف انقضا', 'fa-hourglass-half', 'cyan', '#adm-reports', 'تمدید'),
        ('pending_withdrawals', 'برداشت همکار فروش', 'fa-wallet', 'emerald', '#adm-ops', 'تأیید'),
        ('users_without_license', 'بدون لایسنس فعال', 'fa-user-slash', 'indigo', '#adm-reports', 'فروش'),
    ]
    for key, title, icon, accent, anchor, action in queue:
        count = int(stats.get(key) or 0)
        if count > 0:
            items.append({
                'key': key,
                'title': title,
                'count': count,
                'icon': icon,
                'accent': accent,
                'anchor': anchor,
                'action': action,
            })
    return items


def get_activity_feed(limit: int = 14) -> List[Dict[str, Any]]:
    """فید فعالیت اخیر — سفارش، ثبت‌نام، تیکت، کارت‌به‌کارت."""
    events: List[Dict[str, Any]] = []

    for order in (
        Order.objects.filter(status='paid')
        .select_related('user', 'product')
        .order_by('-paid_at')[:8]
    ):
        if not order.paid_at:
            continue
        events.append({
            'type': 'order_paid',
            'icon': 'fa-circle-check',
            'accent': 'emerald',
            'title': f'پرداخت {order.product.title if order.product_id else "سفارش"}',
            'meta': order.user.get_full_name() or order.user.username,
            'amount': int(order.amount or 0),
            'at': order.paid_at,
        })

    for user in User.objects.order_by('-date_joined')[:6]:
        events.append({
            'type': 'signup',
            'icon': 'fa-user-plus',
            'accent': 'blue',
            'title': 'ثبت‌نام جدید',
            'meta': user.get_full_name() or user.username or user.phone,
            'amount': None,
            'at': user.date_joined,
        })

    for ticket in (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-created_at')[:5]
    ):
        events.append({
            'type': 'ticket',
            'icon': 'fa-headset',
            'accent': 'rose',
            'title': ticket.subject[:60],
            'meta': ticket.user.get_full_name() or ticket.user.username,
            'amount': None,
            'at': ticket.created_at,
            'unread': ticket.staff_has_unread,
        })

    for ct in (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order__user', 'order__product')
        .order_by('-created_at')[:4]
    ):
        events.append({
            'type': 'card_transfer',
            'icon': 'fa-money-check',
            'accent': 'amber',
            'title': 'کارت‌به‌کارت در انتظار',
            'meta': ct.order.user.get_full_name() or ct.order.user.username,
            'amount': int(ct.order.amount or 0),
            'at': ct.created_at,
        })

    events.sort(key=lambda e: e['at'], reverse=True)
    return events[:limit]


def build_health_indicators(stats: Dict[str, Any], sms_balance: Dict[str, Any]) -> List[Dict[str, Any]]:
    """وضعیت سلامت زیرسیستم‌ها."""
    indicators = [
        {
            'key': 'users',
            'label': 'کاربران',
            'status': 'ok' if stats.get('users_active', 0) > 0 else 'warn',
            'detail': f"{stats.get('users_active', 0)} فعال",
        },
        {
            'key': 'licenses',
            'label': 'لایسنس',
            'status': 'warn' if stats.get('licenses_expiring_soon', 0) > 5 else 'ok',
            'detail': f"{stats.get('licenses_active', 0)} فعال",
        },
        {
            'key': 'orders',
            'label': 'سفارش',
            'status': 'warn' if stats.get('orders_pending', 0) > 10 else 'ok',
            'detail': f"{stats.get('conversion_rate', 0)}٪ تبدیل",
        },
        {
            'key': 'sms',
            'label': 'پیامک',
            'status': 'error' if sms_balance.get('error') else ('warn' if sms_balance.get('is_low') else 'ok'),
            'detail': (
                f"{int(sms_balance.get('credit') or 0):,} ت"
                if sms_balance.get('ok') else 'خطا'
            ),
        },
        {
            'key': 'support',
            'label': 'پشتیبانی',
            'status': 'warn' if stats.get('unread_tickets', 0) > 0 else 'ok',
            'detail': f"{stats.get('open_tickets', 0)} تیکت باز",
        },
    ]
    return indicators


def get_affiliate_partners(limit: int = TABLE_FETCH_LIMIT):
    """لیست مشاوران فروش با آمار کمیسیون."""
    return (
        Affiliate.objects.select_related('user', 'user__wallet')
        .annotate(
            sales_count=Count('sales'),
            sales_paid=Count('sales', filter=Q(sales__status='paid')),
            commission_total=Sum(
                'sales__commission_amount',
                filter=Q(sales__status='paid'),
            ),
            commission_pending=Sum(
                'sales__commission_amount',
                filter=Q(sales__status='pending'),
            ),
        )
        .order_by('-sales_paid', '-created_at')[:limit]
    )


def get_recent_affiliate_sales(limit: int = TABLE_FETCH_LIMIT):
    """فروش‌های اخیر همکاری در فروش."""
    return (
        AffiliateSale.objects.select_related(
            'affiliate',
            'affiliate__user',
            'order',
            'order__user',
            'order__product',
        )
        .order_by('-created_at')[:limit]
    )


def get_admin_dashboard_context(days: int = 30) -> Dict[str, Any]:
    stats = get_overview_stats()
    sms_balance = get_sms_balance_snapshot()
    order_status = get_order_status_breakdown()
    license_status = get_license_status_breakdown()
    payment_methods = get_payment_method_breakdown()
    plan_sales = get_plan_sales_breakdown()
    product_revenue = get_product_revenue()
    status_max = max((item['count'] for item in order_status), default=1) or 1
    today_stats = get_today_stats()

    return {
        'stats': stats,
        'today_stats': today_stats,
        'sms_balance': sms_balance,
        'action_queue': build_action_queue(stats),
        'activity_feed': get_activity_feed(),
        'health_indicators': build_health_indicators(stats, sms_balance),
        'charts': build_charts_payload(days),
        'order_status': order_status,
        'order_status_max': status_max,
        'license_status': license_status,
        'license_status_max': max((item['count'] for item in license_status), default=1) or 1,
        'payment_methods': payment_methods,
        'plan_sales': plan_sales,
        'product_revenue': product_revenue,
        'recent_orders': get_recent_orders(),
        'recent_users': get_recent_users(),
        'pending_orders': get_pending_orders(),
        'users_with_pending_orders': get_users_with_pending_orders(),
        'expiring_licenses': get_expiring_licenses(),
        'users_without_license_list': get_users_without_license_preview(),
        'pending_card_transfers': get_pending_card_transfers(),
        'open_tickets': get_open_tickets(),
        'pending_withdrawals': get_pending_withdrawals(),
        'affiliate_partners': get_affiliate_partners(),
        'recent_affiliate_sales': get_recent_affiliate_sales(),
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'export_catalog': get_export_catalog(days=days),
        'export_categories': {
            'orders': 'سفارش‌ها',
            'users': 'کاربران',
            'licenses': 'لایسنس‌ها',
            'finance': 'مالی',
            'support': 'پشتیبانی',
        },
        'chart_days': days,
        'products_count': Product.objects.filter(is_active=True).count(),
        'windows_app_stats': get_windows_app_stats(),
        'windows_download_logs': get_windows_download_logs(TABLE_FETCH_LIMIT),
        'windows_activations': get_windows_activations(TABLE_FETCH_LIMIT),
        'windows_first_launches': get_windows_first_launches(TABLE_FETCH_LIMIT),
        'windows_user_funnel': get_windows_user_funnel(TABLE_FETCH_LIMIT),
    }
