"""API دستیار عمومی."""
from __future__ import annotations

import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from public_assistant.constants import DEFAULT_SUGGESTED_QUESTIONS
from public_assistant.models import PublicAssistantFeedback, PublicChatMessage, PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.feature import is_public_assistant_enabled
from public_assistant.services.persian_text import normalize_persian
from public_assistant.services.rate_limit import (
    RateLimitExceeded,
    check_duplicate_request,
    check_rate_limit,
    ip_hash,
)


def _disabled():
    return JsonResponse({'ok': False, 'error': 'دستیار عمومی غیرفعال است.'}, status=503)


def _parse_json(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None


def _session_from_request(request, data: dict) -> PublicChatSession:
    raw = (data.get('session_id') or request.COOKIES.get('pa_session') or '').strip()
    if raw:
        try:
            sid = uuid.UUID(raw)
            sess = PublicChatSession.objects.filter(pk=sid).first()
            if sess:
                return sess
        except ValueError:
            pass
    sess = PublicChatSession.objects.create(ip_hash=ip_hash(request))
    return sess


@require_GET
def config_view(request):
    if not is_public_assistant_enabled():
        return _disabled()
    return JsonResponse(
        {
            'ok': True,
            'suggested_questions': DEFAULT_SUGGESTED_QUESTIONS,
            'welcome': (
                'سلام! من دستیار فایلینگ دیوار هستم. '
                'درباره امکانات، آموزش، اشتراک و شروع کار می‌توانم راهنمایی‌تان کنم.'
            ),
        }
    )


@csrf_protect
@require_POST
def chat_view(request):
    if not is_public_assistant_enabled():
        return _disabled()

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر.'}, status=400)

    message = (data.get('message') or '').strip()
    if not message:
        return JsonResponse({'ok': False, 'error': 'پیام خالی است.'}, status=400)

    session = _session_from_request(request, data)
    norm = normalize_persian(message)

    try:
        check_rate_limit(request, str(session.id))
        check_duplicate_request(str(session.id), norm)
    except RateLimitExceeded:
        return JsonResponse(
            {'ok': False, 'error': 'تعداد درخواست‌ها زیاد است. لطفاً کمی بعد دوباره تلاش کنید.'},
            status=429,
        )

    result = answer_question(session=session, message=message)
    resp = JsonResponse(result)
    resp.set_cookie(
        'pa_session',
        str(session.id),
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure(),
    )
    return resp


@csrf_protect
@require_POST
def feedback_view(request):
    if not is_public_assistant_enabled():
        return _disabled()
    data = _parse_json(request)
    if data is None:
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر.'}, status=400)

    session = _session_from_request(request, data)
    msg_id = data.get('message_id')
    message = None
    if msg_id:
        message = PublicChatMessage.objects.filter(pk=msg_id, session=session).first()

    PublicAssistantFeedback.objects.create(
        session=session,
        message=message,
        is_helpful=bool(data.get('helpful')),
        comment=(data.get('comment') or '')[:500],
    )
    return JsonResponse({'ok': True})


@csrf_protect
@require_POST
def reset_session_view(request):
    if not is_public_assistant_enabled():
        return _disabled()
    sess = PublicChatSession.objects.create(ip_hash=ip_hash(request))
    resp = JsonResponse({'ok': True, 'session_id': str(sess.id)})
    resp.set_cookie(
        'pa_session',
        str(sess.id),
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure(),
    )
    return resp
