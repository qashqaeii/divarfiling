"""جریان کارت‌به‌کارت: اعلان‌ها، audit و کمک‌متدهای پنل مدیریت."""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.phone_utils import normalize_phone

logger = logging.getLogger('shop.card_transfer')

User = get_user_model()


class CardTransferWorkflowError(Exception):
    """خطای قابل‌نمایش در پنل مدیریت."""

    def __init__(self, message: str, code: str = 'error'):
        self.message = message
        self.code = code
        super().__init__(message)


class CardTransferInvalidStateError(CardTransferWorkflowError):
    pass


class CardTransferFulfillmentError(CardTransferWorkflowError):
    pass


def mask_phone(phone: str) -> str:
    phone = normalize_phone(phone or '')
    if len(phone) < 7:
        return phone or '—'
    return f'{phone[:4]}***{phone[-4:]}'


def get_admin_notification_phones() -> list[str]:
    raw = (getattr(settings, 'CARD_TRANSFER_ADMIN_PHONES', '') or '').strip()
    phones: list[str] = []
    if raw:
        for part in raw.replace(';', ',').split(','):
            normalized = normalize_phone(part.strip())
            if normalized and normalized not in phones:
                phones.append(normalized)
    if phones:
        return phones
    return list(
        User.objects.filter(is_active=True, is_staff=True)
        .exclude(phone='')
        .order_by('-is_superuser', 'id')
        .values_list('phone', flat=True)[:3]
    )


def log_card_transfer_event(
    event_type: str,
    submission,
    *,
    admin_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    order = submission.order
    metadata = {
        'event': event_type,
        'submission_id': submission.pk,
        'order_id': str(order.pk),
        'amount': int(order.amount or 0),
        'product': order.product.title if order.product_id else '',
        'plan': order.plan.name if order.plan_id else '',
        'quantity': int(order.quantity or 1),
        'status': submission.status,
        'admin_id': admin_id,
    }
    if extra:
        metadata.update(extra)
    logger.info('card_transfer audit %s', metadata)


def on_card_transfer_submitted(submission) -> None:
    """پس از ثبت رسید — اعلان مدیر (best-effort)."""
    log_card_transfer_event('card_transfer_submitted', submission)
    try:
        from accounts.services.notifications import notify_card_transfer_admin_review

        notify_card_transfer_admin_review(submission)
    except Exception:
        logger.exception(
            'admin SMS failed submission_id=%s order_id=%s',
            submission.pk,
            submission.order_id,
        )


def send_customer_approval_sms(submission) -> bool:
    if submission.customer_sms_sent_at:
        return True
    try:
        from accounts.services.notifications import notify_card_transfer_approved

        sent = notify_card_transfer_approved(submission)
    except Exception:
        logger.exception('customer approval SMS failed submission_id=%s', submission.pk)
        log_card_transfer_event(
            'customer_activation_sms_failed',
            submission,
            extra={'sms_purpose': 'card_transfer_license_activated'},
        )
        return False
    if sent:
        CardTransferSubmission = submission.__class__
        CardTransferSubmission.objects.filter(pk=submission.pk).update(
            customer_sms_sent_at=timezone.now(),
        )
        log_card_transfer_event(
            'customer_activation_sms_sent',
            submission,
            extra={'sms_purpose': 'card_transfer_license_activated'},
        )
    else:
        log_card_transfer_event(
            'customer_activation_sms_failed',
            submission,
            extra={'sms_purpose': 'card_transfer_license_activated'},
        )
    return sent


def send_customer_rejection_sms(submission) -> bool:
    if submission.customer_rejection_sms_sent_at:
        return True
    try:
        from accounts.services.notifications import notify_card_transfer_rejected

        sent = notify_card_transfer_rejected(submission)
    except Exception:
        logger.exception('customer rejection SMS failed submission_id=%s', submission.pk)
        return False
    if sent:
        CardTransferSubmission = submission.__class__
        CardTransferSubmission.objects.filter(pk=submission.pk).update(
            customer_rejection_sms_sent_at=timezone.now(),
        )
    return sent


def serialize_card_transfer_row(submission) -> dict[str, Any]:
    order = submission.order
    user = order.user
    plan = order.plan
    receipt_url = ''
    if submission.receipt_image:
        try:
            receipt_url = submission.receipt_image.url
        except Exception:
            receipt_url = ''
    return {
        'id': submission.pk,
        'order_id': str(order.pk),
        'order_id_short': str(order.pk)[:8],
        'user_display': user.get_full_name() or user.username,
        'user_phone': mask_phone(getattr(user, 'phone', '') or ''),
        'product_title': order.product.title if order.product_id else '—',
        'plan_name': plan.name if plan else '—',
        'quantity': int(order.quantity or 1),
        'amount': int(order.amount or 0),
        'reference_number': submission.reference_number,
        'payer_name': submission.payer_name or '—',
        'user_note': submission.user_note or '',
        'status': submission.status,
        'status_label': submission.get_status_display(),
        'created_at': submission.created_at,
        'receipt_url': receipt_url,
        'approve_url': reverse('admin_panel_card_transfer_approve', args=[submission.pk]),
        'reject_url': reverse('admin_panel_card_transfer_reject', args=[submission.pk]),
        'admin_url': reverse('admin:shop_cardtransfersubmission_change', args=[submission.pk]),
    }


def serialize_pending_card_transfers(limit: int | None = None) -> list[dict[str, Any]]:
    from shop.models import CardTransferSubmission

    qs = (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order', 'order__user', 'order__product', 'order__plan')
        .order_by('-created_at')
    )
    if limit is not None:
        qs = qs[:limit]
    return [serialize_card_transfer_row(ct) for ct in qs]


def mark_admin_sms_sent(submission_id: int) -> None:
    from shop.models import CardTransferSubmission

    CardTransferSubmission.objects.filter(
        pk=submission_id,
        admin_sms_sent_at__isnull=True,
    ).update(admin_sms_sent_at=timezone.now())


def admin_sms_already_sent(submission) -> bool:
    return bool(submission.admin_sms_sent_at)
