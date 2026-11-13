"""تایم‌لاین یکپارچه فعالیت — بدون حدس‌زدن رویدادهای لاگ‌نشده."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Q
from django.utils import timezone

from accounts.services.admin_user_360.common import _jalali, resolve_timeline_days_filter
from accounts.services.admin_users_management import ORDER_STATUS_LABELS
from licenses.models import ClientAppEvent
from mobile_api.models import MobileDevice, MobileExtractionRun
from shop.models import DownloadLog, Order
from workspace.models import Customer, CRMDeal, Dataset, Ticket

PLATFORM_LABELS = {
    'web': 'وب',
    'shop': 'فروشگاه',
    'windows': 'ویندوز',
    'android': 'اندروید',
    'workspace': 'فضای کار',
    'crm': 'مخاطبین',
    'support': 'پشتیبانی',
    '—': '—',
}

EVENT_LABELS = {
    'signup': 'ثبت‌نام',
    'login_marker': 'آخرین ورود ثبت‌شده',
    'order': 'سفارش',
    'download': 'دانلود ویندوز',
    'app_event': 'رویداد اپ',
    'android_device': 'ثبت دستگاه اندروید',
    'extraction': 'استخراج موبایل',
    'dataset': 'ایجاد دیتاست',
    'crm_contact': 'مخاطب CRM',
    'crm_deal': 'معامله CRM',
    'ticket': 'تیکت پشتیبانی',
}


def _event(
    *,
    kind: str,
    at,
    platform: str = '—',
    success: Optional[bool] = True,
    title: str,
    detail: str = '',
    record_id: str = '',
    record_url: str = '',
) -> Dict[str, Any]:
    return {
        'kind': kind,
        'kind_label': EVENT_LABELS.get(kind, kind),
        'at': at.isoformat() if at else None,
        'at_jalali': _jalali(at),
        'platform': platform,
        'platform_label': PLATFORM_LABELS.get(platform, platform),
        'success': success,
        'title': title,
        'detail': detail,
        'record_id': record_id,
        'record_url': record_url,
    }


def build_activity_timeline(
    user,
    *,
    page: int = 1,
    page_size: int = 40,
    kind_filter: str = '',
    platform_filter: str = '',
    success_filter: str = '',
    sort: str = '-at',
    days: Optional[Any] = None,
) -> Dict[str, Any]:
    if isinstance(days, int):
        days_filtered: Optional[int] = days if days > 0 else None
    else:
        days_filtered = resolve_timeline_days_filter(days)
    events: List[Dict[str, Any]] = []

    if user.date_joined:
        events.append(_event(
            kind='signup',
            at=user.date_joined,
            platform='web',
            title='ثبت‌نام در فایلینگ دیوار',
        ))

    if user.last_login:
        events.append(_event(
            kind='login_marker',
            at=user.last_login,
            platform='—',
            title='آخرین ورود به حساب',
            detail='فقط زمان آخرین ورود به حساب در دسترس است؛ جزئیات هر بار ورود جداگانه ذخیره نمی‌شود.',
        ))

    since = None
    if days_filtered:
        since = timezone.now() - timedelta(days=max(1, days_filtered))

    order_qs = Order.objects.filter(user=user).order_by('-created_at')
    if since:
        order_qs = order_qs.filter(created_at__gte=since)
    for o in order_qs[:200]:
        success = o.status == 'paid'
        events.append(_event(
            kind='order',
            at=o.created_at,
            platform='shop',
            success=success if o.status != 'granted' else True,
            title=f'سفارش — {ORDER_STATUS_LABELS.get(o.status, o.status)}',
            detail=f'مبلغ {int(o.amount or 0):,} تومان',
            record_id=str(o.id),
        ))

    dl_qs = DownloadLog.objects.filter(user=user).order_by('-created_at')
    if since:
        dl_qs = dl_qs.filter(created_at__gte=since)
    for d in dl_qs[:100]:
        events.append(_event(
            kind='download',
            at=d.created_at,
            platform='windows',
            title='دانلود نرم‌افزار ویندوز',
            record_id=str(d.id),
        ))

    ev_qs = ClientAppEvent.objects.filter(user=user).select_related('license').order_by('-created_at')
    if since:
        ev_qs = ev_qs.filter(created_at__gte=since)
    for ev in ev_qs[:150]:
        events.append(_event(
            kind='app_event',
            at=ev.created_at,
            platform=ev.platform or 'windows',
            title=ev.get_event_type_display(),
            detail=ev.app_version or '',
            record_id=str(ev.id),
        ))

    dev_qs = MobileDevice.objects.filter(user=user).order_by('-registered_at')
    if since:
        dev_qs = dev_qs.filter(registered_at__gte=since)
    for d in dev_qs[:50]:
        events.append(_event(
            kind='android_device',
            at=d.registered_at or d.last_seen_at,
            platform='android',
            title='ثبت دستگاه اندروید',
            detail=d.device_model or '—',
            record_id=str(d.id),
        ))

    run_qs = MobileExtractionRun.objects.filter(user=user).order_by('-started_at')
    if since:
        run_qs = run_qs.filter(started_at__gte=since)
    for run in run_qs[:80]:
        ok = run.status not in ('failed', 'cancelled')
        events.append(_event(
            kind='extraction',
            at=run.started_at,
            platform='android',
            success=ok,
            title=f'استخراج — {run.get_status_display() if hasattr(run, "get_status_display") else run.status}',
            record_id=str(run.id),
        ))

    ds_qs = Dataset.objects.filter(user=user).order_by('-created_at')
    if since:
        ds_qs = ds_qs.filter(created_at__gte=since)
    for ds in ds_qs[:80]:
        events.append(_event(
            kind='dataset',
            at=ds.created_at,
            platform='workspace',
            title='ایجاد دیتاست',
            detail=ds.name,
            record_id=str(ds.id),
        ))

    c_qs = Customer.objects.filter(user=user).order_by('-created_at')
    if since:
        c_qs = c_qs.filter(created_at__gte=since)
    for c in c_qs[:80]:
        events.append(_event(
            kind='crm_contact',
            at=c.created_at,
            platform='crm',
            title='مخاطب CRM',
            detail=c.name or c.phone or '',
            record_id=str(c.id),
        ))

    deal_qs = CRMDeal.objects.filter(user=user).order_by('-created_at')
    if since:
        deal_qs = deal_qs.filter(created_at__gte=since)
    for deal in deal_qs[:80]:
        events.append(_event(
            kind='crm_deal',
            at=deal.created_at,
            platform='crm',
            title='معامله CRM',
            detail=deal.title or '',
            record_id=str(deal.id),
        ))

    t_qs = Ticket.objects.filter(user=user).order_by('-created_at')
    if since:
        t_qs = t_qs.filter(created_at__gte=since)
    for t in t_qs[:50]:
        events.append(_event(
            kind='ticket',
            at=t.created_at,
            platform='support',
            title='ثبت تیکت',
            detail=t.subject,
            record_id=t.ticket_number,
        ))

    if kind_filter:
        events = [e for e in events if e['kind'] == kind_filter]
    if platform_filter:
        events = [e for e in events if e['platform'] == platform_filter]
    if success_filter == 'ok':
        events = [e for e in events if e.get('success') is True]
    elif success_filter == 'fail':
        events = [e for e in events if e.get('success') is False]

    reverse = sort.startswith('-')
    events.sort(key=lambda e: e.get('at') or '', reverse=reverse)

    total = len(events)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    page_events = events[start:start + page_size]

    return {
        'events': page_events,
        'filters': {
            'kinds': [{'key': k, 'label': v} for k, v in EVENT_LABELS.items()],
            'platforms': ['web', 'shop', 'windows', 'android', 'workspace', 'crm', 'support'],
        },
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        },
    }


def daily_activity_counts(user, *, days: int = 30) -> List[Dict[str, Any]]:
    """شمارش رویدادهای قابل‌اتکا در هر روز — برای نمودار."""
    from collections import defaultdict

    tl = build_activity_timeline(user, page=1, page_size=500, days=days)
    buckets: Dict[str, int] = defaultdict(int)
    for ev in tl['events']:
        at = ev.get('at')
        if not at:
            continue
        day = at[:10]
        buckets[day] += 1
    labels = sorted(buckets.keys())[-days:]
    return [{'date': d, 'count': buckets[d]} for d in labels]
