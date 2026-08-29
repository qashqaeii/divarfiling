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
    لایسنس، افیلیت و سایر اقدامات پس از پرداخت موفق — idempotent.

    payment_success فقط بعد از موفقیت atomic وضعیت paid ثبت می‌شود
    (یک‌بار به ازای order_id). اگر کل تراکنش بیرونی Rollback شود، Event هم Rollback می‌شود.
    """
    from licenses.services.claim import issue_license_for_paid_order

    with transaction.atomic():
        from shop.models import Order

        locked = Order.objects.select_for_update().get(pk=order.pk)
        already_paid = locked.status == 'paid'

        if not already_paid:
            locked.status = 'paid'
            locked.paid_at = timezone.now()
            locked.save(update_fields=['status', 'paid_at'])

            from affiliates.services.commission import (
                ensure_buyer_affiliate_account,
                record_affiliate_commission,
            )

            record_affiliate_commission(locked)
            ensure_buyer_affiliate_account(locked.user)

        # داخل همان atomic: اگر fulfill شکست بخورد قبل از اینجا، Event نیست.
        # اگر بعداً کل تراکنش Rollback شود، Event هم Rollback می‌شود.
        if record_funnel:
            from shop.services.plan_funnel import ensure_payment_success_event
            ensure_payment_success_event(locked)

        order_ref = locked

    try:
        from accounts.services.lead_attribution import attribute_purchase
        attribute_purchase(order=order_ref)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('lead acquisition purchase attribution failed')

    return issue_license_for_paid_order(order_ref)


def approve_card_transfer(submission, reviewer) -> License | None:
    """تایید درخواست کارت به کارت توسط مدیر."""
    from shop.models import CardTransferSubmission, Transaction

    # همیشه از DB بخوان — در Django Admin وضعیت فرم قبل از save روی obj اعمال شده
    submission = CardTransferSubmission.objects.select_related('order').get(pk=submission.pk)
    order = submission.order
    if submission.status != 'pending':
        if submission.status == 'approved' and order.status == 'paid':
            return License.objects.filter(order=order).first()
        return None
    if order.status == 'paid':
        submission.status = 'approved'
        submission.reviewed_by = reviewer
        submission.reviewed_at = timezone.now()
        submission.save()
        return License.objects.filter(order=order).first()

    submission.status = 'approved'
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.save()

    license_obj = fulfill_order_after_payment(order)

    Transaction.objects.update_or_create(
        order=order,
        defaults={
            'zibal_track_id': f'CARD-{submission.pk}',
            'amount': order.amount,
            'status': 'paid',
            'verified_at': timezone.now(),
        },
    )
    # تکمیل metadata با transaction_id (Event جدید ساخته نمی‌شود)
    from shop.services.plan_funnel import ensure_payment_success_event
    order.refresh_from_db()
    ensure_payment_success_event(order)
    return license_obj


def reject_card_transfer(submission, reviewer, admin_note: str = '') -> None:
    """رد درخواست کارت به کارت."""
    from shop.models import CardTransferSubmission

    submission = CardTransferSubmission.objects.select_related('order').get(pk=submission.pk)
    order = submission.order
    if submission.status != 'pending':
        return

    submission.status = 'rejected'
    submission.admin_note = admin_note.strip()
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.save()

    if order.status in ('pending', 'pending_verification'):
        order.status = 'failed'
        order.save(update_fields=['status'])
