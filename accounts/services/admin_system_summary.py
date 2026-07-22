"""خلاصه آماری یکپارچه سیستم برای خروجی JSON پنل مدیریت.

فقط اعداد و KPI — بدون لیست‌های ریزجزئیات.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import jdatetime
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from affiliates.models import Affiliate, AffiliateSale, Withdrawal
from licenses.models import License
from shop.models import Product
from workspace.models import Dataset, Ticket
from workspace.services.jalali_input import to_persian_digits

from accounts.services.admin_academy import get_academy_dashboard_stats
from accounts.services.admin_blog import get_blog_dashboard_stats
from accounts.services.admin_dashboard import (
    get_license_status_breakdown,
    get_order_status_breakdown,
    get_overview_stats,
    get_payment_method_breakdown,
    get_plan_sales_breakdown,
    get_product_revenue,
    get_revenue_series,
    get_user_registration_series,
)


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


def _trend_totals(series: Dict[str, Any]) -> Dict[str, Any]:
    """خلاصه عددی از یک سری زمانی بدون نگه داشتن ریز نقاط در overview."""
    values = series.get('values') or series.get('counts') or []
    if not isinstance(values, list):
        values = []
    total = sum(int(v or 0) for v in values)
    return {
        'points': len(values),
        'total': total,
        'avg': round(total / len(values), 1) if values else 0,
        'last': int(values[-1] or 0) if values else 0,
        'peak': max((int(v or 0) for v in values), default=0),
    }


def _blog_summary() -> Dict[str, Any]:
    s = get_blog_dashboard_stats()
    return {
        'posts_total': s['posts_total'],
        'posts_published': s['posts_published'],
        'posts_draft': s['posts_draft'],
        'views_total': s['views_total'],
        'avg_views': s['avg_views'],
        'published_month': s['published_month'],
        'created_month': s['created_month'],
        'week_published': s['week_published'],
        'categories_total': s['categories_total'],
        'tags_total': s['tags_total'],
    }


def _academy_summary() -> Dict[str, Any]:
    s = get_academy_dashboard_stats()
    return {
        'videos_total': s['videos_total'],
        'videos_active': s['videos_active'],
        'videos_public': s['videos_public'],
        'videos_private': s['videos_private'],
        'views_total': s['views_total'],
        'avg_views': s['avg_views'],
        'learners_total': s['learners_total'],
        'completions_total': s['completions_total'],
        'completions_month': s['completions_month'],
        'starts_week': s['starts_week'],
        'paths_total': s['paths_total'],
        'mission_started': s['mission_started'],
        'mission_completed': s['mission_completed'],
        'mission_rate': s['mission_rate'],
    }


def _marketing_summary() -> Dict[str, Any]:
    """آمار بازاریابی بدون محاسبه سنگین اندازه سگمنت‌ها."""
    from accounts.models import MarketingCampaign, SmsMessageLog
    from accounts.services.admin_marketing import _marketing_attribution
    from accounts.services.recovery_attribution import executive_attribution_summary

    completed = MarketingCampaign.objects.filter(status=MarketingCampaign.Status.COMPLETED)
    agg = completed.aggregate(
        campaigns=Count('id'),
        sent=Sum('sent_count'),
        failed=Sum('failed_count'),
        skipped=Sum('skipped_count'),
    )
    sent_total = int(agg['sent'] or 0)
    failed_total = int(agg['failed'] or 0)
    attempted = sent_total + failed_total
    delivery_rate = round(100 * sent_total / attempted) if attempted else None

    since_30 = timezone.now() - timedelta(days=30)
    sms_30d = SmsMessageLog.objects.filter(
        purpose='marketing',
        status__in=('sent', 'fake'),
        created_at__gte=since_30,
    ).count()
    pending_send = SmsMessageLog.objects.filter(
        purpose='marketing',
        status=SmsMessageLog.Status.PENDING,
    ).count()

    attribution = _marketing_attribution()
    recovery_attr = executive_attribution_summary(since=since_30)
    campaign_revenue = int(attribution['revenue'] or 0)
    recovery_revenue = int(recovery_attr.get('recovery_revenue') or 0)

    return {
        'campaigns_total': int(agg['campaigns'] or 0),
        'sent_total': sent_total,
        'failed_total': failed_total,
        'skipped_total': int(agg['skipped'] or 0),
        'delivery_rate': delivery_rate,
        'click_rate': (
            round(100 * attribution['engaged_users'] / sent_total) if sent_total else None
        ),
        'conversion_rate': (
            round(100 * attribution['purchases'] / sent_total) if sent_total else None
        ),
        'purchases': attribution['purchases'],
        'campaign_revenue': campaign_revenue,
        'recovery_revenue': recovery_revenue,
        'recovery_purchases': int(recovery_attr.get('recovered') or 0),
        'total_assisted_revenue': campaign_revenue + recovery_revenue,
        'pending_send': pending_send,
        'sms_marketing_30d': sms_30d,
        'draft_campaigns': MarketingCampaign.objects.filter(
            status=MarketingCampaign.Status.DRAFT,
        ).count(),
        'sending_campaigns': MarketingCampaign.objects.filter(
            status=MarketingCampaign.Status.SENDING,
        ).count(),
    }


def _recovery_summary(*, days: int) -> Dict[str, Any]:
    from accounts.services.admin_recovery_center import build_recovery_funnel
    from accounts.services.pending_recovery import get_recovery_config
    from accounts.services.plan_bi import period_bounds
    from accounts.services.recovery_attribution import executive_attribution_summary

    bounds = period_bounds(days)
    since = bounds['since']
    now = bounds['now']
    attribution = executive_attribution_summary(since=since)
    funnel = build_recovery_funnel(since=since, now=now, attribution_summary=attribution)
    cfg = get_recovery_config(simulate_enabled=False)
    exec_kpi = funnel['executive']

    return {
        'flow_enabled': bool(cfg.get('flow_enabled')),
        'abandoned': exec_kpi.get('abandoned', 0),
        'eligible_now': exec_kpi.get('eligible_now', 0),
        'sms_accepted': exec_kpi.get('sms_accepted', 0),
        'sms_delivered': exec_kpi.get('sms_delivered', 0),
        'recovered': exec_kpi.get('recovered', 0),
        'recovery_revenue': exec_kpi.get('recovery_revenue', 0),
        'conversion_rate': exec_kpi.get('conversion_rate'),
        'revenue_per_sms': exec_kpi.get('revenue_per_sms'),
        'range_days': bounds['days'],
    }


def _workspace_summary() -> Dict[str, Any]:
    return {
        'datasets_total': Dataset.objects.count(),
        'open_tickets': Ticket.objects.exclude(status='closed').count(),
        'unread_tickets': Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count(),
        'tickets_by_status': {
            row['status']: row['count']
            for row in Ticket.objects.values('status').annotate(count=Count('id')).order_by('-count')
        },
        'pending_withdrawals': Withdrawal.objects.filter(status='pending').count(),
    }


def _affiliate_summary() -> Dict[str, Any]:
    sales = AffiliateSale.objects.aggregate(
        total_commission=Sum('commission_amount'),
        paid_commission=Sum('commission_amount', filter=Q(status='paid')),
        pending_commission=Sum('commission_amount', filter=Q(status='pending')),
        sales_count=Count('id'),
    )
    return {
        'active_affiliates': Affiliate.objects.filter(is_active=True).count(),
        'total_affiliates': Affiliate.objects.count(),
        'sales_count': sales['sales_count'] or 0,
        'total_commission': int(sales['total_commission'] or 0),
        'paid_commission': int(sales['paid_commission'] or 0),
        'pending_commission': int(sales['pending_commission'] or 0),
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


def _action_items(stats: Dict[str, Any], *, recovery: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
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
    if recovery and recovery.get('eligible_now'):
        items.append({
            'priority': 'high',
            'key': 'recovery_eligible',
            'title': 'واجد بازیابی تسویه',
            'count': recovery['eligible_now'],
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
    """ساخت خلاصه آماری یکپارچه — بدون لیست‌های ریزجزئیات.

    detail_limit برای سازگاری با API قبلی نگه داشته شده و نادیده گرفته می‌شود.
    """
    days = max(7, min(int(days or 30), 90))
    _ = detail_limit  # API سازگاری — خروجی فقط آماری است
    now = timezone.now()
    stats = get_overview_stats()

    revenue_series = get_revenue_series(days)
    signup_series = get_user_registration_series(days)
    blog = _blog_summary()
    academy = _academy_summary()
    marketing = _marketing_summary()
    recovery = _recovery_summary(days=days)
    workspace = _workspace_summary()

    overview = {
        k: (_iso(v) if k == 'system_start_at' else v)
        for k, v in stats.items()
    }
    overview['system_start_at_jalali'] = _jalali(stats.get('system_start_at'))

    return {
        'meta': {
            'generated_at': _iso(now),
            'generated_at_jalali': _jalali(now),
            'system_start_at': _iso(stats.get('system_start_at')),
            'system_start_at_jalali': _jalali(stats.get('system_start_at')),
            'system_uptime_days': stats.get('system_uptime_days'),
            'timezone': str(timezone.get_current_timezone()),
            'range_days': days,
            'mode': 'statistical_summary',
            'version': '2.0',
            'source': 'filing-divar-admin-panel',
            'sections': [
                'overview',
                'trends',
                'action_items',
                'workspace',
                'content',
                'marketing',
                'recovery',
                'sales',
                'affiliates',
            ],
        },
        'overview': overview,
        'action_items': _action_items(stats, recovery=recovery),
        'trends': {
            'revenue': {
                **_trend_totals(revenue_series),
                'series': revenue_series,
            },
            'user_signups': {
                **_trend_totals(signup_series),
                'series': signup_series,
            },
        },
        'workspace': workspace,
        'content': {
            'blog': blog,
            'academy': academy,
        },
        'marketing': marketing,
        'recovery': recovery,
        'sales': {
            'order_status': get_order_status_breakdown(),
            'license_status': get_license_status_breakdown(),
            'payment_methods': get_payment_method_breakdown(),
            'plan_sales': get_plan_sales_breakdown(limit=15),
            'product_revenue': get_product_revenue(),
            'products': _products_summary(),
            'licenses_active': License.objects.filter(status='active').count(),
            'licenses_expiring_soon': stats.get('licenses_expiring_soon', 0),
        },
        'affiliates': _affiliate_summary(),
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
