"""Orchestration parse / confirm / resolve-contact برای nl_command."""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

from django.urls import reverse

from ai_workspace.constants import (
    FEATURE_NL_COMMAND,
    NL_COMMAND_EXAMPLE_PHRASES,
    NL_COMMAND_INTENT_CREATE_CONTACT,
    NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
    NL_COMMAND_INTENT_CREATE_REMINDER,
    NL_COMMAND_INTENT_UNKNOWN,
    NL_COMMAND_PARSE_FAILED_MESSAGE,
    NL_COMMAND_UNKNOWN_MESSAGE,
    nl_command_contact_not_found_message,
    resolve_model_label,
)
from ai_workspace.services.gateway import FeatureDisabledError, GatewayResult, run as gateway_run
from ai_workspace.services.nl_command.contacts import resolve_contact_by_name
from ai_workspace.services.nl_command.datetime_parser import format_due_display, parse_due_datetime
from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.executors.contact import check_phone_duplicate, confirm_create_contact
from ai_workspace.services.nl_command.executors.property import confirm_create_personal_property
from ai_workspace.services.nl_command.executors.reminder import confirm_create_reminder
from ai_workspace.services.nl_command.preview import (
    build_contact_preview,
    build_property_preview,
    existing_contact_payload,
)
from ai_workspace.services.nl_command.state import load_state, new_command_id, save_state, text_hash
from ai_workspace.services.nl_command.validators import (
    hint_for_incomplete_contact,
    inner_from_validated,
    validate_contact_parse,
)
from ai_workspace.services.nl_command.validators_property import (
    hint_for_incomplete_property,
    validate_property_parse,
    validated_as_llm_shape,
)
from ai_workspace.services.payload import is_valid_payload
from ai_workspace.services.quota import QuotaExceededError
from workspace.services.crm_scope import customer_for_user
from workspace.services.jalali_input import format_jalali_today_label
from django.utils import timezone

logger = logging.getLogger(__name__)

# re-export for backward-compatible imports
__all__ = ['NLCommandError', 'parse_command', 'confirm_command', 'resolve_contact']


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


def _unknown_parse_response(ai_meta: Dict[str, Any], *, entity_id: str, user_id: int) -> Dict[str, Any]:
    logger.info(
        'nl_command_unsupported user_id=%s intent=unknown status=unsupported entity_id=%s',
        user_id,
        entity_id,
    )
    return {
        'ok': True,
        'intent': NL_COMMAND_INTENT_UNKNOWN,
        'can_confirm': False,
        'command_id': None,
        'preview': None,
        'missing_fields': [],
        'ambiguous_fields': [],
        'message': NL_COMMAND_UNKNOWN_MESSAGE,
        'examples': list(NL_COMMAND_EXAMPLE_PHRASES),
        'ai': ai_meta,
    }


def _hint_for_incomplete_reminder(
    *,
    missing_fields: list,
    ambiguous_fields: list,
    contact_ambiguity: str,
) -> str:
    if 'due_at' in ambiguous_fields:
        return 'زمان یادآوری در گذشته است یا نامعتبر است.'
    if contact_ambiguity == 'multiple' or 'contact_name' in ambiguous_fields:
        return 'چند مخاطب با این نام پیدا شد؛ یکی را انتخاب کنید.'
    if 'date_text' in missing_fields or 'time_text' in missing_fields:
        return 'زمان یادآوری را مشخص کنید (مثلاً فردا ساعت ۱۰).'
    if contact_ambiguity == 'none':
        return 'مخاطب پیدا نشد؛ نام را اصلاح کنید یا بدون مخاطب بنویسید.'
    if missing_fields:
        return 'برخی اطلاعات یادآوری کامل نیست.'
    return 'برای ثبت، اطلاعات را کامل‌تر بنویسید.'


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
        'content_version': 'v3',
    }


def _merge_property_validated(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, value in new.items():
        if value is None or value == '':
            continue
        merged[key] = value
    return merged


def _merge_contact_validated(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    explicit = set(existing.get('_explicit_fields') or [])
    explicit.update(new.get('_explicit_fields') or [])
    range_keys = (
        'min_area', 'max_area', 'budget_min', 'budget_max', 'deposit_min', 'deposit_max',
        'rent_min', 'rent_max', 'rooms_min', 'rooms_max', 'year_min', 'year_max',
        'floor_min', 'floor_max',
    )
    for key, value in new.items():
        if key == '_explicit_fields':
            continue
        if value is None or value == '':
            continue
        if key in range_keys and merged.get(key) is not None:
            continue
        merged[key] = value
    merged['_explicit_fields'] = sorted(explicit)
    return merged


def _parse_create_contact(
    user,
    *,
    data: Dict[str, Any],
    ai_meta: Dict[str, Any],
    user_text: str,
    locale: str,
    tz_name: str,
    prior_state: Optional[Dict[str, Any]] = None,
    command_id: Optional[str] = None,
) -> Dict[str, Any]:
    inner = data.get('data') or {}
    missing_fields = list(data.get('missing_fields') or [])
    ambiguous_fields = list(data.get('ambiguous_fields') or [])

    validated, missing_fields, ambiguous_fields, field_error = validate_contact_parse(
        inner,
        llm_missing=missing_fields,
        llm_ambiguous=ambiguous_fields,
        user=user,
        tz_name=tz_name,
    )

    if prior_state and prior_state.get('intent') == NL_COMMAND_INTENT_CREATE_CONTACT:
        validated = _merge_contact_validated(prior_state.get('validated') or {}, validated)
        validated, missing_fields, ambiguous_fields, field_error = validate_contact_parse(
            inner_from_validated(validated),
            llm_missing=missing_fields,
            llm_ambiguous=ambiguous_fields,
            user=user,
            tz_name=tz_name,
            prior_explicit=validated.get('_explicit_fields'),
        )

    duplicate_contact = False
    existing_contact = None
    duplicate_message = ''
    phone = validated.get('phone') or ''
    if phone:
        dup = check_phone_duplicate(user, phone)
        if dup:
            duplicate_contact = True
            existing_contact = existing_contact_payload(dup)
            duplicate_message = f'این شماره قبلاً برای {dup.name} ثبت شده است.'

    name_warning = None
    if validated.get('name') and not duplicate_contact:
        _cid, _cands, amb = resolve_contact_by_name(user, validated.get('name'), limit=3)
        if amb == 'multiple' or (amb == '' and _cid):
            name_warning = 'مخاطبی با نام مشابه در CRM وجود دارد.'

    can_confirm = (
        bool(validated.get('name'))
        and bool(validated.get('phone'))
        and not missing_fields
        and not ambiguous_fields
        and not duplicate_contact
        and not field_error
    )

    if not command_id:
        command_id = new_command_id()
    preview = build_contact_preview(validated)

    state = {
        'intent': NL_COMMAND_INTENT_CREATE_CONTACT,
        'validated': validated,
        'preview': preview,
        'missing_fields': missing_fields,
        'ambiguous_fields': ambiguous_fields,
        'duplicate_contact': duplicate_contact,
        'existing_contact': existing_contact,
        'name_warning': name_warning,
        'input_hash': text_hash(user_text),
        'locale': locale,
        'timezone': tz_name,
        'created_contact_id': prior_state.get('created_contact_id') if prior_state else None,
    }
    save_state(user.pk, command_id, state)

    response: Dict[str, Any] = {
        'ok': True,
        'command_id': command_id,
        'intent': NL_COMMAND_INTENT_CREATE_CONTACT,
        'preview': preview,
        'missing_fields': missing_fields,
        'ambiguous_fields': ambiguous_fields,
        'can_confirm': can_confirm,
        'duplicate_contact': duplicate_contact,
        'ai': ai_meta,
    }
    if existing_contact:
        response['existing_contact'] = existing_contact
        response['message'] = duplicate_message
    elif name_warning:
        response['warning'] = name_warning
    if not can_confirm and not duplicate_contact:
        response['hint'] = field_error or hint_for_incomplete_contact(
            missing_fields=missing_fields,
            ambiguous_fields=ambiguous_fields,
            duplicate=False,
        )
    return response


def _parse_create_personal_property(
    user,
    *,
    data: Dict[str, Any],
    ai_meta: Dict[str, Any],
    user_text: str,
    locale: str,
    tz_name: str,
    prior_state: Optional[Dict[str, Any]] = None,
    command_id: Optional[str] = None,
) -> Dict[str, Any]:
    inner = data.get('data') or {}
    missing_fields = list(data.get('missing_fields') or [])
    ambiguous_fields = list(data.get('ambiguous_fields') or [])

    validated, missing_fields, ambiguous_fields, field_error = validate_property_parse(
        inner,
        llm_missing=missing_fields,
        llm_ambiguous=ambiguous_fields,
    )

    if prior_state and prior_state.get('intent') == NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY:
        validated = _merge_property_validated(prior_state.get('validated') or {}, validated)
        validated, missing_fields, ambiguous_fields, field_error = validate_property_parse(
            validated_as_llm_shape(validated),
            llm_missing=missing_fields,
            llm_ambiguous=ambiguous_fields,
        )

    can_confirm = (
        bool(validated.get('area'))
        and bool(validated.get('deal_mode'))
        and not missing_fields
        and not ambiguous_fields
        and not field_error
    )

    if not command_id:
        command_id = new_command_id()
    preview = build_property_preview(validated)

    state = {
        'intent': NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
        'validated': validated,
        'preview': preview,
        'missing_fields': missing_fields,
        'ambiguous_fields': ambiguous_fields,
        'input_hash': text_hash(user_text),
        'locale': locale,
        'timezone': tz_name,
        'created_property_id': prior_state.get('created_property_id') if prior_state else None,
    }
    save_state(user.pk, command_id, state)

    response: Dict[str, Any] = {
        'ok': True,
        'command_id': command_id,
        'intent': NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
        'preview': preview,
        'missing_fields': missing_fields,
        'ambiguous_fields': ambiguous_fields,
        'can_confirm': can_confirm,
        'ai': ai_meta,
    }
    if not can_confirm:
        hint = field_error or hint_for_incomplete_property(
            missing_fields=missing_fields,
            ambiguous_fields=ambiguous_fields,
        )
        if missing_fields == ['area', 'deal_mode'] or set(missing_fields) >= {'area', 'deal_mode'}:
            hint = 'برای ثبت فایل، حداقل متراژ و نوع معامله را مشخص کنید.'
        response['hint'] = hint
        if 'area' in missing_fields or 'deal_mode' in missing_fields:
            response['hint_example'] = 'مثلاً: آپارتمان ۱۲۰ متری پونک برای فروش، ۱۲ میلیارد.'
    return response


def _parse_create_reminder(
    user,
    *,
    data: Dict[str, Any],
    ai_meta: Dict[str, Any],
    user_text: str,
    locale: str,
    tz_name: str,
) -> Dict[str, Any]:
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
    elif not can_confirm:
        response['hint'] = _hint_for_incomplete_reminder(
            missing_fields=missing_fields,
            ambiguous_fields=ambiguous_fields,
            contact_ambiguity=amb,
        )
    return response


def parse_command(
    user,
    *,
    text: str,
    locale: str = 'fa-IR',
    tz_name: str = 'Asia/Tehran',
    command_id: Optional[str] = None,
) -> Dict[str, Any]:
    user_text = (text or '').strip()
    if not user_text:
        raise NLCommandError('متن فرمان خالی است.', code='empty_text')

    prior_state = None
    merge_intents = frozenset({
        NL_COMMAND_INTENT_CREATE_CONTACT,
        NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
    })
    if command_id:
        prior_state = load_state(user.pk, command_id)
        if not prior_state:
            command_id = None
        elif prior_state.get('intent') not in merge_intents:
            prior_state = None
            command_id = None

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
            NL_COMMAND_PARSE_FAILED_MESSAGE,
            code='parse_failed',
            status=503,
        )

    intent = data.get('intent')
    ai_meta = _ai_response_meta(result)

    if intent == NL_COMMAND_INTENT_UNKNOWN:
        return _unknown_parse_response(ai_meta, entity_id=entity_id, user_id=user.pk)

    if intent == NL_COMMAND_INTENT_CREATE_CONTACT:
        return _parse_create_contact(
            user,
            data=data,
            ai_meta=ai_meta,
            user_text=user_text,
            locale=locale,
            tz_name=tz_name,
            prior_state=prior_state,
            command_id=command_id,
        )

    if intent == NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY:
        return _parse_create_personal_property(
            user,
            data=data,
            ai_meta=ai_meta,
            user_text=user_text,
            locale=locale,
            tz_name=tz_name,
            prior_state=prior_state,
            command_id=command_id,
        )

    if intent != NL_COMMAND_INTENT_CREATE_REMINDER:
        return _unknown_parse_response(ai_meta, entity_id=entity_id, user_id=user.pk)

    return _parse_create_reminder(
        user,
        data=data,
        ai_meta=ai_meta,
        user_text=user_text,
        locale=locale,
        tz_name=tz_name,
    )


def resolve_contact(user, command_id: str, contact_id: int) -> Dict[str, Any]:
    state = load_state(user.pk, command_id)
    if not state:
        raise NLCommandError('فرمان منقضی شده یا یافت نشد.', code='expired', status=404)
    if state.get('intent') != NL_COMMAND_INTENT_CREATE_REMINDER:
        raise NLCommandError('این فرمان انتخاب مخاطب ندارد.', code='invalid_intent')

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

    intent = state.get('intent')
    if intent == NL_COMMAND_INTENT_CREATE_CONTACT:
        return confirm_create_contact(user, command_id, state)
    if intent == NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY:
        return confirm_create_personal_property(user, command_id, state)
    if intent == NL_COMMAND_INTENT_CREATE_REMINDER:
        return confirm_create_reminder(user, command_id, state)
    raise NLCommandError('نوع فرمان پشتیبانی نمی‌شود.', code='invalid_intent')
