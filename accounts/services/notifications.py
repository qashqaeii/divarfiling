"""ارسال اعلان‌های سیستمی پیامکی (تمدید لایسنس و …)."""
from __future__ import annotations

import logging

from django.conf import settings

from accounts.models import SmsMessageLog
from accounts.phone_utils import normalize_phone
from accounts.services.sms import SmsError, send_pattern_sms, send_simple_sms

logger = logging.getLogger(__name__)


def notify_license_renewal(phone: str, *, days_left: int | str = '', plan_name: str = '') -> bool:
    """اعلان تمدید لایسنس — الگو‌محور در صورت تنظیم، وگرنه متن ساده در حالت console."""
    phone = normalize_phone(phone)
    attrs = {}
    if days_left != '':
        attrs['days'] = str(days_left)
    if plan_name:
        attrs['plan'] = str(plan_name)

    pattern = (getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}).get('license_renewal') or ''
    log = SmsMessageLog.objects.create(
        phone=phone,
        purpose='license_renewal',
        channel=SmsMessageLog.Channel.PATTERN if pattern else SmsMessageLog.Channel.SIMPLE,
        provider=getattr(settings, 'SMS_PROVIDER', 'console'),
        pattern_code=pattern,
        status=SmsMessageLog.Status.PENDING,
    )
    try:
        if pattern:
            result = send_pattern_sms(phone, purpose='license_renewal', attributes=attrs)
        else:
            text = (
                f'میزکار: لایسنس شما'
                + (f' ({plan_name})' if plan_name else '')
                + (f' تا {days_left} روز دیگر منقضی می‌شود.' if days_left != '' else ' نیاز به تمدید دارد.')
            )
            result = send_simple_sms(phone, text)
        log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
        )
        return True
    except SmsError as exc:
        log.mark_failed(str(exc))
        logger.warning('license renewal SMS failed phone=%s**** err=%s', phone[:4], exc.code)
        return False


def notify_system(phone: str, *, text: str = '', attributes: dict | None = None) -> bool:
    """پیام سیستمی عمومی."""
    phone = normalize_phone(phone)
    pattern = (getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}).get('system') or ''
    log = SmsMessageLog.objects.create(
        phone=phone,
        purpose='system',
        channel=SmsMessageLog.Channel.PATTERN if pattern else SmsMessageLog.Channel.SIMPLE,
        provider=getattr(settings, 'SMS_PROVIDER', 'console'),
        pattern_code=pattern,
        status=SmsMessageLog.Status.PENDING,
    )
    try:
        if pattern:
            result = send_pattern_sms(
                phone,
                purpose='system',
                attributes=attributes or ({'message': text} if text else {}),
            )
        else:
            if not text:
                log.mark_failed('متن پیام خالی است')
                return False
            result = send_simple_sms(phone, text)
        log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
        )
        return True
    except SmsError as exc:
        log.mark_failed(str(exc))
        return False
