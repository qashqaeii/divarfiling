"""محدوده دسترسی CRM آژانس — حریم خصوصی اعضا + اشتراک صریح."""

from __future__ import annotations



from typing import Optional, Set



from django.db.models import Case, IntegerField, Q, QuerySet, Value, When



from workspace.constants import AGENCY_INBOX_ROLES, AGENCY_MANAGER_ROLES

from workspace.models import (

    CRMAgency, CRMAgencyMember, CRMDeal, CRMProperty, CRMResourceShare, Customer, Reminder,

)





_MEMBERSHIP_CACHE_MISS = object()


def get_membership(user) -> Optional[CRMAgencyMember]:

    if not user or not user.is_authenticated:

        return None

    cached = getattr(user, '_cached_crm_membership', _MEMBERSHIP_CACHE_MISS)
    if cached is not _MEMBERSHIP_CACHE_MISS:
        return cached

    membership = (
        CRMAgencyMember.objects
        .filter(user=user, is_active=True)
        .select_related('agency', 'user')
        .annotate(
            role_rank=Case(
                When(role='owner', then=Value(0)),
                When(role='manager', then=Value(1)),
                When(role='secretary', then=Value(2)),
                When(role='advisor', then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            ),
        )
        .order_by('role_rank', 'joined_at')
        .first()
    )
    # فقط عضویت مثبت cache شود — cache کردن None بعد از create_agency عضویت را stale می‌کند.
    if membership is not None:
        setattr(user, '_cached_crm_membership', membership)
    return membership





def get_agency(user) -> Optional[CRMAgency]:

    m = get_membership(user)

    return m.agency if m else None





def can_manage_team(user) -> bool:

    m = get_membership(user)

    return bool(m and m.role in AGENCY_MANAGER_ROLES)





def can_view_team_performance(user) -> bool:

    """مدیر/مالک — مشاهده آمار عملکرد اعضا بدون دسترسی به پرونده‌ها."""

    return can_manage_team(user)





def can_assign_contacts(user) -> bool:

    """مدیریت تیم — بدون دسترسی خودکار به داده‌های دیگران."""

    return can_manage_team(user)


def can_view_team_inbox(user) -> bool:
    m = get_membership(user)
    return bool(m and m.role in AGENCY_INBOX_ROLES)


def can_operate_team_leads(user) -> bool:
    return can_view_team_inbox(user)


def team_inbox_qs(user) -> QuerySet:
    m = get_membership(user)
    if not m or not can_view_team_inbox(user):
        return Customer.objects.none()
    return Customer.objects.filter(
        agency=m.agency,
        team_visibility='team_inbox',
        assigned_to__isnull=True,
    ).order_by('-created_at')


def manager_assigned_customers_qs(user) -> QuerySet:
    """پرونده‌های تخصیص‌یافته قابل مشاهده برای مدیر/منشی."""
    m = get_membership(user)
    if not m or not can_view_team_inbox(user):
        return Customer.objects.none()
    return Customer.objects.filter(
        agency=m.agency,
        team_visibility='assigned',
    ).select_related('assigned_to', 'assigned_by').order_by('-assigned_at')


def agency_customers_qs(agency: CRMAgency) -> QuerySet:
    return Customer.objects.filter(agency=agency)


def agency_properties_qs(agency: CRMAgency) -> QuerySet:
    return CRMProperty.objects.filter(agency=agency, deleted_at__isnull=True)


def agency_deals_qs(agency: CRMAgency) -> QuerySet:
    return CRMDeal.objects.filter(agency=agency)





def agency_members(agency: CRMAgency):

    return (

        CRMAgencyMember.objects

        .filter(agency=agency, is_active=True)

        .select_related('user')

        .order_by('role', 'joined_at')

    )





def _shared_customer_ids(user, agency: CRMAgency) -> Set[int]:

    return set(

        CRMResourceShare.objects.filter(

            agency=agency, shared_with=user, customer_id__isnull=False,

        ).values_list('customer_id', flat=True)

    )





def _shared_property_ids(user, agency: CRMAgency) -> Set[int]:

    return set(

        CRMResourceShare.objects.filter(

            agency=agency, shared_with=user, property_id__isnull=False,

        ).values_list('property_id', flat=True)

    )





def _shared_deal_ids(user, agency: CRMAgency) -> Set[int]:

    return set(

        CRMResourceShare.objects.filter(

            agency=agency, shared_with=user, deal_id__isnull=False,

        ).values_list('deal_id', flat=True)

    )





def is_customer_owner(user, customer: Customer) -> bool:

    return customer.user_id == user.id





def is_property_owner(user, prop: CRMProperty) -> bool:

    return prop.user_id == user.id





def is_deal_owner(user, deal: CRMDeal) -> bool:

    return deal.user_id == user.id





def can_edit_customer(user, customer: Customer) -> bool:

    return is_customer_owner(user, customer)





def can_edit_property(user, prop: CRMProperty) -> bool:
    if prop.deleted_at:
        return False
    if is_property_owner(user, prop):
        return True
    share = (
        CRMResourceShare.objects.filter(property=prop, shared_with=user)
        .only('share_mode')
        .first()
    )
    return bool(
        share and share.share_mode == CRMResourceShare.SHARE_MODE_COLLABORATIVE
    )


def property_share_mode(user, prop: CRMProperty) -> Optional[str]:
    if is_property_owner(user, prop):
        return None
    share = (
        CRMResourceShare.objects.filter(property=prop, shared_with=user)
        .only('share_mode')
        .first()
    )
    return share.share_mode if share else None





def can_edit_deal(user, deal: CRMDeal) -> bool:

    return is_deal_owner(user, deal)


def can_create_property_deal(user, prop: CRMProperty) -> bool:
    """ثبت معامله از فایل شخصی — مالک یا اشتراک کامل."""
    if not prop or prop.deleted_at:
        return False
    if not property_for_user(user, prop.pk):
        return False
    return can_edit_property(user, prop)





def customers_qs(user) -> QuerySet:

    """فقط مخاطبین خود کاربر + موارد به‌اشتراک‌گذاشته‌شده."""

    m = get_membership(user)

    if not m:

        return Customer.objects.filter(user=user)

    shared = _shared_customer_ids(user, m.agency)

    q = Q(user=user)

    if shared:

        q |= Q(pk__in=shared)

    return Customer.objects.filter(agency=m.agency).filter(q)





def properties_qs(user) -> QuerySet:

    """فقط فایل‌های شخصی خود کاربر + موارد به‌اشتراک‌گذاشته‌شده (فعال)."""

    m = get_membership(user)

    if not m:

        return CRMProperty.objects.filter(user=user, deleted_at__isnull=True)

    shared = _shared_property_ids(user, m.agency)

    q = Q(user=user)

    if shared:

        q |= Q(pk__in=shared)

    scope = Q(agency=m.agency) | Q(user=user, agency__isnull=True)
    return CRMProperty.objects.filter(deleted_at__isnull=True).filter(scope).filter(q)





def deals_qs(user) -> QuerySet:

    m = get_membership(user)

    if not m:

        return CRMDeal.objects.filter(user=user)

    shared = _shared_deal_ids(user, m.agency)

    q = Q(user=user)

    if shared:

        q |= Q(pk__in=shared)

    scope = Q(agency=m.agency) | Q(user=user, agency__isnull=True)
    return CRMDeal.objects.filter(scope).filter(q)





def reminders_qs(user) -> QuerySet:

    m = get_membership(user)

    if not m:

        return Reminder.objects.filter(user=user)

    accessible_customers = customers_qs(user).values_list('pk', flat=True)

    return Reminder.objects.filter(

        Q(user=user) | Q(customer_id__in=accessible_customers),

    ).distinct()





def customer_for_user(user, customer_id: int) -> Optional[Customer]:

    return customers_qs(user).filter(pk=customer_id).first()





def deal_for_user(user, deal_id: int) -> Optional[CRMDeal]:

    return deals_qs(user).filter(pk=deal_id).first()





def property_for_user(user, property_id: int) -> Optional[CRMProperty]:

    prop = properties_qs(user).filter(pk=property_id).first()
    if prop:
        return prop

    m = get_membership(user)
    if not m:
        return None

    prop = CRMProperty.objects.filter(
        pk=property_id, agency=m.agency, deleted_at__isnull=False,
    ).first()
    if not prop:
        return None

    if prop.user_id == user.id:
        return prop

    shared = CRMResourceShare.objects.filter(
        agency=m.agency, shared_with=user, property_id=property_id,
    ).exists()
    return prop if shared else None


