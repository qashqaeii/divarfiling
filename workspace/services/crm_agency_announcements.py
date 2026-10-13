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


def _announcement_status(announcement: CRMAgencyAnnouncement, now=None) -> str:
    now = now or timezone.now()
    if announcement.published_at > now:
        return 'scheduled'
    if announcement.expires_at and announcement.expires_at < now:
        return 'expired'
    return 'active'


def _serialize_announcement(a: CRMAgencyAnnouncement, member: CRMAgencyMember) -> Dict[str, Any]:
    is_read = CRMAgencyAnnouncementRead.objects.filter(announcement=a, member=member).exists()
    now = timezone.now()
    return {
        'id': a.pk,
        'title': a.title,
        'body': a.body,
        'body_preview': (a.body or '')[:160],
        'importance': a.importance,
        'is_pinned': a.is_pinned,
        'target_roles': a.target_roles or [],
        'published_at': a.published_at.isoformat(),
        'expires_at': a.expires_at.isoformat() if a.expires_at else None,
        'is_read': is_read,
        'status': _announcement_status(a, now),
        'attachment_url': a.attachment.url if a.attachment else '',
        'attachment_name': a.attachment_name or (a.attachment.name if a.attachment else ''),
        'created_by': a.created_by.get_full_name() if a.created_by else '',
        'created_at': a.created_at.isoformat(),
    }


def _filter_for_role(qs, role: str):
    from django.db import connection
    if connection.vendor == 'postgresql':
        return qs.filter(Q(target_roles=[]) | Q(target_roles__contains=[role]))
    visible_ids = [
        pk for pk, roles in qs.values_list('pk', 'target_roles')
        if not (roles or []) or role in (roles or [])
    ]
    if not visible_ids:
        return qs.none()
    return qs.filter(pk__in=visible_ids)


def _announcement_queryset(membership: CRMAgencyMember, *, include_all: bool = False):
    qs = CRMAgencyAnnouncement.objects.filter(agency=membership.agency)
    if not include_all:
        now = timezone.now()
        qs = qs.filter(published_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
        qs = _filter_for_role(qs, membership.role)
    return qs


def list_announcements(
    user,
    *,
    unread_only: bool = False,
    important_only: bool = False,
    page: int = 1,
    page_size: int = 30,
    include_all: bool = False,
) -> Tuple[List[Dict], int]:
    membership = get_membership(user)
    if not membership:
        return [], 0
    if include_all and membership.role not in AGENCY_MANAGER_ROLES:
        include_all = False
    qs = _announcement_queryset(membership, include_all=include_all)
    if unread_only:
        read_ids = CRMAgencyAnnouncementRead.objects.filter(member=membership).values_list('announcement_id', flat=True)
        qs = qs.exclude(pk__in=read_ids)
    if important_only:
        qs = qs.filter(importance__in=[
            CRMAgencyAnnouncement.IMPORTANCE_HIGH,
            CRMAgencyAnnouncement.IMPORTANCE_URGENT,
        ])
    total = qs.count()
    offset = max(0, (page - 1) * page_size)
    items = [
        _serialize_announcement(a, membership)
        for a in qs.select_related('created_by').order_by('-is_pinned', '-published_at')[offset:offset + page_size]
    ]
    return items, total


def _audience_members(ann: CRMAgencyAnnouncement) -> List[CRMAgencyMember]:
    qs = CRMAgencyMember.objects.filter(agency=ann.agency, is_active=True).select_related('user')
    roles = ann.target_roles or []
    if roles:
        qs = qs.filter(role__in=roles)
    return list(qs)


def _build_read_stats(ann: CRMAgencyAnnouncement) -> Dict[str, Any]:
    audience = _audience_members(ann)
    if not audience:
        return {
            'total_audience': 0,
            'read_count': 0,
            'unread_count': 0,
            'read': [],
            'unread': [],
        }
    audience_ids = [m.pk for m in audience]
    reads = {
        r.member_id: r
        for r in CRMAgencyAnnouncementRead.objects.filter(
            announcement=ann,
            member_id__in=audience_ids,
        ).select_related('member__user')
    }
    read_list = []
    unread_list = []
    for m in audience:
        name = m.user.get_full_name() or m.user.username
        entry = {
            'member_id': m.pk,
            'name': name,
            'role': m.role,
            'role_label': m.get_role_display(),
        }
        if m.pk in reads:
            entry['read_at'] = reads[m.pk].read_at.isoformat()
            read_list.append(entry)
        else:
            unread_list.append(entry)
    read_list.sort(key=lambda x: x.get('read_at', ''), reverse=True)
    unread_list.sort(key=lambda x: x['name'])
    return {
        'total_audience': len(audience),
        'read_count': len(read_list),
        'unread_count': len(unread_list),
        'read': read_list,
        'unread': unread_list,
    }


def get_announcement(user, announcement_id: int) -> Optional[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return None
    ann = CRMAgencyAnnouncement.objects.filter(pk=announcement_id, agency=membership.agency).select_related('created_by').first()
    if not ann:
        return None
    if membership.role not in AGENCY_MANAGER_ROLES and not _visible_for_member(ann, membership):
        return None
    data = _serialize_announcement(ann, membership)
    if membership.role in AGENCY_MANAGER_ROLES:
        data['read_stats'] = _build_read_stats(ann)
    return data


def unread_announcement_count(user) -> int:
    membership = get_membership(user)
    if not membership:
        return 0
    qs = _announcement_queryset(membership, include_all=False)
    read_ids = set(
        CRMAgencyAnnouncementRead.objects.filter(member=membership).values_list('announcement_id', flat=True)
    )
    return qs.exclude(pk__in=read_ids).count()


def _manager_active_announcements(membership: CRMAgencyMember):
    now = timezone.now()
    return CRMAgencyAnnouncement.objects.filter(
        agency=membership.agency,
        published_at__lte=now,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))


def announcements_with_team_unread_count(user) -> int:
    """تعداد اطلاعیه‌های فعال که هنوز حداقل یک عضو مخاطب آن را نخوانده (برای مدیران)."""
    membership = get_membership(user)
    if not membership or membership.role not in AGENCY_MANAGER_ROLES:
        return 0
    pending = 0
    for ann in _manager_active_announcements(membership).iterator():
        if _build_read_stats(ann)['unread_count'] > 0:
            pending += 1
    return pending


def announcements_unread_for_hub(user) -> int:
    """شمارنده کارت «اطلاعیه‌ها» در میزکار — برای مدیران، خوانده‌نشده تیم هم لحاظ می‌شود."""
    personal = unread_announcement_count(user)
    if personal > 0:
        return personal
    return announcements_with_team_unread_count(user)


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
    CRMAgencyAnnouncementRead.objects.get_or_create(announcement=ann, member=membership)
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


def parse_announcement_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        from workspace.services.jalali_input import parse_jalali_datetime_string
        dt = parse_jalali_datetime_string(raw)
        if dt is None:
            try:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except ValueError:
                return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


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
