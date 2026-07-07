"""
Affiliate discount rules for checkout.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from affiliates.services.referral import is_valid_attribution, resolve_order_affiliate


def affiliate_discount_eligible(user, product) -> bool:
    """Whether affiliate referral discount may apply for this purchase."""
    if not user or not user.is_authenticated:
        return False
    if not getattr(settings, 'AFFILIATE_DISCOUNT_ENABLED', True):
        return False
    affiliate = user.referred_by
    if not affiliate or not is_valid_attribution(user, affiliate):
        return False
    if getattr(settings, 'AFFILIATE_DISCOUNT_FIRST_ORDER_ONLY', True):
        from shop.models import Order
        if Order.objects.filter(user=user, product=product, status='paid').exists():
            return False
    return True


def apply_affiliate_discount(user, request, product, price_after_prior_discounts: Decimal) -> tuple[Decimal, Decimal, str | None]:
    """
    Apply affiliate discount on top of prior discounts.
    Returns (discount_amount, new_price, label_or_none).
    """
    affiliate = resolve_order_affiliate(user, request)
    if not affiliate or not is_valid_attribution(user, affiliate):
        return Decimal('0'), price_after_prior_discounts, None

    if not affiliate_discount_eligible(user, product):
        return Decimal('0'), price_after_prior_discounts, None

    rate = affiliate.discount_percentage or Decimal(str(settings.AFFILIATE_DEFAULT_DISCOUNT))
    if rate <= 0:
        return Decimal('0'), price_after_prior_discounts, None

    discount_amount = (price_after_prior_discounts * rate) // 100
    new_price = max(Decimal('0'), price_after_prior_discounts - discount_amount)
    label = f'{int(rate)}٪ تخفیف معرف ({affiliate.code})'
    return discount_amount, new_price, label
