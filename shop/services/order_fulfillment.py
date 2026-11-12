"""تکمیل سفارش پس از تایید پرداخت (درگاه یا کارت به کارت)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from licenses.models import License


def fulfill_order_after_payment(
    order,
    *,
    record_funnel: bool = True,
) -> License | None:
    """
    ثبت paid (commit جدا) سپس تکمیل لایسنس/تمدید.
    شکست تکمیل paid را برنمی‌گرداند — بازیابی: reconcile_order_fulfillments.
    """
    from shop.services.order_fulfillment_recovery import (
        complete_order_fulfillment,
        mark_order_paid_after_gateway,
    )

    order_ref = mark_order_paid_after_gateway(order, record_funnel=record_funnel)
    license_obj = complete_order_fulfillment(order_ref)

    try:
        from accounts.services.lead_attribution import attribute_purchase
        attribute_purchase(order=order_ref)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('lead acquisition purchase attribution failed')

    try:
        from accounts.services.automation_conversion import record_order_conversion
        record_order_conversion(order_ref)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('automation conversion record failed')

    return license_obj


def approve_card_transfer(submission, reviewer) -> License | None:
    """تایید درخواست کارت به کارت — همان fulfillment درگاه زیبال."""
    from shop.models import CardTransferSubmission, Transaction
    from shop.services.card_transfer_workflow import (
        CardTransferFulfillmentError,
        CardTransferInvalidStateError,
        log_card_transfer_event,
        send_customer_approval_sms,
    )

    license_obj: License | None = None
    submission_id = submission.pk

    try:
        with transaction.atomic():
            locked = (
                CardTransferSubmission.objects.select_for_update()
                .select_related('order', 'order__user', 'order__product', 'order__plan')
                .get(pk=submission_id)
            )
            order = locked.order

            if locked.status == 'approved':
                if order.status == 'paid':
                    return License.objects.filter(order=order).first()
                raise CardTransferInvalidStateError(
                    'این پرداخت قبلاً تأیید شده اما سفارش تکمیل نشده است. با پشتیبانی فنی تماس بگیرید.',
                    code='approved_incomplete',
                )

            if locked.status != 'pending':
                raise CardTransferInvalidStateError(
                    'این پرداخت در وضعیت قابل تأیید نیست.',
                    code='not_pending',
                )

            if order.status == 'paid':
                locked.status = 'approved'
                locked.reviewed_by = reviewer
                locked.reviewed_at = timezone.now()
                locked.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
                license_obj = License.objects.filter(order=order).first()
                if not license_obj:
                    license_obj = fulfill_order_after_payment(order)
            elif order.status in ('pending', 'pending_verification'):
                license_obj = fulfill_order_after_payment(order)

                Transaction.objects.update_or_create(
                    order=order,
                    defaults={
                        'zibal_track_id': f'CARD-{locked.pk}',
                        'amount': order.amount,
                        'status': 'paid',
                        'verified_at': timezone.now(),
                    },
                )
                from shop.services.plan_funnel import ensure_payment_success_event
                order.refresh_from_db()
                ensure_payment_success_event(order)

                locked.status = 'approved'
                locked.reviewed_by = reviewer
                locked.reviewed_at = timezone.now()
                locked.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
            else:
                raise CardTransferInvalidStateError(
                    'سفارش مرتبط قابل تأیید نیست.',
                    code='order_invalid',
                )

            order.refresh_from_db()
            if not license_obj and order.status == 'paid':
                license_obj = License.objects.filter(order=order).first()

            if order.status == 'paid' and not license_obj:
                from licenses.services.renewal_orders import order_is_renewal_commerce
                from shop.models import Order as ShopOrder

                renewal_ok = (
                    order_is_renewal_commerce(order)
                    and order.fulfillment_status in (
                        ShopOrder.FulfillmentStatus.COMPLETE,
                        ShopOrder.FulfillmentStatus.PARTIAL,
                    )
                )
                if not renewal_ok:
                    raise CardTransferFulfillmentError(
                        'فعال‌سازی انجام نشد؛ تغییری ثبت نشد. دوباره تلاش کنید یا لاگ را بررسی کنید.',
                        code='fulfillment_failed',
                    )

            log_card_transfer_event(
                'card_transfer_approved',
                locked,
                admin_id=getattr(reviewer, 'pk', None),
            )
            log_card_transfer_event(
                'order_fulfilled_from_card_transfer',
                locked,
                admin_id=getattr(reviewer, 'pk', None),
            )
    except CardTransferInvalidStateError:
        raise
    except CardTransferFulfillmentError:
        raise
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            'card transfer approval failed submission_id=%s', submission_id,
        )
        raise CardTransferFulfillmentError(
            'فعال‌سازی انجام نشد؛ تغییری ثبت نشد. دوباره تلاش کنید یا لاگ را بررسی کنید.',
            code='fulfillment_failed',
        ) from None

    submission = CardTransferSubmission.objects.select_related('order').get(pk=submission_id)
    send_customer_approval_sms(submission)
    return license_obj


def reject_card_transfer(submission, reviewer, admin_note: str = '') -> None:
    """رد درخواست کارت به کارت."""
    from shop.models import CardTransferSubmission
    from shop.services.card_transfer_workflow import (
        CardTransferInvalidStateError,
        log_card_transfer_event,
        send_customer_rejection_sms,
    )

    submission_id = submission.pk

    with transaction.atomic():
        locked = (
            CardTransferSubmission.objects.select_for_update()
            .select_related('order')
            .get(pk=submission_id)
        )
        order = locked.order

        if locked.status == 'rejected':
            return

        if locked.status != 'pending':
            raise CardTransferInvalidStateError(
                'این پرداخت در وضعیت قابل رد نیست.',
                code='not_pending',
            )

        if order.status == 'paid':
            raise CardTransferInvalidStateError(
                'سفارش پرداخت‌شده قابل رد نیست.',
                code='already_fulfilled',
            )

        locked.status = 'rejected'
        locked.admin_note = admin_note.strip()
        locked.reviewed_by = reviewer
        locked.reviewed_at = timezone.now()
        locked.save(update_fields=[
            'status', 'admin_note', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])

        if order.status in ('pending', 'pending_verification'):
            order.status = 'failed'
            order.save(update_fields=['status'])

        log_card_transfer_event(
            'card_transfer_rejected',
            locked,
            admin_id=getattr(reviewer, 'pk', None),
        )

    submission = CardTransferSubmission.objects.select_related('order').get(pk=submission_id)
    send_customer_rejection_sms(submission)
