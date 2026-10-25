"""مدیریت محدودیت و گزارش."""
from django.db.models import Q
from django.utils import timezone

from community_forum.models import ForumBan, ForumModerationAudit


def active_ban(member) -> ForumBan | None:
    now = timezone.now()
    return (
        ForumBan.objects.filter(
            member=member,
            revoked_at__isnull=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .filter(starts_at__lte=now)
        .order_by('-starts_at')
        .first()
    )


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


def log_audit(action: str, actor, *, message_id=None, member_id=None, meta=None):
    ForumModerationAudit.objects.create(
        action=action,
        actor=actor,
        target_message_id=message_id,
        target_member_id=member_id,
        meta=meta or {},
    )
