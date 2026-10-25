"""نگهداری ۳۰ روزه."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from community_forum.constants import RETENTION_DAYS
from community_forum.models import ForumMessage, ForumReaction, ForumReport


def retention_cutoff():
    return timezone.now() - timedelta(days=RETENTION_DAYS)


def visible_messages_qs():
    cutoff = retention_cutoff()
    return ForumMessage.objects.filter(
        created_at__gte=cutoff,
        deleted_at__isnull=True,
    )


def is_message_visible(msg: ForumMessage) -> bool:
    if msg.deleted_at:
        return False
    return msg.created_at >= retention_cutoff()


@transaction.atomic
def purge_expired_messages(*, retention_days: int = RETENTION_DAYS) -> dict:
    cutoff = timezone.now() - timedelta(days=retention_days)
    expired_ids = list(
        ForumMessage.objects.filter(created_at__lt=cutoff).values_list('id', flat=True)[:5000]
    )
    if not expired_ids:
        return {'messages': 0, 'reactions': 0, 'reports': 0}

    reactions = ForumReaction.objects.filter(message_id__in=expired_ids).delete()[0]
    reports = ForumReport.objects.filter(message_id__in=expired_ids).delete()[0]
    messages = ForumMessage.objects.filter(id__in=expired_ids).delete()[0]
    return {'messages': messages, 'reactions': reactions, 'reports': reports}
