"""گزارش عملکرد تیم — E4."""
from __future__ import annotations

import csv
import io
from datetime import timedelta
from typing import Any, Dict, List

from django.db.models import Count, Q, Sum
from django.utils import timezone

from workspace.constants import DEAL_STAGE_WON
from workspace.models import CRMAgency, CRMAgencyTeamGoal, CRMDeal, CRMProperty, Customer, CustomerActivity, PropertyVisit
from workspace.services.crm_agency import get_team_inbox, member_display, role_label
from workspace.services.jalali_input import format_jalali_date, to_persian_digits
from workspace.services.crm_scope import agency_members

def get_team_performance(agency: CRMAgency, days: int = 30) -> Dict[str, Any]:
    since = timezone.now() - timedelta(days=days)
    members = list(agency_members(agency))
    rows: List[Dict[str, Any]] = []

    for member in members:
        uid = member.user_id
        contacts = _member_contacts_count(agency, uid)
        properties = _member_properties_count(agency, uid)

        calls = CustomerActivity.objects.filter(
            activity_type='تماس',
            created_at__gte=since,
        ).filter(_activity_user_q(agency, uid)).count()

        visits = PropertyVisit.objects.filter(
            user_id=uid,
            visit_date__gte=since.date(),
        ).filter(
            Q(customer__agency=agency) | Q(customer__agency__isnull=True, customer__user_id=uid),
        ).count()

        deals_closed = CRMDeal.objects.filter(
            stage=DEAL_STAGE_WON,
            closed_at__gte=since,
        ).filter(_deal_user_q(agency, uid)).count()

        active_deals = CRMDeal.objects.filter(
            _deal_user_q(agency, uid),
        ).exclude(stage__in=['بسته‌شده', 'از دست رفته']).count()

        rows.append({
            'member': member,
            'name': member_display(member),
            'role': role_label(member.role),
            'contacts': contacts,
            'properties': properties,
            'calls': calls,
            'visits': visits,
            'deals_closed': deals_closed,
            'active_deals': active_deals,
        })

    rows.sort(key=lambda r: (r['deals_closed'], r['calls']), reverse=True)

    for r in rows:
        r['score'] = r['calls'] * 2 + r['visits'] * 3 + r['deals_closed'] * 10 + r['active_deals'] * 2

    max_calls = max((r['calls'] for r in rows), default=1) or 1
    max_visits = max((r['visits'] for r in rows), default=1) or 1
    max_closed = max((r['deals_closed'] for r in rows), default=1) or 1
    max_contacts = max((r['contacts'] for r in rows), default=1) or 1
    max_properties = max((r['properties'] for r in rows), default=1) or 1
    max_score = max((r['score'] for r in rows), default=1) or 1
    max_active = max((r['active_deals'] for r in rows), default=1) or 1
    for r in rows:
        r['calls_pct'] = round(r['calls'] * 100 / max_calls)
        r['visits_pct'] = round(r['visits'] * 100 / max_visits)
        r['closed_pct'] = round(r['deals_closed'] * 100 / max_closed)
        r['contacts_pct'] = round(r['contacts'] * 100 / max_contacts)
        r['properties_pct'] = round(r['properties'] * 100 / max_properties)
        r['active_pct'] = round(r['active_deals'] * 100 / max_active)
        r['score_pct'] = round(r['score'] * 100 / max_score)

    for idx, r in enumerate(rows, start=1):
        r['rank'] = idx

    top = max(rows, key=lambda r: r['score']) if rows else None

    return {
        'members': rows,
        'days': days,
        'top': top,
        'totals': {
            'contacts': sum(r['contacts'] for r in rows),
            'properties': sum(r['properties'] for r in rows),
            'calls': sum(r['calls'] for r in rows),
            'visits': sum(r['visits'] for r in rows),
            'deals_closed': sum(r['deals_closed'] for r in rows),
            'active_deals': sum(r['active_deals'] for r in rows),
        },
    }


def _member_scope_q(agency, user_id: int):
    """رکوردهای عضو — شامل داده‌های قبل از پیوستن که هنوز agency ندارند."""
    return Q(user_id=user_id) & (Q(agency=agency) | Q(agency__isnull=True))


def _member_contacts_count(agency, user_id: int) -> int:
    return Customer.objects.filter(_member_scope_q(agency, user_id)).count()


def _member_properties_count(agency, user_id: int) -> int:
    return CRMProperty.objects.filter(
        _member_scope_q(agency, user_id),
        deleted_at__isnull=True,
    ).count()


def _activity_user_q(agency, user_id: int):
    return Q(customer__user_id=user_id) & (
        Q(customer__agency=agency) | Q(customer__agency__isnull=True)
    )


def _deal_user_q(agency, user_id: int):
    return Q(user_id=user_id) & (Q(agency=agency) | Q(agency__isnull=True))


def get_member_performance_row(agency: CRMAgency, user_id: int, days: int = 30) -> Dict[str, Any]:
    """ردیف عملکرد یک عضو — برای نمایش شخصی مشاور."""
    data = get_team_performance(agency, days=days)
    for row in data['members']:
        if row['member'].user_id == user_id:
            return row
    return {}


def get_command_center_stats(agency: CRMAgency, days: int = 30) -> Dict[str, Any]:
    since = timezone.now() - timedelta(days=days)
    today = timezone.now().date()
    inbox_count = get_team_inbox(agency).count()
    overdue = Customer.objects.filter(
        agency=agency,
        next_follow_up__lt=today,
        status__in=['جدید', 'در حال پیگیری'],
    ).count()
    stale_inbox = get_team_inbox(agency).filter(
        created_at__lt=timezone.now() - timedelta(hours=48),
    ).count()
    active_deals = CRMDeal.objects.filter(agency=agency).exclude(
        stage__in=['بسته‌شده', 'از دست رفته'],
    ).count()
    leads_period = Customer.objects.filter(agency=agency, created_at__gte=since).count()
    won_period = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__gte=since,
    ).count()
    conversion_pct = round(won_period * 100 / leads_period) if leads_period else 0
    commission_total = CRMDeal.objects.filter(
        agency=agency, stage=DEAL_STAGE_WON, closed_at__gte=since,
    ).aggregate(total=Sum('commission_amount'))['total'] or 0

    inactive_members = []
    for member in agency_members(agency):
        if member.role == 'owner':
            continue
        last_act = CustomerActivity.objects.filter(
            _activity_user_q(agency, member.user_id),
            created_at__gte=since,
        ).exists()
        if not last_act:
            inactive_members.append(member_display(member))

    return {
        'days': days,
        'inbox_unassigned': inbox_count,
        'overdue_followups': overdue,
        'stale_inbox': stale_inbox,
        'active_deals': active_deals,
        'conversion_pct': conversion_pct,
        'commission_total': commission_total,
        'inactive_members': inactive_members[:5],
        'alerts': [
            a for a in [
                {'level': 'warn', 'text': f'{inbox_count} سرنخ در صندوق بدون تخصیص'} if inbox_count else None,
                {'level': 'danger', 'text': f'{stale_inbox} سرنخ بیش از ۴۸ ساعت بدون تخصیص'} if stale_inbox else None,
                {'level': 'warn', 'text': f'{overdue} پیگیری معوق تیم'} if overdue else None,
                {'level': 'info', 'text': f'عضو بدون فعالیت: {", ".join(inactive_members[:3])}'} if inactive_members else None,
            ] if a
        ],
    }


def get_team_goals_progress(agency: CRMAgency, days: int = 30) -> List[Dict[str, Any]]:
    today = timezone.now().date()
    perf = get_team_performance(agency, days=days)
    perf_by_member = {r['member'].pk: r for r in perf['members']}
    rows = []
    for goal in CRMAgencyTeamGoal.objects.filter(
        agency=agency, period_start__lte=today, period_end__gte=today,
    ).select_related('member', 'member__user'):
        actual = 0
        if goal.member_id and goal.member_id in perf_by_member:
            actual = perf_by_member[goal.member_id].get(goal.metric, 0)
        elif not goal.member_id:
            actual = perf['totals'].get(goal.metric, 0)
        pct = round(actual * 100 / goal.target_value) if goal.target_value else 0
        rows.append({
            'goal': goal,
            'actual': actual,
            'target': goal.target_value,
            'pct': min(pct, 100),
            'member_name': member_display(goal.member) if goal.member else 'کل تیم',
            'period_label': (
                f"{to_persian_digits(format_jalali_date(goal.period_start))}"
                f" — {to_persian_digits(format_jalali_date(goal.period_end))}"
            ),
        })
    return rows


def export_team_performance_csv(agency: CRMAgency, days: int = 30) -> str:
    data = get_team_performance(agency, days=days)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['رتبه', 'نام', 'نقش', 'مخاطب', 'فایل', 'تماس', 'بازدید', 'معامله بسته', 'فعال', 'امتیاز'])
    for r in data['members']:
        writer.writerow([
            r.get('rank', ''),
            r['name'],
            r['role'],
            r['contacts'],
            r['properties'],
            r['calls'],
            r['visits'],
            r['deals_closed'],
            r['active_deals'],
            r.get('score', 0),
        ])
    return buf.getvalue()
