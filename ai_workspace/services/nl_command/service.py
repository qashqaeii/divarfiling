"""Orchestration parse / confirm / resolve-contact برای nl_command."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from django.urls import reverse
from django.utils import timezone

from ai_workspace.constants import (
    FEATURE_NL_COMMAND,
    NL_COMMAND_INTENT_CREATE_REMINDER,
    NL_COMMAND_INTENT_UNKNOWN,
    NL_COMMAND_UNKNOWN_MESSAGE,
    nl_command_contact_not_found_message,
    resolve_model_label,
)
from ai_workspace.services.gateway import FeatureDisabledError, GatewayResult, run as gateway_run
from ai_workspace.services.nl_command.contacts import resolve_contact_by_name
from ai_workspace.services.nl_command.datetime_parser import format_due_display, parse_due_datetime
from ai_workspace.services.nl_command.state import delete_state, load_state, new_command_id, save_state, text_hash
from ai_workspace.services.payload import is_valid_payload
from ai_workspace.services.quota import QuotaExceededError
from mobile_api.services.crm_service import create_reminder, create_standalone_reminder
from workspace.services.crm_scope import customer_for_user
from workspace.services.jalali_input import format_jalali_today_label

logger = logging.getLogger(__name__)


class NLCommandError(Exception):
    def __init__(self, message: str, code: str = 'error', status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _ai_response_meta(result: GatewayResult) -> Dict[str, Any]:
    if result.from_cache or result.provider == 'cache':
        return {
            'model_label': 'پاسخ از کش',
            'provider': 'cache',
            'cached': True,
        }
    label = resolve_model_label(
        provider=result.provider,
        model=result.model,
        is_fallback=result.is_fallback,
        source='fallback' if result.is_fallback or result.provider == 'rule_based' else 'ai',
    )
    return {
        'model_label': label or (result.model or '').strip() or 'مدل ابری',
        'provider': result.provider,
        'cached': False,
    }


def _default_title(contact_name: Optional[str], note: Optional[str]) -> str:
    if contact_name:
        return f'تماس با {contact_name}'
    if note:
        return note[:80]
    return 'یادآوری'


def _build_llm_context(user_text: str, tz_name: str) -> Dict[str, Any]:
    now_local = timezone.localtime(timezone.now())
    return {
        'user_text': user_text.strip()[:500],
        'timezone': tz_name,
        'now_local_display': format_jalali_today_label() + ' ' + now_local.strftime('%H:%M'),
        'content_version': 'v1',
    }


def parse_command(
    user,
    *,
    text: str,
    locale: str = 'fa-IR',
    tz_name: str = 'Asia/Tehran',
) -> Dict[str, Any]:
    user_text = (text or '').strip()
    if not user_text:
        raise NLCommandError('متن فرمان خالی است.', code='empty_text')

    entity_id = hashlib.sha256(user_text.encode('utf-8')).hexdigest()[:32]
    try:
        result = gateway_run(
            FEATURE_NL_COMMAND,
            user,
            context=_build_llm_context(user_text, tz_name),
            entity_type='nl_parse',
            entity_id=entity_id,
        )
    except FeatureDisabledError as exc:
        raise NLCommandError(str(exc), code='feature_disabled', status=403) from exc
    except QuotaExceededError as exc:
        raise NLCommandError(str(exc), code=exc.code, status=429) from exc

    data = result.data
    if not is_valid_payload(FEATURE_NL_COMMAND, data):
        logger.warning(
            'nl_command_parse_invalid user_id=%s entity_id=%s status=%s',
            user.pk,
            entity_id,
            result.status,
        )
        raise NLCommandError(
            'درک فرمان ممکن نشد. لطفاً دوباره یا با فرم یادآور ثبت کنید.',
            code='parse_failed',
            status=503,
        )

    intent = data.get('intent')
    ai_meta = _ai_response_meta(result)

    if intent == NL_COMMAND_INTENT_UNKNOWN:
        return {
            'ok': True,
            'intent': NL_COMMAND_INTENT_UNKNOWN,
            'can_confirm': False,
            'message': NL_COMMAND_UNKNOWN_MESSAGE,
            'ai': ai_meta,
        }

    if intent != NL_COMMAND_INTENT_CREATE_REMINDER:
        return {
            'ok': True,
            'intent': NL_COMMAND_INTENT_UNKNOWN,
            'can_confirm': False,
            'message': NL_COMMAND_UNKNOWN_MESSAGE,
            'ai': ai_meta,
        }

    inner = data.get('data') or {}
    contact_name = inner.get('contact_name')
    title = (inner.get('title') or '').strip() or _default_title(contact_name, inner.get('note'))
    note = (inner.get('note') or '').strip()
    date_text = inner.get('date_text')
    time_text = inner.get('time_text')

    missing_fields = list(data.get('missing_fields') or [])
    ambiguous_fields = list(data.get('ambiguous_fields') or [])

    due_at, dt_error = parse_due_datetime(
        date_text=date_text,
        time_text=time_text,
        tz_name=tz_name,
    )
    if dt_error == 'invalid_date':
        missing_fields.append('date_text')
    elif dt_error == 'invalid_time':
        missing_fields.append('time_text')
    elif dt_error == 'past_datetime':
        ambiguous_fields.append('due_at')

    contact_id, candidates, amb = resolve_contact_by_name(user, contact_name)
    if amb == 'multiple':
        ambiguous_fields.append('contact_name')
    elif amb == 'none' and contact_name:
        ambiguous_fields.append('contact_name')

    can_confirm = (
        bool(due_at)
        and not missing_fields
        and 'contact_name' not in ambiguous_fields
        and amb != 'multiple'
    )

    command_id = new_command_id()
    preview = {
        'contact_name': contact_name or '',
        'title': title,
        'note': note,
        'due_at_display': format_due_display(due_at, tz_name) if due_at else '',
        'date_text': date_text or '',
        'time_text': time_text or '',
    }
    state = {
        'intent': NL_COMMAND_INTENT_CREATE_REMINDER,
        'validated': {
            'title': title,
            'note': note,
            'due_at': due_at.isoformat() if due_at else None,
            'contact_id': contact_id,
            'contact_name': contact_name,
        },
        'preview': preview,
        'missing_fields': missing_fields,
        'ambiguous_fields': ambiguous_fields,
        'contact_candidates': candidates,
        'input_hash': text_hash(user_text),
        'locale': locale,
        'timezone': tz_name,
        'created_reminder_id': None,
    }
    save_state(user.pk, command_id, state)

    response: Dict[str, Any] = {
        'ok': True,
        'command_id': command_id,
        'intent': NL_COMMAND_INTENT_CREATE_REMINDER,
        'preview': preview,
        'missing_fields': missing_fields,
        'ambiguous_fields': ambiguous_fields,
        'can_confirm': can_confirm,
        'ai': ai_meta,
    }
    if candidates and amb == 'multiple':
        response['contact_candidates'] = candidates
    if amb == 'none' and contact_name:
        response['message'] = nl_command_contact_not_found_message(contact_name)
    return response


def resolve_contact(user, command_id: str, contact_id: int) -> Dict[str, Any]:
    state = load_state(user.pk, command_id)
    if not state:
        raise NLCommandError('فرمان منقضی شده یا یافت نشد.', code='expired', status=404)

    customer = customer_for_user(user, int(contact_id))
    if not customer:
        raise NLCommandError('مخاطب یافت نشد.', code='contact_not_found', status=404)

    validated = dict(state.get('validated') or {})
    validated['contact_id'] = customer.pk
    validated['contact_name'] = customer.name
    preview = dict(state.get('preview') or {})
    preview['contact_name'] = customer.name

    missing = list(state.get('missing_fields') or [])
    ambiguous = [f for f in (state.get('ambiguous_fields') or []) if f != 'contact_name']
    due_ok = bool(validated.get('due_at'))
    can_confirm = due_ok and not missing and not ambiguous

    state['validated'] = validated
    state['preview'] = preview
    state['ambiguous_fields'] = ambiguous
    state['contact_candidates'] = []
    save_state(user.pk, command_id, state)

    return {
        'ok': True,
        'command_id': command_id,
        'preview': preview,
        'missing_fields': missing,
        'ambiguous_fields': ambiguous,
        'can_confirm': can_confirm,
    }


def confirm_command(user, command_id: str) -> Dict[str, Any]:
    state = load_state(user.pk, command_id)
    if not state:
        raise NLCommandError('فرمان منقضی شده یا یافت نشد.', code='expired', status=404)

    existing_id = state.get('created_reminder_id')
    if existing_id:
        url = reverse('workspace:crm_reminders')
        return {
            'ok': True,
            'entity_type': 'reminder',
            'entity_id': existing_id,
            'url': url,
            'duplicate': True,
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
    }
