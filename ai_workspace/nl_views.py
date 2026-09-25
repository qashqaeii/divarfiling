"""API فرمان طبیعی — parse / confirm / resolve-contact."""
from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views import View

from ai_workspace.services.nl_command.api_bridge import (
    nl_confirm_from_body,
    nl_parse_from_body,
    nl_resolve_contact_from_body,
    run_nl_action,
)
from ai_workspace.services.nl_command.errors import NLCommandError, is_retryable_error_code, normalize_error_code
from ai_workspace.views import AIEnabledMixin

logger = logging.getLogger(__name__)


def _error_response(
    message: str,
    *,
    code: str,
    status: int,
    error_code: str | None = None,
    retryable: bool | None = None,
) -> JsonResponse:
    ec = error_code or normalize_error_code(code)
    ret = retryable if retryable is not None else is_retryable_error_code(ec)
    return JsonResponse(
        {
            'ok': False,
            'error': message,
            'message': message,
            'code': code,
            'error_code': ec,
            'retryable': ret,
        },
        status=status,
    )


def _error_from_exception(exc: NLCommandError) -> JsonResponse:
    return _error_response(
        str(exc),
        code=exc.code,
        status=exc.status,
        error_code=exc.error_code,
        retryable=exc.retryable,
    )


class _NLJsonMixin(AIEnabledMixin):
    def _parse_body(self, request) -> dict:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}

    def _dispatch_nl(self, handler, request):
        body = self._parse_body(request)
        try:
            payload, status = run_nl_action(handler, request.user, body)
            return JsonResponse(payload, status=status)
        except NLCommandError as exc:
            return _error_from_exception(exc)
        except Exception:
            logger.exception('nl_command_failed user_id=%s', request.user.pk)
            return _error_response(
                'خطا در پردازش فرمان.',
                code='server_error',
                status=500,
            )


class NLCommandParseView(_NLJsonMixin, View):
    def post(self, request):
        return self._dispatch_nl(nl_parse_from_body, request)


class NLCommandConfirmView(_NLJsonMixin, View):
    def post(self, request):
        return self._dispatch_nl(nl_confirm_from_body, request)


class NLCommandResolveContactView(_NLJsonMixin, View):
    def post(self, request):
        return self._dispatch_nl(nl_resolve_contact_from_body, request)
