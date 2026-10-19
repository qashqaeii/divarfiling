"""Context تمپلیت/JS برای اتصال دیوار در باکس مالک."""
from __future__ import annotations

from typing import Any, Optional

from django.http import HttpRequest
from django.urls import reverse

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from workspace.models import Listing
from workspace.services.divar_session.feature import user_can_use_divar_contact
from workspace.services.divar_session.service import public_session_status


def divar_contact_page_context(
    request: HttpRequest,
    listing: Optional[Listing],
) -> dict[str, Any]:
    """کلیدهای مشترک فایلینگ و فایل شخصی (با آگهی منبع دیوار)."""
    if not listing or not user_can_use_divar_contact(request.user):
        return {
            'divar_contact_enabled': False,
            'divar_contact_status': {},
        }

    reg_phone = normalize_phone(getattr(request.user, 'phone', '') or '')
    return {
        'divar_contact_enabled': True,
        'divar_contact_status': public_session_status(request.user),
        'divar_connect_default_phone': reg_phone if is_valid_iran_mobile(reg_phone) else '',
        'divar_contact_fetch_url': reverse(
            'workspace:divar_contact_fetch_phone',
            kwargs={'dataset_id': listing.dataset_id, 'listing_id': listing.pk},
        ),
        'divar_listing_captcha_url': (
            (listing.link or '').strip() or f'https://divar.ir/v/{listing.token}'
        ),
    }
