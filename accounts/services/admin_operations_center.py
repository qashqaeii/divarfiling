"""مرکز عملیات — سلامت سیستم، SMS، بک‌آپ و KPI عملیاتی."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.db import connection
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from accounts.models import SmsMessageLog
from accounts.services.admin_dashboard import (
    _date_range,
    _fill_daily_series,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
    get_operations_stats,
    get_system_meta,
    get_system_start_at,
)
from accounts.services.admin_database_backup import get_database_backup_info
from accounts.services.sms import get_sms_balance_snapshot
from workspace.models import Dataset, Ticket


def _cache_backend_label() -> str:
    backend = settings.CACHES.get('default', {}).get('BACKEND', '')
    if 'redis' in backend.lower():
        return 'Redis'
    return 'Cache'


def _check_database_health() -> Tuple[str, str]:
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        vendor = connection.vendor or 'db'
        labels = {'postgresql': 'PostgreSQL', 'sqlite': 'SQLite', 'mysql': 'MySQL'}
        return 'ok', labels.get(vendor, 'متصل')
    except Exception:
        return 'critical', 'قطع / خطا'


def _check_cache_health() -> Tuple[str, str]:
    from django.core.cache import cache

    label = _cache_backend_label()
    try:
        probe_key = 'admin:ops:health:ping'
        cache.set(probe_key, '1', 5)
        if cache.get(probe_key) == '1':
            return 'ok', f'{label} متصل'
        return 'warning', f'{label} پاسخ نامعتبر'
    except Exception:
        return 'critical', f'{label} خطا'


def _check_app_health() -> Tuple[str, str]:
    meta = get_system_meta()
    return 'ok', meta.get('server_label') or 'عملیاتی'


def _check_sms_health(sms_balance: Dict[str, Any]) -> Tuple[str, str]:
    if sms_balance.get('error'):
        return 'critical', 'خطا در دریافت موجودی'
    if not sms_balance.get('enabled', True):
        return 'warning', 'ارسال غیرفعال'
    if sms_balance.get('is_low'):
        credit = int(sms_balance.get('credit') or 0)
        return 'warning', f'{credit:,} تومان'
    if sms_balance.get('ok'):
        if sms_balance.get('sms_count') is not None:
            return 'ok', f"{int(sms_balance['sms_count']):,} پیامک"
        credit = int(sms_balance.get('credit') or 0)
        return 'ok', f'{credit:,} تومان'
    return 'warning', 'نامشخص'


def _check_backup_health(backup_info: Dict[str, Any]) -> Tuple[str, str]:
    engine = backup_info.get('engine', '')
    if 'postgresql' in engine and not backup_info.get('pg_dump_available'):
        return 'warning', 'JSON (dumpdata)'
    return 'ok', backup_info.get('default_label') or 'آماده'


def _check_support_health(open_tickets: int, unread_tickets: int) -> Tuple[str, str]:
    if unread_tickets > 0:
        return 'warning', f'{unread_tickets} خوانده‌نشده'
    return 'ok', f'{open_tickets} باز'


def build_operations_health(
    *,
    sms_balance: Dict[str, Any],
    backup_info: Dict[str, Any],
    open_tickets: int,
    unread_tickets: int,
) -> List[Dict[str, Any]]:
    checks = [
        ('app', 'اپ / Django', 'fa-server', _check_app_health()),
        ('database', 'پایگاه داده', 'fa-database', _check_database_health()),
        ('cache', _cache_backend_label(), 'fa-bolt', _check_cache_health()),
        ('sms', 'پیامک', 'fa-comment-sms', _check_sms_health(sms_balance)),
        ('backup', 'ذخیره‌سازی / بک‌آپ', 'fa-hard-drive', _check_backup_health(backup_info)),
        ('support', 'پشتیبانی / صف', 'fa-headset', _check_support_health(open_tickets, unread_tickets)),
    ]
    return [
        {
            'key': key,
            'label': label,
            'icon': icon,
            'status': status,
            'detail': detail,
        }
        for key, label, icon, (status, detail) in checks
    ]


def _ticket_counts() -> Dict[str, int]:
    return {
        'open_tickets': Ticket.objects.exclude(status='closed').count(),
        'unread_tickets': Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count(),
    }


def _uptime_days() -> int | None:
    start = get_system_start_at()
    if not start:
        return None
    now = timezone.now()
    start_local = timezone.localtime(start) if timezone.is_aware(start) else start
    return max(0, (now.date() - start_local.date()).days)


def _sms_in_range(start, end) -> int:
    return SmsMessageLog.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _sms_failed_in_range(start, end) -> int:
    return SmsMessageLog.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
        status=SmsMessageLog.Status.FAILED,
    ).count()


def _datasets_in_range(start, end) -> int:
    return Dataset.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _sms_sent_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        SmsMessageLog.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _datasets_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        Dataset.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _series_has_data(series: Dict[str, List]) -> bool:
    return sum(series.get('values') or []) > 0


def _build_charts(days: int) -> Dict[str, Any]:
    sms = _sms_sent_series(days)
    datasets = _datasets_series(days)
    charts: Dict[str, Any] = {}
    if _series_has_data(sms):
        charts['sms_usage_trend'] = {
            'type': 'line',
            'labels': sms['labels'],
            'datasets': [{
                'label': 'پیامک ارسالی',
                'data': sms['values'],
                'borderColor': 'rgba(59, 130, 246, 1)',
                'backgroundColor': 'rgba(59, 130, 246, 0.12)',
                'fill': True,
                'tension': 0.35,
            }],
            'axis': 'count',
        }
    if _series_has_data(datasets):
        charts['dataset_activity_trend'] = {
            'type': 'bar',
            'labels': datasets['labels'],
            'datasets': [{
                'label': 'Dataset جدید',
                'data': datasets['values'],
                'backgroundColor': 'rgba(6, 182, 212, 0.75)',
                'borderRadius': 6,
            }],
            'axis': 'count',
        }
    return charts


def _safe_backup_info(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'engine_label': raw.get('engine_label', ''),
        'default_format': raw.get('default_format', 'auto'),
        'default_label': raw.get('default_label', ''),
        'pg_dump_available': raw.get('pg_dump_available', False),
        'supports_custom_dump': raw.get('supports_custom_dump', False),
    }


def _build_snapshot_kpi_cards(
    *,
    sms_balance: Dict[str, Any],
    operations_stats: Dict[str, Any],
    uptime_days: int | None,
    backup_info: Dict[str, Any],
    sms_failed_7d: int,
) -> List[Dict[str, Any]]:
    sms_value = 0
    sms_format = 'count'
    sms_label = 'موجودی SMS'
    if sms_balance.get('ok'):
        if sms_balance.get('sms_count') is not None:
            sms_value = int(sms_balance['sms_count'])
            sms_label = 'موجودی SMS (تعداد)'
        else:
            sms_value = int(sms_balance.get('credit') or 0)
            sms_format = 'money'
            sms_label = 'موجودی SMS (تومان)'

    cards = [
        {
            'key': 'sms_balance',
            'label': sms_label,
            'value': sms_value,
            'format': sms_format,
            'delta': None,
            'delta_label': 'Snapshot',
            'sublabel': sms_balance.get('provider_label') or 'پیامک',
            'sparkline': [],
            'icon': 'fa-comment-sms',
            'accent': 'amber' if sms_balance.get('is_low') else 'blue',
            'status': 'warn' if sms_balance.get('is_low') else ('error' if sms_balance.get('error') else 'ok'),
        },
        {
            'key': 'datasets_total',
            'label': 'کل Dataset',
            'value': operations_stats.get('datasets_total', 0),
            'format': 'count',
            'delta': None,
            'delta_label': 'Snapshot',
            'sublabel': 'workspace',
            'sparkline': [],
            'icon': 'fa-table',
            'accent': 'cyan',
            'status': 'ok',
        },
        {
            'key': 'system_uptime',
            'label': 'آپ‌تایم سیستم',
            'value': uptime_days if uptime_days is not None else 0,
            'format': 'count',
            'delta': None,
            'delta_label': 'Snapshot',
            'sublabel': 'روز',
            'sparkline': [],
            'icon': 'fa-clock',
            'accent': 'emerald',
            'status': 'ok' if uptime_days is not None else 'warn',
            'pending': uptime_days is None,
        },
        {
            'key': 'backup_ready',
            'label': 'بک‌آپ DB',
            'value': 1 if backup_info.get('default_label') else 0,
            'format': 'count',
            'delta': None,
            'delta_label': backup_info.get('engine_label', ''),
            'sublabel': backup_info.get('default_label', ''),
            'sparkline': [],
            'icon': 'fa-hard-drive',
            'accent': 'violet',
            'status': 'warn' if (
                'postgresql' in (backup_info.get('engine') or '')
                and not backup_info.get('pg_dump_available')
            ) else 'ok',
            'display_text': backup_info.get('default_label', '—'),
        },
        {
            'key': 'sms_failed_7d',
            'label': 'SMS ناموفق (۷ روز)',
            'value': sms_failed_7d,
            'format': 'count',
            'delta': None,
            'delta_label': 'Snapshot',
            'sublabel': 'خطای عملیاتی',
            'sparkline': [],
            'icon': 'fa-triangle-exclamation',
            'accent': 'rose',
            'status': 'warn' if sms_failed_7d else 'ok',
        },
    ]
    return cards


def _build_range_kpi_cards(
    *,
    days: int,
    range_label: str,
    sms_sent: int,
    prev_sms_sent: int,
    sms_failed: int,
    prev_sms_failed: int,
    datasets_created: int,
    prev_datasets_created: int,
) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'sms_sent_period',
            'label': 'پیامک ارسالی',
            'value': sms_sent,
            'format': 'count',
            'delta': _pct_change(sms_sent, prev_sms_sent),
            'delta_label': range_label,
            'sublabel': 'لاگ SMS',
            'sparkline': _sms_sent_series(days)['values'][-7:],
            'icon': 'fa-paper-plane',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'sms_failed_period',
            'label': 'SMS ناموفق',
            'value': sms_failed,
            'format': 'count',
            'delta': _pct_change(sms_failed, prev_sms_failed),
            'delta_label': range_label,
            'sublabel': 'خطای ارسال',
            'sparkline': [],
            'icon': 'fa-circle-xmark',
            'accent': 'rose',
            'status': 'warn' if sms_failed else 'ok',
        },
        {
            'key': 'datasets_created_period',
            'label': 'Dataset جدید',
            'value': datasets_created,
            'format': 'count',
            'delta': _pct_change(datasets_created, prev_datasets_created),
            'delta_label': range_label,
            'sublabel': 'آپلود کاربر',
            'sparkline': _datasets_series(days)['values'][-7:],
            'icon': 'fa-file-import',
            'accent': 'cyan',
            'status': 'ok',
        },
    ]


def build_operations_action_items(
    *,
    days: int,
    sms_balance: Dict[str, Any],
    backup_info: Dict[str, Any],
    system_health: List[Dict[str, Any]],
    sms_failed_period: int,
    unread_tickets: int,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    panel_qs = f'?days={days}'

    if sms_balance.get('is_low') and sms_balance.get('ok'):
        credit = int(sms_balance.get('credit') or 0)
        items.append({
            'key': 'sms_low',
            'priority': 'critical',
            'title': 'موجودی SMS کم',
            'count': credit,
            'detail': f'{credit:,} تومان باقی‌مانده',
            'icon': 'fa-comment-sms',
            'accent': 'amber',
            'cta': 'شارژ پنل',
            'href': '#ops-sms',
        })
    elif sms_balance.get('error'):
        items.append({
            'key': 'sms_error',
            'priority': 'critical',
            'title': 'خطای موجودی SMS',
            'count': 1,
            'detail': (sms_balance.get('error') or '')[:80],
            'icon': 'fa-comment-sms',
            'accent': 'rose',
            'cta': 'بررسی',
            'href': '#ops-sms',
        })

    engine = backup_info.get('engine', '')
    if 'postgresql' in engine and not backup_info.get('pg_dump_available'):
        items.append({
            'key': 'backup_pg_dump',
            'priority': 'medium',
            'title': 'pg_dump در دسترس نیست',
            'count': 1,
            'detail': 'بک‌آپ SQL نیاز به نصب pg_dump دارد',
            'icon': 'fa-hard-drive',
            'accent': 'violet',
            'cta': 'JSON backup',
            'href': reverse('admin_panel_database_backup') + '?format=dumpdata',
        })

    for h in system_health:
        if h['status'] in ('warning', 'critical') and h['key'] not in ('sms', 'backup'):
            items.append({
                'key': f"health_{h['key']}",
                'priority': 'high' if h['status'] == 'critical' else 'medium',
                'title': h['label'],
                'count': 1,
                'detail': h['detail'],
                'icon': h['icon'],
                'accent': 'rose' if h['status'] == 'critical' else 'amber',
                'cta': 'مشاهده',
                'href': f"#ops-health-{h['key']}",
            })

    if sms_failed_period > 0:
        items.append({
            'key': 'sms_failed_period',
            'priority': 'high',
            'title': 'SMS ناموفق در بازه',
            'count': sms_failed_period,
            'detail': f'{sms_failed_period} ارسال ناموفق',
            'icon': 'fa-circle-xmark',
            'accent': 'rose',
            'cta': 'جزئیات',
            'href': '#ops-range-kpi',
        })

    if unread_tickets > 0:
        items.append({
            'key': 'unread_tickets',
            'priority': 'high',
            'title': 'تیکت خوانده‌نشده',
            'count': unread_tickets,
            'detail': f'{unread_tickets} تیکت نیاز به پاسخ',
            'icon': 'fa-headset',
            'accent': 'rose',
            'cta': 'پشتیبانی',
            'href': reverse('admin_panel') + panel_qs + '#ecc-support',
        })

    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    items.sort(key=lambda i: (priority_order.get(i['priority'], 9), -int(i.get('count') or 0)))
    return items


def get_operations_center_context(*, days: int = 30, compare: bool = False) -> Dict[str, Any]:
    del compare

    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)

    sms_balance = get_sms_balance_snapshot()
    operations_stats = get_operations_stats()
    backup_raw = get_database_backup_info()
    backup_info = _safe_backup_info(backup_raw)
    backup_info['engine'] = backup_raw.get('engine', '')

    tickets = _ticket_counts()
    uptime_days = _uptime_days()
    system_health = build_operations_health(
        sms_balance=sms_balance,
        backup_info=backup_raw,
        open_tickets=tickets['open_tickets'],
        unread_tickets=tickets['unread_tickets'],
    )

    sms_sent = _sms_in_range(start, end)
    prev_sms_sent = _sms_in_range(prev_start, prev_end)
    sms_failed = _sms_failed_in_range(start, end)
    prev_sms_failed = _sms_failed_in_range(prev_start, prev_end)
    datasets_created = _datasets_in_range(start, end)
    prev_datasets_created = _datasets_in_range(prev_start, prev_end)

    charts = _build_charts(days)
    system_meta = get_system_meta()
    environment_label = 'توسعه' if settings.DEBUG else 'عملیاتی'

    snapshot_kpis = _build_snapshot_kpi_cards(
        sms_balance=sms_balance,
        operations_stats=operations_stats,
        uptime_days=uptime_days,
        backup_info=backup_raw,
        sms_failed_7d=operations_stats.get('sms_failed_7d', 0),
    )
    range_kpis = _build_range_kpi_cards(
        days=days,
        range_label=range_label,
        sms_sent=sms_sent,
        prev_sms_sent=prev_sms_sent,
        sms_failed=sms_failed,
        prev_sms_failed=prev_sms_failed,
        datasets_created=datasets_created,
        prev_datasets_created=prev_datasets_created,
    )

    return {
        'chart_days': days,
        'range_label': range_label,
        'system_health': system_health,
        'action_items': build_operations_action_items(
            days=days,
            sms_balance=sms_balance,
            backup_info=backup_raw,
            system_health=system_health,
            sms_failed_period=sms_failed,
            unread_tickets=tickets['unread_tickets'],
        ),
        'snapshot_kpi_cards': snapshot_kpis,
        'range_kpi_cards': range_kpis,
        'kpi_cards': range_kpis + snapshot_kpis,
        'charts': charts,
        'charts_enabled': bool(charts),
        'period_metrics': {
            'sms_sent': sms_sent,
            'sms_failed': sms_failed,
            'datasets_created': datasets_created,
        },
        'sms_balance': sms_balance,
        'operations_stats': operations_stats,
        'backup_info': backup_info,
        'system_meta': system_meta,
        'system_metadata': {
            'version': system_meta.get('version', ''),
            'uptime_days': uptime_days,
            'environment': environment_label,
            'engine_label': backup_info.get('engine_label', ''),
            'backup_label': backup_info.get('default_label', ''),
        },
        'backup_urls': {
            'auto': reverse('admin_panel_database_backup') + '?format=auto',
            'dumpdata': reverse('admin_panel_database_backup') + '?format=dumpdata',
            'sqlite': reverse('admin_panel_database_backup') + '?format=sqlite',
            'pg_dump': reverse('admin_panel_database_backup') + '?format=pg_dump',
        },
        'system_summary_url': reverse('admin_panel_system_summary') + f'?days={days}',
        'marketing_url': reverse('admin_panel_marketing'),
    }
