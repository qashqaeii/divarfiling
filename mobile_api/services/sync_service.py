"""همگام‌سازی delta CRM — پروتکل صفحه‌بندی و Push idempotent."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from mobile_api.serializers import (
    activity_to_dict,
    contact_to_dict,
    deal_to_dict,
    property_to_dict,
    reminder_to_dict,
)
from mobile_api.services.sync_cursor import (
    SYNC_PROTOCOL_VERSION,
    SyncCursorError,
    decode_cursor,
    encode_cursor,
    keyset_filter,
    page_keyset,
    parse_cursor_dt,
)
from mobile_api.services.sync_push_fingerprint import push_operation_fingerprint
from mobile_api.services.sync_push_store import (
    get_cached_push_results,
    get_push_op,
    record_push_conflict,
    record_push_success,
    reserve_push_op,
)
from workspace.models import CRMDeal, CRMProperty, Customer, CustomerActivity, Reminder
from workspace.services.crm_contact_archive import archived_contacts_q
from workspace.services.crm_scope import customers_qs, deals_qs, properties_qs, reminders_qs

logger = logging.getLogger(__name__)

SYNC_ENTITIES = ('contacts', 'deals', 'properties', 'reminders', 'activities')

ENTITY_LIMITS = {
    'contacts': 500,
    'deals': 200,
    'properties': 200,
    'reminders': 200,
    'activities': 300,
}

MAX_PUSH_OPERATIONS = 50
MAX_OP_ID_LENGTH = 128


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    return parse_cursor_dt(since)


def _entity_batch(
    upserted: List[dict],
    deleted_ids: Optional[List[int]] = None,
    *,
    has_more: bool = False,
    cursor_piece: Optional[dict] = None,
) -> Dict[str, Any]:
    batch: Dict[str, Any] = {
        'upserted': upserted,
        'deleted_ids': deleted_ids or [],
    }
    if has_more:
        batch['has_more'] = True
    if cursor_piece:
        batch['cursor'] = cursor_piece
    return batch


def _empty_batch() -> Dict[str, Any]:
    return _entity_batch([], [])


def pull_sync(
    user,
    since: Optional[str],
    entities: List[str],
    *,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    requested = [e for e in entities if e in SYNC_ENTITIES] or ['contacts']
    state = decode_cursor(cursor, strict=bool(cursor and str(cursor).strip()))
    entity_cursors: Dict[str, Any] = dict(state.get('entities') or {})
    entity_done: Dict[str, bool] = dict(state.get('done') or {})
    since_watermark = (state.get('since_watermark') or '').strip()
    if state.get('session_started'):
        since_dt = _parse_since(since_watermark) if since_watermark else None
    else:
        since_dt = _parse_since(since) if since else None
        if since_dt is None and since:
            since_dt = _parse_since(since)
        if not since_watermark and since:
            since_watermark = since

    result: Dict[str, Any] = {
        'server_time': timezone.now().isoformat(),
        'entities': requested,
        'sync_protocol': SYNC_PROTOCOL_VERSION,
    }

    has_more_global = False
    next_entities: Dict[str, Any] = {}
    next_done: Dict[str, bool] = dict(entity_done)

    if 'contacts' in requested:
        batch, more, piece, done = _pull_contacts(user, since_dt, entity_cursors.get('contacts'), entity_done.get('contacts'))
        result['contacts'] = batch
        if more and piece:
            has_more_global = True
            next_entities['contacts'] = piece
            next_done['contacts'] = False
        else:
            next_done['contacts'] = True

    if 'deals' in requested:
        batch, more, piece, done = _pull_deals(user, since_dt, entity_cursors.get('deals'), entity_done.get('deals'))
        result['deals'] = batch
        if more and piece:
            has_more_global = True
            next_entities['deals'] = piece
            next_done['deals'] = False
        else:
            next_done['deals'] = True

    if 'properties' in requested:
        batch, more, piece, done = _pull_properties(
            user, since_dt, entity_cursors.get('properties'), entity_done.get('properties'),
        )
        result['properties'] = batch
        if more and piece:
            has_more_global = True
            next_entities['properties'] = piece
            next_done['properties'] = False
        else:
            next_done['properties'] = True

    if 'reminders' in requested:
        batch, more, piece, done = _pull_reminders(
            user, since_dt, entity_cursors.get('reminders'), entity_done.get('reminders'),
        )
        result['reminders'] = batch
        if more and piece:
            has_more_global = True
            next_entities['reminders'] = piece
            next_done['reminders'] = False
        else:
            next_done['reminders'] = True

    if 'activities' in requested:
        batch, more, piece, done = _pull_activities(
            user, since_dt, entity_cursors.get('activities'), entity_done.get('activities'),
        )
        result['activities'] = batch
        if more and piece:
            has_more_global = True
            next_entities['activities'] = piece
            next_done['activities'] = False
        else:
            next_done['activities'] = True

    result['has_more'] = has_more_global
    if has_more_global:
        result['next_cursor'] = encode_cursor({
            'session_started': True,
            'since_watermark': since_watermark or '',
            'entities': next_entities,
            'done': next_done,
        })

    return result


def _paginate_pk_list(qs, after_pk: int, limit: int) -> Tuple[List[int], bool, int]:
    q = qs.order_by('pk')
    if after_pk:
        q = q.filter(pk__gt=after_pk)
    rows = list(q.values_list('pk', flat=True)[: limit + 1])
    has_more = len(rows) > limit
    page = rows[:limit]
    next_after = page[-1] if page else after_pk
    return page, has_more, next_after


def _pull_contacts(user, since_dt, cursor_piece, done_flag) -> Tuple[Dict, bool, Optional[dict], bool]:
    if done_flag:
        return _empty_batch(), False, None, True
    limit = ENTITY_LIMITS['contacts']
    piece: Dict[str, Any] = dict(cursor_piece or {})
    upsert_done = bool(piece.get('upsert_done'))
    deleted_done = bool(piece.get('deleted_done', not since_dt))
    upserted: List[dict] = []
    deleted_ids: List[int] = []
    next_piece: Dict[str, Any] = {}
    has_more = False

    if not upsert_done:
        qs = customers_qs(user).exclude(archived_contacts_q()).order_by('updated_at', 'pk')
        upsert_cursor = piece.get('upsert')
        if upsert_cursor:
            qs = keyset_filter(qs, updated_field='updated_at', pk_field='pk', cursor_piece=upsert_cursor)
        elif since_dt:
            qs = qs.filter(updated_at__gt=since_dt)
        rows = list(qs[: limit + 1])
        page, upsert_more, upsert_next = page_keyset(rows, limit)
        upserted = [contact_to_dict(c) for c in page]
        if upsert_more and upsert_next:
            next_piece = {'upsert': upsert_next, 'upsert_done': False, 'deleted_done': deleted_done}
            if since_dt:
                next_piece['deleted_after_pk'] = piece.get('deleted_after_pk', 0)
            return (
                _entity_batch(upserted, [], has_more=True, cursor_piece=upsert_next),
                True,
                next_piece,
                False,
            )
        upsert_done = True
        piece['upsert_done'] = True
        piece.pop('upsert', None)

    if since_dt and not deleted_done:
        del_qs = (
            customers_qs(user)
            .filter(archived_contacts_q())
            .filter(models.Q(archived_at__gte=since_dt) | models.Q(updated_at__gt=since_dt))
        )
        after_pk = int(piece.get('deleted_after_pk') or 0)
        deleted_ids, del_more, after_pk = _paginate_pk_list(del_qs, after_pk, limit)
        if del_more:
            next_piece = {
                'upsert_done': True,
                'deleted_done': False,
                'deleted_after_pk': after_pk,
            }
            return (
                _entity_batch(upserted, deleted_ids, has_more=True),
                True,
                next_piece,
                False,
            )
        deleted_done = True

    entity_done = upsert_done and deleted_done
    return (
        _entity_batch(upserted, deleted_ids, has_more=False),
        False,
        None,
        entity_done,
    )


def _pull_deals(user, since_dt, cursor_piece, done_flag) -> Tuple[Dict, bool, Optional[dict], bool]:
    if done_flag:
        return _empty_batch(), False, None, True
    limit = ENTITY_LIMITS['deals']
    qs = deals_qs(user).select_related('customer', 'property').order_by('updated_at', 'pk')
    if cursor_piece:
        qs = keyset_filter(qs, updated_field='updated_at', pk_field='pk', cursor_piece=cursor_piece)
    elif since_dt:
        qs = qs.filter(updated_at__gt=since_dt)
    rows = list(qs[: limit + 1])
    page, has_more, next_piece = page_keyset(rows, limit)
    return (
        _entity_batch([deal_to_dict(d) for d in page], has_more=has_more, cursor_piece=next_piece),
        has_more,
        next_piece,
        not has_more,
    )


def _pull_properties(user, since_dt, cursor_piece, done_flag) -> Tuple[Dict, bool, Optional[dict], bool]:
    if done_flag:
        return _empty_batch(), False, None, True
    limit = ENTITY_LIMITS['properties']
    piece: Dict[str, Any] = dict(cursor_piece or {})
    upsert_done = bool(piece.get('upsert_done'))
    deleted_done = bool(piece.get('deleted_done', not since_dt))
    upserted: List[dict] = []
    deleted_ids: List[int] = []

    if not upsert_done:
        qs = properties_qs(user).order_by('updated_at', 'pk')
        upsert_cursor = piece.get('upsert')
        if upsert_cursor:
            qs = keyset_filter(qs, updated_field='updated_at', pk_field='pk', cursor_piece=upsert_cursor)
        elif since_dt:
            qs = qs.filter(updated_at__gt=since_dt)
        rows = list(qs[: limit + 1])
        page, upsert_more, upsert_next = page_keyset(rows, limit)
        upserted = [property_to_dict(p) for p in page]
        if upsert_more and upsert_next:
            next_piece = {
                'upsert': upsert_next,
                'upsert_done': False,
                'deleted_done': deleted_done,
                'deleted_after_pk': piece.get('deleted_after_pk', 0),
            }
            return (
                _entity_batch(upserted, [], has_more=True, cursor_piece=upsert_next),
                True,
                next_piece,
                False,
            )
        upsert_done = True

    if since_dt and not deleted_done:
        from workspace.services.crm_scope import _shared_property_ids, get_membership

        m = get_membership(user)
        scope = models.Q(user=user)
        if m:
            shared = _shared_property_ids(user, m.agency)
            if shared:
                scope |= models.Q(pk__in=shared)
        del_qs = CRMProperty.objects.filter(scope).filter(
            deleted_at__isnull=False,
            deleted_at__gte=since_dt,
        )
        after_pk = int(piece.get('deleted_after_pk') or 0)
        deleted_ids, del_more, after_pk = _paginate_pk_list(del_qs, after_pk, limit)
        if del_more:
            next_piece = {'upsert_done': True, 'deleted_done': False, 'deleted_after_pk': after_pk}
            return (
                _entity_batch(upserted, deleted_ids, has_more=True),
                True,
                next_piece,
                False,
            )
        deleted_done = True

    return (
        _entity_batch(upserted, deleted_ids, has_more=False),
        False,
        None,
        upsert_done and deleted_done,
    )


def _pull_reminders(user, since_dt, cursor_piece, done_flag) -> Tuple[Dict, bool, Optional[dict], bool]:
    if done_flag:
        return _empty_batch(), False, None, True
    limit = ENTITY_LIMITS['reminders']
    qs = reminders_qs(user).select_related('customer').order_by('due_at', 'pk')
    if cursor_piece:
        qs = keyset_filter(qs, updated_field='due_at', pk_field='pk', cursor_piece=cursor_piece)
    elif since_dt:
        qs = qs.filter(
            models.Q(due_at__gte=since_dt) | models.Q(created_at__gte=since_dt),
        )
    rows = list(qs[: limit + 1])
    page, has_more, next_piece = page_keyset(rows, limit, updated_attr='due_at', pk_attr='pk')
    return (
        _entity_batch([reminder_to_dict(r) for r in page], has_more=has_more, cursor_piece=next_piece),
        has_more,
        next_piece,
        not has_more,
    )


def _pull_activities(user, since_dt, cursor_piece, done_flag) -> Tuple[Dict, bool, Optional[dict], bool]:
    if done_flag:
        return _empty_batch(), False, None, True
    limit = ENTITY_LIMITS['activities']
    accessible_customers = customers_qs(user).values_list('pk', flat=True)
    qs = (
        CustomerActivity.objects.filter(customer_id__in=accessible_customers)
        .select_related('customer')
        .order_by('created_at', 'pk')
    )
    if cursor_piece:
        qs = keyset_filter(qs, updated_field='created_at', pk_field='pk', cursor_piece=cursor_piece)
    elif since_dt:
        qs = qs.filter(created_at__gte=since_dt)
    rows = list(qs[: limit + 1])
    page, has_more, next_piece = page_keyset(rows, limit, updated_attr='created_at', pk_attr='pk')
    return (
        _entity_batch([activity_to_dict(a) for a in page], has_more=has_more, cursor_piece=next_piece),
        has_more,
        next_piece,
        not has_more,
    )


def _fingerprint_mismatch_cached(rec, fingerprint: str) -> bool:
    if not fingerprint:
        return False
    stored = (getattr(rec, 'payload_fingerprint', None) or '').strip()
    return bool(stored and stored != fingerprint)


def _sanitize_push_error(exc: Exception) -> str:
    if isinstance(exc, (ValueError, PermissionError)):
        msg = str(exc).strip()
        if msg and len(msg) < 200:
            return msg
    return 'operation_failed'


def push_sync(user, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    from mobile_api.services.crm_service import (
        complete_reminder,
        create_activity,
        create_note,
        create_quick_lead,
        create_reminder,
        postpone_reminder,
        update_contact,
    )
    from mobile_api.services.deals_service import create_deal_from_mobile

    if not isinstance(operations, list):
        return {'mapped': [], 'conflicts': [{'op_id': '', 'reason': 'invalid_payload'}]}

    if len(operations) > MAX_PUSH_OPERATIONS:
        return {
            'mapped': [],
            'conflicts': [{'op_id': '', 'reason': 'too_many_operations'}],
        }

    op_ids = [str(op.get('op_id') or '')[:MAX_OP_ID_LENGTH] for op in operations if op.get('op_id')]
    cached = get_cached_push_results(user, op_ids)

    mapped = []
    conflicts = []
    for op in operations:
        op_id = str(op.get('op_id') or '').strip()[:MAX_OP_ID_LENGTH]
        entity = str(op.get('entity') or '').strip()
        action = str(op.get('action') or '').strip()
        payload = op.get('payload') or {}
        if not isinstance(payload, dict):
            conflicts.append({'op_id': op_id, 'reason': 'invalid_payload'})
            continue

        fingerprint = push_operation_fingerprint(op) if op_id else ''

        if op_id and op_id in cached:
            rec = cached[op_id]
            if rec.status == rec.STATUS_OK and rec.server_id:
                if _fingerprint_mismatch_cached(rec, fingerprint):
                    conflicts.append({'op_id': op_id, 'reason': 'payload_mismatch'})
                    continue
                mapped.append({'op_id': op_id, 'server_id': rec.server_id})
                continue
            if rec.status == rec.STATUS_CONFLICT:
                conflicts.append({'op_id': op_id, 'reason': rec.conflict_reason or 'conflict'})
                continue
            if rec.status == rec.STATUS_PROCESSING:
                conflicts.append({'op_id': op_id, 'reason': 'in_progress'})
                continue

        if op_id:
            slot = reserve_push_op(user, op_id, entity, fingerprint=fingerprint)
            if slot == 'replay_ok':
                rec = get_push_op(user, op_id)
                if rec and rec.server_id:
                    mapped.append({'op_id': op_id, 'server_id': rec.server_id})
                continue
            if slot == 'replay_conflict':
                rec = get_push_op(user, op_id)
                conflicts.append({'op_id': op_id, 'reason': (rec.conflict_reason if rec else '') or 'conflict'})
                continue
            if slot == 'payload_mismatch':
                conflicts.append({'op_id': op_id, 'reason': 'payload_mismatch'})
                record_push_conflict(user, op_id, entity=entity, reason='payload_mismatch', fingerprint=fingerprint)
                continue
            if slot == 'in_progress':
                conflicts.append({'op_id': op_id, 'reason': 'in_progress'})
                continue

        try:
            with transaction.atomic():
                if entity == 'contact' and action == 'create':
                    c = create_quick_lead(user, payload)
                    mapped.append({'op_id': op_id, 'server_id': c.pk})
                    record_push_success(user, op_id, entity='contact', server_id=c.pk, fingerprint=fingerprint)
                elif entity == 'contact' and action == 'update':
                    contact_id = int(payload.get('contact_id') or payload.get('id') or 0)
                    c = update_contact(user, contact_id, payload)
                    if c:
                        mapped.append({'op_id': op_id, 'server_id': c.pk})
                        record_push_success(user, op_id, entity='contact', server_id=c.pk, fingerprint=fingerprint)
                    else:
                        conflicts.append({'op_id': op_id, 'reason': 'not_found'})
                        record_push_conflict(user, op_id, entity='contact', reason='not_found', fingerprint=fingerprint)
                elif entity == 'activity' and action == 'create':
                    contact_id = int(payload.get('contact_id') or payload.get('customer_id') or 0)
                    activity = create_activity(user, contact_id, payload)
                    mapped.append({'op_id': op_id, 'server_id': activity.pk})
                    record_push_success(user, op_id, entity='activity', server_id=activity.pk, fingerprint=fingerprint)
                elif entity == 'note' and action == 'create':
                    contact_id = int(payload.get('contact_id') or payload.get('customer_id') or 0)
                    activity = create_note(user, contact_id, payload)
                    mapped.append({'op_id': op_id, 'server_id': activity.pk})
                    record_push_success(user, op_id, entity='note', server_id=activity.pk, fingerprint=fingerprint)
                elif entity == 'reminder' and action == 'create':
                    contact_id = int(payload.get('contact_id') or payload.get('customer_id') or 0)
                    reminder = create_reminder(user, contact_id, payload)
                    mapped.append({'op_id': op_id, 'server_id': reminder.pk})
                    record_push_success(user, op_id, entity='reminder', server_id=reminder.pk, fingerprint=fingerprint)
                elif entity == 'reminder' and action == 'complete':
                    reminder_id = int(payload.get('reminder_id') or payload.get('id') or 0)
                    r = complete_reminder(user, reminder_id, note=payload.get('note', ''))
                    if r:
                        mapped.append({'op_id': op_id, 'server_id': r.pk})
                        record_push_success(user, op_id, entity='reminder', server_id=r.pk, fingerprint=fingerprint)
                    else:
                        conflicts.append({'op_id': op_id, 'reason': 'not_found'})
                        record_push_conflict(user, op_id, entity='reminder', reason='not_found', fingerprint=fingerprint)
                elif entity == 'reminder' and action == 'postpone':
                    reminder_id = int(payload.get('reminder_id') or payload.get('id') or 0)
                    days = int(payload.get('days', 1) or 1)
                    r = postpone_reminder(user, reminder_id, days=days)
                    if r:
                        mapped.append({'op_id': op_id, 'server_id': r.pk})
                        record_push_success(user, op_id, entity='reminder', server_id=r.pk, fingerprint=fingerprint)
                    else:
                        conflicts.append({'op_id': op_id, 'reason': 'not_found'})
                        record_push_conflict(user, op_id, entity='reminder', reason='not_found', fingerprint=fingerprint)
                elif entity == 'deal' and action == 'create':
                    deal = create_deal_from_mobile(user, payload)
                    mapped.append({'op_id': op_id, 'server_id': deal.pk})
                    record_push_success(user, op_id, entity='deal', server_id=deal.pk, fingerprint=fingerprint)
                else:
                    conflicts.append({'op_id': op_id, 'reason': 'unsupported'})
                    record_push_conflict(user, op_id, entity=entity, reason='unsupported', fingerprint=fingerprint)
        except Exception as exc:
            reason = _sanitize_push_error(exc)
            conflicts.append({'op_id': op_id, 'reason': reason})
            record_push_conflict(user, op_id, entity=entity, reason=reason, fingerprint=fingerprint)
            logger.info('sync push op failed user=%s op_id=%s', user.pk, op_id, exc_info=exc)
    return {'mapped': mapped, 'conflicts': conflicts}
