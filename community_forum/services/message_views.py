"""ثبت بازدید یکتا پیام‌ها (شمارنده شبیه تلگرام)."""
from django.db.models import F

from community_forum.models import ForumMessage, ForumMessageView
from community_forum.services.retention import retention_cutoff

MAX_VIEW_BATCH = 40


def record_message_views(member, message_ids: list[int]) -> dict[int, int]:
    """برای هر پیام معتبر، یک بازدید از این عضو ثبت می‌کند (ایدempotent)."""
    if not message_ids:
        return {}
    try:
        ids = sorted({int(x) for x in message_ids if int(x) > 0})
    except (TypeError, ValueError):
        return {}
    ids = ids[:MAX_VIEW_BATCH]
    if not ids:
        return {}

    cutoff = retention_cutoff()
    valid_ids = list(
        ForumMessage.objects.filter(
            pk__in=ids,
            deleted_at__isnull=True,
            created_at__gte=cutoff,
        ).values_list('pk', flat=True),
    )
    if not valid_ids:
        return {}

    newly_seen: list[int] = []
    for mid in valid_ids:
        _, created = ForumMessageView.objects.get_or_create(
            message_id=mid,
            member_id=member.id,
        )
        if created:
            newly_seen.append(mid)

    if newly_seen:
        ForumMessage.objects.filter(pk__in=newly_seen).update(view_count=F('view_count') + 1)

    return dict(ForumMessage.objects.filter(pk__in=valid_ids).values_list('pk', 'view_count'))
