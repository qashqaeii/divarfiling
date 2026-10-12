"""Agency Mobile Operations — payload builders (reuse workspace services)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from workspace.constants import (
    AGENCY_ROLE_OWNER,
    AGENCY_ROLES,
    LEAD_ROUTING_CHOICES,
    TEAM_VISIBILITY_INBOX,
)
from workspace.models import AgencyActivityEvent, AgencyInvitation, CRMAgencyMember, Customer
from workspace.services.agency_entitlement import (
    can_manage_agency,
    get_subscription_for_agency,
    resolve_managed_agency,
    seat_usage_summary,
)
from workspace.services.agency_hub import build_activity_feed
from workspace.services.agency_invitations import get_agency_invite_capacity
from workspace.services.agency_members import build_members_dashboard
from workspace.services.agency_seats import get_member_seat, list_available_seats
from workspace.services.crm_agency import get_team_inbox, member_display, update_agency_settings
from workspace.services.crm_agency_analytics import (
    get_command_center_stats,
    get_member_performance_row,
    get_team_goals_progress,
    get_team_performance,
)
from workspace.services.crm_scope import (
    agency_members,
    can_manage_team,
    can_operate_team_leads,
    get_membership,
)
from mobile_api.services.team_mobile import member_to_dict, team_overview_for_user
from workspace.services.agency_activity import EVENT_TYPE_LABELS


def _activity_event_title(event_type: str) -> str:
    key = (event_type or '').strip()
    if not key:
        return ''
    return EVENT_TYPE_LABELS.get(key, key.replace('_', ' '))


def _activity_event_payload(ev) -> Dict[str, Any]:
    event_type = ev.event_type
    label = _activity_event_title(event_type)
    return {
        'id': ev.pk,
        'event_type': event_type,
        'event_label': label,
        'title': label,
        'created_at': ev.created_at.isoformat() if ev.created_at else '',
        'actor_name': ev.actor.get_full_name() if ev.actor_id else '',
    }


def _invitation_to_dict(inv: AgencyInvitation) -> Dict[str, Any]:
    return {
        'id': inv.pk,
        'phone': inv.phone,
        'role': inv.role,
        'role_label': dict(AGENCY_ROLES).get(inv.role, inv.role),
        'status': inv.status,
        'expires_at': inv.expires_at.isoformat() if inv.expires_at else '',
        'created_at': inv.created_at.isoformat() if inv.created_at else '',
    }


def _seat_dict(seats) -> Optional[Dict[str, Any]]:
    if not seats:
        return None
    expires = seats.get('expires_at')
    return {
        'total': seats.get('total', 0),
        'assigned': seats.get('assigned', 0),
        'available': seats.get('available', 0),
        'purchased': seats.get('purchased', 0),
        'expires_at': expires.isoformat() if expires else '',
        'status': seats.get('status', ''),
    }


def _member_seat_payload(member: CRMAgencyMember) -> Dict[str, Any]:
    seat = get_member_seat(member)
    if not seat:
        return {'has_seat': False, 'license_id': None, 'sequence': None, 'plan': '', 'status': ''}
    return {
        'has_seat': True,
        'license_id': seat.pk,
        'sequence': seat.sequence,
        'plan': seat.plan.name if seat.plan_id else '',
        'status': seat.status,
        'expires_at': seat.expires_at.isoformat() if seat.expires_at else '',
    }


def _active_leads_count(agency, user_id: int) -> int:
    return Customer.objects.filter(
        agency=agency,
        user_id=user_id,
    ).exclude(status__in=['بایگانی', 'ناموفق']).count()


def _active_deals_count(agency, user_id: int) -> int:
    from workspace.models import CRMDeal

    return CRMDeal.objects.filter(
        agency=agency,
        user_id=user_id,
    ).exclude(stage__in=['بسته‌شده', 'از دست رفته']).count()


def agency_home_for_user(user) -> Dict[str, Any]:
    from mobile_api.services.agency_space_mobile import agency_space_capabilities
    from workspace.services.agency_space_analytics import get_space_header_kpis

    overview = team_overview_for_user(user)
    if not overview.get('has_agency'):
        return overview

    membership = get_membership(user)
    agency = membership.agency
    capabilities = agency_space_capabilities(user, agency)
    _, sub = resolve_managed_agency(user)
    seats = seat_usage_summary(sub) if sub else None
    dash = build_members_dashboard(user, agency) if can_manage_agency(user, agency) else None
    stats = get_command_center_stats(agency, days=1)

    active_members = sum(1 for m in agency_members(agency) if m.is_active)
    permissions = overview['permissions']
    permissions = {
        **permissions,
        'can_manage_agency': can_manage_agency(user, agency),
        'can_manage_seats': can_manage_agency(user, agency),
        'can_invite': can_manage_agency(user, agency),
    }

    attention: List[Dict[str, Any]] = []
    if dash:
        if dash.get('pending_invites'):
            attention.append({
                'kind': 'pending_invites',
                'title': 'دعوت در انتظار',
                'subtitle': f"{dash['pending_invites']} دعوت باز",
                'count': dash['pending_invites'],
            })
        if dash.get('without_seat'):
            attention.append({
                'kind': 'members_without_seat',
                'title': 'عضو بدون صندلی',
                'subtitle': f"{dash['without_seat']} نفر بدون لایسنس",
                'count': dash['without_seat'],
            })
    if stats.get('inbox_unassigned'):
        attention.append({
            'kind': 'inbox_leads',
            'title': 'سرنخ بدون مسئول',
            'subtitle': f"{stats['inbox_unassigned']} سرنخ در صندوق",
            'count': stats['inbox_unassigned'],
        })
    for alert in stats.get('alerts') or []:
        attention.append({
            'kind': 'alert',
            'title': alert.get('text', ''),
            'subtitle': '',
            'level': alert.get('level', 'info'),
            'count': 0,
        })

    kpis = {
        'active_members': active_members,
        'unassigned_leads': stats.get('inbox_unassigned', 0),
        'team_followups_today': stats.get('overdue_followups', 0),
        'active_deals': stats.get('active_deals', 0),
    }

    space_kpis = None
    if capabilities.get('can_view_space_analytics'):
        space_kpis = get_space_header_kpis(user, agency)

    team_activity: List[Dict[str, Any]] = []
    if can_manage_team(user):
        for ev in build_activity_feed(user, limit=8):
            team_activity.append(_activity_event_payload(ev))

    return {
        **overview,
        'permissions': permissions,
        'capabilities': capabilities,
        'seats': _seat_dict(seats),
        'kpis': kpis,
        'space_kpis': space_kpis,
        'attention': attention,
        'team_activity': team_activity,
        'invite_capacity': get_agency_invite_capacity(agency, sub) if sub and can_manage_agency(user, agency) else None,
    }


def list_advisors_for_user(
    user,
    *,
    q: str = '',
    status: str = '',
) -> Dict[str, Any]:
    membership = get_membership(user)
    if not membership:
        return {'advisors': [], 'invitations': [], 'count': 0}
    agency = membership.agency
    can_manage = can_manage_agency(user, agency)
    invitations = []
    if can_manage:
        dash = build_members_dashboard(user, agency)
        invitations = [_invitation_to_dict(i) for i in dash.get('invitations', [])]

    rows: List[Dict[str, Any]] = []
    for member in agency_members(agency):
        if member.role == 'owner' and not can_manage_team(user):
            continue
        base = member_to_dict(member)
        seat = _member_seat_payload(member)
        row = {
            **base,
            **seat,
            'active_leads': _active_leads_count(agency, member.user_id),
            'active_deals': _active_deals_count(agency, member.user_id),
            'membership_status': 'active' if member.is_active else 'inactive',
        }
        if status == 'active' and not member.is_active:
            continue
        if status == 'inactive' and member.is_active:
            continue
        if status == 'invited':
            continue
        if status == 'no_seat' and seat.get('has_seat'):
            continue
        if status == 'with_seat' and not seat.get('has_seat'):
            continue
        query = (q or '').strip().lower()
        if query and query not in base['name'].lower() and query not in base['phone']:
            continue
        rows.append(row)

    if status == 'invited':
        rows = []

    return {
        'advisors': rows,
        'invitations': invitations if status in ('', 'invited') else [],
        'count': len(rows),
    }


def advisor_detail_for_user(user, member_id: int) -> Optional[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return None
    agency = membership.agency
    try:
        member = CRMAgencyMember.objects.select_related('user').get(
            pk=member_id, agency=agency,
        )
    except CRMAgencyMember.DoesNotExist:
        return None

    if member.role == 'owner' and member.user_id != user.id and not can_manage_team(user):
        return None

    perf = get_member_performance_row(agency, member.user_id, days=30)
    performance = {
        'contacts': perf.get('contacts', 0),
        'calls': perf.get('calls', 0),
        'visits': perf.get('visits', 0),
        'active_deals': perf.get('active_deals', 0),
        'deals_closed': perf.get('deals_closed', 0),
        'score_pct': perf.get('score_pct', 0),
        'rank': perf.get('rank'),
    } if perf else {}

    activities = []
    if can_manage_team(user):
        for ev in build_activity_feed(user, advisor_id=member.user_id, limit=8):
            activities.append(_activity_event_payload(ev))

    u = member.user
    can_manage = can_manage_agency(user, agency)
    can_set_role = can_manage and member.role != AGENCY_ROLE_OWNER and member.is_active
    assignable_roles = []
    if can_set_role:
        assignable_roles = [
            {'value': code, 'label': label}
            for code, label in AGENCY_ROLES
            if code != AGENCY_ROLE_OWNER
        ]

    goals: List[Dict[str, Any]] = []
    if can_manage_team(user):
        perf_data = get_team_performance(agency, days=30)
        for row in get_team_goals_progress(agency, days=30, perf=perf_data):
            goal = row.get('goal')
            if goal and goal.member_id and goal.member_id != member.pk:
                continue
            goals.append({
                'member_name': row.get('member_name', ''),
                'metric': goal.metric if goal else '',
                'target': row.get('target', 0),
                'actual': row.get('actual', 0),
                'pct': row.get('pct', 0),
                'period_label': row.get('period_label', ''),
            })

    from mobile_api.services.agency_advisor_mobile import advisor_section_counts
    from workspace.services.agency_entitlement import can_view_agency_member

    section_counts = advisor_section_counts(user, member_id) or {}
    can_workspace = can_view_agency_member(user, member)

    return {
        'member': member_to_dict(member),
        'membership_status': 'active' if member.is_active else 'inactive',
        'section_counts': section_counts,
        'can_view_workspace': can_workspace,
        'email': getattr(u, 'email', '') or '',
        'seat': _member_seat_payload(member),
        'performance': performance,
        'stats': {
            'active_leads': _active_leads_count(agency, member.user_id),
            'active_deals': _active_deals_count(agency, member.user_id),
        },
        'goals': goals,
        'assignable_roles': assignable_roles,
        'recent_activity': activities,
        'permissions': {
            'can_manage_member': can_manage and member.role != 'owner',
            'can_manage_seat': can_manage and member.role != 'owner',
            'can_set_role': can_set_role,
            'can_transfer_leads': can_operate_team_leads(user) or can_manage_team(user),
        },
    }


def seats_overview_for_user(user) -> Dict[str, Any]:
    agency, sub = resolve_managed_agency(user)
    if not agency or not can_manage_agency(user, agency):
        raise ValueError('دسترسی مدیریت صندلی ندارید')
    seats = seat_usage_summary(sub) if sub else None
    dash = build_members_dashboard(user, agency)
    members = []
    for row in dash.get('members', []):
        m = row['member']
        members.append({
            **member_to_dict(m),
            **_member_seat_payload(m),
        })
    available = [
        {
            'id': lic.pk,
            'sequence': lic.sequence,
            'plan': lic.plan.name if lic.plan_id else '',
        }
        for lic in list_available_seats(user, agency)
    ]
    return {
        'seats': _seat_dict(seats),
        'members': members,
        'available_licenses': available,
        'invite_capacity': get_agency_invite_capacity(agency, sub) if sub else None,
    }


def team_performance_for_user(user, *, days: int = 7) -> Dict[str, Any]:
    membership = get_membership(user)
    if not membership or not can_manage_team(user):
        raise ValueError('دسترسی گزارش عملکرد ندارید')
    agency = membership.agency
    data = get_team_performance(agency, days=days)
    goals_raw = get_team_goals_progress(agency, days=days, perf=data)
    goals = [
        {
            'member_name': row.get('member_name', ''),
            'metric': row['goal'].metric if row.get('goal') else '',
            'target': row.get('target', 0),
            'actual': row.get('actual', 0),
            'pct': row.get('pct', 0),
            'period_label': row.get('period_label', ''),
        }
        for row in goals_raw
    ]
    members = []
    for row in data.get('members') or []:
        member = row.get('member')
        members.append({
            'member_id': member.pk if member else None,
            'user_id': member.user_id if member else None,
            'name': row.get('name', ''),
            'role': row.get('role', ''),
            'contacts': row.get('contacts', 0),
            'calls': row.get('calls', 0),
            'visits': row.get('visits', 0),
            'active_deals': row.get('active_deals', 0),
            'deals_closed': row.get('deals_closed', 0),
            'score_pct': row.get('score_pct', 0),
            'rank': row.get('rank'),
        })
    return {
        'days': days,
        'totals': data.get('totals') or {},
        'members': members,
        'goals': goals,
    }


def agency_activity_for_user(
    user,
    *,
    advisor_member_id: int | None = None,
    event_type: str = '',
    limit: int = 50,
) -> Optional[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return None
    agency = membership.agency
    actor_user_id: int | None = None
    advisors: List[Dict[str, Any]] = []
    can_filter = can_manage_team(user)

    if can_filter:
        from workspace.services.agency_data_scope import (
            list_visible_advisor_members,
            resolve_visible_agency_member,
        )

        advisors = [member_to_dict(m) for m in list_visible_advisor_members(user)]
        if advisor_member_id:
            try:
                actor_user_id = resolve_visible_agency_member(
                    user, advisor_member_id,
                ).user_id
            except Exception:
                return {
                    'events': [],
                    'advisors': advisors,
                    'can_filter_advisor': True,
                    'event_type': event_type or '',
                }
    else:
        actor_user_id = user.id

    events = []
    for ev in build_activity_feed(
        user,
        advisor_id=actor_user_id,
        event_type=(event_type or '').strip(),
        limit=limit,
    ):
        events.append(_activity_event_payload(ev))
    since = timezone.now() - timedelta(days=90)
    event_types = list(
        AgencyActivityEvent.objects.filter(agency=agency, created_at__gte=since)
        .order_by('event_type')
        .values_list('event_type', flat=True)
        .distinct()[:40],
    )
    return {
        'events': events,
        'advisors': advisors,
        'can_filter_advisor': can_filter,
        'event_type': (event_type or '').strip(),
        'event_types': event_types,
        'event_type_options': [
            {'value': t, 'label': _activity_event_title(t)}
            for t in event_types
        ],
    }


def agency_settings_payload(user) -> Optional[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return None
    agency = membership.agency
    can_edit = can_manage_team(user)
    return {
        'name': agency.name,
        'slug': agency.slug,
        'lead_routing_policy': agency.lead_routing_policy or '',
        'lead_routing_options': [
            {'value': code, 'label': label} for code, label in LEAD_ROUTING_CHOICES
        ],
        'permissions': {'can_edit': can_edit},
    }


def agency_settings_update(user, *, name: str = '', lead_routing_policy: str = '') -> Dict[str, Any]:
    update_agency_settings(user, name=name, lead_routing_policy=lead_routing_policy)
    payload = agency_settings_payload(user)
    if not payload:
        raise ValueError('آژانس یافت نشد')
    return payload


def agency_audit_payload(user, *, limit: int = 50) -> Dict[str, Any]:
    if not can_manage_team(user):
        raise ValueError('دسترسی گزارش ممیزی ندارید')
    membership = get_membership(user)
    if not membership:
        raise ValueError('آژانس یافت نشد')
    from workspace.models import CRMAgencyAuditLog
    from workspace.services.crm_audit import build_audit_timeline

    cap = max(1, min(int(limit or 50), 80))
    logs = list(
        CRMAgencyAuditLog.objects.filter(agency=membership.agency)
        .select_related('actor')
        .order_by('-created_at')[:cap],
    )
    timeline = build_audit_timeline(logs)
    for group in timeline.get('groups') or []:
        for entry in group.get('entries') or []:
            entry.pop('_created_at', None)
    return {'timeline': timeline}


def serialize_inbox_leads_enriched(agency, *, filter_key: str = 'all') -> List[Dict[str, Any]]:
    now = timezone.now()
    rows = []
    for c in get_team_inbox(agency)[:200]:
        if filter_key == 'fresh' and c.created_at and c.created_at < now - timedelta(hours=24):
            continue
        if filter_key == 'stale' and c.created_at and c.created_at >= now - timedelta(hours=48):
            continue
        need = (c.notes or c.customer_type or c.status or '').strip()[:120]
        rows.append({
            'id': c.pk,
            'name': c.name or '',
            'phone': c.phone or '',
            'source': c.source or '',
            'need_summary': need,
            'created_at': c.created_at.isoformat() if c.created_at else '',
            'assigned_to': None,
            'team_visibility': c.team_visibility or TEAM_VISIBILITY_INBOX,
            'status': c.status or '',
        })
    return rows
