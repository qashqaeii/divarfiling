"""داشبورد TV آژانس — داده‌های امن و بدون PII."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Q, Sum
from django.utils import timezone

from workspace.constants import DEAL_STAGE_WON
from workspace.models import CRMAgency, CRMDeal, Customer, CustomerActivity, PropertyVisit
from workspace.services.crm_agency import get_team_inbox, member_display
from workspace.services.crm_agency_analytics import (
    get_command_center_stats,
    get_member_performance_row,
    get_team_goals_progress,
    get_team_performance,
    _activity_user_q,
)
from workspace.services.crm_agency_announcements import list_announcements
from workspace.services.crm_scope import can_view_team_performance, get_membership
from workspace.services.jalali_input import format_jalali_date, to_persian_digits

TV_WIDGETS = (
    'kpis',
    'goals',
    'leaderboard',
    'announcements',
    'leads',
    'deals',
    'alerts',
)

METRIC_LABELS = {
    'calls': 'تماس',
    'visits': 'بازدید',
    'deals_closed': 'معامله بسته',
}


def _delta_pct(current: int, previous: int) -> Optional[int]:
    if previous <= 0:
        return None if current <= 0 else 100
    return round((current - previous) * 100 / previous)


def _agency_activity_q(agency: CRMAgency):
    return Q(customer__agency=agency)


def _agency_visit_q(agency: CRMAgency):
    return Q(customer__agency=agency)


def get_tv_today_kpis(agency: CRMAgency) -> Dict[str, Any]:
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    calls_today = CustomerActivity.objects.filter(
        activity_type='تماس',
        created_at__date=today,
    ).filter(_agency_activity_q(agency)).count()
    calls_yesterday = CustomerActivity.objects.filter(
        activity_type='تماس',
        created_at__date=yesterday,
    ).filter(_agency_activity_q(agency)).count()

    visits_today = PropertyVisit.objects.filter(
        visit_date=today,
    ).filter(_agency_visit_q(agency)).count()
    visits_yesterday = PropertyVisit.objects.filter(
        visit_date=yesterday,
    ).filter(_agency_visit_q(agency)).count()

    new_contacts_today = Customer.objects.filter(
        agency=agency, created_at__date=today,
    ).count()
    new_contacts_yesterday = Customer.objects.filter(
        agency=agency, created_at__date=yesterday,
    ).count()

    deals_closed_today = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=today,
    ).count()
    deals_closed_yesterday = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=yesterday,
    ).count()

    active_deals = CRMDeal.objects.filter(agency=agency).exclude(
        stage__in=['بسته‌شده', 'از دست رفته'],
    ).count()

    inbox_unassigned = get_team_inbox(agency).count()
    overdue_followups = Customer.objects.filter(
        agency=agency,
        next_follow_up__lt=today,
        status__in=['جدید', 'در حال پیگیری'],
    ).count()

    commission_today = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=today,
    ).aggregate(total=Sum('commission_amount'))['total'] or 0

    return {
        'calls': {'value': calls_today, 'delta': _delta_pct(calls_today, calls_yesterday)},
        'visits': {'value': visits_today, 'delta': _delta_pct(visits_today, visits_yesterday)},
        'new_contacts': {'value': new_contacts_today, 'delta': _delta_pct(new_contacts_today, new_contacts_yesterday)},
        'deals_closed': {'value': deals_closed_today, 'delta': _delta_pct(deals_closed_today, deals_closed_yesterday)},
        'active_deals': {'value': active_deals, 'delta': None},
        'inbox_unassigned': {'value': inbox_unassigned, 'delta': None},
        'overdue_followups': {'value': overdue_followups, 'delta': None},
        'commission_today': {'value': int(commission_today), 'delta': None},
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


def _sanitize_goals(goals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for item in goals[:6]:
        goal = item['goal']
        rows.append({
            'id': goal.pk,
            'member_name': item['member_name'],
            'metric': goal.metric,
            'metric_label': METRIC_LABELS.get(goal.metric, goal.metric),
            'actual': item['actual'],
            'target': item['target'],
            'pct': item['pct'],
            'period_label': item['period_label'],
        })
    return rows


def _sanitize_announcements(user, limit: int = 6) -> List[Dict[str, Any]]:
    items, _ = list_announcements(user, page_size=limit)
    rows = []
    for item in items:
        rows.append({
            'id': item['id'],
            'title': item['title'],
            'body_preview': item.get('body_preview', '')[:120],
            'importance': item['importance'],
            'is_pinned': item['is_pinned'],
            'published_at': item['published_at'],
            'is_read': item['is_read'],
        })
    return rows


def _sanitize_deals(agency: CRMAgency, limit: int = 8) -> Dict[str, Any]:
    today = timezone.now().date()
    active = CRMDeal.objects.filter(agency=agency).exclude(
        stage__in=['بسته‌شده', 'از دست رفته'],
    ).select_related('assigned_to').order_by('-updated_at')[:limit]

    closed_today_qs = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__date=today,
    ).select_related('assigned_to').order_by('-closed_at')
    closed_today = list(closed_today_qs[:limit])
    closed_today_count = closed_today_qs.count()

    def _row(deal: CRMDeal) -> Dict[str, Any]:
        advisor = ''
        if deal.assigned_to_id:
            advisor = deal.assigned_to.get_full_name() or deal.assigned_to.username
        return {
            'id': deal.pk,
            'title': deal.title,
            'stage': deal.stage,
            'advisor': advisor,
            'probability': deal.probability,
        }

    return {
        'active': [_row(d) for d in active],
        'closed_today': [_row(d) for d in closed_today],
        'active_count': CRMDeal.objects.filter(agency=agency).exclude(
            stage__in=['بسته‌شده', 'از دست رفته'],
        ).count(),
        'closed_today_count': closed_today_count,
    }


def _sanitize_leads(agency: CRMAgency) -> Dict[str, Any]:
    inbox = get_team_inbox(agency)
    today = timezone.now().date()
    new_today = inbox.filter(created_at__date=today).count()
    stale = inbox.filter(
        created_at__lt=timezone.now() - timedelta(hours=48),
    ).count()
    return {
        'unassigned': inbox.count(),
        'new_today': new_today,
        'stale': stale,
    }


def _personal_kpis(agency: CRMAgency, user_id: int) -> Dict[str, Any]:
    today = timezone.now().date()
    row = get_member_performance_row(agency, user_id, days=1)
    calls_today = CustomerActivity.objects.filter(
        activity_type='تماس',
        created_at__date=today,
    ).filter(_activity_user_q(agency, user_id)).count()
    visits_today = PropertyVisit.objects.filter(
        user_id=user_id,
        visit_date=today,
    ).filter(
        Q(customer__agency=agency) | Q(customer__agency__isnull=True, customer__user_id=user_id),
    ).count()
    return {
        'calls': {'value': calls_today, 'delta': None},
        'visits': {'value': visits_today, 'delta': None},
        'deals_closed': {'value': row.get('deals_closed', 0), 'delta': None},
        'active_deals': {'value': row.get('active_deals', 0), 'delta': None},
        'score': row.get('score', 0),
        'rank': row.get('rank'),
    }


def get_tv_dashboard_payload(user, *, days: int = 1) -> Dict[str, Any]:
    membership = get_membership(user)
    if not membership:
        return {'ok': False, 'error': 'آژانس یافت نشد'}
    agency = membership.agency
    now = timezone.now()
    team_view = can_view_team_performance(user)

    payload: Dict[str, Any] = {
        'ok': True,
        'agency_name': agency.name,
        'updated_at': now.isoformat(),
        'jalali_date': to_persian_digits(format_jalali_date(now.date())),
        'clock': to_persian_digits(now.strftime('%H:%M')),
        'team_view': team_view,
        'widgets': list(TV_WIDGETS) if team_view else ['kpis', 'announcements', 'leaderboard'],
        'member_name': member_display(membership),
        'member_role': membership.get_role_display(),
    }

    if team_view:
        performance = get_team_performance(agency, days=max(days, 1))
        command = get_command_center_stats(agency, days=30)
        goals = get_team_goals_progress(agency, days=30)
        payload['kpis'] = get_tv_today_kpis(agency)
        payload['leaderboard'] = _sanitize_leaderboard(performance)
        payload['top'] = None
        if performance.get('top'):
            top = performance['top']
            payload['top'] = {
                'name': top['name'],
                'role': top['role'],
                'score_pct': top.get('score_pct', 0),
                'calls': top['calls'],
                'visits': top['visits'],
                'deals_closed': top['deals_closed'],
            }
        payload['goals'] = _sanitize_goals(goals)
        payload['announcements'] = _sanitize_announcements(user)
        payload['leads'] = _sanitize_leads(agency)
        payload['deals'] = _sanitize_deals(agency)
        payload['alerts'] = [
            {'level': a['level'], 'text': a['text']}
            for a in command.get('alerts', [])[:4]
        ]
        payload['conversion_pct'] = command.get('conversion_pct', 0)
    else:
        payload['kpis'] = _personal_kpis(agency, user.id)
        payload['leaderboard'] = _sanitize_leaderboard(
            get_team_performance(agency, days=max(days, 1)), limit=5,
        )
        payload['top'] = None
        payload['goals'] = []
        payload['announcements'] = _sanitize_announcements(user)
        payload['leads'] = {'unassigned': 0, 'new_today': 0, 'stale': 0}
        payload['deals'] = {'active': [], 'closed_today': [], 'active_count': 0, 'closed_today_count': 0}
        payload['alerts'] = []
        payload['conversion_pct'] = 0
        payload['widgets'] = ['kpis', 'leaderboard', 'announcements']

    return payload
