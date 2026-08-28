"""مرکز CRM — Adoption، Funnel و عملیات مدیریتی فایلینگ."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Set

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Exists, Max, OuterRef, Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _date_range,
    _fill_daily_series,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
    _today,
    get_crm_overview_stats,
)
from workspace.constants import DEAL_STAGE_WON, DEAL_TERMINAL_STAGES
from workspace.models import CRMDeal, CRMProperty, Customer, CustomerActivity, Reminder

User = get_user_model()

STALE_OPEN_DEAL_DAYS = 30
OPEN_DEAL_Q = ~Q(stage__in=DEAL_TERMINAL_STAGES)
ACTIVE_PROPERTY_Q = Q(deleted_at__isnull=True)
CRM_CENTER_CACHE_SECONDS = 120


def _safe_user_display(user) -> str:
    return user.get_full_name() or user.username or 'کاربر'


def _customers_new_between(start, end) -> int:
    return Customer.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _properties_new_between(start, end) -> int:
    return CRMProperty.objects.filter(
        ACTIVE_PROPERTY_Q,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _deals_new_between(start, end) -> int:
    return CRMDeal.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _deals_won_between(start, end) -> int:
    return CRMDeal.objects.filter(
        stage=DEAL_STAGE_WON,
        closed_at__isnull=False,
        closed_at__date__gte=start,
        closed_at__date__lte=end,
    ).count()


def _reminders_created_between(start, end) -> int:
    return Reminder.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _crm_active_user_ids_between(start, end) -> Set[int]:
    """شناسه کاربران فعال CRM در بازه — بدون JOIN سنگین روی User."""
    date_q = {'created_at__date__gte': start, 'created_at__date__lte': end}
    ids: Set[int] = set()
    ids.update(Customer.objects.filter(**date_q).values_list('user_id', flat=True))
    ids.update(
        CRMProperty.objects.filter(deleted_at__isnull=True, **date_q).values_list('user_id', flat=True)
    )
    ids.update(CRMDeal.objects.filter(**date_q).values_list('user_id', flat=True))
    ids.update(Reminder.objects.filter(**date_q).values_list('user_id', flat=True))
    ids.update(
        CustomerActivity.objects.filter(**date_q).values_list('customer__user_id', flat=True)
    )
    ids.discard(None)
    return ids


def _crm_active_users_between(start, end) -> int:
    ids = _crm_active_user_ids_between(start, end)
    if not ids:
        return 0
    return User.objects.filter(is_active=True, pk__in=ids).count()


def _build_range_kpi_cards(
    *,
    days: int,
    customers_new: int,
    prev_customers_new: int,
    properties_new: int,
    prev_properties_new: int,
    deals_new: int,
    prev_deals_new: int,
    deals_won: int,
    prev_deals_won: int,
    reminders_created: int,
    prev_reminders_created: int,
    crm_active_users: int,
    prev_crm_active_users: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)

    def card(key, label, value, prev, icon, accent):
        return {
            'key': key,
            'kind': 'range',
            'label': label,
            'sublabel': range_label,
            'value': value,
            'format': 'count',
            'delta': _pct_change(value, prev),
            'delta_label': 'نسبت دوره قبل',
            'icon': icon,
            'accent': accent,
            'status': 'ok',
        }

    return [
        card('customers_new_period', 'مشتری جدید', customers_new, prev_customers_new, 'fa-address-book', 'blue'),
        card('properties_new_period', 'ملک جدید', properties_new, prev_properties_new, 'fa-building', 'cyan'),
        card('deals_new_period', 'معامله جدید', deals_new, prev_deals_new, 'fa-handshake', 'violet'),
        card('deals_won_period', 'معامله موفق', deals_won, prev_deals_won, 'fa-circle-check', 'emerald'),
        card('reminders_created_period', 'یادآور جدید', reminders_created, prev_reminders_created, 'fa-bell', 'amber'),
        card(
            'crm_active_users_period',
            'کاربر فعال CRM',
            crm_active_users,
            prev_crm_active_users,
            'fa-users',
            'indigo',
        ),
    ]


def _build_snapshot_kpi_cards(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'contacts_total',
            'kind': 'snapshot',
            'label': 'کل مشتریان',
            'sublabel': 'وضعیت فعلی',
            'value': snapshot['contacts_total'],
            'format': 'count',
            'icon': 'fa-address-book',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'properties_total',
            'kind': 'snapshot',
            'label': 'کل املاک',
            'sublabel': 'وضعیت فعلی',
            'value': snapshot['properties_total'],
            'format': 'count',
            'icon': 'fa-building',
            'accent': 'cyan',
            'status': 'ok',
        },
        {
            'key': 'deals_open',
            'kind': 'snapshot',
            'label': 'معاملات باز',
            'sublabel': 'وضعیت فعلی',
            'value': snapshot['deals_open'],
            'format': 'count',
            'icon': 'fa-handshake',
            'accent': 'violet',
            'status': 'ok' if snapshot['deals_open'] < 50 else 'warn',
        },
        {
            'key': 'reminders_due',
            'kind': 'snapshot',
            'label': 'یادآور سررسید',
            'sublabel': 'وضعیت فعلی',
            'value': snapshot['reminders_due'],
            'format': 'count',
            'icon': 'fa-bell',
            'accent': 'rose',
            'status': 'warn' if snapshot['reminders_due'] else 'ok',
        },
    ]


def _build_adoption_stats(*, crm_active_users_period: int) -> Dict[str, Any]:
    eligible_users = User.objects.filter(is_active=True).count()
    if not eligible_users:
        return {
            'eligible_users': 0,
            'users_with_customer': 0,
            'users_with_property': 0,
            'users_with_deal': 0,
            'users_with_any_crm': 0,
            'users_without_crm': 0,
            'crm_active_users_period': crm_active_users_period,
            'adoption_pct': None,
        }

    active_qs = User.objects.filter(is_active=True)
    users_with_customer = active_qs.filter(crm_customers__isnull=False).distinct().count()
    users_with_property = active_qs.filter(
        crm_properties__deleted_at__isnull=True,
    ).distinct().count()
    users_with_deal = active_qs.filter(crm_deals__isnull=False).distinct().count()

    has_any_q = (
        Exists(Customer.objects.filter(user_id=OuterRef('pk')))
        | Exists(CRMProperty.objects.filter(user_id=OuterRef('pk'), deleted_at__isnull=True))
        | Exists(CRMDeal.objects.filter(user_id=OuterRef('pk')))
    )
    users_with_any = active_qs.annotate(_has_any=has_any_q).filter(_has_any=True).count()
    users_without = max(0, eligible_users - users_with_any)
    adoption_pct = round((users_with_any / eligible_users) * 100, 1) if eligible_users else None
    return {
        'eligible_users': eligible_users,
        'users_with_customer': users_with_customer,
        'users_with_property': users_with_property,
        'users_with_deal': users_with_deal,
        'users_with_any_crm': users_with_any,
        'users_without_crm': users_without,
        'crm_active_users_period': crm_active_users_period,
        'adoption_pct': adoption_pct,
    }


def _build_pipeline_distribution() -> List[Dict[str, Any]]:
    rows = (
        CRMDeal.objects.filter(OPEN_DEAL_Q)
        .values('stage')
        .annotate(count=Count('id'))
        .order_by('-count', 'stage')
    )
    return [{'stage': row['stage'] or '—', 'count': row['count']} for row in rows]


def _overdue_delay_label(due_at, now) -> str:
    if not due_at:
        return '—'
    if timezone.is_aware(due_at) and timezone.is_naive(now):
        now = timezone.make_aware(now)
    delta = now - due_at
    days = delta.days
    if days <= 0:
        hours = max(1, delta.seconds // 3600)
        return f'{hours} ساعت'
    return f'{days} روز'


def _snapshot_action_counts(now) -> Dict[str, int]:
    today = _today()
    stale_cutoff = now - timedelta(days=STALE_OPEN_DEAL_DAYS)
    return {
        'overdue_reminders': Reminder.objects.filter(is_done=False, due_at__lt=now).count(),
        'stale_open_deals': CRMDeal.objects.filter(OPEN_DEAL_Q, updated_at__lt=stale_cutoff).count(),
        'customers_overdue_followup': Customer.objects.filter(
            next_follow_up__isnull=False,
            next_follow_up__lt=today,
        ).count(),
    }


def build_crm_action_items(counts: Dict[str, int]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if counts.get('overdue_reminders', 0):
        items.append({
            'key': 'overdue_reminders',
            'priority': 'critical',
            'title': 'یادآور عقب‌افتاده',
            'count': counts['overdue_reminders'],
            'detail': f"{counts['overdue_reminders']} مورد نیاز به پیگیری",
            'icon': 'fa-bell',
            'accent': 'rose',
            'cta': 'مشاهده',
            'href': '#crm-table-reminders',
        })
    if counts.get('stale_open_deals', 0):
        items.append({
            'key': 'stale_open_deals',
            'priority': 'high',
            'title': 'معامله باز قدیمی',
            'count': counts['stale_open_deals'],
            'detail': f"بدون تغییر {STALE_OPEN_DEAL_DAYS} روز+",
            'icon': 'fa-hourglass-half',
            'accent': 'amber',
            'cta': 'مشاهده',
            'href': '#crm-table-deals',
        })
    if counts.get('customers_overdue_followup', 0):
        items.append({
            'key': 'customers_overdue_followup',
            'priority': 'medium',
            'title': 'پیگیری عقب‌افتاده',
            'count': counts['customers_overdue_followup'],
            'detail': 'next_follow_up گذشته',
            'icon': 'fa-user-clock',
            'accent': 'blue',
            'cta': 'Admin',
            'href': reverse('admin:workspace_customer_changelist'),
        })
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    items.sort(key=lambda i: (priority_order.get(i['priority'], 9), -int(i.get('count') or 0)))
    return items


def _series_created(model, start, end, *, extra_q=None, days: int):
    qs = model.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    if extra_q is not None:
        qs = qs.filter(extra_q)
    rows = (
        qs.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return labels, values


def _deals_won_series(start, end, days: int):
    rows = (
        CRMDeal.objects.filter(
            stage=DEAL_STAGE_WON,
            closed_at__isnull=False,
            closed_at__date__gte=start,
            closed_at__date__lte=end,
        )
        .annotate(day=TruncDate('closed_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return labels, values


def _build_charts(days: int) -> Dict[str, Any]:
    start, end = _date_range(days)
    cust_labels, cust_values = _series_created(Customer, start, end, days=days)
    prop_labels, prop_values = _series_created(
        CRMProperty, start, end, extra_q=ACTIVE_PROPERTY_Q, days=days,
    )
    deal_labels, deal_values = _series_created(CRMDeal, start, end, days=days)
    won_labels, won_values = _deals_won_series(start, end, days=days)

    has_usage = sum(cust_values + prop_values + deal_values) > 0
    has_deals = sum(deal_values + won_values) > 0
    charts: Dict[str, Any] = {}
    if has_usage:
        charts['crm_usage_trend'] = {
            'type': 'combo',
            'labels': cust_labels,
            'datasets': [
                {
                    'label': 'مشتری',
                    'data': cust_values,
                    'type': 'line',
                    'borderColor': 'rgba(59, 130, 246, 1)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.08)',
                    'fill': False,
                    'tension': 0.3,
                    'yAxisID': 'y',
                },
                {
                    'label': 'ملک',
                    'data': prop_values,
                    'type': 'line',
                    'borderColor': 'rgba(6, 182, 212, 1)',
                    'backgroundColor': 'rgba(6, 182, 212, 0.08)',
                    'fill': False,
                    'tension': 0.3,
                    'yAxisID': 'y',
                },
                {
                    'label': 'معامله',
                    'data': deal_values,
                    'type': 'bar',
                    'backgroundColor': 'rgba(124, 58, 237, 0.65)',
                    'borderRadius': 4,
                    'yAxisID': 'y',
                },
            ],
            'axis': 'count',
        }
    if has_deals:
        charts['crm_deals_trend'] = {
            'type': 'combo',
            'labels': deal_labels,
            'datasets': [
                {
                    'label': 'ایجاد معامله',
                    'data': deal_values,
                    'type': 'bar',
                    'backgroundColor': 'rgba(124, 58, 237, 0.65)',
                    'borderRadius': 4,
                    'yAxisID': 'y',
                },
                {
                    'label': 'معامله موفق',
                    'data': won_values,
                    'type': 'line',
                    'borderColor': 'rgba(16, 185, 129, 1)',
                    'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                    'fill': True,
                    'tension': 0.35,
                    'yAxisID': 'y',
                },
            ],
            'axis': 'count',
        }
    return charts


def _serialize_open_deals(deals) -> List[Dict[str, Any]]:
    rows = []
    for deal in deals:
        rows.append({
            'user_display': _safe_user_display(deal.user),
            'user_admin_url': reverse('admin:accounts_user_change', args=[deal.user_id]),
            'title': deal.title[:60],
            'customer_label': deal.customer.name[:40] if deal.customer_id else '—',
            'customer_admin_url': (
                reverse('admin:workspace_customer_change', args=[deal.customer_id])
                if deal.customer_id else ''
            ),
            'stage': deal.stage,
            'created_at': deal.created_at,
            'updated_at': deal.updated_at,
        })
    return rows


def _serialize_overdue_reminders(items, now) -> List[Dict[str, Any]]:
    rows = []
    for reminder in items:
        rows.append({
            'user_display': _safe_user_display(reminder.user),
            'user_admin_url': reverse('admin:accounts_user_change', args=[reminder.user_id]),
            'title': reminder.title[:60],
            'due_at': reminder.due_at,
            'delay_label': _overdue_delay_label(reminder.due_at, now),
            'admin_url': reverse('admin:workspace_reminder_change', args=[reminder.pk]),
        })
    return rows


def _serialize_active_users(users_qs) -> List[Dict[str, Any]]:
    rows = []
    for row in users_qs:
        user = row['user']
        last_at = row.get('last_activity_at')
        rows.append({
            'user_display': _safe_user_display(user),
            'user_admin_url': reverse('admin:accounts_user_change', args=[user.pk]),
            'customers_count': row.get('customers_count', 0),
            'properties_count': row.get('properties_count', 0),
            'deals_count': row.get('deals_count', 0),
            'last_activity_at': last_at,
        })
    return rows


def _active_crm_users_preview(start, end, limit: int = TABLE_PREVIEW_ROWS) -> List[Dict[str, Any]]:
    user_ids = _crm_active_user_ids_between(start, end)
    if not user_ids:
        return []

    date_q = Q(created_at__date__gte=start, created_at__date__lte=end)
    last_by_user: Dict[int, Any] = {}

    def _merge_last(rows, key='last'):
        for row in rows:
            uid = row['user_id']
            ts = row[key]
            if ts and (uid not in last_by_user or ts > last_by_user[uid]):
                last_by_user[uid] = ts

    _merge_last(
        Customer.objects.filter(user_id__in=user_ids).filter(date_q)
        .values('user_id').annotate(last=Max('updated_at'))
    )
    _merge_last(
        CRMProperty.objects.filter(user_id__in=user_ids, deleted_at__isnull=True).filter(date_q)
        .values('user_id').annotate(last=Max('updated_at'))
    )
    _merge_last(
        CRMDeal.objects.filter(user_id__in=user_ids).filter(date_q)
        .values('user_id').annotate(last=Max('updated_at'))
    )
    _merge_last(
        Reminder.objects.filter(user_id__in=user_ids).filter(date_q)
        .values('user_id').annotate(last=Max('created_at'))
    )

    ranked_ids = sorted(
        last_by_user.keys(),
        key=lambda uid: last_by_user[uid],
        reverse=True,
    )[:limit]
    if not ranked_ids:
        ranked_ids = list(user_ids)[:limit]

    annotated = {
        row.pk: row
        for row in User.objects.filter(pk__in=ranked_ids).annotate(
            customers_count=Count('crm_customers', distinct=True),
            properties_count=Count(
                'crm_properties',
                distinct=True,
                filter=Q(crm_properties__deleted_at__isnull=True),
            ),
            deals_count=Count('crm_deals', distinct=True),
        )
    }

    result = []
    for uid in ranked_ids:
        user = annotated.get(uid)
        if not user:
            continue
        result.append({
            'user': user,
            'customers_count': user.customers_count,
            'properties_count': user.properties_count,
            'deals_count': user.deals_count,
            'last_activity_at': last_by_user.get(uid),
        })
    return result


def _build_snapshot_from_overview() -> Dict[str, Any]:
    overview = get_crm_overview_stats()
    return {
        'contacts_total': overview['contacts_total'],
        'properties_total': overview['properties_total'],
        'deals_total': overview['deals_total'],
        'deals_open': overview['deals_open'],
        'reminders_total': overview['reminders_total'],
        'reminders_due': overview['reminders_due'],
    }


def get_crm_center_context(*, days: int = 30, compare: bool = False) -> Dict[str, Any]:
    del compare

    cache_key = f'admin:crm_center:v2:{days}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    ctx = _build_crm_center_context(days=days)
    cache.set(cache_key, ctx, CRM_CENTER_CACHE_SECONDS)
    return ctx


def _build_crm_center_context(*, days: int = 30) -> Dict[str, Any]:
    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)
    now = timezone.now()
    snapshot = _build_snapshot_from_overview()

    customers_new = _customers_new_between(start, end)
    properties_new = _properties_new_between(start, end)
    deals_new = _deals_new_between(start, end)
    deals_won = _deals_won_between(start, end)
    reminders_created = _reminders_created_between(start, end)
    crm_active_users = _crm_active_users_between(start, end)

    charts = _build_charts(days)
    action_counts = _snapshot_action_counts(now)

    open_deals = (
        CRMDeal.objects.filter(OPEN_DEAL_Q)
        .select_related('user', 'customer')
        .order_by('-updated_at')[:TABLE_PREVIEW_ROWS]
    )
    overdue_reminders = (
        Reminder.objects.filter(is_done=False, due_at__lt=now)
        .select_related('user')
        .order_by('due_at')[:TABLE_PREVIEW_ROWS]
    )

    return {
        'range_label': range_label,
        'days': days,
        'range_kpi_cards': _build_range_kpi_cards(
            days=days,
            customers_new=customers_new,
            prev_customers_new=_customers_new_between(prev_start, prev_end),
            properties_new=properties_new,
            prev_properties_new=_properties_new_between(prev_start, prev_end),
            deals_new=deals_new,
            prev_deals_new=_deals_new_between(prev_start, prev_end),
            deals_won=deals_won,
            prev_deals_won=_deals_won_between(prev_start, prev_end),
            reminders_created=reminders_created,
            prev_reminders_created=_reminders_created_between(prev_start, prev_end),
            crm_active_users=crm_active_users,
            prev_crm_active_users=_crm_active_users_between(prev_start, prev_end),
        ),
        'snapshot_kpi_cards': _build_snapshot_kpi_cards(snapshot),
        'adoption': _build_adoption_stats(crm_active_users_period=crm_active_users),
        'pipeline_distribution': _build_pipeline_distribution(),
        'action_items': build_crm_action_items(action_counts),
        'action_counts': action_counts,
        'charts': charts,
        'charts_enabled': bool(charts),
        'open_deals_rows': _serialize_open_deals(open_deals),
        'overdue_reminder_rows': _serialize_overdue_reminders(overdue_reminders, now),
        'active_user_rows': _serialize_active_users(_active_crm_users_preview(start, end)),
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'workspace_urls': {
            'dashboard': reverse('workspace:crm_dashboard'),
            'deals': reverse('workspace:crm_deals'),
            'contacts': reverse('workspace:crm_contacts'),
            'properties': reverse('workspace:crm_properties'),
            'reminders': reverse('workspace:crm_reminders'),
        },
        'admin_list_urls': {
            'customers': reverse('admin:workspace_customer_changelist'),
            'properties': reverse('admin:workspace_crmproperty_changelist'),
            'reminders': reverse('admin:workspace_reminder_changelist'),
        },
    }
