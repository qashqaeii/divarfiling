"""پاسخ‌های استاندارد JSON برای API موبایل."""
from __future__ import annotations

from typing import Any, Optional

from rest_framework.response import Response


def api_ok(data: Any = None, *, meta: Optional[dict] = None, status: int = 200) -> Response:
    body: dict = {'ok': True}
    if data is not None:
        body['data'] = data
    if meta:
        body['meta'] = meta
    return Response(body, status=status)


def api_error(
    message: str,
    *,
    code: str = 'ERROR',
    status: int = 400,
    fields: Optional[dict] = None,
    retry_after: Optional[int] = None,
) -> Response:
    body: dict = {'ok': False, 'error': message, 'code': code}
    if fields:
        body['fields'] = fields
    if retry_after is not None:
        body['retry_after'] = retry_after
    response = Response(body, status=status)
    if retry_after is not None:
        response['Retry-After'] = str(retry_after)
    return response
