"""بایگانی و بازگردانی فایل‌های شخصی CRM — منبع حقیقت: ``archived_at``."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from workspace.constants import PROPERTY_TX_STATUSES
from workspace.models import CRMProperty, PropertyContact
from workspace.services.crm import log_activity
from workspace.services.crm_scope import can_edit_property, property_for_user

ARCHIVE_SCOPE_ACTIVE = 'active'
ARCHIVE_SCOPE_ARCHIVED = 'archived'
ARCHIVE_SCOPE_ALL = 'all'

BULK_PROPERTY_ARCHIVE_LIMIT = 100
RESTORE_DEFAULT_TX_STATUS = 'فعال'
RENTAL_REMINDER_TITLE_PREFIX = 'سررسید اجاره: '


def archived_properties_q() -> Q:
    return Q(archived_at__isnull=False) | Q(transaction_status='بایگانی')


def is_property_archived(prop: CRMProperty) -> bool:
    if not prop or prop.deleted_at:
        return False
    if prop.archived_at:
        return True
    return prop.transaction_status == 'بایگانی'


def apply_archive_scope(qs: QuerySet, params: dict) -> QuerySet:
    scope = (params.get('archive_scope') or params.get('file_scope') or '').strip().lower()
    tx = (params.get('transaction_status') or '').strip()

    if tx == 'بایگانی':
        return qs.filter(archived_properties_q())
    # فیلتر وضعیت معامله روی لیست جاری: بایگانی‌ها جدا هستند؛ در تب بایگانی/همه نباید حذف شوند.
    scope_includes_archived = scope in (ARCHIVE_SCOPE_ARCHIVED, 'بایگانی', ARCHIVE_SCOPE_ALL)
    if tx and tx != 'بایگانی' and not scope_includes_archived:
        qs = qs.exclude(archived_properties_q())

    if scope in ('', ARCHIVE_SCOPE_ACTIVE, 'current', 'جاری'):
        return qs.exclude(archived_properties_q())
    if scope in (ARCHIVE_SCOPE_ARCHIVED, 'بایگانی'):
        return qs.filter(archived_properties_q())
    if scope == ARCHIVE_SCOPE_ALL:
        return qs
    return qs.exclude(archived_properties_q())


def folder_item_active_property_filter(prefix: str = 'items__property__') -> Q:
    """فیلتر اعضای زونکن/کمد: حذف‌شده و بایگانی‌شده در شمارنده نیستند."""
    return Q(**{f'{prefix}deleted_at__isnull': True}) & (
        Q(**{f'{prefix}archived_at__isnull': True})
        & ~Q(**{f'{prefix}transaction_status': 'بایگانی'})
    )


def _normalize_ids(property_ids) -> List[int]:
    ids: List[int] = []
    seen = set()
    for raw in property_ids or []:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if pid in seen:
            continue
        seen.add(pid)
        ids.append(pid)
        if len(ids) >= BULK_PROPERTY_ARCHIVE_LIMIT:
            break
    return ids


def _log_archive_event(prop: CRMProperty, content: str, *, metadata: Optional[dict] = None) -> None:
    meta = {'property_id': prop.pk}
    if metadata:
        meta.update(metadata)
    for link in PropertyContact.objects.filter(property=prop).select_related('customer'):
        log_activity(
            link.customer,
            'املاک',
            title=prop.title,
            content=content,
            property_obj=prop,
            metadata=meta,
        )


def archive_property(
    user,
    prop: CRMProperty,
    *,
    reason: str = '',
    via_legacy_status: bool = False,
) -> CRMProperty:
    if not prop or prop.deleted_at:
        raise ValueError('ملک یافت نشد')
    if not can_edit_property(user, prop):
        raise PermissionError('امکان ویرایش این ملک را ندارید')
    if is_property_archived(prop):
        return prop

    pre_tx = prop.transaction_status
    if pre_tx == 'بایگانی':
        pre_tx = (prop.pre_archive_transaction_status or '').strip() or RESTORE_DEFAULT_TX_STATUS
    elif not prop.pre_archive_transaction_status:
        prop.pre_archive_transaction_status = pre_tx

    prop.archived_at = timezone.now()
    prop.archive_reason = (reason or '').strip()[:500]
    update_fields = ['archived_at', 'archive_reason', 'pre_archive_transaction_status', 'updated_at']
    if prop.transaction_status == 'بایگانی':
        prop.transaction_status = pre_tx
        update_fields.append('transaction_status')
    prop.save(update_fields=update_fields)
    _log_archive_event(
        prop,
        'فایل به بایگانی منتقل شد',
        metadata={'action': 'archive', 'via_legacy_status': via_legacy_status},
    )
    return prop


def restore_property(user, prop: CRMProperty) -> CRMProperty:
    if not prop or prop.deleted_at:
        raise ValueError('ملک یافت نشد')
    if not can_edit_property(user, prop):
        raise PermissionError('امکان ویرایش این ملک را ندارید')
    if not is_property_archived(prop):
        return prop

    pre = (prop.pre_archive_transaction_status or '').strip()
    if prop.transaction_status == 'بایگانی':
        prop.transaction_status = pre or RESTORE_DEFAULT_TX_STATUS
    elif pre and prop.transaction_status not in PROPERTY_TX_STATUSES:
        prop.transaction_status = RESTORE_DEFAULT_TX_STATUS

    prop.archived_at = None
    prop.pre_archive_transaction_status = ''
    prop.save(update_fields=['archived_at', 'pre_archive_transaction_status', 'transaction_status', 'updated_at'])
    _log_archive_event(prop, 'فایل از بایگانی بازگردانی شد', metadata={'action': 'restore'})
    return prop


def bulk_archive_properties(user, property_ids, *, reason: str = '') -> Dict[str, int]:
    result = {'archived': 0, 'skipped': 0, 'errors': 0}
    for pid in _normalize_ids(property_ids):
        prop = property_for_user(user, pid)
        if not prop:
            result['skipped'] += 1
            continue
        try:
            with transaction.atomic():
                archive_property(user, prop, reason=reason)
            result['archived'] += 1
        except PermissionError:
            result['skipped'] += 1
        except ValueError:
            result['errors'] += 1
    return result


def bulk_restore_properties(user, property_ids) -> Dict[str, int]:
    result = {'restored': 0, 'skipped': 0, 'errors': 0}
    for pid in _normalize_ids(property_ids):
        prop = property_for_user(user, pid)
        if not prop:
            result['skipped'] += 1
            continue
        try:
            with transaction.atomic():
                restore_property(user, prop)
            result['restored'] += 1
        except PermissionError:
            result['skipped'] += 1
        except ValueError:
            result['errors'] += 1
    return result


def rental_reminder_suggestion(prop: CRMProperty) -> Tuple[bool, str]:
    """پیشنهاد تاریخ یادآور اجاره پس از بایگانی — بدون ایجاد یادآور."""
    if not is_property_archived(prop):
        return False, ''
    if prop.deal_mode not in ('رهن و اجاره', 'اجاره'):
        return False, ''
    import jdatetime

    today = timezone.now().date()
    j = jdatetime.date.fromgregorian(date=today)
    remind_month = j.month - 1 if j.month > 1 else 12
    remind_year = j.year + 1 if j.month > 1 else j.year
    if remind_month <= 6:
        max_day = 31
    elif remind_month <= 11:
        max_day = 30
    else:
        max_day = 30 if jdatetime.date(remind_year, 1, 1).isleap() else 29
    remind_day = min(j.day, max_day)
    remind_j = jdatetime.date(remind_year, remind_month, remind_day)
    suggested = f'{remind_j.year}/{remind_j.month:02d}/{remind_j.day:02d}'
    return True, suggested


def has_pending_rental_reminder(user, prop: CRMProperty) -> bool:
    from workspace.services.crm_property_rental_renewal import RENEWAL_REMINDER_KIND
    from workspace.models import Reminder

    return Reminder.objects.filter(
        user=user,
        property=prop,
        reminder_kind=RENEWAL_REMINDER_KIND,
        is_done=False,
    ).exists()
