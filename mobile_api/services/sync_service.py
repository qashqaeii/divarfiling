"""همگام‌سازی delta CRM."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from mobile_api.serializers import (
    activity_to_dict,
    contact_to_dict,
    deal_to_dict,
    property_to_dict,
    reminder_to_dict,
)
from workspace.models import CRMDeal, CRMProperty, CustomerActivity, Reminder
from workspace.services.crm_scope import customers_qs, properties_qs, reminders_qs

SYNC_ENTITIES = ('contacts', 'deals', 'properties', 'reminders', 'activities')


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    raw = since.strip()
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        dt = parse_datetime(raw)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _entity_batch(upserted: List[dict], deleted_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    return {
        'upserted': upserted,
        'deleted_ids': deleted_ids or [],
    }


def pull_sync(user, since: Optional[str], entities: List[str]) -> Dict[str, Any]:
    since_dt = _parse_since(since)
    requested = [e for e in entities if e in SYNC_ENTITIES] or ['contacts']
    result: Dict[str, Any] = {
        'server_time': timezone.now().isoformat(),
        'entities': requested,
    }

    if 'contacts' in requested:
        qs = customers_qs(user)
        if since_dt:
            qs = qs.filter(updated_at__gt=since_dt)
        result['contacts'] = _entity_batch([contact_to_dict(c) for c in qs[:500]])

    if 'deals' in requested:
        qs = CRMDeal.objects.filter(user=user).select_related('customer', 'property')
        if since_dt:
            qs = qs.filter(updated_at__gt=since_dt)
        result['deals'] = _entity_batch([deal_to_dict(d) for d in qs[:200]])

    if 'properties' in requested:
        qs = properties_qs(user)
        deleted_ids: List[int] = []
        if since_dt:
            deleted_ids = list(
                CRMProperty.objects.filter(
                    user=user,
                    deleted_at__isnull=False,
                    deleted_at__gte=since_dt,
                ).values_list('pk', flat=True)[:200]
            )
            qs = qs.filter(updated_at__gt=since_dt)
        result['properties'] = _entity_batch(
            [property_to_dict(p) for p in qs[:200]],
            deleted_ids=deleted_ids,
        )

    if 'reminders' in requested:
        qs = reminders_qs(user).select_related('customer')
        if since_dt:
            qs = qs.filter(
                models.Q(due_at__gte=since_dt) | models.Q(created_at__gte=since_dt),
            )
        result['reminders'] = _entity_batch([reminder_to_dict(r) for r in qs[:200]])

    if 'activities' in requested:
        qs = CustomerActivity.objects.filter(customer__user=user).select_related('customer')
        if since_dt:
            qs = qs.filter(created_at__gte=since_dt)
        result['activities'] = _entity_batch([activity_to_dict(a) for a in qs[:300]])

    return result


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

    mapped = []
    conflicts = []
    for op in operations:
        op_id = op.get('op_id', '')
        entity = op.get('entity', '')
        action = op.get('action', '')
        payload = op.get('payload') or {}
        try:
            if entity == 'contact' and action == 'create':
                c = create_quick_lead(user, payload)
                mapped.append({'op_id': op_id, 'server_id': c.pk})
            elif entity == 'contact' and action == 'update':
                contact_id = int(payload.get('contact_id') or payload.get('id') or 0)
                c = update_contact(user, contact_id, payload)
                if c:
                    mapped.append({'op_id': op_id, 'server_id': c.pk})
                else:
                    conflicts.append({'op_id': op_id, 'reason': 'not_found'})
            elif entity == 'activity' and action == 'create':
                contact_id = int(payload.get('contact_id') or payload.get('customer_id') or 0)
                activity = create_activity(user, contact_id, payload)
                mapped.append({'op_id': op_id, 'server_id': activity.pk})
            elif entity == 'note' and action == 'create':
                contact_id = int(payload.get('contact_id') or payload.get('customer_id') or 0)
                activity = create_note(user, contact_id, payload)
                mapped.append({'op_id': op_id, 'server_id': activity.pk})
            elif entity == 'reminder' and action == 'create':
                contact_id = int(payload.get('contact_id') or payload.get('customer_id') or 0)
                reminder = create_reminder(user, contact_id, payload)
                mapped.append({'op_id': op_id, 'server_id': reminder.pk})
            elif entity == 'reminder' and action == 'complete':
                reminder_id = int(payload.get('reminder_id') or payload.get('id') or 0)
                r = complete_reminder(user, reminder_id, note=payload.get('note', ''))
                if r:
                    mapped.append({'op_id': op_id, 'server_id': r.pk})
                else:
                    conflicts.append({'op_id': op_id, 'reason': 'not_found'})
            elif entity == 'reminder' and action == 'postpone':
                reminder_id = int(payload.get('reminder_id') or payload.get('id') or 0)
                days = int(payload.get('days', 1) or 1)
                r = postpone_reminder(user, reminder_id, days=days)
                if r:
                    mapped.append({'op_id': op_id, 'server_id': r.pk})
                else:
                    conflicts.append({'op_id': op_id, 'reason': 'not_found'})
            elif entity == 'deal' and action == 'create':
                deal = create_deal_from_mobile(user, payload)
                mapped.append({'op_id': op_id, 'server_id': deal.pk})
            else:
                conflicts.append({'op_id': op_id, 'reason': 'unsupported'})
        except Exception as exc:
            conflicts.append({'op_id': op_id, 'reason': str(exc)})
    return {'mapped': mapped, 'conflicts': conflicts}
