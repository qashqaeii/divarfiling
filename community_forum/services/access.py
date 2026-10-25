"""دسترسی و فعال‌بودن تالار."""
from django.conf import settings


def is_forum_enabled() -> bool:
    return bool(getattr(settings, 'COMMUNITY_FORUM_ENABLED', False))


def _rollout_mode() -> str:
    return (getattr(settings, 'COMMUNITY_FORUM_ROLLOUT_MODE', 'none') or 'none').strip().lower()


def user_in_forum_rollout(user) -> bool:
    """کاربر مجاز به دیدن/استفاده از تالار (پس از فعال بودن feature)."""
    if not is_forum_enabled():
        return False
    mode = _rollout_mode()
    if mode == 'all':
        return True
    if mode == 'allowlist':
        allowed = getattr(settings, 'COMMUNITY_FORUM_ALLOWED_USER_IDS', None) or frozenset()
        return bool(user and getattr(user, 'pk', None) in allowed)
    return False


def user_can_access_forum(user) -> bool:
    if not user_in_forum_rollout(user):
        return False
    if not getattr(user, 'is_authenticated', False):
        return False
    if not user.is_active:
        return False
    return True


def user_can_moderate_forum(user) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if not user_in_forum_rollout(user):
        return False
    if user.is_superuser:
        return True
    return user.has_perm('community_forum.can_moderate_forum')
