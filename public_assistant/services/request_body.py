"""پارس امن بدنه JSON درخواست‌های عمومی."""
from __future__ import annotations

import json
from typing import Any, Optional

from django.conf import settings


class InvalidRequestBody(Exception):
    pass


def max_json_bytes() -> int:
    return int(getattr(settings, 'PUBLIC_ASSISTANT_MAX_JSON_BYTES', 4096))


def parse_json_object(request) -> dict[str, Any]:
    raw = request.body
    if raw is None:
        raise InvalidRequestBody('empty')
    if len(raw) > max_json_bytes():
        raise InvalidRequestBody('too_large')
    try:
        data = json.loads(raw.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise InvalidRequestBody('invalid_json')
    if not isinstance(data, dict):
        raise InvalidRequestBody('not_object')
    return data
