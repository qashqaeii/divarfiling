"""سرویس مرکزی دسترسی آژانس — Entitlement و Permission.

منبع حقیقت: AgencySubscription فعال (نه management_status).
management_status فقط state کمکی/نمایشی است.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from workspace.constants import AGENCY_ROLE_OWNER
from workspace.models import (
    AgencySubscription,
    CRMAgency,
    CRMAgencyMember,
)

User = get_user_model()

CONSENT_VERSION_CURRENT = '2026-03-01'


def _now():
    return timezone.now()


def is_agency_plan_order(order) -> bool:
    plan = getattr(order, 'plan', None)
    return bool(plan and getattr(plan, 'allow_bulk_purchase', False))


def get_active_subscription_for_owner(owner) -> Optional[AgencySubscription]:
    if not owner or not getattr(owner, 'is_authenticated', False):
        return None
    now = _now()
    return (
        AgencySubscription.objects.filter(
            owner=owner,
            status=AgencySubscription.STATUS_ACTIVE,
            starts_at__lte=now,
            expires_at__gt=now,
        )
        .select_related('agency', 'plan', 'source_order')
        .order_by('-expires_at')
        .first()
    )


def get_subscription_for_agency(agency: CRMAgency) -> Optional[AgencySubscription]:
    """منبع حقیقت دسترسی مدیریت آژانس."""
    if not agency:
        return None
    now = _now()
    return (
        AgencySubscription.objects.filter(
            agency=agency,
            status=AgencySubscription.STATUS_ACTIVE,
            starts_at__lte=now,
            expires_at__gt=now,
        )
        .select_related('plan', 'owner')
        .order_by('-expires_at')
        .first()
    )


def sync_agency_management_status(agency: CRMAgency) -> None:
    """همگام‌سازی management_status از روی اشتراک — نه برعکس."""
    if not agency:
        return
    locked = get_subscription_for_agency(agency) is None
    new_status = 'locked' if locked else 'active'
    if agency.management_status != new_status:
        agency.management_status = new_status
        agency.save(update_fields=['management_status', 'updated_at'])


def is_agency_management_locked(agency: CRMAgency) -> bool:
    """فقط بر اساس AgencySubscription — management_status نادیده گرفته می‌شود."""
    return get_subscription_for_agency(agency) is None


def has_active_agency_entitlement(user) -> bool:
    """مالک با AgencySubscription فعال — حق مدیریت."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return get_active_subscription_for_owner(user) is not None


def _get_membership(user) -> Optional[CRMAgencyMember]:
    from workspace.services.crm_scope import get_membership
    return get_membership(user)


def _user_phone(user) -> str:
    from accounts.phone_utils import normalize_phone
    return normalize_phone(getattr(user, 'phone', None) or user.username or '')


def get_advisor_agency_seat_context(user) -> Optional[dict[str, Any]]:
    """
    مشاور فقط با:
    - membership فعال در آژانس
    - AgencySubscription معتبر همان آژانس
    - License فعال assigned به همان subscription
    """
    if not user or not user.is_authenticated:
        return None
    membership = _get_membership(user)
    if not membership or not membership.is_active:
        return None
    if membership.role == AGENCY_ROLE_OWNER:
        return None

    agency = membership.agency
    sub = get_subscription_for_agency(agency)
    if not sub:
        return None

    from licenses.models import License

    now = _now()
    license_obj = (
        License.objects.filter(
            assigned_user=user,
            agency_subscription=sub,
            order__status='paid',
        )
        .exclude(status__in=['suspended', 'expired'])
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related('plan', 'agency_subscription')
        .first()
    )
    if not license_obj:
        return None
    return {
        'membership': membership,
        'agency': agency,
        'subscription': sub,
        'license': license_obj,
    }


def has_assigned_agency_seat(user) -> bool:
    return get_advisor_agency_seat_context(user) is not None


def can_access_agency_hub(user) -> bool:
    if has_active_agency_entitlement(user):
        return True
    return has_assigned_agency_seat(user)


def can_share_team_resources(user) -> bool:
    """اشتراک CRM با هم‌تیمی — فقط عضو آژانس با دسترسی فعال (مالک اشتراک یا مشاور با لایسنس)."""
    if not user or not user.is_authenticated:
        return False
    if not _get_membership(user):
        return False
    return can_access_agency_hub(user)


def can_manage_agency(user, agency: Optional[CRMAgency] = None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    sub = get_active_subscription_for_owner(user)
    if not sub or sub.owner_id != user.id:
        return False
    if agency:
        if sub.agency_id:
            return sub.agency_id == agency.id
        return agency.owner_id == user.id
    return True


def resolve_managed_agency(
    user,
) -> tuple[Optional[CRMAgency], Optional[AgencySubscription]]:
    """آژانس قابل مدیریت — منبع حقیقت AgencySubscription است، نه membership."""
    if not user or not user.is_authenticated:
        return None, None
    sub = get_active_subscription_for_owner(user)
    if sub and sub.owner_id == user.id:
        agency = sub.agency
        if not agency:
            agency = CRMAgency.objects.filter(owner=user).order_by('-updated_at').first()
        if agency and can_manage_agency(user, agency):
            return agency, sub
    membership = _get_membership(user)
    if membership and can_manage_agency(user, membership.agency):
        agency = membership.agency
        return agency, get_subscription_for_agency(agency)
    return None, None


def can_view_agency_member(user, member: CRMAgencyMember) -> bool:
    """Owner visibility — data_visibility_consent_at فقط برای این مسیر."""
    if not member or not member.is_active:
        return False
    if member.user_id == user.id:
        return True
    if not can_manage_agency(user, member.agency):
        return False
    return bool(member.data_visibility_consent_at)


def can_export_agency_member_data(user, member: CRMAgencyMember) -> bool:
    return can_view_agency_member(user, member) and can_manage_agency(user, member.agency)


def is_expired_agency_owner(user) -> bool:
    """مالک آژانس با اشتراک منقضی."""
    if not user or not user.is_authenticated:
        return False
    if get_active_subscription_for_owner(user):
        return False
    membership = _get_membership(user)
    if not membership or not membership.is_active or membership.role != AGENCY_ROLE_OWNER:
        return False
    return membership.agency.owner_id == user.id


def agency_hub_access_level(user) -> str:
    """none | owner | owner_locked | advisor"""
    if has_active_agency_entitlement(user):
        return 'owner'
    if is_expired_agency_owner(user):
        return 'owner_locked'
    if has_assigned_agency_seat(user):
        return 'advisor'
    return 'none'


def resolve_post_agency_payment_redirect(order) -> Optional[str]:
    """Redirect پس از پرداخت موفق پلن آژانس — idempotent."""
    if not is_agency_plan_order(order) or order.status != 'paid':
        return None
    provision_subscription_from_paid_order(order)
    sub = get_active_subscription_for_owner(order.user)
    if not sub:
        return None
    agency = sub.agency or CRMAgency.objects.filter(owner=order.user).first()
    if not agency or not agency.onboarding_completed_at:
        return reverse('workspace:agency_onboarding')
    return reverse('workspace:agency_hub_advisors')


@transaction.atomic
def provision_subscription_from_paid_order(order) -> Optional[AgencySubscription]:
    if not is_agency_plan_order(order) or order.status != 'paid':
        return None

    existing = AgencySubscription.objects.filter(source_order=order).first()
    if existing:
        return existing

    from licenses.models import License

    owner = order.user
    plan = order.plan
    seat_count = max(2, int(order.quantity or 2))
    duration_days = int(plan.duration_days or 30)
    now = _now()

    prior_active = get_active_subscription_for_owner(owner)
    prior_latest = (
        AgencySubscription.objects.filter(owner=owner)
        .select_related('agency')
        .order_by('-expires_at')
        .first()
    )
    prior_agency = None
    if prior_active and prior_active.agency_id:
        prior_agency = prior_active.agency
    elif prior_latest and prior_latest.agency_id:
        prior_agency = prior_latest.agency
    else:
        prior_agency = CRMAgency.objects.filter(owner=owner).first()

    if prior_active and prior_active.expires_at and prior_active.expires_at > now:
        new_expires = prior_active.expires_at + timedelta(days=duration_days)
    else:
        new_expires = now + timedelta(days=duration_days)

    AgencySubscription.objects.filter(
        owner=owner,
        status=AgencySubscription.STATUS_ACTIVE,
    ).update(status=AgencySubscription.STATUS_EXPIRED)

    sub = AgencySubscription.objects.create(
        owner=owner,
        agency=prior_agency,
        source_order=order,
        plan=plan,
        seat_count=seat_count,
        starts_at=now,
        expires_at=new_expires,
        status=AgencySubscription.STATUS_ACTIVE,
    )

    if sub.agency_id:
        sync_agency_management_status(sub.agency)

    def _attach_license(lic, subscription):
        lic.agency_subscription = subscription
        lic.expires_at = new_expires
        update_fields = ['agency_subscription', 'expires_at']
        if lic.status == 'expired':
            lic.status = 'active' if lic.assigned_user_id else 'inactive'
            update_fields.append('status')
        lic.save(update_fields=update_fields)

    for lic in License.objects.filter(order=order).order_by('sequence', 'pk'):
        _attach_license(lic, sub)

    if prior_latest and prior_latest.pk != sub.pk:
        for lic in License.objects.filter(agency_subscription=prior_latest).exclude(order=order):
            _attach_license(lic, sub)

    return sub


def link_agency_to_subscription(agency: CRMAgency, subscription: AgencySubscription) -> None:
    subscription.agency = agency
    subscription.save(update_fields=['agency', 'updated_at'])
    sync_agency_management_status(agency)


def seat_usage_summary(subscription: AgencySubscription) -> dict[str, Any]:
    from licenses.models import License

    seats = License.objects.filter(agency_subscription=subscription)
    assigned = seats.filter(assigned_user__isnull=False).count()
    return {
        'total': subscription.seat_count,
        'purchased': seats.count(),
        'assigned': assigned,
        'available': max(0, seats.filter(assigned_user__isnull=True).count()),
        'expires_at': subscription.expires_at,
        'status': subscription.status,
    }


def subscriptions_for_owner_qs(owner) -> QuerySet:
    return AgencySubscription.objects.filter(owner=owner).select_related('agency', 'plan', 'source_order')


def sync_expired_subscriptions() -> int:
    now = _now()
    expired = AgencySubscription.objects.filter(
        status=AgencySubscription.STATUS_ACTIVE,
        expires_at__lte=now,
    )
    count = 0
    for sub in expired.select_related('agency'):
        sub.status = AgencySubscription.STATUS_EXPIRED
        sub.save(update_fields=['status', 'updated_at'])
        if sub.agency_id:
            sync_agency_management_status(sub.agency)
        count += 1
    return count
