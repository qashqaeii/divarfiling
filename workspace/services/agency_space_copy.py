"""کپی شخصی از Agency Space — snapshot مستقل + provenance در AgencySpaceCopy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse

from workspace.models import AgencySpaceCopy, AgencySpaceItem, CRMProperty, Customer
from workspace.services.agency_space_access import (
    assert_can_copy_from_agency_space,
    can_access_agency_space,
    get_user_space_agency,
)
from workspace.services.agency_space_publish import _audit
from workspace.services.agency_space_query import get_space_item_for_user
from workspace.services.crm_property_duplicate import create_property_copy_from_space_source

User = get_user_model()

CUSTOMER_COPY_SCALAR_FIELDS = [
    'name', 'customer_type', 'status', 'priority', 'property_type',
    'city', 'district', 'job', 'is_legal_entity', 'company_name',
    'gender',
    'budget_min', 'budget_max', 'deposit_min', 'deposit_max',
    'rent_min', 'rent_max', 'min_area', 'max_area', 'rooms',
    'rooms_min', 'rooms_max', 'year_min', 'year_max',
    'floor_min', 'floor_max', 'want_parking', 'want_storage', 'want_elevator',
    'areas', 'matching_tolerance_percent', 'tags',
    'builder_buy_property_types', 'builder_buy_budget_min', 'builder_buy_budget_max',
    'builder_buy_areas', 'builder_buy_min_area', 'builder_buy_max_area',
    'notes', 'lease_deadline',
]

CUSTOMER_CONTACT_FIELDS_FULL = ('phone', 'phone_alt', 'email')


class AgencySpaceCopyError(ValueError):
    pass


@dataclass
class SpaceCopyResult:
    kind: str
    target_id: int
    target_url: str
    already_copied: bool
    copy_id: int


def space_copy_target_url(kind: str, target_id: int) -> str:
    if not target_id:
        return ''
    if kind == 'property':
        return reverse('workspace:crm_property_detail', kwargs={'property_id': target_id})
    return reverse('workspace:crm_detail', kwargs={'customer_id': target_id})


def _live_target_id(rec: AgencySpaceCopy) -> Optional[int]:
    if rec.target_kind == AgencySpaceCopy.TARGET_PROPERTY:
        return rec.copied_property_id
    return rec.copied_customer_id


def _result_from_copy(rec: AgencySpaceCopy, already_copied: bool) -> SpaceCopyResult:
    kind = rec.target_kind
    tid = _live_target_id(rec) or 0
    return SpaceCopyResult(
        kind=kind,
        target_id=tid,
        target_url=space_copy_target_url(kind, tid) if tid else '',
        already_copied=already_copied,
        copy_id=rec.pk,
    )


def _validate_item_source(item: AgencySpaceItem) -> None:
    if item.status != AgencySpaceItem.STATUS_ACTIVE:
        raise AgencySpaceCopyError('انتشار فعال نیست')
    if item.property_id:
        prop = item.property
        if not prop or prop.deleted_at:
            raise AgencySpaceCopyError('منبع فایل در دسترس نیست')
        if prop.agency_id and prop.agency_id != item.agency_id:
            raise AgencySpaceCopyError('منبع نامعتبر است')
    elif item.customer_id:
        cust = item.customer
        if not cust:
            raise AgencySpaceCopyError('منبع مخاطب در دسترس نیست')
        if cust.agency_id and cust.agency_id != item.agency_id:
            raise AgencySpaceCopyError('منبع نامعتبر است')
    else:
        raise AgencySpaceCopyError('آیتم بدون منبع')


def duplicate_property_from_space(
    actor: User,
    item: AgencySpaceItem,
    agency,
) -> CRMProperty:
    prop = item.property
    if not prop:
        raise AgencySpaceCopyError('فایل منبع یافت نشد')
    copy = create_property_copy_from_space_source(prop, actor, agency)
    if copy.agency_id != agency.id:
        raise AgencySpaceCopyError('آژانس نسخه شخصی نامعتبر است')
    return copy


def duplicate_customer_from_space(
    actor: User,
    item: AgencySpaceItem,
    agency,
) -> Customer:
    source = item.customer
    if not source:
        raise AgencySpaceCopyError('مخاطب منبع یافت نشد')

    include_contact = item.contact_share_level == AgencySpaceItem.CONTACT_FULL
    data = {field: getattr(source, field) for field in CUSTOMER_COPY_SCALAR_FIELDS}
    data['user'] = actor
    data['agency'] = agency
    data['team_visibility'] = 'private'
    data['assigned_to'] = None
    data['assigned_by'] = None
    data['assigned_at'] = None
    data['converted_from'] = None
    data['source'] = ''
    data['next_follow_up'] = None
    data['social_links'] = {}
    data['active_channels'] = []
    data['national_id'] = ''

    for field in CUSTOMER_CONTACT_FIELDS_FULL:
        data[field] = getattr(source, field) or '' if include_contact else ''

    data['status'] = 'جدید'

    customer = Customer.objects.create(**data)
    if customer.agency_id != agency.id:
        raise AgencySpaceCopyError('آژانس نسخه شخصی نامعتبر است')
    return customer


def copy_space_item_to_personal_crm(actor: User, item_id: int) -> SpaceCopyResult:
    agency = get_user_space_agency(actor)
    if not agency or not can_access_agency_space(actor, agency):
        raise AgencySpaceCopyError('دسترسی فضای آژانس ندارید')

    item = get_space_item_for_user(actor, item_id)
    if not item or item.agency_id != agency.id:
        raise AgencySpaceCopyError('آیتم یافت نشد')

    assert_can_copy_from_agency_space(actor, item)
    _validate_item_source(item)

    existing = AgencySpaceCopy.objects.filter(item=item, copied_by=actor).first()
    if existing and _live_target_id(existing):
        return _result_from_copy(existing, already_copied=True)

    return _create_copy_transactional(actor, item, agency)


@transaction.atomic
def _create_copy_transactional(
    actor: User,
    item: AgencySpaceItem,
    agency,
) -> SpaceCopyResult:
    locked = (
        AgencySpaceCopy.objects.select_for_update()
        .filter(item=item, copied_by=actor)
        .first()
    )
    if locked and _live_target_id(locked):
        return _result_from_copy(locked, already_copied=True)

    target_prop = None
    target_cust = None
    kind = (
        AgencySpaceCopy.TARGET_PROPERTY
        if item.property_id
        else AgencySpaceCopy.TARGET_CUSTOMER
    )
    try:
        if item.property_id:
            target_prop = duplicate_property_from_space(actor, item, agency)
            if locked:
                locked.copied_property = target_prop
                locked.copied_customer = None
                locked.target_kind = kind
                locked.target_id_snapshot = target_prop.pk
                locked.save()
                rec = locked
            else:
                rec = AgencySpaceCopy.objects.create(
                    item=item,
                    copied_by=actor,
                    target_kind=kind,
                    target_id_snapshot=target_prop.pk,
                    copied_property=target_prop,
                )
        else:
            target_cust = duplicate_customer_from_space(actor, item, agency)
            if locked:
                locked.copied_customer = target_cust
                locked.copied_property = None
                locked.target_kind = kind
                locked.target_id_snapshot = target_cust.pk
                locked.save()
                rec = locked
            else:
                rec = AgencySpaceCopy.objects.create(
                    item=item,
                    copied_by=actor,
                    target_kind=kind,
                    target_id_snapshot=target_cust.pk,
                    copied_customer=target_cust,
                )
    except IntegrityError:
        if target_prop:
            target_prop.delete()
        if target_cust:
            target_cust.delete()
        rec = AgencySpaceCopy.objects.filter(item=item, copied_by=actor).first()
        if rec and _live_target_id(rec):
            return _result_from_copy(rec, already_copied=True)
        raise AgencySpaceCopyError('خطا در ثبت کپی — دوباره تلاش کنید')

    target_id = rec.copied_property_id or rec.copied_customer_id
    _audit(item, actor, 'space.item_copied', {
        'copied_by_id': actor.pk,
        'target_id': target_id,
    })
    return _result_from_copy(rec, already_copied=False)


def copy_result_to_api_dict(result: SpaceCopyResult) -> Dict[str, Any]:
    return {
        'kind': result.kind,
        'target_id': result.target_id,
        'target_url': result.target_url,
        'already_copied': result.already_copied,
    }
