"""Bootstrap session برای استودیو."""
from __future__ import annotations

from typing import Any, Dict

from workspace.models import CRMProperty
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.brand import default_brand_from_user, merge_brand
from workspace.services.property_content_studio.draft import get_or_create_draft
from workspace.services.property_content_studio.quality import build_quality_report
from workspace.services.property_content_studio.storyboard import build_default_storyboard
from workspace.services.property_public_share import get_or_create_property_share, property_public_share_url


def build_studio_session(
    user,
    prop: CRMProperty,
    request,
    *,
    mask_sensitive: bool = False,
) -> Dict[str, Any]:
    public_url = ''
    try:
        share = get_or_create_property_share(user, prop)
        public_url = property_public_share_url(request, share) if request else ''
    except Exception:
        public_url = ''

    property_payload = build_studio_property_payload(
        prop,
        mask_sensitive=mask_sensitive,
        public_share_url=public_url,
    )
    brand = default_brand_from_user(user)
    draft_row, draft_meta = get_or_create_draft(user, prop)
    payload = draft_meta['payload']
    brand_effective = merge_brand(brand, payload.get('brand_override'))

    if not payload.get('storyboard', {}).get('slides'):
        payload['storyboard'] = build_default_storyboard(prop, property_payload)

    quality = build_quality_report(prop, user)

    from ai_workspace.constants import FEATURE_PROPERTY_CONTENT_STUDIO, is_ai_enabled, is_feature_enabled
    from ai_workspace.services.quota import feature_quota_dict

    ai_enabled = is_ai_enabled() and is_feature_enabled(FEATURE_PROPERTY_CONTENT_STUDIO, user)
    ai_quota = feature_quota_dict(user, FEATURE_PROPERTY_CONTENT_STUDIO) if ai_enabled else None

    return {
        'ok': True,
        'property': property_payload,
        'brand': brand,
        'brand_effective': brand_effective,
        'draft': payload,
        'draft_stale': draft_meta['stale'],
        'property_fingerprint': draft_meta['fingerprint'],
        'quality': quality,
        'ai_enabled': ai_enabled,
        'ai_quota': ai_quota,
        'mask_sensitive': mask_sensitive,
    }
