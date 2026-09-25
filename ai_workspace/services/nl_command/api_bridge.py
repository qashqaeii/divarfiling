"""HTTP-agnostic NL command handlers — shared by web JSON views and mobile API."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ai_workspace.services.nl_command.errors import NLCommandError, is_retryable_error_code, normalize_error_code
from ai_workspace.services.nl_command.service import confirm_command, parse_command, resolve_contact


def nl_error_payload(exc: NLCommandError) -> Dict[str, Any]:
    ec = exc.error_code or normalize_error_code(exc.code)
    return {
        'ok': False,
        'error': str(exc),
        'message': str(exc),
        'code': exc.code,
        'error_code': ec,
        'retryable': exc.retryable if exc.retryable is not None else is_retryable_error_code(ec),
    }


def nl_parse_from_body(user, body: Dict[str, Any]) -> Dict[str, Any]:
    text = body.get('text') or ''
    locale = body.get('locale') or 'fa-IR'
    tz_name = body.get('timezone') or 'Asia/Tehran'
    command_id = (body.get('command_id') or '').strip() or None
    resume_correction = bool(body.get('resume_correction'))
    return parse_command(
        user,
        text=text,
        locale=locale,
        tz_name=tz_name,
        command_id=command_id,
        resume_correction=resume_correction,
    )


def nl_confirm_from_body(user, body: Dict[str, Any]) -> Dict[str, Any]:
    command_id = (body.get('command_id') or '').strip()
    if not command_id:
        raise NLCommandError('command_id الزامی است.', code='missing_command_id')
    return confirm_command(user, command_id)


def nl_resolve_contact_from_body(user, body: Dict[str, Any]) -> Dict[str, Any]:
    command_id = (body.get('command_id') or '').strip()
    contact_id = body.get('contact_id')
    if not command_id or contact_id is None:
        raise NLCommandError(
            'command_id و contact_id الزامی است.',
            code='missing_fields',
        )
    return resolve_contact(user, command_id, int(contact_id))


def run_nl_action(handler, user, body: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Returns (payload, http_status). Payload always includes ok when success."""
    try:
        data = handler(user, body or {})
        if isinstance(data, dict) and 'ok' not in data:
            data = {**data, 'ok': True}
        return data, 200
    except NLCommandError as exc:
        payload = nl_error_payload(exc)
        return payload, exc.status or 400
