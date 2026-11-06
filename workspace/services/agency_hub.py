"""Context و KPIهای داشبورد آژانس — بدون metric ساختگی."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone

from workspace.models import AgencyActivityEvent, CRMDeal, CRMProperty, Customer
from workspace.services.agency_data_scope import list_visible_advisor_members
from workspace.services.agency_entitlement import (
    can_manage_agency,
    get_subscription_for_agency,
    resolve_managed_agency,
    seat_usage_summary,
)
from workspace.services.agency_members import build_members_dashboard
from workspace.services.agency_seats import get_member_seat
from workspace.services.crm_agency_tv import _agency_logo_url
from workspace.services.agency_rbac import (
    NAV_PROFILE_SECRETARY,
    PERM_CONTRACTS_VIEW_TEAM,
    PERM_DEALS_VIEW_TEAM,
    has_agency_permission,
    is_agency_rbac_v2_enabled,
    is_agency_secretary_hub_enabled,
    resolve_nav_profile,
)
from workspace.services.crm_agency_analytics import get_command_center_stats
from workspace.services.crm_scope import can_operate_team_leads, get_membership, team_inbox_qs


def hub_base_context(user) -> dict[str, Any]:
    agency, sub = resolve_managed_agency(user)
    membership = get_membership(user)
    if not agency and membership and membership.is_active:
        agency = membership.agency
        sub = get_subscription_for_agency(agency) if agency else None
    seats = seat_usage_summary(sub) if sub else None
    hub_member_role = ''
    if membership and membership.is_active:
        hub_member_role = membership.get_role_display()
    return {
        'hub_agency': agency,
        'hub_subscription': sub,
        'hub_seats': seats,
        'hub_agency_logo_url': _agency_logo_url(agency) if agency else None,
        'hub_member_role': hub_member_role,
        'hub_show_invite': bool(agency and can_manage_agency(user, agency)),
    }


def build_secretary_dashboard_context(user, days: int = 30) -> dict[str, Any]:
    ctx = hub_base_context(user)
    agency = ctx['hub_agency']
    membership = get_membership(user)
    if not agency and membership:
        agency = membership.agency
        ctx['hub_agency'] = agency
        ctx['hub_subscription'] = get_subscription_for_agency(agency)
    if not agency:
        return ctx
    ctx['agency_dash_profile'] = NAV_PROFILE_SECRETARY
    stats = get_command_center_stats(agency, days=min(days, 30))
    inbox_qs = team_inbox_qs(user)
    inbox_n = int(stats.get('inbox_unassigned', inbox_qs.count()) or 0)
    followups_n = int(stats.get('followups_today', 0) or 0)
    action_base = max(inbox_n + followups_n, 1)

    def _share(part: int, base: int) -> int:
        if not base:
            return 0
        return int(round((part / base) * 100))

    ctx['summary'] = {
        'inbox_unassigned': inbox_n,
        'followups_today': followups_n,
        'period_days': days,
        'mix_segments': (
            [{'key': 'inbox', 'label': 'سرنخ', 'count': inbox_n, 'pct': _share(inbox_n, action_base)}]
            if inbox_n else []
        ) + (
            [{'key': 'followup', 'label': 'پیگیری', 'count': followups_n, 'pct': _share(followups_n, action_base)}]
            if followups_n else []
        ),
        'hero_meta': (
            f'{inbox_n} سرنخ بدون مسئول'
            if inbox_n else 'صندوق سرنخ خالی است'
        ),
        'inbox_share': _share(inbox_n, action_base),
        'inbox_meta': 'نیاز به ارجاع دارند' if inbox_n else 'الان سرنخ معلقی نیست',
        'followups_share': _share(followups_n, action_base),
        'followups_meta': 'برای امروز زمان‌بندی شده' if followups_n else 'پیگیری امروز ندارید',
    }
    ctx['kpi_links'] = {
        'inbox': reverse('workspace:agency_hub_inbox'),
        'today': reverse('workspace:crm_today'),
        'contacts': reverse('workspace:crm_contacts'),
        'properties': reverse('workspace:crm_properties'),
    }
    ctx['inbox_preview'] = list(inbox_qs[:8])
    ctx['quick_actions'] = [
        {'label': 'ثبت مخاطب', 'url': '/workspace/crm/contacts/new/', 'decor': 'user_plus'},
        {'label': 'ثبت فایل', 'url': '/workspace/crm/properties/new/', 'decor': 'building'},
        {'label': 'صندوق سرنخ', 'url': '/workspace/crm/agency/inbox/', 'decor': 'inbox'},
    ]
    return ctx


def build_dashboard_context(user, days: int = 30) -> dict[str, Any]:
    ctx = hub_base_context(user)
    agency = ctx['hub_agency']
    membership = get_membership(user)
    if not agency and membership:
        agency = membership.agency
        ctx['hub_agency'] = agency
        ctx['hub_subscription'] = get_subscription_for_agency(agency)
    if not agency:
        return ctx

    profile = resolve_nav_profile(user)
    ctx['agency_dash_profile'] = profile
    if profile == NAV_PROFILE_SECRETARY and is_agency_secretary_hub_enabled(agency):
        return build_secretary_dashboard_context(user, days=days)

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
    contracts_count = 0
    if has_agency_permission(user, PERM_CONTRACTS_VIEW_TEAM):
        contracts_count = Contract.objects.filter(
            Q(agency=agency) & Q(user_id__in=member_users),
        ).count()

    summary_deals = deals_active
    if is_agency_rbac_v2_enabled(agency) and not has_agency_permission(user, PERM_DEALS_VIEW_TEAM):
        summary_deals = None

    seats = ctx['hub_seats'] or {}
    seats_total = int(seats.get('total') or 0)
    seats_assigned = int(seats.get('assigned') or 0)
    seats_available = int(seats.get('available') or 0)
    active_advisors = members.count()
    contracts_val = contracts_count if has_agency_permission(user, PERM_CONTRACTS_VIEW_TEAM) else None

    def _share(part: int, base: int) -> int:
        if not base:
            return 0
        return int(round((part / base) * 100))

    mix_segments = []
    if seats_total > 0:
        if seats_assigned:
            mix_segments.append({
                'key': 'occupied',
                'label': 'اشغال',
                'count': seats_assigned,
                'pct': _share(seats_assigned, seats_total),
            })
        if seats_available:
            mix_segments.append({
                'key': 'available',
                'label': 'آزاد',
                'count': seats_available,
                'pct': _share(seats_available, seats_total),
            })
    elif active_advisors:
        mix_segments.append({
            'key': 'occupied',
            'label': 'مشاور',
            'count': active_advisors,
            'pct': 100,
        })

    if active_advisors:
        hero_meta = f'{active_advisors} مشاور'
        if seats_total:
            hero_meta += f' · {seats_assigned} از {seats_total} صندلی'
    else:
        hero_meta = 'هنوز مشاوری در تیم نیست'

    growth_base = max(contacts_new + properties_new, 1)
    pipeline_base = max(
        (summary_deals or 0) + contacts_new + properties_new,
        1,
    ) if summary_deals is not None else max(contacts_new + properties_new, 1)

    if summary_deals is None:
        deals_meta = 'دسترسی به معاملات تیم ندارید'
        deals_share = 0
    elif summary_deals:
        deals_meta = f'{_share(summary_deals, pipeline_base)}٪ از جریان کاری باز'
        deals_share = _share(summary_deals, pipeline_base)
    else:
        deals_meta = 'معامله فعالی در تیم نیست'
        deals_share = 0

    if contacts_new:
        contacts_meta = f'در {days} روز اخیر'
        contacts_share = _share(contacts_new, growth_base)
    else:
        contacts_meta = f'در {days} روز اخیر مخاطب جدیدی نبود'
        contacts_share = 0

    if properties_new:
        properties_meta = f'در {days} روز اخیر'
        properties_share = _share(properties_new, growth_base)
    else:
        properties_meta = f'در {days} روز اخیر فایل جدیدی نبود'
        properties_share = 0

    ctx['summary'] = {
        'active_advisors': active_advisors,
        'available_seats': seats_available,
        'seats_total': seats_total,
        'seats_assigned': seats_assigned,
        'contacts_new': contacts_new,
        'properties_new': properties_new,
        'deals_active': summary_deals,
        'contracts': contracts_val,
        'period_days': days,
        'mix_segments': mix_segments,
        'hero_meta': hero_meta,
        'deals_share': deals_share,
        'deals_meta': deals_meta,
        'contacts_share': contacts_share,
        'contacts_meta': contacts_meta,
        'properties_share': properties_share,
        'properties_meta': properties_meta,
        'seat_fill_share': _share(seats_assigned, seats_total) if seats_total else 0,
    }
    ctx['kpi_links'] = {
        'advisors': reverse('workspace:agency_hub_advisors'),
        'deals': f"{reverse('workspace:crm_deals')}?bucket=active",
        'contacts': reverse('workspace:crm_contacts'),
        'properties': reverse('workspace:crm_properties'),
        'licenses': reverse('workspace:agency_hub_licenses'),
        'contracts': reverse('workspace:contracts_dashboard'),
    }

    def _counts_by_user(model, **extra):
        qs = model.objects.filter(agency=agency, user_id__in=member_users, **extra)
        return dict(qs.values('user_id').annotate(c=Count('id')).values_list('user_id', 'c'))

    contact_counts = _counts_by_user(Customer)
    property_counts = _counts_by_user(CRMProperty, deleted_at__isnull=True)
    deal_counts = _counts_by_user(CRMDeal)
    contract_counts = {}
    if has_agency_permission(user, PERM_CONTRACTS_VIEW_TEAM):
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
