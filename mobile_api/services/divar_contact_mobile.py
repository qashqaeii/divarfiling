"""API موبایل برای دریافت شماره مالک از دیوار — همان سرویس وب."""
from __future__ import annotations

from typing import Any, Optional

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from workspace.models import Listing
from workspace.services.divar_session.errors import DivarSessionError
from workspace.services.divar_session.feature import user_can_use_divar_contact
from workspace.services.divar_session.service import (
    disconnect_divar_session,
    fetch_listing_phone,
    public_session_status,
    send_divar_otp,
    verify_divar_otp,
)


def _assert_feature(user) -> None:
    if not user_can_use_divar_contact(user):
        raise DivarSessionError('دسترسی مجاز نیست.', code='forbidden')


def _default_phone(user) -> str:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    return phone if is_valid_iran_mobile(phone) else ''


def status_payload(user) -> dict[str, Any]:
    enabled = user_can_use_divar_contact(user)
    if not enabled:
        return {
            'enabled': False,
            'default_phone': '',
            'status': {
                'has_session': False,
                'show_connected_badge': False,
                'button_state': 'connect',
            },
            'captcha_fallback_url': '',
        }
    return {
        'enabled': True,
        'default_phone': _default_phone(user),
        'status': public_session_status(user),
        'captcha_fallback_url': '',
    }


def status_for_listing(user, token: str) -> Optional[dict[str, Any]]:
    listing = Listing.objects.filter(dataset__user=user, token=token).first()
    if not listing:
        return None
    payload = status_payload(user)
    payload['captcha_fallback_url'] = (
        (listing.link or '').strip() or f'https://divar.ir/v/{listing.token}'
    )
    return payload


def send_otp_payload(user, phone: str) -> dict[str, Any]:
    _assert_feature(user)
    return send_divar_otp(user, phone)


def verify_otp_payload(user, phone: str, otp: str) -> dict[str, Any]:
    _assert_feature(user)
    return verify_divar_otp(user, phone, otp)


def disconnect_payload(user) -> dict[str, Any]:
    _assert_feature(user)
    result = disconnect_divar_session(user)
    result['status'] = public_session_status(user)
    return result


def fetch_phone_payload(user, token: str) -> dict[str, Any]:
    _assert_feature(user)
    listing = Listing.objects.filter(dataset__user=user, token=token).first()
    if not listing:
        raise DivarSessionError('آگهی یافت نشد.', code='not_found')
    return fetch_listing_phone(user, listing)
