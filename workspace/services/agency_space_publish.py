"""انتشار و مدیریت Agency Space — Publish ≠ Transfer."""
from __future__ import annotations

from typing import List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from workspace.models import AgencySpaceItem, AgencySpaceItemMember, CRMProperty, Customer, CRMAgencyMember
from workspace.services.agency_space_access import (
    assert_can_publish,
    can_edit_space_item,
    can_unpublish_space_item,
    get_user_space_agency,
)
from workspace.services.agency_space_query import get_active_space_item_for_source
from workspace.services.crm_audit import log_agency_audit
from workspace.services.crm_scope import get_membership

User = get_user_model()


class AgencySpacePublishError(ValueError):
    pass


def _validate_property_source(publisher: User, prop: CRMProperty, agency_id: int) -> None:
    if prop.user_id != publisher.id:
        raise AgencySpacePublishError('فقط مالک فایل می‌تواند آن را منتشر کند')
    if prop.deleted_at:
        raise AgencySpacePublishError('فایل حذف‌شده قابل انتشار نیست')
    if prop.agency_id and prop.agency_id != agency_id:
        raise AgencySpacePublishError('فایل متعلق به آژانس دیگری است')
    if not prop.agency_id:
        prop.agency_id = agency_id
        prop.save(update_fields=['agency_id'])


def _validate_customer_source(publisher: User, customer: Customer, agency_id: int) -> None:
    if customer.user_id != publisher.id:
        raise AgencySpacePublishError('فقط مالک مخاطب می‌تواند آن را منتشر کند')
    if customer.agency_id and customer.agency_id != agency_id:
        raise AgencySpacePublishError('مخاطب متعلق به آژانس دیگری است')
    if not customer.agency_id:
        customer.agency_id = agency_id
        customer.save(update_fields=['agency_id'])


def _set_audience(item: AgencySpaceItem, member_ids: List[int], agency_id: int) -> None:
    AgencySpaceItemMember.objects.filter(item=item).delete()
    if item.visibility != AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS:
        return
    if not member_ids:
        raise AgencySpacePublishError('برای انتشار محرمانه حداقل یک عضو انتخاب کنید')
    members = CRMAgencyMember.objects.filter(
        agency_id=agency_id, pk__in=member_ids, is_active=True,
    )
    found = set(members.values_list('pk', flat=True))
    if len(found) != len(set(member_ids)):
        raise AgencySpacePublishError('عضو انتخاب‌شده معتبر نیست')
    for m in members:
        if m.user_id == item.publisher_id:
            continue
        AgencySpaceItemMember.objects.create(item=item, member=m)


def _audit(item: AgencySpaceItem, actor: User, event: str, extra: dict = None) -> None:
    payload = {
        'agency_id': item.agency_id,
        'item_id': item.pk,
        'source_type': item.content_kind(),
        'publisher_id': item.publisher_id,
        'actor_id': actor.pk,
    }
    if extra:
        payload.update(extra)
    log_agency_audit(item.agency, actor, event, payload)


def _emit_public_activity(item: AgencySpaceItem, actor: User) -> None:
    if item.visibility != AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC:
        return
    from workspace.services.agency_activity import emit_agency_activity

    kind = 'فایل' if item.property_id else 'مخاطب'
    from workspace.services.agency_activity import EVENT_SPACE_ITEM_PUBLISHED

    emit_agency_activity(
        item.agency, actor, EVENT_SPACE_ITEM_PUBLISHED,
        object_type=item.content_kind(), object_id=item.pk,
        metadata={'kind_label': kind},
    )


@transaction.atomic
def publish_property(
    actor: User,
    property_id: int,
    *,
    visibility: str,
    member_ids: Optional[List[int]] = None,
    note: str = '',
) -> AgencySpaceItem:
    agency = get_user_space_agency(actor)
    if not agency:
        raise AgencySpacePublishError('دسترسی فضای آژانس ندارید')
    assert_can_publish(actor, agency)

    existing = get_active_space_item_for_source(actor, property_id=property_id)
    if existing:
        raise AgencySpacePublishError('انتشار فعال از قبل وجود دارد — از مدیریت انتشار استفاده کنید')

    try:
        prop = CRMProperty.objects.get(pk=property_id)
    except CRMProperty.DoesNotExist:
        raise AgencySpacePublishError('فایل یافت نشد')

    _validate_property_source(actor, prop, agency.pk)

    if visibility not in dict(AgencySpaceItem.VISIBILITY_CHOICES):
        raise AgencySpacePublishError('سطح دسترسی نامعتبر است')

    item = AgencySpaceItem.objects.create(
        agency=agency,
        publisher=actor,
        property=prop,
        visibility=visibility,
        status=AgencySpaceItem.STATUS_ACTIVE,
        note=(note or '')[:300],
        contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
    )
    _set_audience(item, member_ids or [], agency.pk)
    _audit(item, actor, 'space.published', {'visibility': visibility})
    _emit_public_activity(item, actor)
    return item


@transaction.atomic
def publish_customer(
    actor: User,
    customer_id: int,
    *,
    visibility: str,
    contact_share_level: str,
    member_ids: Optional[List[int]] = None,
    note: str = '',
) -> AgencySpaceItem:
    agency = get_user_space_agency(actor)
    if not agency:
        raise AgencySpacePublishError('دسترسی فضای آژانس ندارید')
    assert_can_publish(actor, agency)

    existing = get_active_space_item_for_source(actor, customer_id=customer_id)
    if existing:
        raise AgencySpacePublishError('انتشار فعال از قبل وجود دارد')

    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        raise AgencySpacePublishError('مخاطب یافت نشد')

    _validate_customer_source(actor, customer, agency.pk)

    if visibility not in dict(AgencySpaceItem.VISIBILITY_CHOICES):
        raise AgencySpacePublishError('سطح دسترسی نامعتبر است')
    if contact_share_level not in dict(AgencySpaceItem.CONTACT_SHARE_LEVEL_CHOICES):
        raise AgencySpacePublishError('سطح اشتراک مخاطب نامعتبر است')

    item = AgencySpaceItem.objects.create(
        agency=agency,
        publisher=actor,
        customer=customer,
        visibility=visibility,
        status=AgencySpaceItem.STATUS_ACTIVE,
        contact_share_level=contact_share_level,
        note=(note or '')[:300],
    )
    _set_audience(item, member_ids or [], agency.pk)
    _audit(item, actor, 'space.published', {
        'visibility': visibility,
        'contact_share_level': contact_share_level,
    })
    _emit_public_activity(item, actor)
    return item


@transaction.atomic
def update_space_item(
    actor: User,
    item_id: int,
    *,
    visibility: Optional[str] = None,
    contact_share_level: Optional[str] = None,
    member_ids: Optional[List[int]] = None,
    note: Optional[str] = None,
) -> AgencySpaceItem:
    from workspace.services.agency_space_query import get_space_item_for_user

    item = get_space_item_for_user(actor, item_id)
    if not item or not can_edit_space_item(actor, item):
        raise AgencySpacePublishError('دسترسی ویرایش ندارید')

    old_vis = item.visibility
    if visibility is not None:
        if visibility not in dict(AgencySpaceItem.VISIBILITY_CHOICES):
            raise AgencySpacePublishError('سطح دسترسی نامعتبر است')
        item.visibility = visibility
    if contact_share_level is not None and item.customer_id:
        if contact_share_level not in dict(AgencySpaceItem.CONTACT_SHARE_LEVEL_CHOICES):
            raise AgencySpacePublishError('سطح اشتراک نامعتبر است')
        item.contact_share_level = contact_share_level
    if note is not None:
        item.note = (note or '')[:300]
    item.save()

    if member_ids is not None or visibility is not None:
        mids = member_ids
        if mids is None and item.visibility == AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS:
            mids = list(item.audience_members.values_list('member_id', flat=True))
        _set_audience(item, mids or [], item.agency_id)

    if visibility is not None and visibility != old_vis:
        _audit(item, actor, 'space.visibility_changed', {'from': old_vis, 'to': visibility})
    if member_ids is not None:
        _audit(item, actor, 'space.audience_changed', {'count': len(member_ids or [])})
    return item


@transaction.atomic
def unpublish_space_item(actor: User, item_id: int) -> AgencySpaceItem:
    from workspace.services.agency_space_query import get_space_item_for_user

    item = get_space_item_for_user(actor, item_id)
    if not item:
        raise AgencySpacePublishError('آیتم یافت نشد')
    if not can_unpublish_space_item(actor, item):
        raise AgencySpacePublishError('دسترسی لغو انتشار ندارید')
    if item.status != AgencySpaceItem.STATUS_ACTIVE:
        raise AgencySpacePublishError('این انتشار فعال نیست')

    item.status = AgencySpaceItem.STATUS_ARCHIVED
    item.archived_at = timezone.now()
    item.archived_reason = AgencySpaceItem.ARCHIVE_USER_UNPUBLISH
    item.save(update_fields=['status', 'archived_at', 'archived_reason', 'updated_at'])
    _audit(item, actor, 'space.unpublished', {})
    return item
