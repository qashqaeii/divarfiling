"""اشتراک‌گذاری صریح منابع CRM بین اعضای تیم."""
from __future__ import annotations

from typing import List, Optional

from django.db import transaction

from workspace.models import CRMAgencyMember, CRMDeal, CRMProperty, CRMResourceShare, Customer
from workspace.services.crm import log_activity
from workspace.services.agency_entitlement import can_share_team_resources
from workspace.services.crm_scope import get_membership


def _agency_member(agency, user_id: int) -> CRMAgencyMember:
    return CRMAgencyMember.objects.get(agency=agency, user_id=user_id, is_active=True)


@transaction.atomic
def share_customer(
    actor,
    customer: Customer,
    to_member_id: int,
    *,
    note: str = '',
    share_mode: str = CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
) -> CRMResourceShare:
    if customer.user_id != actor.id:
        raise ValueError('فقط مالک مخاطب می‌تواند آن را به اشتراک بگذارد')
    if not can_share_team_resources(actor):
        raise ValueError('اشتراک با هم‌تیمی فقط برای اعضای آژانس با لایسنس فعال است')
    m = get_membership(actor)
    if not m or customer.agency_id != m.agency_id:
        raise ValueError('مخاطب در آژانس شما نیست')
    to_member = CRMAgencyMember.objects.get(pk=to_member_id, agency=m.agency, is_active=True)
    if to_member.user_id == actor.id:
        raise ValueError('نمی‌توانید با خودتان به اشتراک بگذارید')
    mode = share_mode if share_mode in dict(CRMResourceShare.SHARE_MODE_CHOICES) else CRMResourceShare.SHARE_MODE_CONFIDENTIAL
    share, created = CRMResourceShare.objects.update_or_create(
        agency=m.agency,
        customer=customer,
        shared_with=to_member.user,
        defaults={
            'owner': actor,
            'shared_by': actor,
            'note': (note or '').strip()[:300],
            'share_mode': mode,
            'property': None,
            'deal': None,
        },
    )
    if created:
        log_activity(
            customer, 'یادداشت',
            title='اشتراک با هم‌تیمی',
            content=f'با {to_member.user.get_full_name() or to_member.user.username}',
        )
    return share


@transaction.atomic
def share_property(
    actor,
    prop: CRMProperty,
    to_member_id: int,
    *,
    note: str = '',
    share_mode: str = CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
) -> CRMResourceShare:
    if prop.user_id != actor.id:
        raise ValueError('فقط مالک ملک می‌تواند آن را به اشتراک بگذارد')
    if not can_share_team_resources(actor):
        raise ValueError('اشتراک با هم‌تیمی فقط برای اعضای آژانس با لایسنس فعال است')
    m = get_membership(actor)
    if not m:
        raise ValueError('عضویت آژانس یافت نشد')
    if not to_member_id:
        raise ValueError('هم‌تیمی مقصد را انتخاب کنید')
    if not prop.agency_id:
        prop.agency_id = m.agency_id
        prop.save(update_fields=['agency_id'])
    elif prop.agency_id != m.agency_id:
        raise ValueError('ملک در آژانس شما نیست')
    try:
        to_member = CRMAgencyMember.objects.get(pk=to_member_id, agency=m.agency, is_active=True)
    except CRMAgencyMember.DoesNotExist:
        raise ValueError('عضو تیم یافت نشد')
    if to_member.user_id == actor.id:
        raise ValueError('نمی‌توانید با خودتان به اشتراک بگذارید')
    mode = share_mode if share_mode in dict(CRMResourceShare.SHARE_MODE_CHOICES) else CRMResourceShare.SHARE_MODE_CONFIDENTIAL
    share, _ = CRMResourceShare.objects.update_or_create(
        agency=m.agency,
        property=prop,
        shared_with=to_member.user,
        defaults={
            'owner': actor,
            'shared_by': actor,
            'note': (note or '').strip()[:300],
            'share_mode': mode,
            'customer': None,
            'deal': None,
        },
    )
    return share


def revoke_share(actor, share_id: int) -> None:
    m = get_membership(actor)
    if not m:
        raise ValueError('آژانس یافت نشد')
    share = CRMResourceShare.objects.get(pk=share_id, agency=m.agency)
    if share.owner_id != actor.id and share.shared_with_id != actor.id:
        raise ValueError('دسترسی لغو اشتراک ندارید')
    share.delete()


def list_shares_for_customer(customer: Customer) -> List[CRMResourceShare]:
    return list(
        customer.shares.select_related('shared_with', 'shared_by').order_by('-created_at')
    )


def list_shares_for_property(prop: CRMProperty) -> List[CRMResourceShare]:
    return list(
        prop.shares.select_related('shared_with', 'shared_by').order_by('-created_at')
    )


def share_for_customer_recipient(user, customer: Customer) -> Optional[CRMResourceShare]:
    """رکورد اشتراک وقتی کاربر جاری گیرنده مخاطب است."""
    return (
        CRMResourceShare.objects.filter(customer=customer, shared_with=user)
        .select_related('shared_by', 'owner', 'shared_with')
        .first()
    )
