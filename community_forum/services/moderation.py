"""مدیریت محدودیت و گزارش."""
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from community_forum.models import ForumBan, ForumModerationAudit


def _ban_cache_key(member_id: int) -> str:
    return f'forum:active_ban:{member_id}'


def invalidate_ban_cache(member_id: int) -> None:
    cache.delete(_ban_cache_key(member_id))


def active_ban(member) -> ForumBan | None:
    key = _ban_cache_key(member.id)
    if cache.get(key) == 'none':
        return None

    now = timezone.now()
    ban = (
        ForumBan.objects.filter(
            member=member,
            revoked_at__isnull=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .filter(starts_at__lte=now)
        .order_by('-starts_at')
        .first()
    )
    if not ban:
        cache.set(key, 'none', timeout=60)
        return None
    cache.set(key, 'active', timeout=60)
    return ban


def member_can_send(member) -> tuple[bool, str]:
    ban = active_ban(member)
    if not ban:
        return True, ''
    if ban.can_read:
        return False, 'ارسال پیام برای شما در تالار محدود شده است.'
    return False, 'دسترسی شما به تالار محدود شده است.'


def member_can_read(member) -> bool:
    ban = active_ban(member)
    if not ban:
        return True
    return bool(ban.can_read)


def on_ban_applied(ban: ForumBan) -> None:
    invalidate_ban_cache(ban.member_id)
    from community_forum.services.realtime import notify_member

    notify_member(ban.member_id, 'session.revoked', {'reason': 'ban'})


def on_ban_revoked(member_id: int) -> None:
    invalidate_ban_cache(member_id)


def log_audit(action: str, actor, *, message_id=None, member_id=None, meta=None):
    ForumModerationAudit.objects.create(
        action=action,
        actor=actor,
        target_message_id=message_id,
        target_member_id=member_id,
        meta=meta or {},
    )
