"""گزارش عملکرد تیم — E4."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.db.models import Count, Q
from django.utils import timezone

from workspace.constants import DEAL_STAGE_WON
from workspace.models import CRMAgency, CRMDeal, CRMProperty, Customer, CustomerActivity, PropertyVisit
from workspace.services.crm_agency import member_display, role_label
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
            customer__agency=agency,
            activity_type='تماس',
            created_at__gte=since,
        ).filter(_activity_user_q(uid)).count()

        visits = PropertyVisit.objects.filter(
            user_id=uid,
            customer__agency=agency,
            visit_date__gte=since.date(),
        ).count()

        deals_closed = CRMDeal.objects.filter(
            agency=agency,
            stage=DEAL_STAGE_WON,
            closed_at__gte=since,
        ).filter(_deal_user_q(uid)).count()

        active_deals = CRMDeal.objects.filter(agency=agency).filter(
            _deal_user_q(uid),
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


def _member_contacts_count(agency, user_id: int) -> int:
    return Customer.objects.filter(agency=agency, user_id=user_id).count()


def _member_properties_count(agency, user_id: int) -> int:
    return CRMProperty.objects.filter(agency=agency, user_id=user_id).count()


def _activity_user_q(user_id: int):
    return Q(customer__user_id=user_id)


def _deal_user_q(user_id: int):
    return Q(user_id=user_id)


def get_member_performance_row(agency: CRMAgency, user_id: int, days: int = 30) -> Dict[str, Any]:
    """ردیف عملکرد یک عضو — برای نمایش شخصی مشاور."""
    data = get_team_performance(agency, days=days)
    for row in data['members']:
        if row['member'].user_id == user_id:
            return row
    return {}
