"""مدیریت اعضای آژانس — حذف، لیست."""
from __future__ import annotations

from django.db import transaction

from workspace.models import CRMAgencyMember
from workspace.services.agency_entitlement import can_manage_agency, resolve_managed_agency
from workspace.services.agency_seats import get_member_seat, unassign_seat
from workspace.services.crm_audit import log_agency_audit
from workspace.services.crm_scope import agency_members


def build_members_dashboard(actor, agency) -> dict:
    from workspace.models import AgencyInvitation
    from workspace.services.agency_entitlement import get_subscription_for_agency, seat_usage_summary
    from workspace.services.agency_invitations import list_agency_invitations

    sub = get_subscription_for_agency(agency)
    seats = seat_usage_summary(sub) if sub else None
    members = []
    for m in agency_members(agency):
        if m.role == 'owner':
            continue
        seat = get_member_seat(m)
        members.append({
            'member': m,
            'seat': seat,
            'has_seat': seat is not None,
        })
    invitations = list_agency_invitations(agency)
    return {
        'members': members,
        'invitations': invitations,
        'seats': seats,
        'active_count': sum(1 for row in members if row['member'].is_active),
        'without_seat': sum(1 for row in members if row['member'].is_active and not row['has_seat']),
        'pending_invites': sum(
            1 for i in invitations if i.status == AgencyInvitation.STATUS_PENDING
        ),
    }


@transaction.atomic
def remove_agency_member(actor, member_id: int) -> CRMAgencyMember:
    agency, _sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        raise ValueError('دسترسی مدیریت آژانس ندارید')

    try:
        member = CRMAgencyMember.objects.select_related('user', 'agency').get(
            pk=member_id, agency=agency,
        )
    except CRMAgencyMember.DoesNotExist:
        raise ValueError('عضو یافت نشد')

    if member.role == 'owner':
        raise ValueError('مالک آژانس قابل حذف نیست')

    seat = get_member_seat(member)
    if seat:
        unassign_seat(actor, seat.pk)

    member.is_active = False
    member.save(update_fields=['is_active'])

    log_agency_audit(
        agency, actor, 'agency_member_removed',
        {'member_id': member.pk, 'user_id': member.user_id},
    )
    return member
