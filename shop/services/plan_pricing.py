"""محاسبه قیمت پلن — آفر ویژه، تخفیف وفاداری، معرف و کد تخفیف."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest

    from shop.models import DiscountCode, LicensePlan, Product


def _as_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def plan_unit_list_price(plan: LicensePlan) -> Decimal:
    """قیمت واحد قبل از تخفیف‌های سفارش (نمایش خط‌خورده)."""
    compare_at = getattr(plan, 'compare_at_price', None)
    if compare_at and compare_at > plan.price:
        return _as_decimal(compare_at)
    return _as_decimal(plan.price)


def plan_unit_sale_price(plan: LicensePlan) -> Decimal:
    """قیمت واحد فروش پلن (قبل از تخفیف‌های سطح سفارش)."""
    return _as_decimal(plan.price)


def clamp_quantity(plan: LicensePlan, quantity: int) -> int:
    qty = max(1, int(quantity or 1))
    if not getattr(plan, 'allow_bulk_purchase', False):
        return 1
    min_q = max(1, int(getattr(plan, 'min_quantity', 1) or 1))
    max_q = max(min_q, int(getattr(plan, 'max_quantity', 20) or 20))
    return max(min_q, min(max_q, qty))


def calculate_plan_purchase_prices(
    plan: LicensePlan,
    product: Product,
    user,
    *,
    request: HttpRequest | None = None,
    quantity: int = 1,
    discount_code: DiscountCode | None = None,
) -> dict:
    """
    محاسبه قیمت خرید یک پلن.

    original_price: مبلغ لیست (compare_at × تعداد)
    final_price: مبلغ نهایی پس از همه تخفیف‌ها
    """
    from shop.models import Order

    qty = clamp_quantity(plan, quantity)
    unit_list = plan_unit_list_price(plan)
    unit_sale = plan_unit_sale_price(plan)

    original_price = unit_list * qty
    price_after_discounts = unit_sale * qty
    discount_amount = max(Decimal('0'), original_price - price_after_discounts)
    discount_reasons: list[str] = []

    if plan.has_promo_offer():
        pct = plan.promo_discount_percent()
        if pct:
            discount_reasons.append(f'{pct}% آفر ویژه')

    has_previous_purchase = False
    if user and getattr(user, 'is_authenticated', False):
        has_previous_purchase = Order.objects.filter(
            user=user,
            product=product,
            status='paid',
        ).exists()

    if has_previous_purchase and product.repeat_purchase_discount > 0:
        repeat_discount_percentage = _as_decimal(product.repeat_purchase_discount)
        repeat_discount = (price_after_discounts * repeat_discount_percentage) // 100
        if repeat_discount > 0:
            discount_amount += repeat_discount
            price_after_discounts -= repeat_discount
            discount_reasons.append(f'{int(repeat_discount_percentage)}% تخفیف خرید مجدد')

    if user and getattr(user, 'is_authenticated', False) and request is not None:
        from affiliates.services import apply_affiliate_discount

        aff_disc, price_after_discounts, aff_label = apply_affiliate_discount(
            user, request, product, price_after_discounts
        )
        if aff_disc > 0:
            discount_amount += _as_decimal(aff_disc)
            if aff_label:
                discount_reasons.append(aff_label)

    if discount_code:
        code_discount, _message = discount_code.calculate_discount(price_after_discounts, user)
        if code_discount > 0:
            discount_amount += _as_decimal(code_discount)
            price_after_discounts -= _as_decimal(code_discount)
            if discount_code.discount_type == 'percentage':
                discount_reasons.append(f'{int(discount_code.discount_value)}% کد تخفیف')
            else:
                discount_reasons.append('کد تخفیف')

    final_price = max(Decimal('0'), price_after_discounts)

    return {
        'quantity': qty,
        'unit_list_price': unit_list,
        'unit_sale_price': unit_sale,
        'original_price': original_price,
        'discount_amount': discount_amount,
        'final_price': final_price,
        'has_discount': discount_amount > 0,
        'has_promo_offer': plan.has_promo_offer(),
        'has_repeat_discount': has_previous_purchase and product.repeat_purchase_discount > 0,
        'repeat_discount_percentage': int(product.repeat_purchase_discount) if has_previous_purchase else 0,
        'discount_reasons': discount_reasons,
    }
