"""Mobile NL Command API — /api/mobile/v1/ai/nl/"""
from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ai_workspace.services.nl_command.api_bridge import (
    nl_confirm_from_body,
    nl_error_payload,
    nl_parse_from_body,
    nl_resolve_contact_from_body,
    run_nl_action,
)
from ai_workspace.services.nl_command.errors import NLCommandError
from mobile_api.responses import api_error, api_ok
from mobile_api.services.nl_mobile import ai_capabilities_for_user, require_nl_access
from mobile_api.views import _parse_body

logger = logging.getLogger(__name__)


def _map_nl_error(exc: NLCommandError):
    code_map = {
        'quota_exceeded': ('QUOTA_EXCEEDED', 429),
        'feature_disabled': ('FORBIDDEN', 403),
        'license_required': ('FORBIDDEN', 403),
        'ai_disabled': ('SERVICE_UNAVAILABLE', 503),
        'empty_text': ('VALIDATION_ERROR', 400),
        'input_too_long': ('VALIDATION_ERROR', 400),
        'missing_command_id': ('VALIDATION_ERROR', 400),
        'missing_fields': ('VALIDATION_ERROR', 400),
        'expired': ('NOT_FOUND', 404),
        'confirm_conflict': ('CONFLICT', 409),
        'contact_not_found': ('NOT_FOUND', 404),
        'contact_scope': ('FORBIDDEN', 403),
    }
    api_code, status = code_map.get(exc.code, ('VALIDATION_ERROR', exc.status or 400))
    payload = nl_error_payload(exc)
    return api_error(
        payload.get('message') or str(exc),
        code=api_code,
        status=status,
        fields={
            'error_code': payload.get('error_code'),
            'retryable': payload.get('retryable'),
            'nl_code': exc.code,
        },
    )


class _NLMobileBase(APIView):
    permission_classes = [IsAuthenticated]

    def _guard(self, user):
        try:
            require_nl_access(user)
        except NLCommandError as exc:
            return _map_nl_error(exc)
        return None


class AICapabilitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(ai_capabilities_for_user(request.user))


class NLCommandParseView(_NLMobileBase):
    def post(self, request):
        if (err := self._guard(request.user)):
            return err
        body = _parse_body(request)
        try:
            payload, status = run_nl_action(nl_parse_from_body, request.user, body)
            if not payload.get('ok', True):
                return api_error(
                    payload.get('message') or payload.get('error') or 'خطا',
                    code='NL_ERROR',
                    status=status,
                    fields={k: v for k, v in payload.items() if k not in ('ok', 'error', 'message')},
                )
            return api_ok(payload, status=status)
        except NLCommandError as exc:
            return _map_nl_error(exc)
        except Exception:
            logger.exception('mobile_nl_parse_failed user_id=%s', request.user.pk)
            return api_error('خطا در پردازش فرمان.', code='SERVER_ERROR', status=500)


class NLCommandConfirmView(_NLMobileBase):
    def post(self, request):
        if (err := self._guard(request.user)):
            return err
        body = _parse_body(request)
        try:
            payload, status = run_nl_action(nl_confirm_from_body, request.user, body)
            if not payload.get('ok', True):
                return api_error(
                    payload.get('message') or payload.get('error') or 'خطا',
                    code='NL_ERROR',
                    status=status,
                    fields={k: v for k, v in payload.items() if k not in ('ok', 'error', 'message')},
                )
            return api_ok(payload, status=status)
        except NLCommandError as exc:
            return _map_nl_error(exc)
        except Exception:
            logger.exception('mobile_nl_confirm_failed user_id=%s', request.user.pk)
            return api_error('خطا در ثبت فرمان.', code='SERVER_ERROR', status=500)


class NLCommandResolveContactView(_NLMobileBase):
    def post(self, request):
        if (err := self._guard(request.user)):
            return err
        body = _parse_body(request)
        try:
            payload, status = run_nl_action(nl_resolve_contact_from_body, request.user, body)
            if not payload.get('ok', True):
                return api_error(
                    payload.get('message') or payload.get('error') or 'خطا',
                    code='NL_ERROR',
                    status=status,
                    fields={k: v for k, v in payload.items() if k not in ('ok', 'error', 'message')},
                )
            return api_ok(payload, status=status)
        except NLCommandError as exc:
            return _map_nl_error(exc)
        except Exception:
            logger.exception('mobile_nl_resolve_failed user_id=%s', request.user.pk)
            return api_error('خطا در انتخاب مخاطب.', code='SERVER_ERROR', status=500)
