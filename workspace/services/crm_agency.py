"""سرویس آژانس CRM — فاز ۴."""
from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.phone_utils import find_user_by_phone, is_valid_iran_mobile, normalize_phone
from workspace.constants import (
    AGENCY_ROLE_ADVISOR, AGENCY_ROLE_OWNER,
    LEAD_ROUTING_INBOX, LEAD_ROUTING_OWNER, LEAD_ROUTING_ROUND_ROBIN,
    TEAM_VISIBILITY_ASSIGNED, TEAM_VISIBILITY_INBOX, TEAM_VISIBILITY_PRIVATE,
)
from workspace.models import (
    CRMAgency, CRMAgencyMember, CRMAgencyMembershipRequest, CRMDeal, CRMDealCommissionSplit,
    CRMProperty, Customer, CustomerTransferLog,
)
from workspace.services.crm import log_activity
from workspace.services.crm_audit import log_agency_audit
from workspace.services.crm_scope import can_manage_team, can_operate_team_leads, get_membership

User = get_user_model()


def _unique_slug(base: str) -> str:
    slug = slugify(base, allow_unicode=True) or 'agency'
    slug = slug[:70]
    candidate = slug
    n = 1
    while CRMAgency.objects.filter(slug=candidate).exists():
        candidate = f'{slug}-{n}'
        n += 1
    return candidate


def _gen_api_key() -> str:
    return secrets.token_hex(24)


def _assert_not_in_agency(user) -> None:
    if get_membership(user):
        raise ValueError('کاربر از قبل عضو یک آژانس است')


def _pending_request_exists(agency, user, request_type: str) -> bool:
    return CRMAgencyMembershipRequest.objects.filter(
        agency=agency, user=user, request_type=request_type, status=CRMAgencyMembershipRequest.STATUS_PENDING,
    ).exists()


@transaction.atomic
def create_agency(user, name: str) -> CRMAgency:
    name = (name or '').strip()
    if not name:
        raise ValueError('نام آژانس الزامی است')
    if get_membership(user):
        raise ValueError('شما عضو یک آژانس هستید')
    agency = CRMAgency.objects.create(
        name=name,
        slug=_unique_slug(name),
        owner=user,
        api_key=_gen_api_key(),
    )
    CRMAgencyMember.objects.create(agency=agency, user=user, role=AGENCY_ROLE_OWNER)
    _attach_user_records(user, agency)
    return agency


def _attach_user_records(user, agency: CRMAgency) -> None:
    user_id = user.id if hasattr(user, 'id') else int(user)
    Customer.objects.filter(user_id=user_id, agency__isnull=True).update(agency=agency)
    CRMProperty.objects.filter(user_id=user_id, agency__isnull=True).update(agency=agency)
    CRMDeal.objects.filter(user_id=user_id, agency__isnull=True).update(agency=agency)


def sync_agency_member_records(agency: CRMAgency) -> None:
    """اتصال داده‌های بدون آژانس همهٔ اعضای فعال — برای اعضای دعوت‌شدهٔ قدیمی."""
    for uid in agency.members.filter(is_active=True).values_list('user_id', flat=True):
        _attach_user_records(uid, agency)


@transaction.atomic
def invite_member_by_phone(actor, phone: str, role: str = AGENCY_ROLE_ADVISOR) -> CRMAgencyMembershipRequest:
    """DEPRECATED — از create_agency_invitation (AgencyInvitation + SMS) استفاده کنید."""
    if not can_manage_team(actor):
        raise ValueError('دسترسی مدیریت تیم ندارید')
    m = get_membership(actor)
    if not m:
        raise ValueError('آژانس یافت نشد')
    phone = normalize_phone(phone or '')
    if not is_valid_iran_mobile(phone):
        raise ValueError('شماره موبایل معتبر نیست')
    if role == AGENCY_ROLE_OWNER:
        raise ValueError('نقش مالک قابل تخصیص نیست')
    target = find_user_by_phone(phone)
    if not target:
        raise ValueError('کاربری با این شماره یافت نشد — ابتدا باید در سیستم ثبت‌نام کند')
    if target.id == actor.id:
        raise ValueError('نمی‌توانید خودتان را دعوت کنید')
    if CRMAgencyMember.objects.filter(agency=m.agency, user=target, is_active=True).exists():
        raise ValueError('کاربر از قبل عضو است')
    if get_membership(target):
        raise ValueError('کاربر عضو آژانس دیگری است')
    if _pending_request_exists(m.agency, target, CRMAgencyMembershipRequest.TYPE_INVITE):
        raise ValueError('دعوت در انتظار تأیید از قبل ارسال شده است')
    return CRMAgencyMembershipRequest.objects.create(
        agency=m.agency,
        user=target,
        requested_by=actor,
        request_type=CRMAgencyMembershipRequest.TYPE_INVITE,
        role=role,
    )


@transaction.atomic
def request_join_agency(user, agency_slug: str, message: str = '') -> CRMAgencyMembershipRequest:
    if get_membership(user):
        raise ValueError('شما عضو یک آژانس هستید')
    slug = (agency_slug or '').strip()
    if not slug:
        raise ValueError('شناسه آژانس الزامی است')
    agency = CRMAgency.objects.filter(slug__iexact=slug).first()
    if not agency:
        raise ValueError('آژانس با این شناسه یافت نشد')
    if CRMAgencyMember.objects.filter(agency=agency, user=user, is_active=True).exists():
        raise ValueError('شما از قبل عضو این آژانس هستید')
    if _pending_request_exists(agency, user, CRMAgencyMembershipRequest.TYPE_JOIN):
        raise ValueError('درخواست عضویت شما در انتظار تأیید است')
    return CRMAgencyMembershipRequest.objects.create(
        agency=agency,
        user=user,
        requested_by=user,
        request_type=CRMAgencyMembershipRequest.TYPE_JOIN,
        message=(message or '').strip()[:500],
    )


def _finalize_membership(request: CRMAgencyMembershipRequest) -> CRMAgencyMember:
    _assert_not_in_agency(request.user)
    member, _ = CRMAgencyMember.objects.update_or_create(
        agency=request.agency, user=request.user,
        defaults={'role': request.role, 'is_active': True},
    )
    _attach_user_records(request.user, request.agency)
    return member


@transaction.atomic
def respond_membership_request(actor, request_id: int, *, accept: bool) -> CRMAgencyMembershipRequest:
    req = CRMAgencyMembershipRequest.objects.select_related('agency', 'user').get(pk=request_id)
    if req.status != CRMAgencyMembershipRequest.STATUS_PENDING:
        raise ValueError('این درخواست دیگر قابل پاسخ نیست')

    if req.request_type == CRMAgencyMembershipRequest.TYPE_INVITE:
        if req.user_id != actor.id:
            raise ValueError('فقط کاربر دعوت‌شده می‌تواند پاسخ دهد')
    elif req.request_type == CRMAgencyMembershipRequest.TYPE_JOIN:
        m = get_membership(actor)
        if not m or m.agency_id != req.agency_id or not can_manage_team(actor):
            raise ValueError('فقط مدیر آژانس می‌تواند درخواست عضویت را بررسی کند')
    else:
        raise ValueError('نوع درخواست نامعتبر است')

    req.responded_by = actor
    req.responded_at = timezone.now()
    if accept:
        _finalize_membership(req)
        req.status = CRMAgencyMembershipRequest.STATUS_ACCEPTED
    else:
        req.status = CRMAgencyMembershipRequest.STATUS_REJECTED
    req.save(update_fields=['status', 'responded_by', 'responded_at'])
    return req


@transaction.atomic
def cancel_membership_request(actor, request_id: int) -> None:
    req = CRMAgencyMembershipRequest.objects.get(pk=request_id)
    if req.status != CRMAgencyMembershipRequest.STATUS_PENDING:
        raise ValueError('این درخواست دیگر قابل لغو نیست')
    if req.requested_by_id != actor.id:
        raise ValueError('فقط درخواست‌دهنده می‌تواند لغو کند')
    req.status = CRMAgencyMembershipRequest.STATUS_CANCELLED
    req.responded_by = actor
    req.responded_at = timezone.now()
    req.save(update_fields=['status', 'responded_by', 'responded_at'])


def update_member_role(actor, member_id: int, role: str) -> CRMAgencyMember:
    if not can_manage_team(actor):
        raise ValueError('دسترسی ندارید')
    m = get_membership(actor)
    member = CRMAgencyMember.objects.get(pk=member_id, agency=m.agency, is_active=True)
    if member.role == AGENCY_ROLE_OWNER:
        raise ValueError('نقش مالک قابل تغییر نیست')
    if role == AGENCY_ROLE_OWNER:
        raise ValueError('نقش مالک مجاز نیست')
    member.role = role
    member.save(update_fields=['role'])
    return member


def remove_member(actor, member_id: int) -> None:
    if not can_manage_team(actor):
        raise ValueError('دسترسی ندارید')
    m = get_membership(actor)
    member = CRMAgencyMember.objects.get(pk=member_id, agency=m.agency)
    if member.role == AGENCY_ROLE_OWNER:
        raise ValueError('مالک قابل حذف نیست')
    member.is_active = False
    member.save(update_fields=['is_active'])


def assign_customer(actor, customer: Customer, advisor_id: int) -> Customer:
    """تخصیص = اشتراک‌گذاری مخاطب با مشاور (فقط مالک)."""
    from workspace.services.crm_sharing import share_customer
    share_customer(actor, customer, advisor_id)
    m = get_membership(actor)
    advisor = CRMAgencyMember.objects.get(pk=advisor_id, agency=m.agency, is_active=True)
    customer.assigned_to = advisor.user
    customer.save(update_fields=['assigned_to', 'updated_at'])
    return customer


def transfer_customer(
    actor, customer: Customer, to_member_id: int, *, note: str = '',
) -> Customer:
    if customer.user_id != actor.id:
        raise ValueError('فقط مالک پرونده می‌تواند آن را منتقل کند')
    m = get_membership(actor)
    if not m:
        raise ValueError('آژانس یافت نشد')
    if customer.agency_id != m.agency_id:
        raise ValueError('مخاطب در آژانس شما نیست')
    to_member = CRMAgencyMember.objects.get(pk=to_member_id, agency=m.agency, is_active=True)
    from_user = customer.assigned_to or customer.user
    customer.assigned_to = to_member.user
    customer.user = to_member.user
    customer.save(update_fields=['assigned_to', 'user', 'updated_at'])
    customer.shares.all().delete()
    CustomerTransferLog.objects.create(
        agency=m.agency,
        customer=customer,
        from_user=from_user,
        to_user=to_member.user,
        transferred_by=actor,
        note=(note or '').strip()[:300],
    )
    log_activity(
        customer, 'یادداشت',
        title='انتقال پرونده',
        content=f'به {to_member.user.get_full_name() or to_member.user.username}',
    )
    return customer


def set_commission_splits(actor, deal: CRMDeal, splits: List[Dict[str, Any]]) -> List[CRMDealCommissionSplit]:
    if not can_manage_team(actor):
        raise ValueError('دسترسی ندارید')
    m = get_membership(actor)
    if deal.agency_id != m.agency_id:
        raise ValueError('معامله در آژانس شما نیست')
    total_pct = sum(float(s.get('percent') or 0) for s in splits)
    if splits and abs(total_pct - 100) > 0.01:
        raise ValueError('مجموع درصدها باید ۱۰۰ باشد')
    deal.commission_splits.all().delete()
    rows = []
    base = deal.commission_amount or 0
    for s in splits:
        member = CRMAgencyMember.objects.get(pk=s['member_id'], agency=m.agency, is_active=True)
        pct = float(s.get('percent') or 0)
        amount = int(base * pct / 100) if base else None
        rows.append(CRMDealCommissionSplit.objects.create(
            deal=deal, member=member, percent=pct, amount=amount,
        ))
    return rows


def member_display(member: CRMAgencyMember) -> str:
    u = member.user
    return u.get_full_name() or u.phone or u.username


def role_label(role: str) -> str:
    return dict(CRMAgencyMember._meta.get_field('role').choices).get(role, role)


def regenerate_api_key(actor) -> str:
    if not can_manage_team(actor):
        raise ValueError('دسترسی ندارید')
    m = get_membership(actor)
    if not m:
        raise ValueError('آژانس یافت نشد')
    m.agency.api_key = _gen_api_key()
    m.agency.save(update_fields=['api_key', 'updated_at'])
    log_agency_audit(m.agency, actor, 'api_key.regenerated', {})
    return m.agency.api_key


def update_agency_settings(actor, *, name: str = '', lead_routing_policy: str = '') -> CRMAgency:
    if not can_manage_team(actor):
        raise ValueError('دسترسی ندارید')
    m = get_membership(actor)
    if not m:
        raise ValueError('آژانس یافت نشد')
    agency = m.agency
    updates = []
    name = (name or '').strip()
    if name and name != agency.name:
        agency.name = name
        updates.append('name')
    policy = (lead_routing_policy or '').strip()
    if policy and policy in {LEAD_ROUTING_OWNER, LEAD_ROUTING_INBOX, LEAD_ROUTING_ROUND_ROBIN}:
        agency.lead_routing_policy = policy
        updates.append('lead_routing_policy')
    if updates:
        agency.save(update_fields=updates + ['updated_at'])
        log_agency_audit(agency, actor, 'agency.updated', {'fields': updates})
    return agency


def _next_round_robin_member(agency: CRMAgency) -> Optional[CRMAgencyMember]:
    advisors = list(
        agency.members.filter(is_active=True, role=AGENCY_ROLE_ADVISOR).order_by('joined_at', 'pk'),
    )
    if not advisors:
        advisors = list(
            agency.members.filter(is_active=True).exclude(role=AGENCY_ROLE_OWNER).order_by('joined_at', 'pk'),
        )
    if not advisors:
        return None
    idx = agency.round_robin_cursor % len(advisors)
    agency.round_robin_cursor = (idx + 1) % len(advisors)
    agency.save(update_fields=['round_robin_cursor', 'updated_at'])
    return advisors[idx]


def apply_lead_routing(agency: CRMAgency, customer: Customer) -> Customer:
    """اعمال سیاست تخصیص سرنخ API/وب."""
    policy = agency.lead_routing_policy or LEAD_ROUTING_INBOX
    if policy == LEAD_ROUTING_OWNER:
        customer.user = agency.owner
        customer.assigned_to = agency.owner
        customer.assigned_at = timezone.now()
        customer.team_visibility = TEAM_VISIBILITY_ASSIGNED
        customer.save(update_fields=['user', 'assigned_to', 'assigned_at', 'team_visibility', 'updated_at'])
        return customer
    if policy == LEAD_ROUTING_ROUND_ROBIN:
        member = _next_round_robin_member(agency)
        if member:
            customer.user = member.user
            customer.assigned_to = member.user
            customer.assigned_at = timezone.now()
            customer.team_visibility = TEAM_VISIBILITY_ASSIGNED
            customer.save(update_fields=['user', 'assigned_to', 'assigned_at', 'team_visibility', 'updated_at'])
            return customer
    customer.team_visibility = TEAM_VISIBILITY_INBOX
    customer.assigned_to = None
    customer.save(update_fields=['team_visibility', 'assigned_to', 'updated_at'])
    return customer


def get_team_inbox(agency: CRMAgency):
    return Customer.objects.filter(
        agency=agency,
        team_visibility=TEAM_VISIBILITY_INBOX,
        assigned_to__isnull=True,
    ).order_by('-created_at')


@transaction.atomic
def assign_lead_to_member(actor, customer: Customer, member_id: int) -> Customer:
    if not can_operate_team_leads(actor):
        raise ValueError('دسترسی ندارید')
    m = get_membership(actor)
    if not m or customer.agency_id != m.agency_id:
        raise ValueError('مخاطب در آژانس شما نیست')
    member = CRMAgencyMember.objects.get(pk=member_id, agency=m.agency, is_active=True)
    customer.user = member.user
    customer.assigned_to = member.user
    customer.assigned_by = actor
    customer.assigned_at = timezone.now()
    customer.team_visibility = TEAM_VISIBILITY_ASSIGNED
    customer.save(update_fields=[
        'user', 'assigned_to', 'assigned_by', 'assigned_at', 'team_visibility', 'updated_at',
    ])
    log_activity(
        customer, 'یادداشت',
        title='تخصیص سرنخ',
        content=f'به {member_display(member)}',
    )
    from workspace.services.crm_webhooks import dispatch_webhook
    dispatch_webhook(m.agency, 'customer.assigned', {
        'id': customer.pk,
        'name': customer.name,
        'phone': customer.phone,
        'assigned_to': member.user_id,
    })
    log_agency_audit(m.agency, actor, 'lead.assigned', {
        'customer_id': customer.pk,
        'member_id': member.pk,
    })
    return customer


@transaction.atomic
def bulk_assign_leads(actor, customer_ids: List[int], member_id: int) -> int:
    if not can_operate_team_leads(actor):
        raise ValueError('دسترسی ندارید')
    count = 0
    for cid in customer_ids:
        try:
            customer = get_team_inbox(get_membership(actor).agency).get(pk=cid)
            assign_lead_to_member(actor, customer, member_id)
            count += 1
        except Customer.DoesNotExist:
            continue
    if count:
        log_agency_audit(get_membership(actor).agency, actor, 'lead.bulk_assigned', {
            'count': count, 'member_id': member_id,
        })
    return count


@transaction.atomic
def transfer_agency_lead(
    actor,
    customer: Customer,
    to_member_id: int,
    *,
    note: str = '',
) -> Customer:
    """انتقال سرنخ/مخاطب — مالک پرونده یا مدیر آژانس (با لاگ انتقال)."""
    if customer.user_id == actor.id:
        return transfer_customer(actor, customer, to_member_id, note=note)
    if not can_manage_team(actor):
        raise ValueError('فقط مالک پرونده یا مدیر می‌تواند منتقل کند')
    m = get_membership(actor)
    if not m or customer.agency_id != m.agency_id:
        raise ValueError('مخاطب در آژانس شما نیست')
    to_member = CRMAgencyMember.objects.get(pk=to_member_id, agency=m.agency, is_active=True)
    from_user = customer.assigned_to or customer.user
    customer.assigned_to = to_member.user
    customer.user = to_member.user
    customer.save(update_fields=['assigned_to', 'user', 'updated_at'])
    customer.shares.all().delete()
    CustomerTransferLog.objects.create(
        agency=m.agency,
        customer=customer,
        from_user=from_user,
        to_user=to_member.user,
        transferred_by=actor,
        note=(note or '').strip()[:300],
    )
    log_activity(
        customer, 'یادداشت',
        title='انتقال پرونده',
        content=f'به {member_display(to_member)}',
    )
    log_agency_audit(m.agency, actor, 'lead.transferred', {
        'customer_id': customer.pk,
        'member_id': to_member.pk,
    })
    return customer

