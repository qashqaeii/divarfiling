"""محدوده داده مدیریتی آژانس — جدا از crm_scope (privacy workspace).

Agency Owner با AgencySubscription فعال + consent مشاور
می‌تواند داده‌های Business Advisor را ببیند/export کند.
مالکیت رکوردها تغییر نمی‌کند.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q, QuerySet
from django.utils import timezone

from contracts.models import Contract
from workspace.models import (
    AgencyActivityEvent,
    CRMDeal,
    CRMDealFollowUp,
    CRMProperty,
    Customer,
    CustomerActivity,
    Dataset,
    Listing,
    PropertyVisit,
    Reminder,
    CRMAgencyMember,
)
from workspace.services.agency_entitlement import (
    can_export_agency_member_data,
    can_view_agency_member,
    get_subscription_for_agency,
    resolve_managed_agency,
)

PERIOD_DAYS = (7, 30, 90)


class AgencyDataScopeError(PermissionDenied):
    """دسترسی به داده مشاور مجاز نیست."""


def resolve_visible_agency_member(viewer, member_id: int) -> CRMAgencyMember:
    """اعتبارسنجی target member — تنها نقطه ورود به داده مشاور."""
    if not viewer or not viewer.is_authenticated:
        raise AgencyDataScopeError('ورود الزامی است')

    agency, sub = resolve_managed_agency(viewer)
    if not agency or not sub:
        raise AgencyDataScopeError('اشتراک آژانس فعال نیست')

    try:
        member = (
            CRMAgencyMember.objects.select_related('user', 'agency')
            .get(pk=member_id, agency=agency)
        )
    except CRMAgencyMember.DoesNotExist:
        raise AgencyDataScopeError('عضو یافت نشد')

    if member.role == 'owner':
        raise AgencyDataScopeError('این عضو قابل مشاهده نیست')

    if not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی به داده این مشاور مجاز نیست')

    if not get_subscription_for_agency(agency):
        raise AgencyDataScopeError('اشتراک آژانس در حال حاضر فعال نیست')

    return member


def assert_can_export(viewer, member: CRMAgencyMember) -> None:
    if not can_export_agency_member_data(viewer, member):
        raise AgencyDataScopeError('دسترسی خروجی مجاز نیست')


def _member_record_scope(member: CRMAgencyMember) -> Q:
    """فیلتر مالکیت — user=advisor، agency هم‌راستا در صورت وجود."""
    scope = Q(user_id=member.user_id)
    if member.agency_id:
        scope &= Q(agency_id=member.agency_id) | Q(agency__isnull=True)
    return scope


def get_member_contacts_qs(
    viewer,
    member: CRMAgencyMember,
    *,
    search: str = '',
    status: str = '',
    date_from=None,
    date_to=None,
) -> QuerySet:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    qs = Customer.objects.filter(_member_record_scope(member)).select_related('assigned_to')
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(phone__icontains=search)
            | Q(phone_alt__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    qs = _apply_date_filter(qs, 'created_at', date_from, date_to)
    return qs.order_by('-updated_at')


def get_member_properties_qs(
    viewer,
    member: CRMAgencyMember,
    *,
    search: str = '',
    transaction_status: str = '',
    date_from=None,
    date_to=None,
) -> QuerySet:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    qs = (
        CRMProperty.objects.filter(_member_record_scope(member))
        .filter(deleted_at__isnull=True)
    )
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(address__icontains=search)
            | Q(district__icontains=search)
            | Q(neighborhood__icontains=search)
        )
    if transaction_status:
        qs = qs.filter(transaction_status=transaction_status)
    qs = _apply_date_filter(qs, 'created_at', date_from, date_to)
    return qs.order_by('-updated_at')


def get_member_filing_qs(
    viewer, member: CRMAgencyMember, *, date_from=None, date_to=None,
) -> QuerySet:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')
    qs = (
        Dataset.objects.filter(user_id=member.user_id, is_active=True)
        .annotate(listing_count=Count('listings'))
    )
    qs = _apply_date_filter(qs, 'created_at', date_from, date_to)
    return qs.order_by('-updated_at')


def get_member_listings_qs(
    viewer,
    member: CRMAgencyMember,
    *,
    dataset_id: Optional[str] = None,
) -> QuerySet:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    qs = Listing.objects.filter(dataset__user_id=member.user_id).select_related('dataset')
    if dataset_id:
        qs = qs.filter(dataset_id=dataset_id)
    return qs.order_by('-created_at')


def get_member_deals_qs(
    viewer,
    member: CRMAgencyMember,
    *,
    search: str = '',
    stage: str = '',
    date_from=None,
    date_to=None,
) -> QuerySet:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    qs = (
        CRMDeal.objects.filter(_member_record_scope(member))
        .select_related('customer', 'property')
    )
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(customer__name__icontains=search)
        )
    if stage:
        qs = qs.filter(stage=stage)
    qs = _apply_date_filter(qs, 'created_at', date_from, date_to)
    return qs.order_by('-updated_at')


def get_member_contracts_qs(viewer, member: CRMAgencyMember) -> QuerySet:
    """مسیر read-only مدیریتی — مستقل از ContractLicenseRequiredMixin."""
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    deal_ids = CRMDeal.objects.filter(_member_record_scope(member)).values_list('pk', flat=True)
    return (
        Contract.objects.filter(
            Q(user_id=member.user_id) | Q(deal_id__in=deal_ids),
        )
        .filter(Q(agency_id=member.agency_id) | Q(agency__isnull=True, user_id=member.user_id))
        .select_related('deal', 'deal__customer', 'current_version')
        .distinct()
        .order_by('-updated_at')
    )


def get_member_contract(viewer, member: CRMAgencyMember, contract_id: int) -> Contract | None:
    return get_member_contracts_qs(viewer, member).filter(pk=contract_id).first()


def get_agency_contracts_qs(viewer) -> QuerySet:
    """قراردادهای مشاوران قابل‌مشاهده برای مدیر تیم — read-only."""
    from workspace.services.crm_scope import can_manage_team

    agency, sub = resolve_managed_agency(viewer)
    if not agency or not sub:
        raise AgencyDataScopeError('اشتراک آژانس فعال نیست')
    if not can_manage_team(viewer):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    visible_user_ids: list[int] = []
    for member in list_visible_advisor_members(viewer):
        if can_view_agency_member(viewer, member):
            visible_user_ids.append(member.user_id)
    if not visible_user_ids:
        return Contract.objects.none()

    deal_ids = CRMDeal.objects.filter(
        agency=agency,
        user_id__in=visible_user_ids,
    ).values_list('pk', flat=True)
    return (
        Contract.objects.filter(
            Q(user_id__in=visible_user_ids) | Q(deal_id__in=deal_ids),
        )
        .filter(Q(agency_id=agency.id) | Q(agency__isnull=True, user_id__in=visible_user_ids))
        .select_related('deal', 'deal__customer', 'current_version', 'user')
        .distinct()
    )


def get_member_tasks_qs(viewer, member: CRMAgencyMember) -> QuerySet:
    """پیگیری‌های باز — Reminder + next_action روی Deal."""
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    customer_ids = get_member_contacts_qs(viewer, member).values_list('pk', flat=True)
    return (
        Reminder.objects.filter(
            Q(user_id=member.user_id) | Q(customer_id__in=customer_ids),
            is_done=False,
        )
        .select_related('customer')
        .order_by('due_at')
    )


def get_member_activity_qs(viewer, member: CRMAgencyMember, *, limit: int = 100) -> list[dict[str, Any]]:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)
    elif not can_view_agency_member(viewer, member):
        raise AgencyDataScopeError('دسترسی مجاز نیست')

    events: list[dict[str, Any]] = []
    customer_ids = list(get_member_contacts_qs(viewer, member).values_list('pk', flat=True)[:5000])

    for act in (
        CustomerActivity.objects.filter(customer_id__in=customer_ids)
        .select_related('customer')
        .order_by('-created_at')[:limit]
    ):
        events.append({
            'at': act.created_at,
            'type': 'customer_activity',
            'label': act.activity_type,
            'title': act.title or act.customer.name,
            'detail': (act.content or '')[:200],
        })

    for fu in (
        CRMDealFollowUp.objects.filter(deal__user_id=member.user_id)
        .select_related('deal')
        .order_by('-created_at')[:limit]
    ):
        events.append({
            'at': fu.created_at,
            'type': 'deal_followup',
            'label': fu.follow_up_type,
            'title': fu.deal.title,
            'detail': (fu.note or '')[:200],
        })

    for visit in (
        PropertyVisit.objects.filter(user_id=member.user_id)
        .select_related('customer', 'property')
        .order_by('-visit_date', '-created_at')[:limit]
    ):
        events.append({
            'at': visit.created_at,
            'type': 'property_visit',
            'label': 'بازدید',
            'title': visit.property.title if visit.property_id else 'بازدید',
            'detail': visit.customer.name if visit.customer_id else '',
        })

    for ev in (
        AgencyActivityEvent.objects.filter(agency_id=member.agency_id, actor_id=member.user_id)
        .order_by('-created_at')[:limit]
    ):
        events.append({
            'at': ev.created_at,
            'type': 'agency_event',
            'label': ev.event_type,
            'title': ev.object_type or ev.event_type,
            'detail': '',
        })

    events.sort(key=lambda e: e['at'], reverse=True)
    return events[:limit]


def _period_bounds(days: int):
    now = timezone.now()
    since = now - timedelta(days=days)
    prior = since - timedelta(days=days)
    return since, prior, now


def _count_in_period(qs: QuerySet, field: str, since, until=None) -> int:
    flt = {f'{field}__gte': since}
    if until:
        flt[f'{field}__lt'] = until
    return qs.filter(**flt).count()


def get_member_overview_kpis(viewer, member: CRMAgencyMember, days: int = 30) -> dict[str, Any]:
    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)

    since, prior, now = _period_bounds(days)
    contacts = get_member_contacts_qs(viewer, member)
    properties = get_member_properties_qs(viewer, member)
    datasets = get_member_filing_qs(viewer, member)
    deals = get_member_deals_qs(viewer, member)
    contracts = get_member_contracts_qs(viewer, member)
    tasks = get_member_tasks_qs(viewer, member)

    active_stages = deals.exclude(stage__in=['بسته‌شده', 'از دست رفته'])
    closed_stages = deals.filter(stage__in=['بسته‌شده', 'از دست رفته'])

    def delta(cur: int, prev: int) -> Optional[float]:
        if prev == 0:
            return None if cur == 0 else 100.0
        return round((cur - prev) / prev * 100, 1)

    c_cur = _count_in_period(contacts, 'created_at', since)
    c_prev = _count_in_period(contacts, 'created_at', prior, since)
    p_cur = _count_in_period(properties, 'created_at', since)
    p_prev = _count_in_period(properties, 'created_at', prior, since)
    d_cur = _count_in_period(datasets, 'created_at', since)
    d_prev = _count_in_period(datasets, 'created_at', prior, since)

    activity_candidates = [
        contacts.aggregate(m=Max('updated_at'))['m'],
        properties.aggregate(m=Max('updated_at'))['m'],
        deals.aggregate(m=Max('updated_at'))['m'],
        datasets.aggregate(m=Max('updated_at'))['m'],
    ]
    activity_candidates = [c for c in activity_candidates if c]
    last_activity = max(activity_candidates) if activity_candidates else None

    return {
        'period_days': days,
        'contacts': {
            'total': contacts.count(),
            'period': c_cur,
            'delta_pct': delta(c_cur, c_prev),
        },
        'properties': {
            'total': properties.count(),
            'period': p_cur,
            'delta_pct': delta(p_cur, p_prev),
        },
        'datasets': {
            'total': datasets.count(),
            'period': d_cur,
            'delta_pct': delta(d_cur, d_prev),
        },
        'deals_active': active_stages.count(),
        'deals_closed': closed_stages.count(),
        'contracts': contracts.count(),
        'open_tasks': tasks.count(),
        'last_activity': last_activity,
    }


def get_advisor_member_header(viewer, member: CRMAgencyMember) -> dict[str, Any]:
    from workspace.services.agency_seats import get_member_seat

    if isinstance(member, int):
        member = resolve_visible_agency_member(viewer, member)

    seat = get_member_seat(member)
    sub = get_subscription_for_agency(member.agency)
    return {
        'member': member,
        'user': member.user,
        'seat': seat,
        'subscription': sub,
        'has_seat': seat is not None,
    }


def list_visible_advisor_members(viewer) -> QuerySet:
    agency, sub = resolve_managed_agency(viewer)
    if not agency or not sub:
        return CRMAgencyMember.objects.none()
    return (
        CRMAgencyMember.objects.filter(
            agency=agency,
            is_active=True,
            role__in=['advisor', 'manager', 'secretary'],
            data_visibility_consent_at__isnull=False,
        )
        .select_related('user')
        .order_by('joined_at')
    )


def log_agency_activity(
    agency,
    actor,
    event_type: str,
    *,
    object_type: str = '',
    object_id: int | None = None,
    metadata: dict | None = None,
) -> AgencyActivityEvent | None:
    from workspace.services.agency_activity import emit_agency_activity
    emit_agency_activity(
        agency, actor, event_type,
        object_type=object_type, object_id=object_id, metadata=metadata,
    )
    return (
        AgencyActivityEvent.objects.filter(
            agency=agency, actor=actor, event_type=event_type,
        ).order_by('-pk').first()
    )


def _apply_date_filter(qs, field: str, date_from=None, date_to=None):
    if date_from:
        qs = qs.filter(**{f'{field}__gte': date_from})
    if date_to:
        qs = qs.filter(**{f'{field}__lte': date_to})
    return qs


def build_agency_viewer_record_scope_q(viewer) -> Q:
    """اتحاد محدوده رکوردهای مشاورانی که viewer مجاز به دیدن داده‌شان است."""
    agency, sub = resolve_managed_agency(viewer)
    if not agency or not sub:
        return Q(pk__in=[])
    combined = Q()
    has_scope = False
    members = CRMAgencyMember.objects.filter(agency=agency).exclude(role='owner')
    for member in members:
        if can_view_agency_member(viewer, member):
            combined |= _member_record_scope(member)
            has_scope = True
    return combined if has_scope else Q(pk__in=[])


def customer_for_agency_viewer(viewer, contact_id: int) -> Optional[Customer]:
    scope = build_agency_viewer_record_scope_q(viewer)
    if scope == Q(pk__in=[]):
        return None
    return Customer.objects.filter(pk=contact_id).filter(scope).first()


def property_for_agency_viewer(viewer, property_id: int) -> Optional[CRMProperty]:
    scope = build_agency_viewer_record_scope_q(viewer)
    if scope == Q(pk__in=[]):
        return None
    return CRMProperty.objects.filter(pk=property_id).filter(scope).first()


def deal_for_agency_viewer(viewer, deal_id: int) -> Optional[CRMDeal]:
    scope = build_agency_viewer_record_scope_q(viewer)
    if scope == Q(pk__in=[]):
        return None
    return CRMDeal.objects.filter(pk=deal_id).filter(scope).first()


def contract_for_agency_viewer(viewer, contract_id: int) -> Optional[Contract]:
    agency, sub = resolve_managed_agency(viewer)
    if not agency or not sub:
        return None
    members = CRMAgencyMember.objects.filter(agency=agency).exclude(role='owner')
    for member in members:
        if not can_view_agency_member(viewer, member):
            continue
        contract = get_member_contracts_qs(viewer, member).filter(pk=contract_id).first()
        if contract:
            return contract
    return None
