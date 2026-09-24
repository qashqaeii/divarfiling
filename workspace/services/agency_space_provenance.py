"""Provenance کپی فضای آژانس برای صفحه detail CRM — reverse lookup از AgencySpaceCopy."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.urls import reverse

from workspace.models import AgencySpaceCopy, CRMProperty, Customer
from workspace.services.agency_space_query import get_space_item_for_user


def provenance_for_property(prop: CRMProperty, viewer=None) -> Optional[Dict[str, Any]]:
    rec = (
        AgencySpaceCopy.objects.filter(
            target_kind=AgencySpaceCopy.TARGET_PROPERTY,
            target_id_snapshot=prop.pk,
        )
        .select_related('item', 'item__publisher', 'item__agency')
        .first()
    )
    if not rec and prop.pk:
        rec = (
            AgencySpaceCopy.objects.filter(copied_property_id=prop.pk)
            .select_related('item', 'item__publisher', 'item__agency')
            .first()
        )
    return _payload(rec, viewer)


def provenance_for_customer(customer: Customer, viewer=None) -> Optional[Dict[str, Any]]:
    rec = (
        AgencySpaceCopy.objects.filter(
            target_kind=AgencySpaceCopy.TARGET_CUSTOMER,
            target_id_snapshot=customer.pk,
        )
        .select_related('item', 'item__publisher', 'item__agency')
        .first()
    )
    if not rec and customer.pk:
        rec = (
            AgencySpaceCopy.objects.filter(copied_customer_id=customer.pk)
            .select_related('item', 'item__publisher', 'item__agency')
            .first()
        )
    return _payload(rec, viewer)


def _payload(rec: Optional[AgencySpaceCopy], viewer) -> Optional[Dict[str, Any]]:
    if not rec or not rec.item_id:
        return None
    item = rec.item
    pub = item.publisher
    name = ''
    if pub:
        name = pub.get_full_name() or getattr(pub, 'phone', '') or pub.username
    space_item_url = ''
    if viewer and viewer.is_authenticated:
        if get_space_item_for_user(viewer, item.pk):
            space_item_url = reverse(
                'workspace:agency_hub_space_item',
                kwargs={'item_id': item.pk},
            )
    return {
        'label': 'فضای آژانس',
        'publisher_name': name,
        'copied_at': rec.created_at.isoformat() if rec.created_at else '',
        'space_item_id': item.pk,
        'space_item_url': space_item_url,
    }
