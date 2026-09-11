"""Context و KPIهای داشبورد آژانس — بدون metric ساختگی."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Max, Q
from django.utils import timezone

from workspace.models import AgencyActivityEvent, CRMDeal, CRMProperty, Customer
from workspace.services.agency_data_scope import list_visible_advisor_members
from workspace.services.agency_entitlement import (
    get_subscription_for_agency,
    resolve_managed_agency,
    seat_usage_summary,
)
from workspace.services.agency_members import build_members_dashboard
from workspace.services.agency_seats import get_member_seat
from workspace.services.crm_agency_tv import _agency_logo_url


def hub_base_context(user) -> dict[str, Any]:
    agency, sub = resolve_managed_agency(user)
    seats = seat_usage_summary(sub) if sub else None
    return {
        'hub_agency': agency,
        'hub_subscription': sub,
        'hub_seats': seats,
        'hub_agency_logo_url': _agency_logo_url(agency) if agency else None,
    }


def build_dashboard_context(user, days: int = 30) -> dict[str, Any]:
    ctx = hub_base_context(user)
    agency = ctx['hub_agency']
    if not agency:
        return ctx

    since = timezone.now() - timedelta(days=days)
    members = list_visible_advisor_members(user)
    member_users = [m.user_id for m in members]

    contacts_new = Customer.objects.filter(
        agency=agency, user_id__in=member_users, created_at__gte=since,
    ).count()
    properties_new = CRMProperty.objects.filter(
        agency=agency, user_id__in=member_users, created_at__gte=since, deleted_at__isnull=True,
    ).count()
    deals_active = CRMDeal.objects.filter(
        agency=agency, user_id__in=member_users,
    ).exclude(stage__in=['بسته‌شده', 'از دست رفته']).count()

    from contracts.models import Contract
    contracts_count = Contract.objects.filter(
        Q(agency=agency) & Q(user_id__in=member_users),
    ).count()

    ctx['summary'] = {
        'active_advisors': members.count(),
        'available_seats': (ctx['hub_seats'] or {}).get('available', 0),
        'contacts_new': contacts_new,
        'properties_new': properties_new,
        'deals_active': deals_active,
        'contracts': contracts_count,
        'period_days': days,
    }

    def _counts_by_user(model, **extra):
        qs = model.objects.filter(agency=agency, user_id__in=member_users, **extra)
        return dict(qs.values('user_id').annotate(c=Count('id')).values_list('user_id', 'c'))

    contact_counts = _counts_by_user(Customer)
    property_counts = _counts_by_user(CRMProperty, deleted_at__isnull=True)
    deal_counts = _counts_by_user(CRMDeal)
    contract_counts = _counts_by_user(Contract)

    perf_rows = []
    dash = build_members_dashboard(user, agency)
    for row in dash.get('members', []):
        m = row['member']
        uid = m.user_id
        perf_rows.append({
            'member': m,
            'seat': row.get('seat'),
            'has_seat': row.get('has_seat'),
            'contacts': contact_counts.get(uid, 0),
            'properties': property_counts.get(uid, 0),
            'deals': deal_counts.get(uid, 0),
            'contracts': contract_counts.get(uid, 0),
            'last_activity': _last_activity_for_user(uid, agency),
        })
    ctx['performance_rows'] = perf_rows
    ctx['recent_events'] = list(
        AgencyActivityEvent.objects.filter(agency=agency)
        .select_related('actor')
        .order_by('-created_at')[:15]
    )
    ctx['members_dashboard'] = dash
    return ctx


def _last_activity_for_user(user_id: int, agency) -> timezone.datetime | None:
    candidates = [
        Customer.objects.filter(agency=agency, user_id=user_id).aggregate(m=Max('updated_at'))['m'],
        CRMProperty.objects.filter(agency=agency, user_id=user_id).aggregate(m=Max('updated_at'))['m'],
        CRMDeal.objects.filter(agency=agency, user_id=user_id).aggregate(m=Max('updated_at'))['m'],
    ]
    candidates = [c for c in candidates if c]
    return max(candidates) if candidates else None


def build_activity_feed(
    user,
    *,
    advisor_id: int | None = None,
    event_type: str = '',
    date_from=None,
    date_to=None,
    limit: int = 50,
) -> list[AgencyActivityEvent]:
    agency, sub = resolve_managed_agency(user)
    if not agency or not sub:
        return []
    qs = AgencyActivityEvent.objects.filter(agency=agency).select_related('actor')
    if advisor_id:
        qs = qs.filter(actor_id=advisor_id)
    if event_type:
        qs = qs.filter(event_type=event_type)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    return list(qs.order_by('-created_at')[:limit])
