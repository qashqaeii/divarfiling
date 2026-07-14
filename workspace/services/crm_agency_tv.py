"""داشبورد TV آژانس — Payload امن، role-based و cache‌شده."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from workspace.constants import AGENCY_MANAGER_ROLES, DEAL_STAGE_WON
from workspace.models import CRMAgency, CRMAgencyMember, CRMDeal, Customer, CustomerActivity, PropertyVisit
from workspace.services.crm_agency import get_team_inbox, member_display
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
TV_PAYLOAD_SCHEMA_VERSION = 2
TV_CACHE_SECONDS = 35
TV_REFRESH_AFTER_SECONDS = 45

TV_ROLE_MANAGER = 'manager'
TV_ROLE_SECRETARY = 'secretary'
TV_ROLE_ADVISOR = 'advisor'

TV_WIDGETS_ALL = (
    'kpis',
    'goals',
    'leaderboard',
    'announcements',
    'leads',
    'deals',
    'alerts',
)

ALLOWED_WIDGETS_BY_ROLE: Dict[str, Tuple[str, ...]] = {
    TV_ROLE_MANAGER: TV_WIDGETS_ALL,
    TV_ROLE_SECRETARY: ('kpis', 'goals', 'leaderboard', 'announcements', 'leads', 'deals', 'alerts'),
    TV_ROLE_ADVISOR: ('kpis', 'leaderboard', 'goals', 'announcements'),
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
    'deals_closed': 'معامله بسته',
}


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


def _advisor_first_name(user) -> str:
    if not user:
        return ''
    full = (user.get_full_name() or '').strip()
    if full:
        return full.split()[0]
    return user.username or ''


def _deal_public_summary(deal: CRMDeal, index: int) -> Dict[str, Any]:
    return {
        'summary': f'معامله {deal.stage}',
        'stage': deal.stage,
        'advisor': _advisor_first_name(deal.assigned_to),
        'slot': index,
    }


def _sanitize_leaderboard(performance: Dict[str, Any], limit: int = 8) -> List[Dict[str, Any]]:
    rows = []
    for row in performance.get('members', [])[:limit]:
        rows.append({
            'rank': row.get('rank'),
            'name': row['name'],
            'role': row['role'],
            'score': row.get('score', 0),
            'score_pct': row.get('score_pct', 0),
            'calls': row['calls'],
            'visits': row['visits'],
            'deals_closed': row['deals_closed'],
            'active_deals': row['active_deals'],
        })
    return rows


def _sanitize_goals(
    goals: List[Dict[str, Any]],
    *,
    team_only: bool = False,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    rows = []
    for item in goals:
        goal = item['goal']
        if team_only and goal.member_id:
            continue
        rows.append({
            'goal_key': f'g{goal.pk}',
            'member_name': item['member_name'] if not team_only else 'هدف تیم',
            'metric': goal.metric,
            'metric_label': METRIC_LABELS.get(goal.metric, goal.metric),
            'actual': item['actual'],
            'target': item['target'],
            'pct': item['pct'],
            'period_label': item['period_label'],
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
        'goals': payload.get('goals'),
        'announcements': payload.get('announcements'),
        'leads': payload.get('leads'),
        'deals': payload.get('deals'),
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
        'agency': {'name': agency.name},
        'member_name': member_display(membership),
        'member_role': membership.get_role_display(),
    }

    if role == TV_ROLE_MANAGER:
        goals = get_team_goals_progress(agency, days=30, perf=performance)
        kpis = _build_team_kpis(agency, include_commission=True)
        payload['kpis'] = kpis
        payload['leaderboard'] = _sanitize_leaderboard(performance)
        payload['top'] = _spotlight_from_performance(performance)
        payload['goals'] = _sanitize_goals(goals)
        payload['announcements'] = _sanitize_announcements(user)
        payload['leads'] = _sanitize_leads(agency)
        payload['deals'] = _sanitize_deals(agency)
        payload['alerts'] = _build_sanitized_alerts(kpis)
        payload['conversion_pct'] = _conversion_pct(agency)
    elif role == TV_ROLE_SECRETARY:
        goals = get_team_goals_progress(agency, days=30, perf=performance)
        kpis = _build_team_kpis(agency, include_commission=False)
        payload['kpis'] = kpis
        payload['leaderboard'] = _sanitize_leaderboard(performance)
        payload['top'] = _spotlight_from_performance(performance)
        payload['goals'] = _sanitize_goals(goals)
        payload['announcements'] = _sanitize_announcements(user)
        payload['leads'] = _sanitize_leads(agency)
        payload['deals'] = _sanitize_deals(agency)
        payload['alerts'] = _build_sanitized_alerts(kpis)
        payload['conversion_pct'] = _conversion_pct(agency)
    else:
        payload['kpis'] = _build_advisor_kpis(agency, user.id)
        payload['leaderboard'] = _sanitize_leaderboard(performance, limit=5)
        payload['top'] = None
        goals = get_team_goals_progress(agency, days=30, perf=performance)
        payload['goals'] = _sanitize_goals(goals, team_only=True)
        payload['announcements'] = _sanitize_announcements(user)
        payload['leads'] = {'unassigned': 0, 'new_today': 0, 'stale': 0}
        payload['deals'] = {
            'active': [],
            'closed_today': [],
            'active_count': 0,
            'closed_today_count': 0,
        }
        payload['alerts'] = []
        payload['conversion_pct'] = 0

    payload['payload_version'] = _payload_version_hash(payload)
    return payload


def _spotlight_from_performance(performance: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    top = performance.get('top')
    if not top:
        return None
    return {
        'name': top['name'],
        'role': top['role'],
        'score_pct': top.get('score_pct', 0),
        'calls': top['calls'],
        'visits': top['visits'],
        'deals_closed': top['deals_closed'],
    }


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
