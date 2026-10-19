"""هدیه خوش‌آمدگویی ۷روزه — اعطا در ثبت‌نام و نمایش یک‌باره در میزکار."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from licenses.models import LicenseCampaignGrant
from licenses.services.weekly_trial_campaign import (
    CAMPAIGN_DURATION_DAYS,
    grant_weekly_trial_to_user,
    resolve_professional_gift_plan,
)

logger = logging.getLogger(__name__)

DEFAULT_CAMPAIGN_KEY = 'signup_welcome_7d_v1'
SMS_SKIP_REASON = 'signup_welcome_no_sms'


def campaign_key() -> str:
    return (
        getattr(settings, 'SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY', None)
        or DEFAULT_CAMPAIGN_KEY
    )


def _parse_start_at() -> Optional[datetime]:
    raw = (getattr(settings, 'SIGNUP_WELCOME_GIFT_START_AT', None) or '').strip()
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        logger.warning('signup_welcome_gift: invalid SIGNUP_WELCOME_GIFT_START_AT=%s', raw)
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def is_feature_enabled() -> bool:
    if not getattr(settings, 'SIGNUP_WELCOME_GIFT_ENABLED', False):
        return False
    start_at = _parse_start_at()
    if start_at and timezone.now() < start_at:
        return False
    return True


def _user_joined_after_campaign_start(user) -> bool:
    start_at = _parse_start_at()
    if not start_at:
        return True
    joined = getattr(user, 'date_joined', None)
    if not joined:
        return False
    if timezone.is_naive(joined):
        joined = timezone.make_aware(joined, timezone.get_current_timezone())
    return joined >= start_at


def user_may_receive_signup_gift(user) -> tuple[bool, str]:
    if not is_feature_enabled():
        return False, 'feature_disabled'
    if not user or not getattr(user, 'is_active', False):
        return False, 'inactive_user'
    if not _user_joined_after_campaign_start(user):
        return False, 'user_before_campaign_start'
    if not getattr(user, 'phone_verified', False):
        return False, 'phone_not_verified'
    return True, ''


def _get_grant_row(user, *, for_update: bool = False) -> Optional[LicenseCampaignGrant]:
    qs = LicenseCampaignGrant.objects.filter(user=user, campaign_key=campaign_key())
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def offer_signup_welcome_gift(user, *, channel: str = 'unknown') -> str:
    """
    تلاش idempotent برای اعطای هدیه — خطا ثبت‌نام را خراب نمی‌کند.
    خروجی: granted | already_granted | skipped | failed
    """
    ok, reason = user_may_receive_signup_gift(user)
    if not ok:
        return f'skipped:{reason}'

    try:
        plan = resolve_professional_gift_plan()
    except Exception:
        logger.exception('signup_welcome_gift: plan resolution failed user_id=%s', user.pk)
        _record_failed_grant(user, channel=channel, error='plan_resolution_failed')
        return 'failed'

    try:
        grant_row, status = grant_weekly_trial_to_user(
            user,
            campaign_key=campaign_key(),
            plan=plan,
            grant_metadata={
                'source': 'signup_welcome_gift',
                'signup_channel': (channel or 'unknown')[:32],
            },
            audit_event='signup_welcome_gift_granted',
            skip_sms=True,
        )
    except Exception as exc:
        logger.exception('signup_welcome_gift: grant failed user_id=%s', user.pk)
        _record_failed_grant(user, channel=channel, error=str(exc))
        return 'failed'

    if grant_row and status == 'granted':
        _touch_grant_metadata(grant_row, channel=channel)
        logger.info(
            'signup_welcome_gift granted user_id=%s channel=%s grant_id=%s',
            user.pk,
            channel,
            grant_row.pk,
        )
        return 'granted'
    if status == 'already_granted':
        return 'already_granted'
    return f'skipped:{status}'


def _record_failed_grant(user, *, channel: str, error: str) -> None:
    try:
        LicenseCampaignGrant.objects.update_or_create(
            user=user,
            campaign_key=campaign_key(),
            defaults={
                'status': LicenseCampaignGrant.Status.FAILED,
                'error_message': (error or '')[:500],
                'metadata': {
                    'source': 'signup_welcome_gift',
                    'signup_channel': (channel or 'unknown')[:32],
                },
            },
        )
    except Exception:
        logger.exception('signup_welcome_gift: failed to persist failure user_id=%s', user.pk)


def _touch_grant_metadata(grant_row: LicenseCampaignGrant, *, channel: str) -> None:
    meta = dict(grant_row.metadata or {})
    meta.setdefault('source', 'signup_welcome_gift')
    meta['signup_channel'] = (channel or meta.get('signup_channel') or 'unknown')[:32]
    if grant_row.sms_skip_reason != SMS_SKIP_REASON:
        grant_row.sms_skip_reason = SMS_SKIP_REASON
    grant_row.metadata = meta
    grant_row.save(update_fields=['metadata', 'sms_skip_reason', 'updated_at'])


def retry_signup_welcome_gift_if_needed(user) -> None:
    """تلاش مجدد امن پس از خطای قبلی — فقط برای grant ناموفق بدون لایسنس."""
    if not is_feature_enabled():
        return
    ok, _ = user_may_receive_signup_gift(user)
    if not ok:
        return
    grant_row = _get_grant_row(user)
    if not grant_row:
        offer_signup_welcome_gift(user, channel='retry_workspace')
        return
    if grant_row.status == LicenseCampaignGrant.Status.FAILED:
        offer_signup_welcome_gift(user, channel='retry_after_failure')
        return
    if (
        grant_row.status == LicenseCampaignGrant.Status.GRANTED
        and not grant_row.license_id
        and not grant_row.order_id
    ):
        offer_signup_welcome_gift(user, channel='retry_incomplete')


def get_signup_welcome_grant(user) -> Optional[LicenseCampaignGrant]:
    if not user or not user.is_authenticated:
        return None
    grant = (
        LicenseCampaignGrant.objects.filter(
            user=user,
            campaign_key=campaign_key(),
            status=LicenseCampaignGrant.Status.GRANTED,
        )
        .select_related('license', 'order')
        .first()
    )
    if not grant or not grant.license_id:
        return None
    lic = grant.license
    if not lic or not lic.is_valid():
        return None
    return grant


def should_show_welcome_modal(user) -> bool:
    grant = get_signup_welcome_grant(user)
    if not grant:
        return False
    return grant.welcome_modal_seen_at is None


@transaction.atomic
def acknowledge_welcome_modal(user, *, start_tour: bool = False) -> tuple[bool, dict[str, Any]]:
    grant = _get_grant_row(user, for_update=True)
    if not grant or grant.status != LicenseCampaignGrant.Status.GRANTED or not grant.license_id:
        return False, {'error': 'no_active_gift'}

    now = timezone.now()
    update_fields = ['updated_at']
    if grant.welcome_modal_seen_at is None:
        grant.welcome_modal_seen_at = now
        update_fields.append('welcome_modal_seen_at')
    if start_tour and grant.welcome_tour_started_at is None:
        grant.welcome_tour_started_at = now
        update_fields.append('welcome_tour_started_at')
    grant.save(update_fields=update_fields)
    return True, {
        'welcome_modal_seen_at': grant.welcome_modal_seen_at.isoformat() if grant.welcome_modal_seen_at else None,
        'welcome_tour_started_at': grant.welcome_tour_started_at.isoformat() if grant.welcome_tour_started_at else None,
    }


def gift_duration_days() -> int:
    return CAMPAIGN_DURATION_DAYS
