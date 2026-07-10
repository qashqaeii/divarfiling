"""آمار و داده نمودار برای پنل مدیریت سیستم."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from workspace.services.jalali_input import to_persian_digits

from accounts.services.admin_exports import get_export_catalog
from accounts.services.sms import get_sms_balance_snapshot

from affiliates.models import Affiliate, AffiliateSale, Withdrawal
from licenses.models import License, LicenseActivation
from shop.models import CardTransferSubmission, Order, Product
from workspace.models import Dataset, Ticket

User = get_user_model()

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

PENDING_ORDER_STATUSES = ('pending', 'pending_verification')

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


def get_pending_orders(limit: int = 15):
    return (
        Order.objects.filter(status__in=PENDING_ORDER_STATUSES)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )


def get_users_with_pending_orders(limit: int = 12):
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


def get_expiring_licenses(limit: int = 10):
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


def get_users_without_license_preview(limit: int = 10):
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


def get_recent_orders(limit: int = 10):
    return (
        Order.objects.select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )


def get_recent_users(limit: int = 10):
    return User.objects.order_by('-date_joined')[:limit]


def get_pending_card_transfers(limit: int = 8):
    return (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order', 'order__user', 'order__product')
        .order_by('-created_at')[:limit]
    )


def get_open_tickets(limit: int = 8):
    return (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-staff_has_unread', '-last_message_at', '-created_at')[:limit]
    )


def get_pending_withdrawals(limit: int = 6):
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


def get_admin_dashboard_context(days: int = 30) -> Dict[str, Any]:
    stats = get_overview_stats()
    order_status = get_order_status_breakdown()
    license_status = get_license_status_breakdown()
    payment_methods = get_payment_method_breakdown()
    plan_sales = get_plan_sales_breakdown()
    product_revenue = get_product_revenue()
    status_max = max((item['count'] for item in order_status), default=1) or 1

    return {
        'stats': stats,
        'sms_balance': get_sms_balance_snapshot(),
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
    }
