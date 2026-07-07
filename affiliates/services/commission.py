"""
Idempotent affiliate commission recording after successful payment.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction

from affiliates.services.referral import is_valid_attribution


def _resolve_commission_affiliate(order):
    """Use order.affiliate, fallback to buyer.referred_by, persist on order if missing."""
    affiliate = order.affiliate
    if affiliate and is_valid_attribution(order.user, affiliate):
        return affiliate

    buyer = order.user
    if buyer.referred_by_id and is_valid_attribution(buyer, buyer.referred_by):
        affiliate = buyer.referred_by
        if not order.affiliate_id:
            order.affiliate = affiliate
            order.save(update_fields=['affiliate'])
        return affiliate
    return None


def record_affiliate_commission(order) -> bool:
    """
    Record commission once per paid order. Returns True if sale recorded (new or existing).
    """
    affiliate = _resolve_commission_affiliate(order)
    if not affiliate:
        return False

    from affiliates.models import AffiliateSale, Wallet

    commission_rate = affiliate.commission_rate or Decimal(str(settings.AFFILIATE_DEFAULT_COMMISSION))
    original_price = order.original_price or order.plan.price
    commission_amount = (original_price * commission_rate) // 100

    with transaction.atomic():
        from shop.models import Order
        order = Order.objects.select_for_update().get(pk=order.pk)

        sale, created = AffiliateSale.objects.get_or_create(
            order=order,
            defaults={
                'affiliate': affiliate,
                'commission_rate': commission_rate,
                'commission_amount': commission_amount,
                'status': 'paid',
            },
        )
        if not created:
            return True

        if not order.affiliate_id:
            order.affiliate = affiliate
            order.save(update_fields=['affiliate'])

        wallet, _ = Wallet.objects.get_or_create(user=affiliate.user)
        wallet.add_balance(
            commission_amount,
            f'کمیسیون فروش — سفارش {order.id}',
            related_sale=sale,
        )
    return True


def ensure_buyer_affiliate_account(user) -> None:
    """Create affiliate + wallet for buyer after first paid order (existing behavior)."""
    from affiliates.models import Affiliate, Wallet

    if Affiliate.objects.filter(user=user).exists():
        return
    Affiliate.objects.create(user=user, is_active=True)
    Wallet.objects.get_or_create(user=user)
