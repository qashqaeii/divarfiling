"""نشست چت — فقط از کوکی امن."""
from __future__ import annotations

import uuid

from django.http import HttpRequest

from public_assistant.models import PublicChatSession
from public_assistant.services.rate_limit import check_session_create_rate, ip_hash


def session_from_cookie(request: HttpRequest) -> tuple[PublicChatSession, bool]:
    """
    نشست را فقط از کوکی pa_session می‌گیرد.
    خروجی: (session, created_new)
    """
    raw = (request.COOKIES.get('pa_session') or '').strip()
    if raw:
        try:
            sid = uuid.UUID(raw)
        except ValueError:
            sid = None
        if sid:
            sess = PublicChatSession.objects.filter(pk=sid).first()
            if sess:
                return sess, False

    check_session_create_rate(request)
    sess = PublicChatSession.objects.create(ip_hash=ip_hash(request))
    return sess, True


def set_session_cookie(response, request: HttpRequest, session: PublicChatSession) -> None:
    response.set_cookie(
        'pa_session',
        str(session.id),
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite='Lax',
        secure=request.is_secure(),
    )
