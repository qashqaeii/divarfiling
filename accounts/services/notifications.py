"""ارسال اعلان‌های سیستمی پیامکی (تمدید لایسنس و …)."""
from __future__ import annotations

import logging

from django.conf import settings

from accounts.models import SmsMessageLog
from accounts.phone_utils import normalize_phone
from accounts.services.sms import SmsError, send_pattern_sms, send_simple_sms

logger = logging.getLogger(__name__)


def _sms_log_preview_for_send(
    log: SmsMessageLog,
    *,
    text: str = '',
    attributes: dict | None = None,
) -> str:
    from accounts.services.sms.log_preview import build_sms_log_preview

    return build_sms_log_preview(
        purpose=log.purpose or '',
        channel=log.channel or '',
        pattern_code=log.pattern_code or '',
        text=text,
        attributes=attributes,
    )


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
        simple_text = ''
        if pattern:
            result = send_pattern_sms(phone, purpose='license_renewal', attributes=attrs)
            preview = _sms_log_preview_for_send(log, attributes=attrs)
        else:
            simple_text = (
                f'میزکار: لایسنس شما'
                + (f' ({plan_name})' if plan_name else '')
                + (f' تا {days_left} روز دیگر منقضی می‌شود.' if days_left != '' else ' نیاز به تمدید دارد.')
            )
            result = send_simple_sms(phone, simple_text)
            preview = _sms_log_preview_for_send(log, text=simple_text)
        log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
            message_preview=preview,
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
        attrs = attributes or ({'message': text} if text else {})
        if pattern:
            result = send_pattern_sms(
                phone,
                purpose='system',
                attributes=attrs,
            )
            preview = _sms_log_preview_for_send(log, text=text, attributes=attrs)
        else:
            if not text:
                log.mark_failed('متن پیام خالی است')
                return False
            result = send_simple_sms(phone, text)
            preview = _sms_log_preview_for_send(log, text=text)
        log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
            message_preview=preview,
        )
        return True
    except SmsError as exc:
        log.mark_failed(str(exc))
        return False


def notify_marketing(
    phone: str,
    *,
    text: str = '',
    attributes: dict | None = None,
) -> tuple[bool, SmsMessageLog]:
    """
    پیام بازاریابی — ترجیح با الگوی FARAZSMS_PATTERNS['marketing']،
    در غیر این صورت ارسال متن ساده.
    خروجی: (موفقیت، لاگ SmsMessageLog)
    """
    phone = normalize_phone(phone)
    pattern = (getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}).get('marketing') or ''
    log = SmsMessageLog.objects.create(
        phone=phone,
        purpose='marketing',
        channel=SmsMessageLog.Channel.PATTERN if pattern else SmsMessageLog.Channel.SIMPLE,
        provider=getattr(settings, 'SMS_PROVIDER', 'console'),
        pattern_code=pattern,
        status=SmsMessageLog.Status.PENDING,
    )
    try:
        if pattern:
            attrs = dict(attributes or {})
            if text and 'message' not in attrs:
                attrs['message'] = text[:500]
            result = send_pattern_sms(phone, purpose='marketing', attributes=attrs)
            preview = _sms_log_preview_for_send(log, text=text, attributes=attrs)
        else:
            if not (text or '').strip():
                log.mark_failed('متن پیام خالی است')
                return False, log
            body = text.strip()
            result = send_simple_sms(phone, body)
            preview = _sms_log_preview_for_send(log, text=body)
        log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
            message_preview=preview,
        )
        return True, log
    except SmsError as exc:
        log.mark_failed(str(exc))
        logger.warning('marketing SMS failed phone=%s**** err=%s', phone[:4], exc.code)
        return False, log


def _send_templated_or_simple_sms(
    phone: str,
    *,
    purpose: str,
    text: str,
    attributes: dict | None = None,
) -> bool:
    """ارسال پیامک با الگو یا متن ساده — لاگ در SmsMessageLog."""
    phone = normalize_phone(phone)
    if not phone:
        return False
    pattern = (getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}).get(purpose) or ''
    log = SmsMessageLog.objects.create(
        phone=phone,
        purpose=purpose,
        channel=SmsMessageLog.Channel.PATTERN if pattern else SmsMessageLog.Channel.SIMPLE,
        provider=getattr(settings, 'SMS_PROVIDER', 'console'),
        pattern_code=pattern,
        status=SmsMessageLog.Status.PENDING,
    )
    try:
        if pattern:
            attrs = attributes or {}
            result = send_pattern_sms(phone, purpose=purpose, attributes=attrs)
            preview = _sms_log_preview_for_send(log, text=text, attributes=attrs)
        else:
            result = send_simple_sms(phone, text)
            preview = _sms_log_preview_for_send(log, text=text)
        log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
            message_preview=preview,
        )
        return True
    except SmsError as exc:
        log.mark_failed(str(exc))
        logger.warning('%s SMS failed phone=%s**** err=%s', purpose, phone[:4], exc.code)
        return False


def notify_card_transfer_admin_review(submission) -> bool:
    """اطلاع‌رسانی به مدیر — پرداخت کارت‌به‌کارت جدید."""
    from shop.services.card_transfer_workflow import (
        admin_sms_already_sent,
        get_admin_notification_phones,
        mark_admin_sms_sent,
    )

    if admin_sms_already_sent(submission):
        return True

    order = submission.order
    user = order.user
    amount = int(order.amount or 0)
    order_ref = str(order.pk)[:8]
    user_label = user.get_full_name() or user.username or 'کاربر'
    plan_name = order.plan.name if order.plan_id else order.product.title

    text = (
        'پرداخت کارت‌به‌کارت جدید ثبت شد.\n'
        f'مبلغ: {amount:,} تومان\n'
        f'سفارش: {order_ref}\n'
        f'کاربر: {user_label}\n'
        f'پلن: {plan_name}\n'
        'برای بررسی وارد پنل مدیریت شوید.'
    )
    attrs = {
        'amount': str(amount),
        'order': order_ref,
        'user': user_label[:40],
        'plan': (plan_name or '')[:40],
    }

    phones = get_admin_notification_phones()
    if not phones:
        logger.warning('no admin phones for card transfer submission_id=%s', submission.pk)
        return False

    sent_any = False
    for phone in phones:
        if _send_templated_or_simple_sms(
            phone,
            purpose='card_transfer_admin_review',
            text=text,
            attributes=attrs,
        ):
            sent_any = True

    if sent_any:
        mark_admin_sms_sent(submission.pk)
    return sent_any


def notify_card_transfer_approved(submission) -> bool:
    """پیامک تأیید پرداخت و فعال‌سازی لایسنس برای کاربر."""
    order = submission.order
    user = order.user
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not phone:
        return False

    from workspace.services.agency_entitlement import is_agency_plan_order

    if is_agency_plan_order(order):
        text = (
            'پرداخت شما تأیید شد ✅\n'
            'پلن آژانس فعال شد.\n'
            'اکنون می‌توانید آژانس خود را راه‌اندازی و مشاوران را دعوت کنید.'
        )
        plan_label = 'پلن آژانس'
    else:
        text = (
            'پرداخت شما تأیید شد ✅\n'
            'لایسنس فایلینگ دیوار فعال شد.\n'
            'برای استفاده وارد میزکار شوید.'
        )
        plan_label = order.plan.name if order.plan_id else 'لایسنس'

    return _send_templated_or_simple_sms(
        phone,
        purpose='card_transfer_license_activated',
        text=text,
        attributes={'plan': plan_label[:40]},
    )


def notify_card_transfer_rejected(submission) -> bool:
    """پیامک رد پرداخت کارت‌به‌کارت برای کاربر."""
    order = submission.order
    user = order.user
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not phone:
        return False

    text = (
        'پرداخت کارت‌به‌کارت شما تأیید نشد.\n'
        'برای بررسی بیشتر با پشتیبانی تماس بگیرید.'
    )
    return _send_templated_or_simple_sms(
        phone,
        purpose='card_transfer_rejected',
        text=text,
    )
