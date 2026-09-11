"""Onboarding wizard پس از خرید پلن آژانس."""
from __future__ import annotations

from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from workspace.models import CRMAgency, CRMAgencyMember
from workspace.services.agency_entitlement import (
    get_active_subscription_for_owner,
    link_agency_to_subscription,
    seat_usage_summary,
)
from workspace.services.crm_agency import _attach_user_records, _gen_api_key, _unique_slug
from workspace.services.crm_scope import get_membership


def get_owner_agency(user) -> Optional[CRMAgency]:
    sub = get_active_subscription_for_owner(user)
    if sub and sub.agency_id:
        return sub.agency
    membership = get_membership(user)
    if membership and membership.agency.owner_id == user.id:
        return membership.agency
    return CRMAgency.objects.filter(owner=user).first()


def resolve_onboarding_step(user) -> int:
    """1=agency, 2=invite, 3=seats, 4=done"""
    sub = get_active_subscription_for_owner(user)
    if not sub:
        return 1
    agency = get_owner_agency(user)
    if not agency:
        return 1
    if not agency.onboarding_completed_at:
        return 2
    from workspace.services.agency_members import build_members_dashboard
    dash = build_members_dashboard(user, agency)
    if dash.get('without_seat', 0) > 0 and dash.get('active_count', 0) > 0:
        return 3
    return 2


def onboarding_context(user) -> dict[str, Any]:
    from workspace.models import AgencyInvitation
    from workspace.services.agency_invitations import list_agency_invitations

    sub = get_active_subscription_for_owner(user)
    agency = get_owner_agency(user)
    seats = seat_usage_summary(sub) if sub else None
    invite_capacity = None
    if agency and sub:
        from workspace.services.agency_invitations import get_agency_invite_capacity
        invite_capacity = get_agency_invite_capacity(agency, sub)
    invitations = list_agency_invitations(agency) if agency else []
    pending_invites = [i for i in invitations if i.status == AgencyInvitation.STATUS_PENDING]
    members = []
    if agency:
        members = list(
            agency.members.filter(is_active=True, role__in=['advisor', 'manager', 'secretary'])
            .select_related('user')
            .order_by('joined_at')
        )
    return {
        'subscription': sub,
        'agency': agency,
        'seats': seats,
        'invite_capacity': invite_capacity,
        'step': resolve_onboarding_step(user),
        'invitations': invitations,
        'pending_invite_count': len(pending_invites),
        'members': members,
    }


@transaction.atomic
def create_or_link_agency(user, name: str, *, use_existing: bool = False) -> CRMAgency:
    sub = get_active_subscription_for_owner(user)
    if not sub:
        raise ValueError('اشتراک آژانس فعال یافت نشد')

    if use_existing:
        agency = CRMAgency.objects.filter(owner=user).first()
        if not agency:
            raise ValueError('آژانس قبلی برای ادامه یافت نشد')
    else:
        name = (name or '').strip()
        if not name:
            raise ValueError('نام آژانس الزامی است')
        membership = get_membership(user)
        if membership and membership.agency.owner_id != user.id:
            raise ValueError('شما عضو آژانس دیگری هستید')
        if membership and membership.agency.owner_id == user.id:
            agency = membership.agency
            if name and agency.name != name:
                agency.name = name
                agency.save(update_fields=['name', 'updated_at'])
        else:
            agency = CRMAgency.objects.create(
                name=name,
                slug=_unique_slug(name),
                owner=user,
                api_key=_gen_api_key(),
            )
            CRMAgencyMember.objects.get_or_create(
                agency=agency, user=user,
                defaults={'role': 'owner'},
            )
            _attach_user_records(user, agency)

    link_agency_to_subscription(agency, sub)
    if not agency.onboarding_completed_at:
        mark_agency_onboarding_complete(agency)
    return agency


def mark_agency_onboarding_complete(agency: CRMAgency) -> None:
    if not agency.onboarding_completed_at:
        agency.onboarding_completed_at = timezone.now()
        agency.save(update_fields=['onboarding_completed_at', 'updated_at'])
