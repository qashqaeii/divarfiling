"""تأیید موبایل و صدور idempotent هدیه خوش‌آمدگویی — مسیر واحد وب و موبایل."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _log_gift_offer(
    user,
    *,
    channel: str,
    result: str,
    newly_verified: bool,
) -> None:
    extra = {
        'event': 'signup_welcome_gift_offer',
        'user_id': getattr(user, 'pk', None),
        'channel': (channel or 'unknown')[:32],
        'gift_result': result,
        'newly_verified': newly_verified,
        'phone_verified': bool(getattr(user, 'phone_verified', False)),
    }
    if result == 'granted':
        logger.info('signup_welcome_gift offer granted', extra=extra)
    elif result == 'already_granted':
        logger.info('signup_welcome_gift offer already_granted', extra=extra)
    elif result == 'failed':
        logger.error('signup_welcome_gift offer failed', extra=extra)
    elif result.startswith('skipped:'):
        reason = result.split(':', 1)[-1]
        extra['skip_reason'] = reason
        level = logging.WARNING if reason not in ('phone_not_verified', 'feature_disabled') else logging.INFO
        logger.log(level, 'signup_welcome_gift offer skipped (%s)', reason, extra=extra)
    else:
        logger.warning('signup_welcome_gift offer unexpected result=%s', result, extra=extra)


def complete_phone_verification(user, *, channel: str) -> str:
    """
    پس از OTP معتبر: mark_phone_verified در صورت نیاز + offer_signup_welcome_gift.
    خروجی همان offer_signup_welcome_gift است.
    """
    newly_verified = False
    if not getattr(user, 'phone_verified', False):
        user.mark_phone_verified()
        newly_verified = True
    from licenses.services.signup_welcome_gift import offer_signup_welcome_gift

    try:
        result = offer_signup_welcome_gift(user, channel=channel)
    except Exception:
        logger.exception(
            'signup_welcome_gift unexpected exception user_id=%s channel=%s',
            getattr(user, 'pk', None),
            channel,
            extra={
                'event': 'signup_welcome_gift_offer',
                'user_id': getattr(user, 'pk', None),
                'channel': (channel or 'unknown')[:32],
                'newly_verified': newly_verified,
            },
        )
        result = 'failed'
    _log_gift_offer(user, channel=channel, result=result, newly_verified=newly_verified)
    return result
