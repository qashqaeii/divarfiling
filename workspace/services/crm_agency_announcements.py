"""تابلو اطلاعیه‌های آژانس."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from workspace.constants import AGENCY_MANAGER_ROLES, MESSAGE_MAX_ATTACHMENT_BYTES, MESSAGE_ALLOWED_EXTENSIONS
from workspace.models import (
    CRMAgencyAnnouncement,
    CRMAgencyAnnouncementRead,
    CRMAgencyMember,
    CRMAgencyPanelNotification,
)
from workspace.services.crm_audit import log_agency_audit
from workspace.services.crm_scope import get_membership
import os


def _visible_for_member(announcement: CRMAgencyAnnouncement, member: CRMAgencyMember) -> bool:
    now = timezone.now()
    if announcement.published_at > now:
        return False
    if announcement.expires_at and announcement.expires_at < now:
        return False
    roles = announcement.target_roles or []
    if roles and member.role not in roles:
        return False
    return True


def _serialize_announcement(a: CRMAgencyAnnouncement, member: CRMAgencyMember) -> Dict[str, Any]:
    is_read = CRMAgencyAnnouncementRead.objects.filter(announcement=a, member=member).exists()
    return {
        'id': a.pk,
        'title': a.title,
        'body': a.body,
        'importance': a.importance,
        'is_pinned': a.is_pinned,
        'target_roles': a.target_roles,
        'published_at': a.published_at.isoformat(),
        'expires_at': a.expires_at.isoformat() if a.expires_at else None,
        'is_read': is_read,
        'attachment_url': a.attachment.url if a.attachment else '',
        'attachment_name': a.attachment_name or (a.attachment.name if a.attachment else ''),
        'created_by': a.created_by.get_full_name() if a.created_by else '',
    }


def list_announcements(user, *, unread_only: bool = False, page: int = 1, page_size: int = 30) -> Tuple[List[Dict], int]:
    membership = get_membership(user)
    if not membership:
        return [], 0
    now = timezone.now()
    qs = CRMAgencyAnnouncement.objects.filter(
        agency=membership.agency,
        published_at__lte=now,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    roles = membership.role
    qs = qs.filter(Q(target_roles=[]) | Q(target_roles__contains=[roles]))
    if unread_only:
        read_ids = CRMAgencyAnnouncementRead.objects.filter(member=membership).values_list('announcement_id', flat=True)
        qs = qs.exclude(pk__in=read_ids)
    total = qs.count()
    offset = max(0, (page - 1) * page_size)
    items = [
        _serialize_announcement(a, membership)
        for a in qs.select_related('created_by').order_by('-is_pinned', '-published_at')[offset:offset + page_size]
    ]
    return items, total


def unread_announcement_count(user) -> int:
    membership = get_membership(user)
    if not membership:
        return 0
    now = timezone.now()
    qs = CRMAgencyAnnouncement.objects.filter(
        agency=membership.agency, published_at__lte=now,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    qs = qs.filter(Q(target_roles=[]) | Q(target_roles__contains=[membership.role]))
    read_ids = set(
        CRMAgencyAnnouncementRead.objects.filter(member=membership).values_list('announcement_id', flat=True)
    )
    return qs.exclude(pk__in=read_ids).count()


@transaction.atomic
def create_announcement(
    actor,
    *,
    title: str,
    body: str,
    importance: str = CRMAgencyAnnouncement.IMPORTANCE_NORMAL,
    is_pinned: bool = False,
    target_roles: Optional[List[str]] = None,
    published_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    attachment=None,
) -> CRMAgencyAnnouncement:
    membership = get_membership(actor)
    if not membership or membership.role not in AGENCY_MANAGER_ROLES:
        raise ValueError('فقط مدیر یا مالک می‌توانند اطلاعیه ثبت کنند.')
    title = (title or '').strip()
    body = (body or '').strip()
    if not title or not body:
        raise ValueError('عنوان و متن الزامی است.')
    if attachment:
        _validate_attachment(attachment)
    ann = CRMAgencyAnnouncement.objects.create(
        agency=membership.agency,
        created_by=actor,
        title=title,
        body=body,
        importance=importance,
        is_pinned=is_pinned,
        target_roles=list(target_roles or []),
        published_at=published_at or timezone.now(),
        expires_at=expires_at,
        attachment=attachment,
        attachment_name=getattr(attachment, 'name', '') if attachment else '',
    )
    _notify_announcement(ann, membership)
    log_agency_audit(membership.agency, actor, 'announcement.created', {'announcement_id': ann.pk})
    return ann


@transaction.atomic
def update_announcement(actor, announcement_id: int, **fields) -> CRMAgencyAnnouncement:
    membership = get_membership(actor)
    if not membership or membership.role not in AGENCY_MANAGER_ROLES:
        raise ValueError('دسترسی ندارید.')
    ann = CRMAgencyAnnouncement.objects.filter(pk=announcement_id, agency=membership.agency).first()
    if not ann:
        raise ValueError('اطلاعیه یافت نشد.')
    allowed = {'title', 'body', 'importance', 'is_pinned', 'target_roles', 'published_at', 'expires_at'}
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(ann, k, v)
    if fields.get('attachment'):
        _validate_attachment(fields['attachment'])
        ann.attachment = fields['attachment']
        ann.attachment_name = fields['attachment'].name
    ann.save()
    log_agency_audit(membership.agency, actor, 'announcement.updated', {'announcement_id': ann.pk})
    return ann


@transaction.atomic
def delete_announcement(actor, announcement_id: int) -> None:
    membership = get_membership(actor)
    if not membership or membership.role not in AGENCY_MANAGER_ROLES:
        raise ValueError('دسترسی ندارید.')
    ann = CRMAgencyAnnouncement.objects.filter(pk=announcement_id, agency=membership.agency).first()
    if not ann:
        raise ValueError('اطلاعیه یافت نشد.')
    if ann.attachment:
        ann.attachment.delete(save=False)
    ann_id = ann.pk
    ann.delete()
    log_agency_audit(membership.agency, actor, 'announcement.deleted', {'announcement_id': ann_id})


def mark_announcement_read(user, announcement_id: int) -> bool:
    membership = get_membership(user)
    if not membership:
        return False
    ann = CRMAgencyAnnouncement.objects.filter(pk=announcement_id, agency=membership.agency).first()
    if not ann or not _visible_for_member(ann, membership):
        return False
    CRMAgencyAnnouncementRead.objects.get_or_create(announcement=ann, member=membership)
    return True


def _validate_attachment(uploaded_file) -> None:
    ext = os.path.splitext(uploaded_file.name or '')[1].lower()
    if ext not in MESSAGE_ALLOWED_EXTENSIONS:
        raise ValueError('نوع فایل مجاز نیست.')
    if uploaded_file.size > MESSAGE_MAX_ATTACHMENT_BYTES:
        raise ValueError('حجم فایل بیش از حد مجاز است.')


def _notify_announcement(ann: CRMAgencyAnnouncement, creator: CRMAgencyMember) -> None:
    members = CRMAgencyMember.objects.filter(agency=ann.agency, is_active=True).select_related('user')
    for m in members:
        if m.pk == creator.pk:
            continue
        if not _visible_for_member(ann, m):
            continue
        CRMAgencyPanelNotification.objects.create(
            user=m.user,
            agency=ann.agency,
            kind='announcement',
            title=ann.title,
            body=(ann.body or '')[:200],
            link=f'?tab=announcements&id={ann.pk}',
            data={'announcement_id': ann.pk},
        )
