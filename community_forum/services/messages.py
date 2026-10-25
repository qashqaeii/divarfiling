"""عملیات پیام تالار."""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from community_forum.constants import (
    ALLOWED_REACTIONS,
    EDIT_WINDOW_MINUTES,
    INITIAL_PAGE_SIZE,
    MAX_BODY_LENGTH,
    REPORT_REASONS,
)
from community_forum.models import ForumMessage, ForumReaction, ForumReport
from community_forum.services.moderation import member_can_read, member_can_send
from community_forum.services.pii import check_message_pii, normalize_message_body
from community_forum.services.rate_limit import enforce_send_rate_limit
from community_forum.services.realtime import broadcast_event
from community_forum.services.retention import retention_cutoff, visible_messages_qs
from community_forum.models import ForumMember
from community_forum.services.serialization import (
    build_reactions_map,
    serialize_message,
    serialize_message_public,
)


def _validate_body(body: str) -> str:
    text = normalize_message_body(body)
    if not text:
        raise ValidationError('پیام نمی‌تواند خالی باشد.', code='empty')
    if len(text) > MAX_BODY_LENGTH:
        raise ValidationError(f'حداکثر طول پیام {MAX_BODY_LENGTH} کاراکتر است.', code='too_long')
    check_message_pii(text)
    return text


def _base_qs():
    return visible_messages_qs().select_related('sender__user', 'reply_to__sender__user')


def list_messages(
    viewer_member,
    *,
    before_id: int | None = None,
    after_id: int | None = None,
    limit: int = INITIAL_PAGE_SIZE,
):
    limit = max(1, min(limit, 100))
    qs = _base_qs().order_by('-id')
    if before_id:
        qs = qs.filter(id__lt=before_id)
    if after_id:
        qs = _base_qs().filter(id__gt=after_id).order_by('id')
        chunk = list(qs[: limit + 1])
        has_more_after = len(chunk) > limit
        if has_more_after:
            chunk = chunk[:limit]
        return chunk, None, has_more_after
    items = list(qs[: limit + 1])
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    items.reverse()
    next_before = items[0].pk if items and has_more else None
    return items, next_before, False


def serialize_many(messages, viewer_member):
    ids = [m.pk for m in messages]
    reactions, mine = build_reactions_map(ids, viewer_member)
    return [
        serialize_message(
            m,
            viewer_member=viewer_member,
            reactions_map=reactions,
            my_reactions=mine,
        )
        for m in messages
    ]


def send_message(
    member,
    body: str,
    *,
    reply_to_id: int | None = None,
    client_message_id: str | None = None,
) -> ForumMessage:
    can_send, msg = member_can_send(member)
    if not can_send:
        raise ValidationError(msg, code='banned')
    if not member_can_read(member):
        raise ValidationError('دسترسی شما به تالار محدود شده است.', code='banned_read')

    client_uuid = None
    if client_message_id:
        try:
            client_uuid = uuid.UUID(str(client_message_id))
        except ValueError:
            raise ValidationError('شناسه پیام نامعتبر است.', code='client_id')

        existing = ForumMessage.objects.filter(sender=member, client_message_id=client_uuid).first()
        if existing and not existing.deleted_at and existing.created_at >= retention_cutoff():
            return existing

    text = _validate_body(body)
    enforce_send_rate_limit(member.id, member.user)

    reply_to = None
    if reply_to_id:
        reply_to = ForumMessage.objects.filter(pk=reply_to_id).first()
        if not reply_to or reply_to.deleted_at or reply_to.created_at < retention_cutoff():
            raise ValidationError('پیام مورد پاسخ در دسترس نیست.', code='reply_invalid')

    try:
        with transaction.atomic():
            msg = ForumMessage.objects.create(
                sender=member,
                body=text,
                reply_to=reply_to,
                client_message_id=client_uuid,
            )
    except IntegrityError:
        if client_uuid:
            existing = ForumMessage.objects.filter(sender=member, client_message_id=client_uuid).first()
            if existing and not existing.deleted_at and existing.created_at >= retention_cutoff():
                return existing
        raise

    pub = serialize_message_public(msg, reactions_map={})
    transaction.on_commit(lambda p=pub: broadcast_event('message.new', {'message': p}))
    return msg


SYNC_PAGE_SIZE = 200


def list_sync_changes(
    viewer_member,
    *,
    anchor_id: int,
    since_iso: str,
    cursor_id: int = 0,
    limit: int = SYNC_PAGE_SIZE,
):
    """ویرایش/حذف/واکنش پیام‌های با id <= anchor از زمان since (صفحه‌بندی)."""
    from django.utils.dateparse import parse_datetime

    since = parse_datetime(since_iso)
    if not since:
        raise ValidationError('زمان نامعتبر', code='since_invalid')
    if anchor_id < 0:
        raise ValidationError('شناسه نامعتبر', code='anchor_invalid')
    if cursor_id < 0:
        raise ValidationError('شناسه نامعتبر', code='cursor_invalid')

    limit = min(max(int(limit or SYNC_PAGE_SIZE), 1), SYNC_PAGE_SIZE)
    cutoff = retention_cutoff()
    change_filter = (
        Q(edited_at__gte=since)
        | Q(deleted_at__gte=since)
        | Q(reactions_updated_at__gte=since)
    )
    qs = (
        ForumMessage.objects.filter(
            id__lte=anchor_id,
            id__gt=cursor_id,
            created_at__gte=cutoff,
        )
        .filter(change_filter)
        .select_related('sender__user', 'reply_to__sender__user')
        .order_by('id')
    )
    batch = list(qs[: limit + 1])
    has_more = len(batch) > limit
    items = batch[:limit]
    messages = serialize_many(items, viewer_member)
    next_cursor = items[-1].pk if has_more and items else None
    return {
        'messages': messages,
        'has_more': has_more,
        'next_cursor': next_cursor,
    }


def edit_message(member, message_id: int, body: str) -> ForumMessage:
    msg = ForumMessage.objects.select_related('sender').filter(pk=message_id).first()
    if not msg or msg.deleted_at or msg.created_at < retention_cutoff():
        raise ValidationError('پیام یافت نشد.', code='not_found')
    if msg.sender_id != member.id:
        raise ValidationError('اجازه ویرایش این پیام را ندارید.', code='forbidden')
    deadline = msg.created_at + timedelta(minutes=EDIT_WINDOW_MINUTES)
    if timezone.now() > deadline:
        raise ValidationError('مهلت ویرایش پیام به پایان رسیده است.', code='edit_window')

    text = _validate_body(body)
    msg.body = text
    msg.edited_at = timezone.now()
    msg.save(update_fields=['body', 'edited_at'])
    rx, _mine = build_reactions_map([msg.pk])
    pub = serialize_message_public(msg, reactions_map=rx)
    transaction.on_commit(lambda p=pub: broadcast_event('message.updated', {'message': p}))
    return msg


def delete_message(member, message_id: int, *, moderator_user=None) -> ForumMessage:
    msg = ForumMessage.objects.select_related('sender').filter(pk=message_id).first()
    if not msg or msg.deleted_at:
        raise ValidationError('پیام یافت نشد.', code='not_found')
    from community_forum.services.access import user_can_moderate_forum

    is_mod = moderator_user and user_can_moderate_forum(moderator_user)
    if msg.sender_id != member.id and not is_mod:
        raise ValidationError('اجازه حذف این پیام را ندارید.', code='forbidden')

    msg.deleted_at = timezone.now()
    msg.body = ''
    msg.save(update_fields=['deleted_at', 'body'])
    if is_mod:
        from community_forum.services.moderation import log_audit

        log_audit('delete_message', moderator_user, message_id=msg.pk, member_id=msg.sender_id)
    payload = {'id': msg.pk}
    transaction.on_commit(lambda: broadcast_event('message.deleted', payload))
    return msg


def set_reaction(member, message_id: int, emoji: str | None) -> dict:
    if emoji and emoji not in ALLOWED_REACTIONS:
        raise ValidationError('واکنش مجاز نیست.', code='emoji')
    msg = ForumMessage.objects.filter(pk=message_id).first()
    if not msg or msg.deleted_at or msg.created_at < retention_cutoff():
        raise ValidationError('پیام یافت نشد.', code='not_found')

    existing = ForumReaction.objects.filter(message=msg, member=member).first()
    changed = False
    if not emoji:
        if existing:
            existing.delete()
            changed = True
    elif existing:
        if existing.emoji != emoji:
            existing.emoji = emoji
            existing.save(update_fields=['emoji'])
            changed = True
    else:
        ForumReaction.objects.create(message=msg, member=member, emoji=emoji)
        changed = True

    if changed:
        ForumMessage.objects.filter(pk=msg.pk).update(reactions_updated_at=timezone.now())

    counts, _ = build_reactions_map([msg.pk])
    payload = {'message_id': msg.pk, 'reactions': counts.get(msg.pk, [])}
    transaction.on_commit(lambda: broadcast_event('reaction.updated', payload))
    return payload


def report_message(member, message_id: int, reason: str, note: str = '') -> None:
    valid = {c[0] for c in REPORT_REASONS}
    if reason not in valid:
        raise ValidationError('دلیل گزارش نامعتبر است.', code='reason')
    msg = ForumMessage.objects.filter(pk=message_id).first()
    if not msg or msg.deleted_at:
        raise ValidationError('پیام یافت نشد.', code='not_found')
    if msg.sender_id == member.id:
        raise ValidationError('نمی‌توانید پیام خود را گزارش کنید.', code='self')
    try:
        ForumReport.objects.create(
            message=msg,
            reporter=member,
            reason=reason,
            note=(note or '')[:500],
        )
    except IntegrityError:
        raise ValidationError('این پیام را قبلاً گزارش کرده‌اید.', code='duplicate')


def update_read_cursor(member, message_id: int) -> None:
    msg = ForumMessage.objects.filter(pk=message_id).first()
    if not msg:
        return
    ForumMember.objects.filter(pk=member.pk).filter(
        Q(last_read_message_id__isnull=True) | Q(last_read_message_id__lt=message_id),
    ).update(last_read_message_id=message_id, updated_at=timezone.now())


def unread_count(member) -> int:
    if not member.last_read_message_id:
        last_id = 0
    else:
        last_id = member.last_read_message_id
    return (
        visible_messages_qs()
        .filter(id__gt=last_id)
        .exclude(sender=member)
        .count()
    )


def search_messages(member, query: str, *, page: int = 1, page_size: int = 20):
    q = (query or '').strip()
    if len(q) < 2:
        raise ValidationError('عبارت جستجو خیلی کوتاه است.', code='query')
    if len(q) > 100:
        q = q[:100]
    page = max(1, page)
    page_size = max(1, min(page_size, 30))
    qs = (
        _base_qs()
        .filter(body__icontains=q)
        .order_by('-id')
    )
    total = qs.count()
    start = (page - 1) * page_size
    items = list(qs[start : start + page_size])
    items.reverse()
    return serialize_many(items, member), total
