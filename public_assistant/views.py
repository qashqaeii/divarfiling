"""API دستیار عمومی."""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from public_assistant.constants import DEFAULT_SUGGESTED_QUESTIONS, MAX_USER_MESSAGE_LENGTH
from public_assistant.models import PublicAssistantFeedback, PublicChatMessage, PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.feature import is_public_assistant_enabled
from public_assistant.services.persian_text import normalize_persian
from public_assistant.services.rate_limit import (
    RateLimitExceeded,
    check_chat_rate_limit,
    check_duplicate_request,
    check_feedback_rate_limit,
    check_reset_rate_limit,
    check_session_create_rate,
    ip_hash,
)
from public_assistant.services.request_body import InvalidRequestBody, parse_json_object
from public_assistant.services.session import session_from_cookie, set_session_cookie


def _disabled():
    return JsonResponse({'ok': False, 'error': 'دستیار عمومی غیرفعال است.'}, status=503)


def _rate_limit_response():
    return JsonResponse(
        {'ok': False, 'error': 'تعداد درخواست‌ها زیاد است. لطفاً کمی بعد دوباره تلاش کنید.'},
        status=429,
    )


@ensure_csrf_cookie
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

    try:
        data = parse_json_object(request)
    except InvalidRequestBody:
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر.'}, status=400)

    message = data.get('message')
    if not isinstance(message, str):
        return JsonResponse({'ok': False, 'error': 'فرمت پیام نامعتبر است.'}, status=400)
    message = message.strip()
    if not message:
        return JsonResponse({'ok': False, 'error': 'پیام خالی است.'}, status=400)
    if len(message) > MAX_USER_MESSAGE_LENGTH:
        return JsonResponse({'ok': False, 'error': 'پیام بیش از حد طولانی است.'}, status=400)

    session, _created = session_from_cookie(request)
    norm = normalize_persian(message)

    try:
        check_chat_rate_limit(request, str(session.id))
        check_duplicate_request(str(session.id), norm)
    except RateLimitExceeded:
        return _rate_limit_response()

    result = answer_question(session=session, message=message)
    resp = JsonResponse(result)
    set_session_cookie(resp, request, session)
    return resp


@csrf_protect
@require_POST
def feedback_view(request):
    if not is_public_assistant_enabled():
        return _disabled()
    try:
        data = parse_json_object(request)
    except InvalidRequestBody:
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر.'}, status=400)

    session, _ = session_from_cookie(request)

    try:
        check_feedback_rate_limit(request, str(session.id))
    except RateLimitExceeded:
        return _rate_limit_response()

    msg_id = data.get('message_id')
    message = None
    if msg_id is not None:
        if not isinstance(msg_id, int):
            return JsonResponse({'ok': False, 'error': 'شناسه پیام نامعتبر.'}, status=400)
        message = PublicChatMessage.objects.filter(pk=msg_id, session=session).first()

    comment = data.get('comment')
    if comment is not None and not isinstance(comment, str):
        return JsonResponse({'ok': False, 'error': 'فرمت بازخورد نامعتبر.'}, status=400)

    PublicAssistantFeedback.objects.create(
        session=session,
        message=message,
        is_helpful=bool(data.get('helpful')),
        comment=(comment or '')[:500],
    )
    resp = JsonResponse({'ok': True})
    set_session_cookie(resp, request, session)
    return resp


@csrf_protect
@require_POST
def reset_session_view(request):
    if not is_public_assistant_enabled():
        return _disabled()
    try:
        parse_json_object(request)
    except InvalidRequestBody:
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر.'}, status=400)

    try:
        check_reset_rate_limit(request)
        check_session_create_rate(request)
    except RateLimitExceeded:
        return _rate_limit_response()

    session = PublicChatSession.objects.create(ip_hash=ip_hash(request))
    resp = JsonResponse({'ok': True, 'session_id': str(session.id)})
    set_session_cookie(resp, request, session)
    return resp
