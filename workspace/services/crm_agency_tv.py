"""داشبورد TV آژانس — Payload امن، role-based و cache‌شده."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from workspace.constants import AGENCY_MANAGER_ROLES, CRM_STATUSES, DEAL_STAGE_WON
from workspace.models import (
    CRMAgency, CRMAgencyAuditLog, CRMAgencyMember, CRMDeal, Customer, CustomerActivity, PropertyVisit,
    WorkspaceSettings,
)
from workspace.services.crm_agency import get_team_inbox, role_label
from workspace.services.crm_audit import get_audit_event_meta
from workspace.services.crm_agency_analytics import (
    get_member_performance_row,
    get_team_goals_progress,
    get_team_performance,
    _activity_user_q,
)
from workspace.services.crm_agency_announcements import list_announcements
from workspace.services.crm_scope import get_membership
from workspace.services.jalali_input import format_jalali_date, to_persian_digits

# ── نسخه Schema — با تغییر ساختار Payload افزایش دهید ──
TV_PAYLOAD_SCHEMA_VERSION = 4
TV_CACHE_SECONDS = 35
TV_REFRESH_AFTER_SECONDS = 45

TV_ROLE_MANAGER = 'manager'
TV_ROLE_SECRETARY = 'secretary'
TV_ROLE_ADVISOR = 'advisor'

STATUS_DONUT_COLORS = {
    'جدید': '#3b82f6',
    'در حال پیگیری': '#f59e0b',
    'بازدید انجام شد': '#10b981',
    'قرارداد': '#f43f5e',
    'بایگانی': '#8b5cf6',
}

TREND_SERIES = (
    {'key': 'calls', 'color': '#7c3aed', 'label': 'تماس'},
    {'key': 'visits', 'color': '#06b6d4', 'label': 'بازدید'},
    {'key': 'leads', 'color': '#f59e0b', 'label': 'لید'},
    {'key': 'deals', 'color': '#22c55e', 'label': 'قرارداد'},
)

TV_WIDGETS_ALL = (
    'kpis',
    'leaderboard',
    'chart',
    'goals',
    'activity',
    'schedule',
    'alerts',
)

# KPI و Leaderboard همیشه نمایش داده می‌شوند؛ ticker جداگانه است.
ALLOWED_WIDGETS_BY_ROLE: Dict[str, Tuple[str, ...]] = {
    TV_ROLE_MANAGER: TV_WIDGETS_ALL,
    TV_ROLE_SECRETARY: ('kpis', 'leaderboard', 'chart', 'goals', 'activity', 'schedule', 'alerts'),
    TV_ROLE_ADVISOR: ('kpis', 'leaderboard', 'chart', 'goals', 'activity'),
}

PUBLIC_TV_AUDIT_EVENTS = frozenset({
    'lead.assigned',
    'lead.bulk_assigned',
    'announcement.created',
})

DEAL_STAGE_TV_LABELS = {
    'سرنخ': 'سرنخ جدید',
    'مذاکره': 'مذاکره جدید',
    'پیش‌قرارداد': 'پیش‌قرارداد جدید',
    'قرارداد': 'قرارداد جدید',
    'بسته‌شده': 'معامله بسته‌شده',
    'از دست رفته': 'معامله از دست رفته',
    DEAL_STAGE_WON: 'قرارداد موفق',
}

GOAL_METRIC_TITLES = {
    'calls': 'هدف تماس‌های تیم',
    'visits': 'هدف بازدیدهای تیم',
    'deals_closed': 'هدف قراردادهای تیم',
}

# کلیدهای ممنوع در JSON خروجی
FORBIDDEN_PAYLOAD_KEYS = frozenset({
    'phone', 'mobile', 'email', 'address', 'customer_name', 'customer_id',
    'notes', 'body', 'attachment_url', 'user_id', 'member_id', 'customer',
    'title', 'id', 'pk', 'api_key', 'slug',
})

METRIC_LABELS = {
    'calls': 'تماس',
    'visits': 'بازدید',
    'deals_closed': 'قرارداد',
}


def _looks_like_phone(value: str) -> bool:
    digits = ''.join(c for c in (value or '') if c.isdigit())
    return len(digits) >= 10 and digits.startswith('09')


def tv_safe_display_name(user) -> str:
    """نام امن برای TV — بدون شماره موبایل یا username عددی."""
    if not user:
        return 'عضو تیم'
    full = (user.get_full_name() or '').strip()
    if full and not _looks_like_phone(full):
        return full
    username = (user.username or '').strip()
    if username and not _looks_like_phone(username) and not username.isdigit():
        return username
    return 'عضو تیم'


def tv_safe_first_name(user) -> str:
    name = tv_safe_display_name(user)
    if name == 'عضو تیم':
        return name
    return name.split()[0]


def _agency_logo_url(agency: CRMAgency) -> Optional[str]:
    """لوگوی ثبت‌شده مالک آژانس در تنظیمات میزکار."""
    ws = (
        WorkspaceSettings.objects
        .filter(user_id=agency.owner_id)
        .only('agency_logo')
        .first()
    )
    if ws and ws.agency_logo:
        return ws.agency_logo.url
    return None


def resolve_tv_role(membership: CRMAgencyMember) -> str:
    if membership.role in AGENCY_MANAGER_ROLES:
        return TV_ROLE_MANAGER
    if membership.role == 'secretary':
        return TV_ROLE_SECRETARY
    return TV_ROLE_ADVISOR


def get_tv_cache_key(agency_id: int, role: str) -> str:
    return f'crm:agency:{agency_id}:tv:v{TV_PAYLOAD_SCHEMA_VERSION}:{role}'


def invalidate_tv_cache(agency_id: int) -> None:
    for role in ALLOWED_WIDGETS_BY_ROLE:
        cache.delete(get_tv_cache_key(agency_id, role))


def _delta_pct(current: int, previous: int) -> Optional[int]:
    if previous <= 0:
        return None if current <= 0 else 100
    return round((current - previous) * 100 / previous)


def _kpi_status(key: str, value: int) -> str:
    if key == 'overdue_followups' and value >= 10:
        return 'danger'
    if key == 'overdue_followups' and value >= 3:
        return 'warn'
    if key == 'inbox_unassigned' and value >= 5:
        return 'warn'
    if key == 'stale_leads' and value >= 3:
        return 'warn'
    return 'ok'


def _kpi_entry(value: int, delta: Optional[int], key: str) -> Dict[str, Any]:
    return {'value': value, 'delta': delta, 'status': _kpi_status(key, value)}


def _agency_activity_q(agency: CRMAgency):
    return Q(customer__agency=agency)


def _agency_visit_q(agency: CRMAgency):
    return Q(customer__agency=agency)


def _count_calls(agency: CRMAgency, day) -> int:
    return CustomerActivity.objects.filter(
        activity_type='تماس',
        created_at__date=day,
    ).filter(_agency_activity_q(agency)).count()


def _count_visits(agency: CRMAgency, day) -> int:
    return PropertyVisit.objects.filter(
        visit_date=day,
    ).filter(_agency_visit_q(agency)).count()


def _build_team_kpis(agency: CRMAgency, *, include_commission: bool) -> Dict[str, Any]:
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)

    new_today = Customer.objects.filter(agency=agency, created_at__date=today).count()
    new_yesterday = Customer.objects.filter(agency=agency, created_at__date=yesterday).count()

    deals_closed_today = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=today,
    ).count()
    deals_closed_yesterday = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=yesterday,
    ).count()

    active_deals = CRMDeal.objects.filter(agency=agency).exclude(
        stage__in=['بسته‌شده', 'از دست رفته'],
    ).count()

    inbox = get_team_inbox(agency)
    inbox_count = inbox.count()
    stale = inbox.filter(created_at__lt=timezone.now() - timedelta(hours=48)).count()

    overdue = Customer.objects.filter(
        agency=agency,
        next_follow_up__lt=today,
        status__in=['جدید', 'در حال پیگیری'],
    ).count()

    calls_today = _count_calls(agency, today)
    calls_yesterday = _count_calls(agency, yesterday)
    visits_today = _count_visits(agency, today)
    visits_yesterday = _count_visits(agency, yesterday)

    kpis = {
        'new_leads_today': _kpi_entry(new_today, _delta_pct(new_today, new_yesterday), 'new_leads_today'),
        'calls_today': _kpi_entry(calls_today, _delta_pct(calls_today, calls_yesterday), 'calls_today'),
        'visits_today': _kpi_entry(visits_today, _delta_pct(visits_today, visits_yesterday), 'visits_today'),
        'deals_won_today': _kpi_entry(
            deals_closed_today, _delta_pct(deals_closed_today, deals_closed_yesterday), 'deals_won_today',
        ),
        'active_deals': _kpi_entry(active_deals, None, 'active_deals'),
        'inbox_unassigned': _kpi_entry(inbox_count, None, 'inbox_unassigned'),
        'overdue_followups': _kpi_entry(overdue, None, 'overdue_followups'),
        'stale_leads': _kpi_entry(stale, None, 'stale_leads'),
    }

    if include_commission:
        commission_month = CRMDeal.objects.filter(
            agency=agency,
            stage=DEAL_STAGE_WON,
            closed_at__date__gte=month_start,
        ).aggregate(total=Sum('commission_amount'))['total'] or 0
        kpis['commission_month'] = _kpi_entry(int(commission_month), None, 'commission_month')

    return kpis


def _build_advisor_kpis(agency: CRMAgency, user_id: int) -> Dict[str, Any]:
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    calls_today = CustomerActivity.objects.filter(
        activity_type='تماس',
        created_at__date=today,
    ).filter(_activity_user_q(agency, user_id)).count()
    calls_yesterday = CustomerActivity.objects.filter(
        activity_type='تماس',
        created_at__date=yesterday,
    ).filter(_activity_user_q(agency, user_id)).count()

    visits_today = PropertyVisit.objects.filter(
        user_id=user_id,
        visit_date=today,
    ).filter(
        Q(customer__agency=agency) | Q(customer__agency__isnull=True, customer__user_id=user_id),
    ).count()
    visits_yesterday = PropertyVisit.objects.filter(
        user_id=user_id,
        visit_date=yesterday,
    ).filter(
        Q(customer__agency=agency) | Q(customer__agency__isnull=True, customer__user_id=user_id),
    ).count()

    row = get_member_performance_row(agency, user_id, days=1)

    deals_today = CRMDeal.objects.filter(
        _deal_scope_q(agency, user_id),
        stage=DEAL_STAGE_WON,
        closed_at__date=today,
    ).count()
    deals_yesterday = CRMDeal.objects.filter(
        _deal_scope_q(agency, user_id),
        stage=DEAL_STAGE_WON,
        closed_at__date=yesterday,
    ).count()

    return {
        'calls_today': _kpi_entry(calls_today, _delta_pct(calls_today, calls_yesterday), 'calls_today'),
        'visits_today': _kpi_entry(visits_today, _delta_pct(visits_today, visits_yesterday), 'visits_today'),
        'deals_won_today': _kpi_entry(deals_today, _delta_pct(deals_today, deals_yesterday), 'deals_won_today'),
        'active_deals': _kpi_entry(row.get('active_deals', 0), None, 'active_deals'),
        'my_score': _kpi_entry(row.get('score', 0), None, 'my_score'),
        'my_rank': _kpi_entry(row.get('rank') or 0, None, 'my_rank'),
    }


def _deal_scope_q(agency: CRMAgency, user_id: int):
    return Q(user_id=user_id) & (Q(agency=agency) | Q(agency__isnull=True))


def _deal_public_summary(deal: CRMDeal, index: int) -> Dict[str, Any]:
    stage = (deal.stage or '').strip()
    label = DEAL_STAGE_TV_LABELS.get(stage, stage or 'معامله فعال')
    advisor = tv_safe_first_name(deal.assigned_to)
    return {
        'summary': label,
        'advisor': advisor,
        'slot': index,
    }


def _sanitize_leaderboard(performance: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    rows = []
    for row in performance.get('members', [])[:limit]:
        member = row.get('member')
        user = member.user if member else None
        rows.append({
            'rank': row.get('rank'),
            'name': tv_safe_display_name(user),
            'role': row['role'],
            'score': row.get('score', 0),
            'score_pct': row.get('score_pct', 0),
            'calls': row['calls'],
            'visits': row['visits'],
            'deals_closed': row['deals_closed'],
        })
    return rows


def _sanitize_goals(
    goals: List[Dict[str, Any]],
    *,
    team_only: bool = False,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    today = timezone.now().date()
    rows = []
    for item in goals:
        goal = item['goal']
        if team_only and goal.member_id:
            continue
        days_left = max((goal.period_end - today).days, 0)
        pct = item['pct']
        completed = pct >= 100
        if team_only:
            title = GOAL_METRIC_TITLES.get(goal.metric, f'هدف {METRIC_LABELS.get(goal.metric, goal.metric)}')
        elif goal.member_id:
            member_label = tv_safe_display_name(goal.member.user) if goal.member else 'عضو تیم'
            title = f'هدف {METRIC_LABELS.get(goal.metric, goal.metric)} — {member_label}'
        else:
            title = GOAL_METRIC_TITLES.get(goal.metric, f'هدف {METRIC_LABELS.get(goal.metric, goal.metric)}')
        rows.append({
            'goal_key': f'g{goal.pk}',
            'title': title,
            'metric': goal.metric,
            'actual': item['actual'],
            'target': item['target'],
            'pct': pct,
            'days_left': days_left,
            'completed': completed,
            'status': 'ok' if completed else ('warn' if pct >= 50 else 'low'),
        })
        if len(rows) >= limit:
            break
    return rows


def _sanitize_announcements(user, limit: int = 6) -> List[Dict[str, Any]]:
    items, _ = list_announcements(user, page_size=limit)
    rows = []
    for item in items:
        if item.get('status') == 'expired':
            continue
        rows.append({
            'ann_key': f'a{item["id"]}',
            'title': item['title'],
            'preview': (item.get('body_preview') or '')[:120],
            'importance': item['importance'],
            'is_pinned': item['is_pinned'],
            'published_at': item['published_at'],
        })
    return rows


def _sanitize_deals(agency: CRMAgency, limit: int = 6) -> Dict[str, Any]:
    today = timezone.now().date()
    active_qs = CRMDeal.objects.filter(agency=agency).exclude(
        stage__in=['بسته‌شده', 'از دست رفته'],
    ).select_related('assigned_to').order_by('-updated_at')
    closed_qs = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=today,
    ).select_related('assigned_to').order_by('-closed_at')

    return {
        'active': [_deal_public_summary(d, i + 1) for i, d in enumerate(active_qs[:limit])],
        'closed_today': [_deal_public_summary(d, i + 1) for i, d in enumerate(closed_qs[:limit])],
        'active_count': active_qs.count(),
        'closed_today_count': closed_qs.count(),
    }


def _sanitize_leads(agency: CRMAgency) -> Dict[str, Any]:
    inbox = get_team_inbox(agency)
    today = timezone.now().date()
    return {
        'unassigned': inbox.count(),
        'new_today': inbox.filter(created_at__date=today).count(),
        'stale': inbox.filter(created_at__lt=timezone.now() - timedelta(hours=48)).count(),
    }


def _build_sanitized_alerts(kpis: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts = []
    inbox = kpis.get('inbox_unassigned', {}).get('value', 0)
    stale = kpis.get('stale_leads', {}).get('value', 0)
    overdue = kpis.get('overdue_followups', {}).get('value', 0)
    if inbox:
        alerts.append({'level': 'warn', 'text': f'{inbox} سرنخ در صندوق بدون تخصیص'})
    if stale:
        alerts.append({'level': 'danger', 'text': f'{stale} سرنخ بیش از ۴۸ ساعت بدون تخصیص'})
    if overdue:
        alerts.append({'level': 'warn', 'text': f'{overdue} پیگیری معوق تیم'})
    return alerts[:4]


def _build_status_doughnut(agency: CRMAgency) -> Dict[str, Any]:
    """توزیع مخاطبین آژانس — نمودار دایره‌ای مرکز فرمان."""
    counts = dict(
        Customer.objects.filter(agency=agency)
        .values('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    total = sum(counts.get(s, 0) for s in CRM_STATUSES)
    slices: List[Dict[str, Any]] = []
    for status in CRM_STATUSES:
        value = int(counts.get(status, 0) or 0)
        if not value:
            continue
        slices.append({
            'label': status,
            'value': value,
            'pct': round(value * 100 / total) if total else 0,
            'color': STATUS_DONUT_COLORS.get(status, '#64748b'),
        })
    if slices and total:
        drift = 100 - sum(s['pct'] for s in slices)
        if drift:
            slices[0]['pct'] += drift
    if not slices:
        slices.append({
            'label': 'بدون مخاطب',
            'value': 0,
            'pct': 100,
            'color': '#334155',
        })
    return {
        'title': 'پرونده مخاطبین',
        'center_label': 'مخاطب',
        'center_value': total,
        'slices': slices,
    }


def _build_chart_trend(agency: CRMAgency, days: int = 7) -> Dict[str, Any]:
    today = timezone.now().date()
    points = []
    series_keys = [s['key'] for s in TREND_SERIES]
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        points.append({
            'label': to_persian_digits(format_jalali_date(day)[-5:]),
            'calls': _count_calls(agency, day),
            'visits': _count_visits(agency, day),
            'leads': Customer.objects.filter(agency=agency, created_at__date=day).count(),
            'deals': CRMDeal.objects.filter(
                agency=agency, stage=DEAL_STAGE_WON, closed_at__date=day,
            ).count(),
        })
    series_totals = {
        key: sum(int(p.get(key) or 0) for p in points)
        for key in series_keys
    }
    activity_total = sum(series_totals.values())
    return {
        'days': days,
        'points': points,
        'doughnut': _build_status_doughnut(agency),
        'series': [
            {
                **meta,
                'total': series_totals[meta['key']],
                'share_pct': round(series_totals[meta['key']] * 100 / activity_total) if activity_total else 0,
            }
            for meta in TREND_SERIES
        ],
        'activity_total': activity_total,
    }


def _tv_audit_text(event: str) -> str:
    templates = {
        'lead.assigned': 'یک سرنخ جدید تخصیص یافت',
        'lead.bulk_assigned': 'تخصیص گروهی سرنخ انجام شد',
        'announcement.created': 'اطلاعیه جدید منتشر شد',
    }
    return templates.get(event) or get_audit_event_meta(event).get('title', 'رویداد تیم')


def _build_activity_feed(agency: CRMAgency, limit: int = 5) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    today = timezone.now().date()

    for log in CRMAgencyAuditLog.objects.filter(
        agency=agency,
        event__in=PUBLIC_TV_AUDIT_EVENTS,
    ).select_related('actor').order_by('-created_at')[:limit]:
        rows.append({
            'key': f'audit-{log.pk}',
            'text': _tv_audit_text(log.event),
            'time': to_persian_digits(log.created_at.strftime('%H:%M')),
        })

    for visit in PropertyVisit.objects.filter(
        visit_date=today,
    ).filter(_agency_visit_q(agency)).select_related('user').order_by('-created_at')[:3]:
        name = tv_safe_first_name(visit.user)
        rows.append({
            'key': f'visit-{visit.pk}',
            'text': f'{name} یک بازدید ثبت کرد',
            'time': to_persian_digits(visit.created_at.strftime('%H:%M')) if visit.created_at else '',
        })

    for deal in CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=today,
    ).select_related('assigned_to').order_by('-closed_at')[:3]:
        advisor = tv_safe_first_name(deal.assigned_to)
        rows.append({
            'key': f'deal-{deal.pk}',
            'text': f'{DEAL_STAGE_TV_LABELS.get(DEAL_STAGE_WON, "قرارداد موفق")} — {advisor}',
            'time': to_persian_digits(deal.closed_at.strftime('%H:%M')) if deal.closed_at else '',
        })

    rows.sort(key=lambda r: r.get('time', ''), reverse=True)
    return rows[:limit]


def _build_today_schedule(agency: CRMAgency) -> Dict[str, Any]:
    today = timezone.now().date()
    visits_today = PropertyVisit.objects.filter(
        visit_date=today,
    ).filter(_agency_visit_q(agency)).count()
    followups_today = Customer.objects.filter(
        agency=agency,
        next_follow_up=today,
        status__in=['جدید', 'در حال پیگیری'],
    ).count()
    overdue = Customer.objects.filter(
        agency=agency,
        next_follow_up__lt=today,
        status__in=['جدید', 'در حال پیگیری'],
    ).count()
    inbox = get_team_inbox(agency).count()
    return {
        'visits_today': visits_today,
        'followups_today': followups_today,
        'overdue_followups': overdue,
        'inbox_unassigned': inbox,
        'next_hint': (
            f'{followups_today} پیگیری برای امروز'
            if followups_today
            else (f'{visits_today} بازدید ثبت‌شده' if visits_today else 'برنامه‌ای ثبت نشده')
        ),
    }


def _conversion_pct(agency: CRMAgency, days: int = 30) -> int:
    since = timezone.now() - timedelta(days=days)
    leads_period = Customer.objects.filter(agency=agency, created_at__gte=since).count()
    won_period = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__gte=since,
    ).count()
    return round(won_period * 100 / leads_period) if leads_period else 0


def _payload_version_hash(payload: Dict[str, Any]) -> str:
    core = {
        'kpis': payload.get('kpis'),
        'leaderboard': payload.get('leaderboard'),
        'chart': payload.get('chart'),
        'goals': payload.get('goals'),
        'activity': payload.get('activity'),
        'schedule': payload.get('schedule'),
        'announcements': payload.get('announcements'),
        'alerts': payload.get('alerts'),
    }
    raw = json.dumps(core, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]


def _build_payload_for_role(
    user,
    membership: CRMAgencyMember,
    agency: CRMAgency,
    role: str,
    *,
    days: int = 1,
) -> Dict[str, Any]:
    now = timezone.now()
    allowed = list(ALLOWED_WIDGETS_BY_ROLE.get(role, ALLOWED_WIDGETS_BY_ROLE[TV_ROLE_ADVISOR]))
    performance = get_team_performance(agency, days=max(days, 30))

    payload: Dict[str, Any] = {
        'ok': True,
        'schema_version': TV_PAYLOAD_SCHEMA_VERSION,
        'payload_version': '',
        'refresh_after': TV_REFRESH_AFTER_SECONDS,
        'generated_at': now.isoformat(),
        'jalali_date': to_persian_digits(format_jalali_date(now.date())),
        'clock': to_persian_digits(now.strftime('%H:%M')),
        'role': role,
        'allowed_widgets': allowed,
        'agency': {'name': agency.name, 'logo_url': _agency_logo_url(agency)},
        'member_name': tv_safe_display_name(membership.user),
        'member_role': membership.get_role_display(),
    }

    chart = _build_chart_trend(agency)
    announcements = _sanitize_announcements(user, limit=8)

    if role == TV_ROLE_MANAGER:
        goals = get_team_goals_progress(agency, days=30, perf=performance)
        kpis = _build_team_kpis(agency, include_commission=True)
        payload['kpis'] = kpis
        payload['leaderboard'] = _sanitize_leaderboard(performance, limit=5)
        payload['chart'] = chart
        payload['goals'] = _sanitize_goals(goals)
        payload['activity'] = _build_activity_feed(agency)
        payload['schedule'] = _build_today_schedule(agency)
        payload['announcements'] = announcements
        payload['alerts'] = _build_sanitized_alerts(kpis)
        payload['conversion_pct'] = _conversion_pct(agency)
        payload['recent_deals'] = _sanitize_deals(agency, limit=4)
    elif role == TV_ROLE_SECRETARY:
        goals = get_team_goals_progress(agency, days=30, perf=performance)
        kpis = _build_team_kpis(agency, include_commission=False)
        payload['kpis'] = kpis
        payload['leaderboard'] = _sanitize_leaderboard(performance, limit=5)
        payload['chart'] = chart
        payload['goals'] = _sanitize_goals(goals)
        payload['activity'] = _build_activity_feed(agency)
        payload['schedule'] = _build_today_schedule(agency)
        payload['announcements'] = announcements
        payload['alerts'] = _build_sanitized_alerts(kpis)
        payload['conversion_pct'] = _conversion_pct(agency)
        payload['recent_deals'] = _sanitize_deals(agency, limit=4)
    else:
        payload['kpis'] = _build_advisor_kpis(agency, user.id)
        payload['leaderboard'] = _sanitize_leaderboard(performance, limit=5)
        payload['chart'] = chart
        goals = get_team_goals_progress(agency, days=30, perf=performance)
        payload['goals'] = _sanitize_goals(goals, team_only=True)
        payload['activity'] = _build_activity_feed(agency, limit=4)
        payload['schedule'] = {
            'visits_today': payload['kpis'].get('visits_today', {}).get('value', 0),
            'followups_today': 0,
            'overdue_followups': 0,
            'inbox_unassigned': 0,
            'next_hint': 'عملکرد شخصی امروز',
        }
        payload['announcements'] = announcements
        payload['alerts'] = []
        payload['conversion_pct'] = 0
        payload['recent_deals'] = {'active': [], 'closed_today': [], 'active_count': 0, 'closed_today_count': 0}

    payload['payload_version'] = _payload_version_hash(payload)
    return payload


def get_tv_dashboard_payload(user, *, days: int = 1, use_cache: bool = True) -> Dict[str, Any]:
    membership = get_membership(user)
    if not membership:
        return {'ok': False, 'error': 'آژانس یافت نشد'}
    agency = membership.agency
    role = resolve_tv_role(membership)
    cache_key = get_tv_cache_key(agency.pk, role)

    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            cached = dict(cached)
            now = timezone.now()
            cached['generated_at'] = now.isoformat()
            cached['jalali_date'] = to_persian_digits(format_jalali_date(now.date()))
            cached['clock'] = to_persian_digits(now.strftime('%H:%M'))
            return cached

    payload = _build_payload_for_role(user, membership, agency, role, days=days)
    if use_cache:
        cache.set(cache_key, payload, TV_CACHE_SECONDS)
    return payload


def scan_payload_for_pii(payload: Dict[str, Any]) -> List[str]:
    """برای تست — یافتن کلیدها یا الگوهای ممنوع در Payload."""
    issues: List[str] = []

    def walk(obj, path=''):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in FORBIDDEN_PAYLOAD_KEYS:
                    issues.append(f'{path}.{k}' if path else k)
                walk(v, f'{path}.{k}' if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f'{path}[{i}]')

    walk(payload)
    return issues


# سازگاری با importهای قدیمی
TV_WIDGETS = TV_WIDGETS_ALL
