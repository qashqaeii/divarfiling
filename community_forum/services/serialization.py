"""سریالایز خروجی عمومی — allowlist."""
from collections import defaultdict

from community_forum.constants import ALLOWED_REACTIONS
from community_forum.models import ForumMessage, ForumReaction
from community_forum.services.identity import member_avatar_url, member_display_label
from community_forum.services.retention import is_message_visible


def _reply_preview(msg: ForumMessage | None) -> dict | None:
    if not msg:
        return None
    if not is_message_visible(msg) or msg.deleted_at:
        return {'id': msg.pk, 'unavailable': True, 'sender_label': ''}
    sender = msg.sender
    body = (msg.body or '')[:120]
    return {
        'id': msg.pk,
        'unavailable': False,
        'sender_label': member_display_label(sender),
        'body_preview': body,
    }


def serialize_message(
    msg: ForumMessage,
    *,
    viewer_member,
    reactions_map: dict | None = None,
) -> dict:
    sender = msg.sender
    deleted = bool(msg.deleted_at)
    data = {
        'id': msg.pk,
        'public_id': str(msg.sender.public_id),
        'sender_label': member_display_label(sender),
        'avatar_url': member_avatar_url(sender),
        'body': '' if deleted else msg.body,
        'is_deleted': deleted,
        'is_mine': viewer_member and msg.sender_id == viewer_member.id,
        'is_edited': bool(msg.edited_at),
        'created_at': msg.created_at.isoformat(),
        'edited_at': msg.edited_at.isoformat() if msg.edited_at else None,
        'reply_to': _reply_preview(msg.reply_to) if msg.reply_to_id else None,
        'reactions': reactions_map.get(msg.pk, []) if reactions_map else [],
    }
    return data


def build_reactions_map(message_ids: list[int]) -> dict:
    if not message_ids:
        return {}
    rows = ForumReaction.objects.filter(message_id__in=message_ids).select_related('member')
    grouped: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    mine: dict[int, str] = {}
    for r in rows:
        if r.emoji not in ALLOWED_REACTIONS:
            continue
        grouped[r.message_id][r.emoji] += 1
    for r in rows:
        if r.emoji in ALLOWED_REACTIONS:
            mine[r.message_id] = r.emoji
    out = {}
    for mid in message_ids:
        counts = grouped.get(mid, {})
        out[mid] = [
            {'emoji': emoji, 'count': counts[emoji]}
            for emoji in sorted(counts.keys())
        ]
    return out
