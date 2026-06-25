"""لایسنس و feature flags موبایل."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.utils import timezone

from licenses.models import License
from workspace.services.access import has_active_bot_license, _paid_license_qs


def _primary_license(user) -> Optional[License]:
    return (
        _paid_license_qs(user)
        .filter(status='active')
        .select_related('plan')
        .order_by('-expires_at')
        .first()
    )


def license_payload_for_user(user) -> Dict[str, Any]:
    valid = has_active_bot_license(user)
    lic = _primary_license(user) if valid else _paid_license_qs(user).first()
    plan_name = lic.plan.name if lic and lic.plan_id else None
    expires = lic.expires_at.isoformat() if lic and lic.expires_at else None
    if lic:
        lic.sync_expiration_status(save=True)
        valid = lic.is_valid() and has_active_bot_license(user)

    features = {
        'crm_mobile': valid,
        'filing_view': valid,
        'light_extract': valid,
        'map': valid,
        'push': valid,
    }
    return {
        'valid': valid,
        'plan': plan_name,
        'mobile_extract_enabled': valid,
        'expires_at': expires,
        'features': features,
    }


def license_status_payload(user) -> Dict[str, Any]:
    p = license_payload_for_user(user)
    return {
        'valid': p['valid'],
        'plan': p.get('plan'),
        'features': p.get('features'),
        'expires_at': p.get('expires_at'),
    }


def require_light_extract(user) -> Optional[str]:
    """پیام خطا اگر استخراج سبک مجاز نیست."""
    if not has_active_bot_license(user):
        return 'برای استخراج سبک نیاز به لایسنس فعال دارید.'
    return None
