"""Moderation Agency Space — بدون leak محتوای confidential."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from workspace.models import AgencySpaceItem
from workspace.services.agency_space_access import can_moderate_agency_space
from workspace.services.agency_space_publish import _audit

User = get_user_model()


class AgencySpaceModerationError(ValueError):
    pass


@transaction.atomic
def hide_space_item_public(
    actor: User,
    item_id: int,
    *,
    moderation_reason: str = '',
) -> AgencySpaceItem:
    agency_item = _get_item_for_moderation(actor, item_id)
    if agency_item.visibility != AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC:
        raise AgencySpaceModerationError('مخفی‌سازی مدیریتی فقط برای انتشار عمومی است')
    if agency_item.status != AgencySpaceItem.STATUS_ACTIVE:
        raise AgencySpaceModerationError('آیتم فعال نیست')

    agency_item.status = AgencySpaceItem.STATUS_MODERATION_HIDDEN
    agency_item.archived_at = timezone.now()
    agency_item.archived_reason = AgencySpaceItem.ARCHIVE_MODERATION
    agency_item.save(update_fields=['status', 'archived_at', 'archived_reason', 'updated_at'])
    meta = {}
    reason = (moderation_reason or '').strip()[:200]
    if reason:
        meta['moderation_reason'] = reason
    _audit(agency_item, actor, 'space.moderation_hidden', meta)
    return agency_item


@transaction.atomic
def restore_space_item_moderation(actor: User, item_id: int) -> AgencySpaceItem:
    if not can_moderate_agency_space(actor):
        raise AgencySpaceModerationError('دسترسی مدیریت ندارید')
    from workspace.services.agency_space_access import get_user_space_agency

    agency = get_user_space_agency(actor)
    if not agency:
        raise AgencySpaceModerationError('آژانس یافت نشد')
    try:
        item = AgencySpaceItem.objects.get(pk=item_id, agency=agency)
    except AgencySpaceItem.DoesNotExist:
        raise AgencySpaceModerationError('آیتم یافت نشد')
    if item.status != AgencySpaceItem.STATUS_MODERATION_HIDDEN:
        raise AgencySpaceModerationError('آیتم در وضعیت مخفی مدیریتی نیست')
    if item.visibility != AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC:
        raise AgencySpaceModerationError('بازگردانی فقط برای انتشار عمومی')

    item.status = AgencySpaceItem.STATUS_ACTIVE
    item.archived_at = None
    item.archived_reason = ''
    item.save(update_fields=['status', 'archived_at', 'archived_reason', 'updated_at'])
    _audit(item, actor, 'space.moderation_restored', {})
    return item


def _get_item_for_moderation(actor: User, item_id: int) -> AgencySpaceItem:
    if not can_moderate_agency_space(actor):
        raise AgencySpaceModerationError('دسترسی مدیریت ندارید')
    from workspace.services.agency_space_access import get_user_space_agency

    agency = get_user_space_agency(actor)
    if not agency:
        raise AgencySpaceModerationError('آژانس یافت نشد')
    try:
        raw = AgencySpaceItem.objects.get(pk=item_id, agency=agency)
    except AgencySpaceItem.DoesNotExist:
        raise AgencySpaceModerationError('آیتم یافت نشد')
    if raw.visibility != AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC:
        raise AgencySpaceModerationError(
            'فقط انتشار عمومی از لیست فضای آژانس قابل moderation است',
        )
    if raw.status != AgencySpaceItem.STATUS_ACTIVE:
        raise AgencySpaceModerationError('آیتم فعال نیست')
    return raw
