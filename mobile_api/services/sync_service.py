"""همگام‌سازی delta CRM."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from mobile_api.serializers import activity_to_dict, contact_to_dict, reminder_to_dict
from workspace.models import CRMDeal, CRMProperty, CustomerActivity, Reminder
from workspace.services.crm_scope import customers_qs, properties_qs, reminders_qs


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    dt = parse_datetime(since)
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def pull_sync(user, since: Optional[str], entities: List[str]) -> Dict[str, Any]:
    since_dt = _parse_since(since)
    result: Dict[str, Any] = {'server_time': timezone.now().isoformat()}

    if 'contacts' in entities:
        qs = customers_qs(user)
        if since_dt:
            qs = qs.filter(updated_at__gte=since_dt)
        result['contacts'] = {
            'upserted': [contact_to_dict(c) for c in qs[:500]],
            'deleted_ids': [],
        }

    if 'deals' in entities:
        qs = CRMDeal.objects.filter(user=user)
        if since_dt:
            qs = qs.filter(updated_at__gte=since_dt)
        result['deals'] = {'upserted': [_deal_dict(d) for d in qs[:200]], 'deleted_ids': []}

    if 'properties' in entities:
        qs = properties_qs(user)
        if since_dt:
            qs = qs.filter(updated_at__gte=since_dt)
        result['properties'] = {
            'upserted': [_property_dict(p) for p in qs[:200]],
            'deleted_ids': [],
        }

    if 'reminders' in entities:
        qs = reminders_qs(user)
        if since_dt:
            qs = qs.filter(due_at__gte=since_dt)
        result['reminders'] = {
            'upserted': [_reminder_sync_dict(r) for r in qs[:200]],
            'deleted_ids': [],
        }

    if 'activities' in entities:
        qs = CustomerActivity.objects.filter(customer__user=user)
        if since_dt:
            qs = qs.filter(created_at__gte=since_dt)
        result['activities'] = {
            'upserted': [_activity_dict(a) for a in qs[:300]],
            'deleted_ids': [],
        }

    return result


def push_sync(user, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    from mobile_api.services.crm_service import (
        complete_reminder,
        create_activity,
        create_note,
        create_quick_lead,
        create_reminder,
    )

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
            else:
                conflicts.append({'op_id': op_id, 'reason': 'unsupported'})
        except Exception as exc:
            conflicts.append({'op_id': op_id, 'reason': str(exc)})
    return {'mapped': mapped, 'conflicts': conflicts}


def _deal_dict(d: CRMDeal) -> dict:
    return {
        'id': d.pk,
        'title': d.title,
        'stage': d.stage,
        'amount': d.value,
        'updated_at': d.updated_at.isoformat() if d.updated_at else None,
    }


def _property_dict(p: CRMProperty) -> dict:
    return {
        'id': p.pk,
        'title': p.title,
        'transaction_status': p.transaction_status,
        'city': p.city,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }


def _reminder_sync_dict(r: Reminder) -> dict:
    return {
        'id': r.pk,
        'title': r.title,
        'contact_id': r.customer_id,
        'due_at': r.due_at.isoformat() if r.due_at else None,
        'done': r.is_done,
    }


def _activity_dict(a: CustomerActivity) -> dict:
    return activity_to_dict(a)
