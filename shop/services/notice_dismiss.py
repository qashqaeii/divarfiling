"""مدیریت بستن موقت بنر دعوت، اطلاعیه و بنر تا پایان نشست."""
from __future__ import annotations

SESSION_KEY = 'dismissed_notices'


def _store(request) -> dict:
    raw = request.session.get(SESSION_KEY)
    if not isinstance(raw, dict):
        raw = {}
        request.session[SESSION_KEY] = raw
    return raw


def notice_key(kind: str, notice_id: str | int | None = None) -> str:
    kind = (kind or '').strip().lower()
    if kind == 'referral':
        return 'referral'
    if notice_id is None or notice_id == '':
        return kind
    return f'{kind}:{notice_id}'


def is_dismissed(request, kind: str, notice_id: str | int | None = None) -> bool:
    store = request.session.get(SESSION_KEY) or {}
    if not isinstance(store, dict):
        return False
    return bool(store.get(notice_key(kind, notice_id)))


def dismiss_notice(request, kind: str, notice_id: str | int | None = None) -> str:
    key = notice_key(kind, notice_id)
    store = _store(request)
    store[key] = True
    request.session[SESSION_KEY] = store
    request.session.modified = True
    return key


def filter_dismissed(request, items, *, kind: str):
    """حذف آیتم‌هایی که در این نشست بسته شده‌اند."""
    store = request.session.get(SESSION_KEY) or {}
    if not isinstance(store, dict) or not store:
        return list(items)
    result = []
    for item in items:
        item_id = getattr(item, 'pk', None) or getattr(item, 'id', None)
        if store.get(notice_key(kind, item_id)):
            continue
        result.append(item)
    return result
