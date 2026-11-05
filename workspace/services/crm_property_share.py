"""نمایش و دسترسی اشتراک فایل شخصی (ملک)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from django.contrib.auth import get_user_model

from workspace.models import CRMProperty, CRMResourceShare

User = get_user_model()


@dataclass
class PropertyShareContext:
    is_owner: bool
    is_recipient: bool
    share: Optional[CRMResourceShare]
    share_mode: Optional[str]
    is_confidential: bool
    is_collaborative: bool
    can_edit: bool
    mask_sensitive: bool
    owner_user: Optional[User]


def property_share_for_user(user, prop: CRMProperty) -> Optional[CRMResourceShare]:
    if not user or not user.is_authenticated or prop.user_id == user.id:
        return None
    return (
        CRMResourceShare.objects.filter(property=prop, shared_with=user)
        .select_related('owner', 'shared_by', 'shared_with')
        .first()
    )


def build_property_share_context(user, prop: CRMProperty) -> PropertyShareContext:
    is_owner = prop.user_id == user.id
    share = None if is_owner else property_share_for_user(user, prop)
    mode = share.share_mode if share else None
    is_confidential = mode == CRMResourceShare.SHARE_MODE_CONFIDENTIAL
    is_collaborative = mode == CRMResourceShare.SHARE_MODE_COLLABORATIVE
    can_edit = is_owner or is_collaborative
    mask_sensitive = is_confidential
    owner_user = prop.user
    return PropertyShareContext(
        is_owner=is_owner,
        is_recipient=bool(share),
        share=share,
        share_mode=mode,
        is_confidential=is_confidential,
        is_collaborative=is_collaborative,
        can_edit=can_edit,
        mask_sensitive=mask_sensitive,
        owner_user=owner_user,
    )


def location_display(prop: CRMProperty, *, mask: bool) -> str:
    from workspace.services.listing_street_data import property_street_for_display

    if mask:
        parts = [p for p in (prop.city, prop.district) if p]
        return ' · '.join(parts) if parts else 'محدوده عمومی (محرمانه)'
    chunks = []
    if prop.neighborhood:
        chunks.append(prop.neighborhood)
    if prop.city:
        chunks.append(prop.city)
    text = ' — '.join(chunks) if chunks else ''
    if prop.district:
        text = f'{text} ({prop.district})' if text else prop.district
    street = property_street_for_display(prop)
    if street:
        street_norm = street.strip()
        if street_norm and street_norm not in text:
            text = f'{text} · {street_norm}' if text else street_norm
    return text or '—'


def share_mode_label(mode: str) -> str:
    return dict(CRMResourceShare.SHARE_MODE_CHOICES).get(mode, mode)


def list_outgoing_property_shares(prop: CRMProperty) -> List[CRMResourceShare]:
    return list(
        prop.shares.select_related('shared_with', 'shared_by', 'owner').order_by('-created_at')
    )
