"""اجرای confirm برای create_reminder."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from django.urls import reverse
from django.utils import timezone

from ai_workspace.constants import nl_command_contact_not_found_message
from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.state import save_state
from mobile_api.services.crm_service import create_reminder, create_standalone_reminder
from workspace.services.crm_scope import customer_for_user


def confirm_create_reminder(user, command_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    existing_id = state.get('created_reminder_id')
    if existing_id:
        url = reverse('workspace:crm_reminders')
        return {
            'ok': True,
            'entity_type': 'reminder',
            'entity_id': existing_id,
            'url': url,
            'duplicate': True,
            'message': 'یادآوری قبلاً ثبت شده است.',
        }

    validated = state.get('validated') or {}
    due_raw = validated.get('due_at')
    if not due_raw:
        raise NLCommandError('زمان یادآوری مشخص نیست.', code='missing_due_at')
    due_at = datetime.fromisoformat(due_raw)
    if timezone.is_naive(due_at):
        due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
    now = timezone.now()
    if due_at <= now:
        raise NLCommandError('زمان یادآوری در گذشته است.', code='past_datetime')

    contact_name_requested = (validated.get('contact_name') or '').strip()
    contact_id = validated.get('contact_id')

    if contact_name_requested and not contact_id:
        raise NLCommandError(
            nl_command_contact_not_found_message(contact_name_requested),
            code='contact_not_found',
        )

    payload = {
        'title': validated.get('title') or 'یادآوری',
        'note': validated.get('note') or '',
        'due_at': due_at.isoformat(),
    }

    if contact_id:
        customer = customer_for_user(user, int(contact_id))
        if not customer:
            raise NLCommandError('مخاطب در دسترس نیست.', code='contact_scope')
        reminder = create_reminder(user, int(contact_id), payload)
    else:
        reminder = create_standalone_reminder(user, payload)
    state['created_reminder_id'] = reminder.pk
    save_state(user.pk, command_id, state)

    url = reverse('workspace:crm_reminders')
    return {
        'ok': True,
        'entity_type': 'reminder',
        'entity_id': reminder.pk,
        'url': url,
        'message': 'یادآوری با موفقیت ثبت شد.',
    }
