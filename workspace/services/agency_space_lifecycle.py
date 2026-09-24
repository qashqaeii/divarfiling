"""Lifecycle Agency Space — عضو خارج‌شده، حذف منبع."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from workspace.models import AgencySpaceItem, CRMProperty, Customer

User = get_user_model()


def _archive_items(qs, reason: str) -> int:
    now = timezone.now()
    return qs.update(
        status=AgencySpaceItem.STATUS_ARCHIVED,
        archived_at=now,
        archived_reason=reason,
    )


@transaction.atomic
def archive_publications_for_member_user(
    agency_id: int,
    user_id: int,
    *,
    reason: str,
) -> int:
    qs = AgencySpaceItem.objects.filter(
        agency_id=agency_id,
        publisher_id=user_id,
        status=AgencySpaceItem.STATUS_ACTIVE,
    )
    return _archive_items(qs, reason)


@transaction.atomic
def archive_publications_for_property(prop: CRMProperty) -> int:
    qs = AgencySpaceItem.objects.filter(
        property_id=prop.pk,
        status__in=(
            AgencySpaceItem.STATUS_ACTIVE,
            AgencySpaceItem.STATUS_MODERATION_HIDDEN,
        ),
    )
    return _archive_items(qs, AgencySpaceItem.ARCHIVE_SOURCE_DELETED)


@transaction.atomic
def archive_publications_for_customer(customer: Customer) -> int:
    qs = AgencySpaceItem.objects.filter(
        customer_id=customer.pk,
        status__in=(
            AgencySpaceItem.STATUS_ACTIVE,
            AgencySpaceItem.STATUS_MODERATION_HIDDEN,
        ),
    )
    return _archive_items(qs, AgencySpaceItem.ARCHIVE_SOURCE_DELETED)
