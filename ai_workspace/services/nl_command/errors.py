"""خطاهای nl_command."""

from __future__ import annotations

from typing import Optional

# نگاشت code داخلی → error_code استاندارد API
_CODE_TO_ERROR: dict[str, str] = {
    'empty_text': 'invalid_input',
    'input_too_long': 'input_too_long',
    'missing_command_id': 'invalid_input',
    'missing_fields': 'missing_fields',
    'missing_due_at': 'missing_fields',
    'parse_failed': 'provider_unavailable',
    'provider_unavailable': 'provider_unavailable',
    'provider_timeout': 'provider_timeout',
    'server_error': 'internal_error',
    'error': 'internal_error',
    'feature_disabled': 'permission_denied',
    'no_license': 'permission_denied',
    'daily_limit': 'quota_exceeded',
    'token_limit': 'quota_exceeded',
    'feature_limit': 'quota_exceeded',
    'quota_exceeded': 'quota_exceeded',
    'expired': 'command_expired',
    'contact_not_found': 'command_not_found',
    'invalid_intent': 'invalid_input',
    'invalid_contact': 'invalid_input',
    'invalid_property': 'invalid_property_data',
    'invalid_phone': 'invalid_phone',
    'duplicate_contact': 'duplicate',
    'past_datetime': 'invalid_date',
    'contact_scope': 'permission_denied',
    'confirm_conflict': 'confirm_conflict',
}

_RETRYABLE: frozenset[str] = frozenset({
    'provider_unavailable',
    'provider_timeout',
    'confirm_conflict',
    'internal_error',
})


def normalize_error_code(code: str) -> str:
    return _CODE_TO_ERROR.get(code or '', code or 'internal_error')


def is_retryable_error_code(error_code: str) -> bool:
    return error_code in _RETRYABLE


class NLCommandError(Exception):
    def __init__(
        self,
        message: str,
        code: str = 'error',
        status: int = 400,
        *,
        error_code: Optional[str] = None,
        retryable: Optional[bool] = None,
    ):
        super().__init__(message)
        self.code = code
        self.error_code = error_code or normalize_error_code(code)
        self.retryable = retryable if retryable is not None else is_retryable_error_code(self.error_code)
        self.status = status
