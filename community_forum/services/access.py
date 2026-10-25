"""دسترسی و فعال‌بودن تالار."""
from django.conf import settings


def is_forum_enabled() -> bool:
    return bool(getattr(settings, 'COMMUNITY_FORUM_ENABLED', False))


def user_can_access_forum(user) -> bool:
    if not is_forum_enabled():
        return False
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if not user.is_active:
        return False
    return True


def user_can_moderate_forum(user) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.has_perm('community_forum.can_moderate_forum')
