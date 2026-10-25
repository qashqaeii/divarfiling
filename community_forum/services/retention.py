"""نگهداری ۳۰ روزه."""
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from community_forum.constants import RETENTION_DAYS
from community_forum.models import ForumMessage, ForumReaction, ForumReport

logger = logging.getLogger(__name__)

PURGE_LOCK_KEY = 'forum:purge:lock'
PURGE_BATCH_SIZE = 5000


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
def _purge_batch(expired_ids: list[int]) -> dict:
    if not expired_ids:
        return {'messages': 0, 'reactions': 0, 'reports': 0}
    reactions = ForumReaction.objects.filter(message_id__in=expired_ids).delete()[0]
    reports = ForumReport.objects.filter(message_id__in=expired_ids).delete()[0]
    messages = ForumMessage.objects.filter(id__in=expired_ids).delete()[0]
    return {'messages': messages, 'reactions': reactions, 'reports': reports}


def purge_expired_messages(*, retention_days: int = RETENTION_DAYS, max_batches: int = 50) -> dict:
    """پاکسازی دسته‌ای تا خالی شدن؛ با قفل کوتاه برای جلوگیری از اجرای همزمان."""
    if not cache.add(PURGE_LOCK_KEY, '1', timeout=3600):
        return {'messages': 0, 'reactions': 0, 'reports': 0, 'skipped': True}

    totals = {'messages': 0, 'reactions': 0, 'reports': 0, 'batches': 0}
    cutoff = timezone.now() - timedelta(days=retention_days)
    try:
        for _ in range(max_batches):
            expired_ids = list(
                ForumMessage.objects.filter(created_at__lt=cutoff).values_list('id', flat=True)[:PURGE_BATCH_SIZE],
            )
            if not expired_ids:
                break
            stats = _purge_batch(expired_ids)
            totals['messages'] += stats['messages']
            totals['reactions'] += stats['reactions']
            totals['reports'] += stats['reports']
            totals['batches'] += 1
    except Exception:
        logger.exception('forum purge failed')
        raise
    finally:
        cache.delete(PURGE_LOCK_KEY)

    logger.info('forum purge complete: %s', totals)
    return totals
