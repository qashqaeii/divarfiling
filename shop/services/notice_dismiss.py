"""مدیریت بستن بنر دعوت، اطلاعیه و بنر.

برای مهمان‌ها فقط در نشست ذخیره می‌شود.
برای کاربران لاگین‌شده در دیتابیس هم ذخیره می‌شود تا بعد از logout برنگردد.
"""
from __future__ import annotations

SESSION_KEY = 'dismissed_notices'
_REQUEST_CACHE_ATTR = '_dismissed_notice_keys'


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


def _normalize_notice_id(kind: str, notice_id: str | int | None = None) -> str:
    if kind == 'referral' or notice_id is None or notice_id == '':
        return ''
    return str(notice_id).strip()


def _user_dismissed_keys(request) -> set[str]:
    cached = getattr(request, _REQUEST_CACHE_ATTR, None)
    if cached is not None:
        return cached

    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        keys: set[str] = set()
        setattr(request, _REQUEST_CACHE_ATTR, keys)
        return keys

    from shop.models import UserDismissedNotice

    rows = UserDismissedNotice.objects.filter(user=user).values_list('kind', 'notice_id')
    keys = {notice_key(kind, notice_id or None) for kind, notice_id in rows}
    setattr(request, _REQUEST_CACHE_ATTR, keys)
    return keys


def _persist_user_dismiss(request, kind: str, notice_id: str | int | None = None) -> None:
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return
    from shop.models import UserDismissedNotice

    UserDismissedNotice.objects.get_or_create(
        user=user,
        kind=(kind or '').strip().lower(),
        notice_id=_normalize_notice_id(kind, notice_id),
    )
    cached = getattr(request, _REQUEST_CACHE_ATTR, None)
    if cached is not None:
        cached.add(notice_key(kind, notice_id))


def is_dismissed(request, kind: str, notice_id: str | int | None = None) -> bool:
    key = notice_key(kind, notice_id)
    store = request.session.get(SESSION_KEY) or {}
    if isinstance(store, dict) and store.get(key):
        return True
    return key in _user_dismissed_keys(request)


def dismiss_notice(request, kind: str, notice_id: str | int | None = None) -> str:
    key = notice_key(kind, notice_id)
    store = _store(request)
    store[key] = True
    request.session[SESSION_KEY] = store
    request.session.modified = True
    _persist_user_dismiss(request, kind, notice_id)
    return key


def filter_dismissed(request, items, *, kind: str):
    """حذف آیتم‌هایی که کاربر بسته است (نشست یا دیتابیس)."""
    store = request.session.get(SESSION_KEY) or {}
    if not isinstance(store, dict):
        store = {}
    user_keys = _user_dismissed_keys(request)
    if not store and not user_keys:
        return list(items)
    result = []
    for item in items:
        item_id = getattr(item, 'pk', None) or getattr(item, 'id', None)
        key = notice_key(kind, item_id)
        if store.get(key) or key in user_keys:
            continue
        result.append(item)
    return result
