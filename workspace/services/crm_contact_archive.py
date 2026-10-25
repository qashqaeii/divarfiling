"""بایگانی و بازگردانی مخاطبین CRM — منبع حقیقت: ``archived_at``."""
from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from workspace.constants import CRM_STATUSES
from workspace.models import Customer, Reminder
from workspace.services.crm import log_activity
from workspace.services.crm_scope import can_edit_customer, customer_for_user

ARCHIVE_SCOPE_ACTIVE = 'active'
ARCHIVE_SCOPE_ARCHIVED = 'archived'
ARCHIVE_SCOPE_ALL = 'all'

BULK_CONTACT_ARCHIVE_LIMIT = 100
CONTACT_REACTIVATION_REMINDER_KIND = 'contact_reactivate'
CONTACT_REACTIVATION_REMINDER_TITLE = 'بازبینی مخاطب بایگانی‌شده'

ARCHIVE_REASON_CHOICES = (
    'معامله انجام شد',
    'عدم نیاز فعلی',
    'پیگیری در آینده',
    'سایر',
)

COMMUNICATION_STATUSES = tuple(s for s in CRM_STATUSES if s != 'بایگانی')


def archived_contacts_q() -> Q:
    return Q(archived_at__isnull=False) | Q(status='بایگانی')


def is_contact_archived(customer: Customer) -> bool:
    if not customer:
        return False
    if customer.archived_at:
        return True
    return customer.status == 'بایگانی'


def contact_last_communication_status(customer: Customer) -> str:
    """وضعیت ارتباط واقعی برای نمایش — برای legacy بایگانی خالی."""
    if not is_contact_archived(customer):
        return customer.status or ''
    status = (customer.status or '').strip()
    if status == 'بایگانی':
        return ''
    return status


def contact_display_status(customer: Customer) -> str:
    if is_contact_archived(customer):
        return 'بایگانی‌شده'
    return customer.status or ''


def apply_contact_archive_scope(qs: QuerySet, params: dict) -> QuerySet:
    scope = (params.get('archive_scope') or params.get('contact_scope') or '').strip().lower()
    status = (params.get('status') or '').strip()

    if status == 'بایگانی':
        return qs.filter(archived_contacts_q())

    scope_includes_archived = scope in (ARCHIVE_SCOPE_ARCHIVED, 'بایگانی', ARCHIVE_SCOPE_ALL)
    if status and status != 'بایگانی' and not scope_includes_archived:
        qs = qs.exclude(archived_contacts_q())

    if scope in ('', ARCHIVE_SCOPE_ACTIVE, 'current', 'جاری'):
        return qs.exclude(archived_contacts_q())
    if scope in (ARCHIVE_SCOPE_ARCHIVED, 'بایگانی'):
        return qs.filter(archived_contacts_q())
    if scope == ARCHIVE_SCOPE_ALL:
        return qs
    return qs.exclude(archived_contacts_q())


def _normalize_ids(contact_ids) -> List[int]:
    ids: List[int] = []
    seen = set()
    for raw in contact_ids or []:
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
        if len(ids) >= BULK_CONTACT_ARCHIVE_LIMIT:
            break
    return ids


def open_reminders_count(user, customer: Customer) -> int:
    return Reminder.objects.filter(user=user, customer=customer, is_done=False).count()


def lease_deadline_reactivation_suggestion(customer: Customer) -> Tuple[bool, str]:
    """یک ماه تقویمی جلالی قبل از ``lease_deadline`` — فقط پیشنهاد."""
    if not customer.lease_deadline:
        return False, ''
    import jdatetime

    j = jdatetime.date.fromgregorian(date=customer.lease_deadline)
    month = j.month - 1 if j.month > 1 else 12
    year = j.year - 1 if j.month == 1 else j.year
    if month <= 6:
        max_day = 31
    elif month <= 11:
        max_day = 30
    else:
        max_day = 30 if jdatetime.date(year, 1, 1).isleap() else 29
    day = min(j.day, max_day)
    remind_j = jdatetime.date(year, month, day)
    return True, f'{remind_j.year}/{remind_j.month:02d}/{remind_j.day:02d}'


def _log_archive_event(
    customer: Customer,
    content: str,
    *,
    metadata: Optional[dict] = None,
) -> None:
    meta = {'customer_id': customer.pk}
    if metadata:
        meta.update(metadata)
    log_activity(
        customer,
        'تغییر وضعیت',
        content=content,
        title='بایگانی مخاطب',
        metadata=meta,
    )


def _parse_reactivation_due_jalali(due_jalali: str):
    raw = (due_jalali or '').strip()
    if not raw:
        return None
    from workspace.services.jalali_input import parse_jalali_date_string

    due_date = parse_jalali_date_string(raw)
    if not due_date:
        raise ValueError('تاریخ پیگیری مجدد نامعتبر است.')
    return due_date


def _maybe_create_reactivation_reminder(
    user,
    customer: Customer,
    *,
    due_jalali: str = '',
    note: str = '',
    due_date=None,
) -> Optional[Reminder]:
    if due_date is None:
        due_date = _parse_reactivation_due_jalali(due_jalali)
    if not due_date:
        return None
    raw = (due_jalali or '').strip()
    exists = Reminder.objects.filter(
        user=user,
        customer=customer,
        reminder_kind=CONTACT_REACTIVATION_REMINDER_KIND,
        is_done=False,
    ).exists()
    if exists:
        return None
    due_at = timezone.make_aware(datetime.combine(due_date, time(hour=9, minute=0)))
    reminder = Reminder.objects.create(
        user=user,
        customer=customer,
        title=CONTACT_REACTIVATION_REMINDER_TITLE,
        note=(note or '').strip()[:500],
        due_at=due_at,
        reminder_kind=CONTACT_REACTIVATION_REMINDER_KIND,
    )
    log_activity(
        customer,
        'یادآور',
        content=f'یادآور بازبینی پس از بایگانی — {raw}',
        title=CONTACT_REACTIVATION_REMINDER_TITLE,
        metadata={'reminder_id': reminder.pk, 'action': 'archive_reactivation'},
    )
    return reminder


def archive_contact(
    user,
    customer: Customer,
    *,
    reason: str = '',
    archive_note: str = '',
    reactivation_due_jalali: str = '',
    via_legacy_status: bool = False,
) -> Customer:
    if not customer:
        raise ValueError('مخاطب یافت نشد')
    if not can_edit_customer(user, customer):
        raise PermissionError('امکان ویرایش این مخاطب را ندارید')
    if is_contact_archived(customer):
        return customer

    reactivation_due = _parse_reactivation_due_jalali(reactivation_due_jalali)

    with transaction.atomic():
        customer.archived_at = timezone.now()
        customer.archive_reason = (reason or '').strip()[:500]
        customer.save(update_fields=['archived_at', 'archive_reason', 'updated_at'])

        meta = {
            'action': 'archive',
            'via_legacy_status': via_legacy_status,
            'reason': customer.archive_reason,
        }
        if archive_note:
            meta['archive_note'] = archive_note.strip()[:500]
        content = 'مخاطب به بایگانی منتقل شد.'
        if customer.archive_reason:
            content += f' دلیل: {customer.archive_reason}.'
        if archive_note:
            content += f' یادداشت: {archive_note.strip()[:200]}'
        _log_archive_event(customer, content, metadata=meta)

        if reactivation_due:
            _maybe_create_reactivation_reminder(
                user,
                customer,
                due_jalali=reactivation_due_jalali,
                note=archive_note,
                due_date=reactivation_due,
            )
    return customer


def restore_contact(
    user,
    customer: Customer,
    *,
    restore_status: str = '',
) -> Customer:
    if not customer:
        raise ValueError('مخاطب یافت نشد')
    if not can_edit_customer(user, customer):
        raise PermissionError('امکان ویرایش این مخاطب را ندارید')
    if not is_contact_archived(customer):
        return customer

    new_status = (restore_status or '').strip()
    if (customer.status or '').strip() == 'بایگانی':
        if new_status not in COMMUNICATION_STATUSES:
            raise ValueError('انتخاب مرحله ارتباط برای بازگردانی الزامی است.')
        customer.status = new_status

    customer.archived_at = None
    customer.archive_reason = ''
    customer.save(update_fields=['archived_at', 'archive_reason', 'status', 'updated_at'])
    _log_archive_event(
        customer,
        'مخاطب از بایگانی بازگردانی شد.',
        metadata={'action': 'restore', 'status': customer.status},
    )
    return customer


def bulk_archive_contacts(
    user,
    contact_ids,
    *,
    reason: str = '',
) -> Dict[str, int]:
    result = {'archived': 0, 'skipped': 0, 'errors': 0}
    for cid in _normalize_ids(contact_ids):
        customer = customer_for_user(user, cid)
        if not customer:
            result['skipped'] += 1
            continue
        try:
            with transaction.atomic():
                archive_contact(user, customer, reason=reason)
            result['archived'] += 1
        except PermissionError:
            result['skipped'] += 1
        except ValueError:
            result['errors'] += 1
    return result


def bulk_restore_contacts(
    user,
    contact_ids,
    *,
    restore_status: str = '',
) -> Dict[str, int]:
    result = {'restored': 0, 'skipped': 0, 'errors': 0}
    for cid in _normalize_ids(contact_ids):
        customer = customer_for_user(user, cid)
        if not customer:
            result['skipped'] += 1
            continue
        if not is_contact_archived(customer):
            result['skipped'] += 1
            continue
        try:
            with transaction.atomic():
                restore_contact(user, customer, restore_status=restore_status)
            result['restored'] += 1
        except PermissionError:
            result['skipped'] += 1
        except ValueError:
            result['errors'] += 1
    return result
