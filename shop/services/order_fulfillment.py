"""تکمیل سفارش پس از تایید پرداخت (درگاه یا کارت به کارت)."""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from licenses.models import License


def _record_affiliate_commission(order) -> None:
    if not order.affiliate_id:
        return
    from affiliates.models import Affiliate, AffiliateSale, Wallet

    commission_rate = order.affiliate.commission_rate or settings.AFFILIATE_DEFAULT_COMMISSION
    original_price = order.original_price or order.plan.price
    commission_amount = (original_price * commission_rate) // 100

    sale, created = AffiliateSale.objects.get_or_create(
        order=order,
        defaults={
            'affiliate': order.affiliate,
            'commission_rate': commission_rate,
            'commission_amount': commission_amount,
            'status': 'paid',
        },
    )
    if not created:
        return

    wallet, _ = Wallet.objects.get_or_create(user=order.affiliate.user)
    wallet.add_balance(
        commission_amount,
        f'کمیسیون فروش - سفارش {order.id}',
        related_sale=sale,
    )


def fulfill_order_after_payment(order) -> License | None:
    """لایسنس، افیلیت و سایر اقدامات پس از پرداخت موفق — idempotent."""
    if order.status == 'paid':
        return License.objects.filter(order=order).first()

    with transaction.atomic():
        from shop.models import Order

        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == 'paid':
            return License.objects.filter(order=order).first()

        order.status = 'paid'
        order.paid_at = timezone.now()
        order.save(update_fields=['status', 'paid_at'])

        _record_affiliate_commission(order)

    from affiliates.models import Affiliate, Wallet as AffiliateWallet

    if not Affiliate.objects.filter(user=order.user).exists():
        Affiliate.objects.create(user=order.user, is_active=True)
        AffiliateWallet.objects.get_or_create(user=order.user)

    return License.objects.filter(order=order).first()


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
