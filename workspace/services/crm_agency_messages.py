"""صندوق پیام داخلی آژانس — بدون Real-time."""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from workspace.constants import (
    AGENCY_MANAGER_ROLES,
    MESSAGE_ALLOWED_EXTENSIONS,
    MESSAGE_MAX_ATTACHMENT_BYTES,
    MESSAGE_RETENTION_DAYS,
)
from workspace.models import (
    CRMAgency,
    CRMAgencyMember,
    CRMAgencyMessage,
    CRMAgencyMessageAttachment,
    CRMAgencyMessageParticipant,
    CRMAgencyMessageThread,
    CRMAgencyPanelNotification,
)
from workspace.services.crm_audit import log_agency_audit
from workspace.services.crm_scope import agency_members, get_membership


def _member_display(member: CRMAgencyMember) -> str:
    return member.user.get_full_name() or member.user.phone or member.user.username


def _serialize_attachment(att: CRMAgencyMessageAttachment) -> Dict[str, Any]:
    return {
        'id': att.pk,
        'name': att.original_name,
        'size': att.file_size,
        'content_type': att.content_type,
        'url': att.file.url if att.file else '',
    }


def _serialize_message(msg: CRMAgencyMessage, *, viewer_id: int) -> Dict[str, Any]:
    sender = msg.sender
    return {
        'id': msg.pk,
        'body': msg.body,
        'sender_id': msg.sender_id,
        'sender_name': (sender.get_full_name() or sender.phone or sender.username) if sender else 'سیستم',
        'is_mine': msg.sender_id == viewer_id,
        'reply_to_id': msg.reply_to_id,
        'created_at': msg.created_at.isoformat(),
        'attachments': [_serialize_attachment(a) for a in msg.attachments.all()],
    }


def _serialize_thread_summary(
    thread: CRMAgencyMessageThread,
    participant: CRMAgencyMessageParticipant,
    *,
    viewer_id: int,
) -> Dict[str, Any]:
    last_msg = (
        thread.messages.select_related('sender').prefetch_related('attachments').order_by('-created_at').first()
    )
    other_names: List[str] = []
    if thread.kind == CRMAgencyMessageThread.KIND_DIRECT:
        for p in thread.participants.select_related('member__user'):
            if p.member.user_id != viewer_id:
                other_names.append(_member_display(p.member))
    elif thread.target_roles:
        role_labels = dict(CRMAgencyMember._meta.get_field('role').choices)
        other_names = [role_labels.get(r, r) for r in thread.target_roles]
    else:
        other_names = ['همه اعضا']
    return {
        'id': thread.pk,
        'kind': thread.kind,
        'subject': thread.subject or (other_names[0] if other_names else 'پیام'),
        'participants_label': '، '.join(other_names) if other_names else thread.subject,
        'is_starred': participant.is_starred,
        'is_archived': participant.is_archived,
        'unread_count': participant.unread_count,
        'updated_at': thread.updated_at.isoformat(),
        'last_message': _serialize_message(last_msg, viewer_id=viewer_id) if last_msg else None,
    }


def validate_attachment(uploaded_file) -> None:
    ext = os.path.splitext(uploaded_file.name or '')[1].lower()
    if ext not in MESSAGE_ALLOWED_EXTENSIONS:
        allowed = '، '.join(sorted(MESSAGE_ALLOWED_EXTENSIONS))
        raise ValueError(f'نوع فایل مجاز نیست. فرمت‌های مجاز: {allowed}')
    if uploaded_file.size > MESSAGE_MAX_ATTACHMENT_BYTES:
        mb = MESSAGE_MAX_ATTACHMENT_BYTES // (1024 * 1024)
        raise ValueError(f'حداکثر حجم فایل {mb} مگابایت است.')


def _participants_for_broadcast(agency: CRMAgency, target_roles: List[str]) -> List[CRMAgencyMember]:
    members = list(agency_members(agency))
    if not target_roles:
        return members
    roles = set(target_roles)
    return [m for m in members if m.role in roles]


def _get_or_create_direct_thread(
    agency: CRMAgency,
    sender: CRMAgencyMember,
    recipient: CRMAgencyMember,
) -> CRMAgencyMessageThread:
    if sender.pk == recipient.pk:
        raise ValueError('نمی‌توانید به خودتان پیام بفرستید.')
    existing = (
        CRMAgencyMessageThread.objects.filter(
            agency=agency,
            kind=CRMAgencyMessageThread.KIND_DIRECT,
            participants__member=sender,
        )
        .filter(participants__member=recipient)
        .distinct()
        .first()
    )
    if existing:
        return existing
    thread = CRMAgencyMessageThread.objects.create(
        agency=agency,
        kind=CRMAgencyMessageThread.KIND_DIRECT,
        created_by=sender.user,
    )
    for m in (sender, recipient):
        CRMAgencyMessageParticipant.objects.create(thread=thread, member=m)
    return thread


def _ensure_participant(thread: CRMAgencyMessageThread, member: CRMAgencyMember) -> CRMAgencyMessageParticipant:
    part, _ = CRMAgencyMessageParticipant.objects.get_or_create(thread=thread, member=member)
    return part


def _notify_recipients(
    thread: CRMAgencyMessageThread,
    message: CRMAgencyMessage,
    *,
    exclude_user_id: Optional[int] = None,
) -> None:
    sender_name = ''
    if message.sender:
        sender_name = message.sender.get_full_name() or message.sender.phone or message.sender.username
    title = thread.subject or f'پیام از {sender_name}'
    body = (message.body or '')[:200]
    link = f'?tab=messages&thread={thread.pk}'
    for part in thread.participants.select_related('member__user'):
        uid = part.member.user_id
        if uid == exclude_user_id:
            continue
        CRMAgencyMessageParticipant.objects.filter(pk=part.pk).update(
            unread_count=F('unread_count') + 1,
        )
        CRMAgencyPanelNotification.objects.create(
            user_id=uid,
            agency=thread.agency,
            kind='team_message',
            title=title,
            body=body,
            link=link,
            data={'thread_id': thread.pk, 'message_id': message.pk},
        )


@transaction.atomic
def send_direct_message(
    actor,
    recipient_member_id: int,
    body: str,
    *,
    attachments: Optional[List] = None,
    reply_thread_id: Optional[int] = None,
) -> CRMAgencyMessageThread:
    membership = get_membership(actor)
    if not membership:
        raise ValueError('عضو آژانس نیستید.')
    recipient = CRMAgencyMember.objects.filter(
        pk=recipient_member_id, agency=membership.agency, is_active=True,
    ).select_related('user').first()
    if not recipient:
        raise ValueError('گیرنده یافت نشد.')
    body = (body or '').strip()
    if not body and not attachments:
        raise ValueError('متن یا فایل ضمیمه الزامی است.')
    if reply_thread_id:
        thread = CRMAgencyMessageThread.objects.filter(
            pk=reply_thread_id, agency=membership.agency,
        ).first()
        if not thread:
            raise ValueError('رشته پیام یافت نشد.')
        _ensure_participant(thread, membership)
        _ensure_participant(thread, recipient)
    else:
        thread = _get_or_create_direct_thread(membership.agency, membership, recipient)
    message = CRMAgencyMessage.objects.create(
        thread=thread,
        sender=actor,
        body=body,
    )
    _save_attachments(message, attachments or [])
    CRMAgencyMessageThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    _notify_recipients(thread, message, exclude_user_id=actor.pk)
    log_agency_audit(membership.agency, actor, 'message.sent', {
        'thread_id': thread.pk, 'message_id': message.pk, 'kind': 'direct',
    })
    return thread


@transaction.atomic
def send_broadcast_message(
    actor,
    body: str,
    *,
    subject: str = '',
    target_roles: Optional[List[str]] = None,
    attachments: Optional[List] = None,
) -> CRMAgencyMessageThread:
    membership = get_membership(actor)
    if not membership or membership.role not in AGENCY_MANAGER_ROLES:
        raise ValueError('فقط مدیر یا مالک می‌توانند پیام گروهی ارسال کنند.')
    body = (body or '').strip()
    if not body and not attachments:
        raise ValueError('متن یا فایل ضمیمه الزامی است.')
    roles = list(target_roles or [])
    thread = CRMAgencyMessageThread.objects.create(
        agency=membership.agency,
        kind=CRMAgencyMessageThread.KIND_BROADCAST,
        subject=(subject or '').strip() or 'اطلاعیه تیم',
        created_by=actor,
        target_roles=roles,
    )
    targets = _participants_for_broadcast(membership.agency, roles)
    target_ids = {m.pk for m in targets}
    if membership.pk not in target_ids:
        targets.append(membership)
    for m in targets:
        CRMAgencyMessageParticipant.objects.create(thread=thread, member=m)
    message = CRMAgencyMessage.objects.create(thread=thread, sender=actor, body=body)
    _save_attachments(message, attachments or [])
    _notify_recipients(thread, message, exclude_user_id=actor.pk)
    log_agency_audit(membership.agency, actor, 'message.broadcast', {
        'thread_id': thread.pk,
        'message_id': message.pk,
        'target_roles': roles,
        'recipient_count': len(targets),
    })
    return thread


@transaction.atomic
def reply_to_thread(actor, thread_id: int, body: str, *, attachments: Optional[List] = None) -> CRMAgencyMessage:
    membership = get_membership(actor)
    if not membership:
        raise ValueError('عضو آژانس نیستید.')
    thread = (
        CRMAgencyMessageThread.objects.filter(pk=thread_id, agency=membership.agency)
        .select_for_update()
        .first()
    )
    if not thread:
        raise ValueError('رشته پیام یافت نشد.')
    part = CRMAgencyMessageParticipant.objects.filter(thread=thread, member=membership).first()
    if not part:
        raise ValueError('به این مکالمه دسترسی ندارید.')
    body = (body or '').strip()
    if not body and not attachments:
        raise ValueError('متن یا فایل ضمیمه الزامی است.')
    last_msg = thread.messages.order_by('-created_at').first()
    message = CRMAgencyMessage.objects.create(
        thread=thread,
        sender=actor,
        body=body,
        reply_to=last_msg,
    )
    _save_attachments(message, attachments or [])
    CRMAgencyMessageThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    _notify_recipients(thread, message, exclude_user_id=actor.pk)
    log_agency_audit(membership.agency, actor, 'message.sent', {
        'thread_id': thread.pk, 'message_id': message.pk, 'kind': 'reply',
    })
    return message


def _save_attachments(message: CRMAgencyMessage, files: List) -> None:
    for f in files:
        if not f:
            continue
        validate_attachment(f)
        CRMAgencyMessageAttachment.objects.create(
            message=message,
            file=f,
            original_name=f.name,
            file_size=f.size,
            content_type=getattr(f, 'content_type', '') or '',
        )


def list_threads_for_user(
    user,
    *,
    folder: str = 'inbox',
    page: int = 1,
    page_size: int = 30,
) -> Tuple[List[Dict[str, Any]], int]:
    membership = get_membership(user)
    if not membership:
        return [], 0
    qs = CRMAgencyMessageParticipant.objects.filter(
        member=membership,
    ).select_related('thread', 'thread__created_by').filter(thread__agency=membership.agency)
    if folder == 'starred':
        qs = qs.filter(is_starred=True, is_archived=False)
    elif folder == 'archived':
        qs = qs.filter(is_archived=True)
    else:
        qs = qs.filter(is_archived=False)
    total = qs.count()
    offset = max(0, (page - 1) * page_size)
    rows = list(qs.order_by('-thread__updated_at')[offset:offset + page_size])
    items = [
        _serialize_thread_summary(p.thread, p, viewer_id=user.pk)
        for p in rows
    ]
    return items, total


def get_thread_detail(user, thread_id: int) -> Optional[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return None
    part = (
        CRMAgencyMessageParticipant.objects.filter(
            thread_id=thread_id,
            member=membership,
            thread__agency=membership.agency,
        )
        .select_related('thread')
        .first()
    )
    if not part:
        return None
    thread = part.thread
    messages = list(
        thread.messages.select_related('sender', 'reply_to')
        .prefetch_related('attachments')
        .order_by('created_at')[:200]
    )
    mark_thread_read(part)
    return {
        'thread': _serialize_thread_summary(thread, part, viewer_id=user.pk),
        'messages': [_serialize_message(m, viewer_id=user.pk) for m in messages],
    }


def mark_thread_read(participant: CRMAgencyMessageParticipant) -> None:
    now = timezone.now()
    CRMAgencyMessageParticipant.objects.filter(pk=participant.pk).update(
        last_read_at=now,
        unread_count=0,
    )


def update_thread_state(
    user,
    thread_id: int,
    *,
    is_starred: Optional[bool] = None,
    is_archived: Optional[bool] = None,
) -> bool:
    membership = get_membership(user)
    if not membership:
        return False
    part = CRMAgencyMessageParticipant.objects.filter(
        thread_id=thread_id, member=membership, thread__agency=membership.agency,
    ).first()
    if not part:
        return False
    updates = {}
    if is_starred is not None:
        updates['is_starred'] = bool(is_starred)
    if is_archived is not None:
        updates['is_archived'] = bool(is_archived)
    if updates:
        CRMAgencyMessageParticipant.objects.filter(pk=part.pk).update(**updates)
    return True


def unread_message_count(user) -> int:
    from django.db.models import Sum
    membership = get_membership(user)
    if not membership:
        return 0
    result = CRMAgencyMessageParticipant.objects.filter(
        member=membership,
        thread__agency=membership.agency,
        is_archived=False,
        unread_count__gt=0,
    ).aggregate(total=Sum('unread_count'))
    return int(result['total'] or 0)


def purge_old_messages(*, retention_days: int = MESSAGE_RETENTION_DAYS) -> Dict[str, int]:
    cutoff = timezone.now() - timedelta(days=retention_days)
    old_threads = CRMAgencyMessageThread.objects.filter(updated_at__lt=cutoff)
    attachment_qs = CRMAgencyMessageAttachment.objects.filter(message__thread__in=old_threads)
    files_deleted = 0
    for att in attachment_qs.iterator():
        if att.file:
            att.file.delete(save=False)
            files_deleted += 1
    msg_count = CRMAgencyMessage.objects.filter(thread__in=old_threads).count()
    thread_count = old_threads.count()
    attachment_qs.delete()
    CRMAgencyMessage.objects.filter(thread__in=old_threads).delete()
    old_threads.delete()
    return {'threads': thread_count, 'messages': msg_count, 'files': files_deleted}
