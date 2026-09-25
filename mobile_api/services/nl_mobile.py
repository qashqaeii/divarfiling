"""Mobile NL Command — capabilities + license gate."""
from __future__ import annotations

from typing import Any, Dict, List

from ai_workspace.constants import (
    CRM_MESSAGE_TONES,
    FEATURE_CRM_MESSAGE,
    FEATURE_LISTING_SUMMARY,
    FEATURE_NL_COMMAND,
    is_ai_enabled,
    is_feature_enabled,
)
from ai_workspace.services.quota import feature_quota_dict, get_status
from workspace.services.access import has_active_bot_license
from workspace.services.crm_smart_command import SMART_COMMAND_PROFILES


def _tone_options() -> List[Dict[str, str]]:
    return [{'id': key, 'label': meta['label']} for key, meta in CRM_MESSAGE_TONES.items()]


def _profile_for_mobile(key: str) -> Dict[str, Any]:
    spec = dict(SMART_COMMAND_PROFILES.get(key) or {})
    if not spec:
        return {}
    return {
        'context': spec.get('context', key),
        'allowed_intent': spec.get('allowed_intent', ''),
        'title': spec.get('title', ''),
        'subtitle': spec.get('subtitle', ''),
        'placeholder': spec.get('placeholder', ''),
        'wrong_intent_message': spec.get('wrong_intent_message', ''),
        'enable_contact_resolve': bool(spec.get('enable_contact_resolve')),
        'examples': spec.get('examples') or [],
    }


def ai_capabilities_for_user(user) -> Dict[str, Any]:
    ai_on = is_ai_enabled()
    licensed = bool(user and user.is_authenticated and has_active_bot_license(user))
    can_nl = ai_on and is_feature_enabled(FEATURE_NL_COMMAND, user)
    can_msg = ai_on and is_feature_enabled(FEATURE_CRM_MESSAGE, user)
    can_listing = ai_on and is_feature_enabled(FEATURE_LISTING_SUMMARY, user)

    quota_nl = feature_quota_dict(user, FEATURE_NL_COMMAND) if can_nl else None
    quota_msg = feature_quota_dict(user, FEATURE_CRM_MESSAGE) if can_msg else None

    overall = None
    if ai_on and licensed:
        try:
            st = get_status(user)
            overall = {
                'remaining': st.remaining,
                'limit': st.daily_limit,
                'has_license': st.has_license,
            }
        except Exception:
            overall = {'remaining': 0, 'limit': 0, 'has_license': licensed}

    no_license_message = 'این قابلیت برای کاربران دارای لایسنس فعال در دسترس است.'
    quota_exhausted_message = 'سهمیه امروز دستیار هوشمند شما تمام شده است.'
    ai_disabled_message = 'سرویس AI فعلاً غیرفعال است.'

    return {
        'ai_enabled': ai_on,
        'has_license': licensed,
        'can_use_smart_command': can_nl and licensed,
        'can_use_crm_message': can_msg and licensed,
        'can_use_listing_summary': can_listing and licensed,
        'messages': {
            'no_license': no_license_message,
            'quota_exhausted': quota_exhausted_message,
            'ai_disabled': ai_disabled_message,
        },
        'quota': overall,
        'nl_command': quota_nl,
        'crm_message': quota_msg,
        'crm_message_tones': _tone_options(),
        'smart_command_profiles': {
            'today': _profile_for_mobile('today'),
            'contacts': _profile_for_mobile('contacts'),
            'properties': _profile_for_mobile('properties'),
        },
    }


def require_nl_access(user) -> None:
    from ai_workspace.services.nl_command.errors import NLCommandError

    if not is_ai_enabled():
        raise NLCommandError('سرویس AI فعلاً غیرفعال است.', code='ai_disabled', status=503)
    if not user or not user.is_authenticated:
        raise NLCommandError('ورود لازم است.', code='unauthorized', status=401)
    if not has_active_bot_license(user):
        raise NLCommandError(
            'این قابلیت برای کاربران دارای لایسنس فعال در دسترس است.',
            code='license_required',
            status=403,
        )
    if not is_feature_enabled(FEATURE_NL_COMMAND, user):
        raise NLCommandError('فرمان هوشمند فعال نیست.', code='feature_disabled', status=403)
