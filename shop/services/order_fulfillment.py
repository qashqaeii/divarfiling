"""تکمیل سفارش پس از تایید پرداخت (درگاه یا کارت به کارت)."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from licenses.models import License


def fulfill_order_after_payment(order) -> License | None:
    """لایسنس، افیلیت و سایر اقدامات پس از پرداخت موفق — idempotent."""
    from licenses.services.claim import issue_license_for_paid_order

    if order.status == 'paid':
        return issue_license_for_paid_order(order)

    with transaction.atomic():
        from shop.models import Order

        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == 'paid':
            return issue_license_for_paid_order(order)

        order.status = 'paid'
        order.paid_at = timezone.now()
        order.save(update_fields=['status', 'paid_at'])

        from affiliates.services.commission import (
            ensure_buyer_affiliate_account,
            record_affiliate_commission,
        )

        record_affiliate_commission(order)
        ensure_buyer_affiliate_account(order.user)

    return issue_license_for_paid_order(order)


def approve_card_transfer(submission, reviewer) -> License | None:
    """تایید درخواست کارت به کارت توسط مدیر."""
    from shop.models import Transaction

    order = submission.order
    if submission.status != 'pending':
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
    return license_obj


def reject_card_transfer(submission, reviewer, admin_note: str = '') -> None:
    """رد درخواست کارت به کارت."""
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
