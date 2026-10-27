"""دسترسی استودیو — هم‌تراز با اشتراک CRM."""
from __future__ import annotations

from typing import Optional, Tuple

from workspace.models import CRMProperty
from workspace.services.crm_property_share import PropertyShareContext, build_property_share_context
from workspace.services.crm_scope import property_for_user


def resolve_studio_access(
    user,
    property_id: int,
) -> Tuple[Optional[CRMProperty], Optional[PropertyShareContext]]:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at:
        return None, None
    share_ctx = build_property_share_context(user, prop)
    return prop, share_ctx
