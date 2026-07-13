"""اعلان‌های درون‌پنلی آژانس."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils import timezone

from workspace.models import CRMAgencyPanelNotification
from workspace.services.crm_scope import get_membership


def list_panel_notifications(user, *, limit: int = 20, unread_only: bool = False) -> List[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return []
    qs = CRMAgencyPanelNotification.objects.filter(
        user=user, agency=membership.agency,
    )
    if unread_only:
        qs = qs.filter(is_read=False)
    return [
        {
            'id': n.pk,
            'kind': n.kind,
            'title': n.title,
            'body': n.body,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        }
        for n in qs.order_by('-created_at')[:limit]
    ]


def unread_panel_count(user) -> int:
    membership = get_membership(user)
    if not membership:
        return 0
    return CRMAgencyPanelNotification.objects.filter(
        user=user, agency=membership.agency, is_read=False,
    ).count()


def mark_notification_read(user, notification_id: int) -> bool:
    membership = get_membership(user)
    if not membership:
        return False
    updated = CRMAgencyPanelNotification.objects.filter(
        pk=notification_id, user=user, agency=membership.agency,
    ).update(is_read=True, read_at=timezone.now())
    return updated > 0


def mark_all_notifications_read(user) -> int:
    membership = get_membership(user)
    if not membership:
        return 0
    return CRMAgencyPanelNotification.objects.filter(
        user=user, agency=membership.agency, is_read=False,
    ).update(is_read=True, read_at=timezone.now())
