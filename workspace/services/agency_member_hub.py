"""Agency Member Hub — context برای پنل مشاور عضو آژانس."""
from __future__ import annotations

from typing import Any, Optional

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from workspace.models import CRMAgency, CRMAgencyMember, CRMAgencyTeamGoal
from workspace.services.agency_data_scope import (
    get_member_activity_qs,
    get_member_contracts_qs,
    get_member_overview_kpis,
    get_member_tasks_qs,
)
from workspace.services.crm_agency import member_display
from workspace.services.crm_agency_analytics import get_member_performance_row
from workspace.services.crm_agency_announcements import list_announcements, unread_announcement_count
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_agency_messages import unread_message_count
from workspace.services.crm_agency_tv import _agency_logo_url
from workspace.services.crm_today import count_today_queue
from workspace.services.jalali_input import format_jalali_date, to_persian_digits

MEMBER_HUB_TABS = (
    ('overview', 'نمای من'),
    ('performance', 'عملکرد من'),
    ('messages', 'پیام‌ها'),
    ('announcements', 'اطلاعیه‌ها'),
    ('membership', 'عضویت و لایسنس'),
)

GOAL_METRIC_LABELS = {
    'calls': 'تماس',
    'visits': 'بازدید',
    'deals_closed': 'معامله بسته',
}


def _agency_leader_name(agency: CRMAgency) -> Optional[str]:
    owner = (
        CRMAgencyMember.objects.filter(agency=agency, role='owner', is_active=True)
        .select_related('user')
        .first()
    )
    if owner:
        return member_display(owner)
    manager = (
        CRMAgencyMember.objects.filter(agency=agency, role='manager', is_active=True)
        .select_related('user')
        .first()
    )
    if manager:
        return member_display(manager)
    return None


def _member_goals(agency: CRMAgency, member: CRMAgencyMember, perf: dict, days: int) -> list[dict]:
    today = timezone.now().date()
    rows = []
    for goal in CRMAgencyTeamGoal.objects.filter(
        agency=agency,
        member=member,
        period_start__lte=today,
        period_end__gte=today,
    ).order_by('-period_start'):
        actual = perf.get(goal.metric, 0) if perf else 0
        target = goal.target_value or 0
        pct = round(actual * 100 / target) if target else 0
        rows.append({
            'goal': goal,
            'metric_label': GOAL_METRIC_LABELS.get(goal.metric, goal.metric),
            'actual': actual,
            'target': target,
            'pct': min(pct, 100),
            'period_label': (
                f"{to_persian_digits(format_jalali_date(goal.period_start))}"
                f" — {to_persian_digits(format_jalali_date(goal.period_end))}"
            ),
        })
    return rows


def build_member_hub_context(
    request,
    *,
    membership: CRMAgencyMember,
    agency: CRMAgency,
    subscription,
    license_obj,
    tab: str = 'overview',
    period: int = 30,
) -> dict[str, Any]:
    user = request.user
    if tab not in {t[0] for t in MEMBER_HUB_TABS}:
        tab = 'overview'
    if period not in (7, 30, 90):
        period = 30

    perf = get_member_performance_row(agency, user.id, days=period) or {}
    kpis = get_member_overview_kpis(user, membership, days=period)
    contracts_count = get_member_contracts_qs(user, membership).count()
    open_tasks = get_member_tasks_qs(user, membership).count()
    today_tasks = count_today_queue(user)
    goals = _member_goals(agency, membership, perf, period)
    activities = get_member_activity_qs(user, membership, limit=8)
    announcements, ann_total = list_announcements(user, page_size=5)
    for ann in announcements:
        ann['published_dt'] = parse_datetime(ann.get('published_at') or '')

    feature_messages = is_agency_feature_enabled('messages', agency)
    feature_announcements = is_agency_feature_enabled('announcements', agency)

    ctx: dict[str, Any] = {
        'crm_section': 'agency',
        'tab': tab,
        'period': period,
        'periods': (7, 30, 90),
        'member_hub_tabs': MEMBER_HUB_TABS,
        'agency_logo_url': _agency_logo_url(agency),
        'agency_leader_name': _agency_leader_name(agency),
        'hub_kpis': {
            'contacts': kpis['contacts']['total'],
            'properties': kpis['properties']['total'],
            'open_tasks': open_tasks,
            'active_deals': kpis['deals_active'],
            'contracts': contracts_count,
            'today_tasks': today_tasks,
        },
        'period_stats': {
            'contacts_new': kpis['contacts']['period'],
            'properties_new': kpis['properties']['period'],
            'calls': perf.get('calls', 0),
            'visits': perf.get('visits', 0),
            'deals_closed': perf.get('deals_closed', 0),
            'active_deals': perf.get('active_deals', 0),
        },
        'my_performance': perf,
        'my_goals': goals,
        'recent_activities': activities,
        'recent_announcements': announcements,
        'announcements_total': ann_total,
        'agency_feature_messages': feature_messages,
        'agency_feature_announcements': feature_announcements,
        'messages_unread_count': unread_message_count(user) if feature_messages else 0,
        'announcements_unread_count': unread_announcement_count(user) if feature_announcements else 0,
        'quick_links': {
            'contacts': reverse('workspace:crm_contacts'),
            'properties': reverse('workspace:crm_properties'),
            'deals': reverse('workspace:crm_deals'),
            'contracts': reverse('workspace:contracts_dashboard'),
            'calendar': reverse('workspace:crm_calendar'),
            'today': reverse('workspace:crm_today'),
            'filing': reverse('workspace:dataset_list'),
        },
        'can_manage_team': False,
    }

    if feature_messages:
        ctx.update({
            'api_crm_team_messages_url': reverse('workspace:api_crm_team_messages'),
            'api_crm_team_messages_unread_url': reverse('workspace:api_crm_team_messages_unread'),
            'api_crm_team_messages_members_url': reverse('workspace:api_crm_team_messages_members'),
            'api_crm_team_notifications_url': reverse('workspace:api_crm_team_notifications'),
        })
    if feature_announcements:
        ctx['api_crm_team_announcements_url'] = reverse('workspace:api_crm_team_announcements')

    return ctx
