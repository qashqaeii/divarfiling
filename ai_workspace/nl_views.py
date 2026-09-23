"""API فرمان طبیعی — parse / confirm / resolve-contact."""
from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views import View

from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.service import confirm_command, parse_command, resolve_contact
from ai_workspace.views import AIEnabledMixin

logger = logging.getLogger(__name__)


class _NLJsonMixin(AIEnabledMixin):
    def _parse_body(self, request) -> dict:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}


class NLCommandParseView(_NLJsonMixin, View):
    def post(self, request):
        body = self._parse_body(request)
        text = body.get('text') or ''
        locale = body.get('locale') or 'fa-IR'
        tz_name = body.get('timezone') or 'Asia/Tehran'
        command_id = (body.get('command_id') or '').strip() or None
        resume_correction = bool(body.get('resume_correction'))
        try:
            payload = parse_command(
                request.user,
                text=text,
                locale=locale,
                tz_name=tz_name,
                command_id=command_id,
                resume_correction=resume_correction,
            )
            return JsonResponse(payload)
        except NLCommandError as exc:
            return JsonResponse({'ok': False, 'error': str(exc), 'code': exc.code}, status=exc.status)
        except Exception:
            logger.exception('nl_command_parse_failed user_id=%s', request.user.pk)
            return JsonResponse(
                {'ok': False, 'error': 'خطا در پردازش فرمان.', 'code': 'server_error'},
                status=500,
            )


class NLCommandConfirmView(_NLJsonMixin, View):
    def post(self, request):
        body = self._parse_body(request)
        command_id = (body.get('command_id') or '').strip()
        if not command_id:
            return JsonResponse({'ok': False, 'error': 'command_id الزامی است.', 'code': 'missing_command_id'}, status=400)
        try:
            payload = confirm_command(request.user, command_id)
            return JsonResponse(payload)
        except NLCommandError as exc:
            return JsonResponse({'ok': False, 'error': str(exc), 'code': exc.code}, status=exc.status)
        except Exception:
            logger.exception('nl_command_confirm_failed user_id=%s', request.user.pk)
            return JsonResponse(
                {'ok': False, 'error': 'خطا در ثبت فرمان.', 'code': 'server_error'},
                status=500,
            )


class NLCommandResolveContactView(_NLJsonMixin, View):
    def post(self, request):
        body = self._parse_body(request)
        command_id = (body.get('command_id') or '').strip()
        contact_id = body.get('contact_id')
        if not command_id or contact_id is None:
            return JsonResponse(
                {'ok': False, 'error': 'command_id و contact_id الزامی است.', 'code': 'missing_fields'},
                status=400,
            )
        try:
            payload = resolve_contact(request.user, command_id, int(contact_id))
            return JsonResponse(payload)
        except NLCommandError as exc:
            return JsonResponse({'ok': False, 'error': str(exc), 'code': exc.code}, status=exc.status)
