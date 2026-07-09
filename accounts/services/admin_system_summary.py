"""خلاصه کامل سیستم برای خروجی JSON پنل مدیریت."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from affiliates.models import Affiliate, AffiliateSale, Withdrawal
from licenses.models import License, LicenseActivation
from shop.models import CardTransferSubmission, Order, Product
from workspace.models import Dataset, Ticket
from workspace.services.jalali_input import to_persian_digits

from accounts.services.admin_dashboard import (
    PENDING_ORDER_STATUSES,
    get_license_status_breakdown,
    get_order_status_breakdown,
    get_overview_stats,
    get_payment_method_breakdown,
    get_plan_sales_breakdown,
    get_product_revenue,
    get_revenue_series,
    get_user_registration_series,
)

User = get_user_model()


def _iso(dt) -> str | None:
    if not dt:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.isoformat()
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.isoformat()


def _jalali(dt) -> str | None:
    if not dt:
        return None
    try:
        if isinstance(dt, date) and not isinstance(dt, datetime):
            j = jdatetime.date.fromgregorian(date=dt)
            return to_persian_digits(j.strftime('%Y/%m/%d'))
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        jdt = jdatetime.datetime.fromgregorian(datetime=dt)
        if jdt.hour or jdt.minute or jdt.second:
            return to_persian_digits(jdt.strftime('%Y/%m/%d %H:%M'))
        return to_persian_digits(jdt.strftime('%Y/%m/%d'))
    except Exception:
        return str(dt)


def _user_brief(user) -> Dict[str, Any]:
    return {
        'id': user.pk,
        'username': user.username,
        'full_name': user.get_full_name() or '',
        'phone': user.phone or '',
        'email': user.email or '',
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'date_joined': _iso(user.date_joined),
        'date_joined_jalali': _jalali(user.date_joined),
    }


def _order_brief(order: Order) -> Dict[str, Any]:
    return {
        'id': str(order.id),
        'user': _user_brief(order.user),
        'product': order.product.title,
        'plan': order.plan.name,
        'amount': int(order.amount),
        'discount_amount': int(order.discount_amount or 0),
        'status': order.status,
        'status_label': order.get_status_display(),
        'payment_method': order.payment_method,
        'payment_method_label': order.get_payment_method_display(),
        'created_at': _iso(order.created_at),
        'created_at_jalali': _jalali(order.created_at),
        'paid_at': _iso(order.paid_at),
        'paid_at_jalali': _jalali(order.paid_at),
    }


def _license_brief(lic: License) -> Dict[str, Any]:
    now = timezone.now()
    days_left = None
    if lic.expires_at:
        days_left = (lic.expires_at - now).days
    return {
        'license_key': lic.license_key,
        'status': lic.status,
        'status_label': lic.get_status_display(),
        'plan': lic.plan.name,
        'max_activations': lic.max_activations,
        'active_devices': lic.activations.filter(is_active=True).count(),
        'user': _user_brief(lic.order.user),
        'expires_at': _iso(lic.expires_at),
        'expires_at_jalali': _jalali(lic.expires_at),
        'days_until_expiry': days_left,
        'created_at': _iso(lic.created_at),
        'created_at_jalali': _jalali(lic.created_at),
    }


def _ticket_brief(ticket: Ticket) -> Dict[str, Any]:
    return {
        'ticket_number': ticket.ticket_number,
        'subject': ticket.subject,
        'category': ticket.category,
        'category_label': ticket.get_category_display_fa(),
        'priority': ticket.priority,
        'priority_label': ticket.get_priority_display_fa(),
        'status': ticket.status,
        'status_label': ticket.get_status_display_fa(),
        'staff_has_unread': ticket.staff_has_unread,
        'user': _user_brief(ticket.user),
        'created_at': _iso(ticket.created_at),
        'created_at_jalali': _jalali(ticket.created_at),
        'last_message_at': _iso(ticket.last_message_at),
        'last_message_at_jalali': _jalali(ticket.last_message_at),
    }


def _pending_orders(limit: int = 50) -> List[Dict[str, Any]]:
    qs = (
        Order.objects.filter(status__in=PENDING_ORDER_STATUSES)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )
    return [_order_brief(o) for o in qs]


def _recent_paid_orders(limit: int = 30) -> List[Dict[str, Any]]:
    qs = (
        Order.objects.filter(status='paid')
        .select_related('user', 'product', 'plan')
        .order_by('-paid_at')[:limit]
    )
    return [_order_brief(o) for o in qs]


def _users_with_pending_orders(limit: int = 50) -> List[Dict[str, Any]]:
    qs = (
        User.objects.filter(orders__status__in=PENDING_ORDER_STATUSES)
        .annotate(
            pending_count=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            pending_total=Sum('orders__amount', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            last_pending=Max('orders__created_at', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .distinct()
        .order_by('-last_pending')[:limit]
    )
    rows = []
    for u in qs:
        products = list(
            Order.objects.filter(user=u, status__in=PENDING_ORDER_STATUSES)
            .values_list('product__title', flat=True)
            .distinct()
        )
        rows.append({
            **_user_brief(u),
            'pending_count': u.pending_count,
            'pending_total': int(u.pending_total or 0),
            'last_pending_at': _iso(u.last_pending),
            'last_pending_at_jalali': _jalali(u.last_pending),
            'pending_products': products,
        })
    return rows


def _expiring_licenses(limit: int = 50) -> List[Dict[str, Any]]:
    now = timezone.now()
    qs = (
        License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=now + timedelta(days=14),
        )
        .select_related('order__user', 'plan')
        .prefetch_related('activations')
        .order_by('expires_at')[:limit]
    )
    return [_license_brief(lic) for lic in qs]


def _expired_licenses(limit: int = 30) -> List[Dict[str, Any]]:
    qs = (
        License.objects.filter(status='expired')
        .select_related('order__user', 'plan')
        .prefetch_related('activations')
        .order_by('-expires_at')[:limit]
    )
    return [_license_brief(lic) for lic in qs]


def _active_licenses_sample(limit: int = 30) -> List[Dict[str, Any]]:
    now = timezone.now()
    qs = (
        License.objects.filter(status='active')
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related('order__user', 'plan')
        .prefetch_related('activations')
        .order_by('-created_at')[:limit]
    )
    return [_license_brief(lic) for lic in qs]


def _users_without_license(limit: int = 50) -> List[Dict[str, Any]]:
    now = timezone.now()
    active_license = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    qs = (
        User.objects.filter(is_active=True)
        .annotate(
            has_active_license=Exists(active_license),
            paid_orders=Count('orders', filter=Q(orders__status='paid')),
            pending_orders=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .filter(has_active_license=False)
        .order_by('-date_joined')[:limit]
    )
    return [
        {
            **_user_brief(u),
            'paid_orders': u.paid_orders,
            'pending_orders': u.pending_orders,
        }
        for u in qs
    ]


def _recent_users(limit: int = 30) -> List[Dict[str, Any]]:
    qs = User.objects.order_by('-date_joined')[:limit]
    return [_user_brief(u) for u in qs]


def _pending_card_transfers(limit: int = 30) -> List[Dict[str, Any]]:
    qs = (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order__user', 'order__product', 'order__plan')
        .order_by('-created_at')[:limit]
    )
    return [
        {
            'order_id': str(ct.order_id),
            'reference_number': ct.reference_number,
            'payer_name': ct.payer_name or '',
            'amount': int(ct.order.amount),
            'user': _user_brief(ct.order.user),
            'product': ct.order.product.title,
            'created_at': _iso(ct.created_at),
            'created_at_jalali': _jalali(ct.created_at),
        }
        for ct in qs
    ]


def _open_tickets(limit: int = 30) -> List[Dict[str, Any]]:
    qs = (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-staff_has_unread', '-last_message_at', '-created_at')[:limit]
    )
    return [_ticket_brief(t) for t in qs]


def _pending_withdrawals(limit: int = 30) -> List[Dict[str, Any]]:
    qs = (
        Withdrawal.objects.filter(status='pending')
        .select_related('wallet__user')
        .order_by('-created_at')[:limit]
    )
    return [
        {
            'id': w.pk,
            'amount': int(w.amount),
            'bank_name': w.bank_name,
            'bank_account': w.bank_account,
            'account_holder': w.account_holder,
            'user': _user_brief(w.wallet.user),
            'created_at': _iso(w.created_at),
            'created_at_jalali': _jalali(w.created_at),
        }
        for w in qs
    ]


def _affiliate_summary() -> Dict[str, Any]:
    sales = AffiliateSale.objects.aggregate(
        total_commission=Sum('commission_amount'),
        paid_commission=Sum('commission_amount', filter=Q(status='paid')),
        pending_commission=Sum('commission_amount', filter=Q(status='pending')),
        sales_count=Count('id'),
    )
    top = (
        AffiliateSale.objects.values('affiliate__code', 'affiliate__user__username', 'affiliate__user__phone')
        .annotate(total=Sum('commission_amount'), count=Count('id'))
        .order_by('-total')[:10]
    )
    return {
        'active_affiliates': Affiliate.objects.filter(is_active=True).count(),
        'total_affiliates': Affiliate.objects.count(),
        'sales_count': sales['sales_count'] or 0,
        'total_commission': int(sales['total_commission'] or 0),
        'paid_commission': int(sales['paid_commission'] or 0),
        'pending_commission': int(sales['pending_commission'] or 0),
        'top_affiliates': [
            {
                'code': row['affiliate__code'],
                'username': row['affiliate__user__username'] or '',
                'phone': row['affiliate__user__phone'] or '',
                'commission_total': int(row['total'] or 0),
                'sales_count': row['count'],
            }
            for row in top
        ],
    }


def _products_summary() -> List[Dict[str, Any]]:
    products = Product.objects.annotate(
        paid_orders=Count('product_orders', filter=Q(product_orders__status='paid')),
        revenue=Sum('product_orders__amount', filter=Q(product_orders__status='paid')),
        plans_count=Count('plans'),
    ).order_by('-revenue')
    return [
        {
            'id': p.pk,
            'title': p.title,
            'slug': p.slug,
            'is_active': p.is_active,
            'plans_count': p.plans_count,
            'paid_orders': p.paid_orders,
            'revenue': int(p.revenue or 0),
        }
        for p in products
    ]


def _workspace_summary() -> Dict[str, Any]:
    return {
        'datasets_total': Dataset.objects.count(),
        'datasets_by_user_top': list(
            Dataset.objects.values('user__username', 'user__phone')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        ),
        'open_tickets': Ticket.objects.exclude(status='closed').count(),
        'unread_tickets': Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count(),
        'tickets_by_status': list(
            Ticket.objects.values('status').annotate(count=Count('id')).order_by('-count')
        ),
    }


def _action_items(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    if stats.get('pending_card_transfers'):
        items.append({
            'priority': 'high',
            'key': 'card_transfers',
            'title': 'پرداخت کارت‌به‌کارت در انتظار تایید',
            'count': stats['pending_card_transfers'],
        })
    if stats.get('orders_pending'):
        items.append({
            'priority': 'high',
            'key': 'pending_orders',
            'title': 'سفارش پرداخت‌نشده',
            'count': stats['orders_pending'],
        })
    if stats.get('users_pending_payment'):
        items.append({
            'priority': 'medium',
            'key': 'users_pending_payment',
            'title': 'کاربر با سفارش معلق',
            'count': stats['users_pending_payment'],
        })
    if stats.get('unread_tickets'):
        items.append({
            'priority': 'medium',
            'key': 'unread_tickets',
            'title': 'تیکت پشتیبانی خوانده‌نشده',
            'count': stats['unread_tickets'],
        })
    if stats.get('pending_withdrawals'):
        items.append({
            'priority': 'medium',
            'key': 'pending_withdrawals',
            'title': 'درخواست برداشت در انتظار',
            'count': stats['pending_withdrawals'],
        })
    if stats.get('licenses_expiring_soon'):
        items.append({
            'priority': 'low',
            'key': 'expiring_licenses',
            'title': 'لایسنس در شرف انقضا (۱۴ روز)',
            'count': stats['licenses_expiring_soon'],
        })
    if stats.get('users_without_license'):
        items.append({
            'priority': 'low',
            'key': 'users_without_license',
            'title': 'کاربر بدون لایسنس فعال',
            'count': stats['users_without_license'],
        })
    return items


def build_system_summary(days: int = 30, detail_limit: int = 50) -> Dict[str, Any]:
    """ساخت خلاصه کامل سیستم برای خروجی JSON."""
    days = max(7, min(int(days or 30), 90))
    detail_limit = max(10, min(int(detail_limit or 50), 200))
    now = timezone.now()
    stats = get_overview_stats()

    return {
        'meta': {
            'generated_at': _iso(now),
            'generated_at_jalali': _jalali(now),
            'timezone': str(timezone.get_current_timezone()),
            'range_days': days,
            'detail_limit': detail_limit,
            'version': '1.0',
            'source': 'filing-divar-admin-panel',
        },
        'overview': stats,
        'action_items': _action_items(stats),
        'breakdowns': {
            'order_status': get_order_status_breakdown(),
            'license_status': get_license_status_breakdown(),
            'payment_methods': get_payment_method_breakdown(),
            'plan_sales': get_plan_sales_breakdown(limit=15),
            'product_revenue': get_product_revenue(),
        },
        'trends': {
            'revenue': get_revenue_series(days),
            'user_signups': get_user_registration_series(days),
        },
        'products': _products_summary(),
        'affiliates': _affiliate_summary(),
        'workspace': _workspace_summary(),
        'lists': {
            'pending_orders': _pending_orders(detail_limit),
            'users_with_pending_orders': _users_with_pending_orders(detail_limit),
            'recent_paid_orders': _recent_paid_orders(min(detail_limit, 30)),
            'recent_users': _recent_users(min(detail_limit, 30)),
            'users_without_license': _users_without_license(detail_limit),
            'active_licenses_sample': _active_licenses_sample(min(detail_limit, 30)),
            'expiring_licenses': _expiring_licenses(detail_limit),
            'expired_licenses': _expired_licenses(min(detail_limit, 30)),
            'pending_card_transfers': _pending_card_transfers(detail_limit),
            'open_tickets': _open_tickets(detail_limit),
            'pending_withdrawals': _pending_withdrawals(detail_limit),
        },
    }


def system_summary_json_response(
    days: int = 30,
    detail_limit: int = 50,
    *,
    download: bool = True,
) -> HttpResponse:
    payload = build_system_summary(days=days, detail_limit=detail_limit)
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    if download:
        stamp = jdatetime.datetime.now().strftime('%Y%m%d-%H%M')
        filename = f'filing-divar-system-summary-{stamp}.json'
        response = HttpResponse(body, content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
