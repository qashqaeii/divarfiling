"""محاسبه قیمت پلن — آفر ویژه، تخفیف آژانس، وفاداری، معرف و کد تخفیف."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest

    from shop.models import DiscountCode, LicensePlan, Product

# qty min, qty max, discount percent — فقط برای پلن آژانس
AGENCY_BULK_DISCOUNT_TIERS = (
    (2, 2, Decimal('10')),
    (3, 5, Decimal('15')),
    (6, 10, Decimal('20')),
    (11, 25, Decimal('25')),
)

AGENCY_MIN_QUANTITY = 2
AGENCY_MAX_QUANTITY = 25


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


def get_agency_bulk_discount_percent(quantity: int) -> Decimal:
    """درصد تخفیف حجمی آژانس بر اساس تعداد مشاور."""
    qty = int(quantity or 0)
    for min_q, max_q, pct in AGENCY_BULK_DISCOUNT_TIERS:
        if min_q <= qty <= max_q:
            return pct
    return Decimal('0')


def clamp_quantity(plan: LicensePlan, quantity: int) -> int:
    qty = max(1, int(quantity or 1))
    if not getattr(plan, 'allow_bulk_purchase', False):
        return 1
    min_q = max(AGENCY_MIN_QUANTITY, int(getattr(plan, 'min_quantity', AGENCY_MIN_QUANTITY) or AGENCY_MIN_QUANTITY))
    max_q = max(min_q, int(getattr(plan, 'max_quantity', AGENCY_MAX_QUANTITY) or AGENCY_MAX_QUANTITY))
    return max(min_q, min(max_q, qty))


def _repeat_discount_percent(product: Product, user, *, has_previous_purchase: bool | None = None) -> Decimal:
    if has_previous_purchase is None:
        from shop.models import Order

        has_previous_purchase = bool(
            user
            and getattr(user, 'is_authenticated', False)
            and Order.objects.filter(user=user, product=product, status='paid').exists()
        )
    if not has_previous_purchase:
        return Decimal('0')
    return _as_decimal(product.repeat_purchase_discount)


def _applied_discount(
    plan: LicensePlan,
    *,
    quantity: int,
    bulk_pct: Decimal,
    repeat_pct: Decimal,
) -> tuple[Decimal, str, Decimal, Decimal]:
    """(applied_pct, reason, bulk_pct, repeat_pct) — bulk و repeat stack نمی‌شوند."""
    if plan.allow_bulk_purchase:
        if bulk_pct >= repeat_pct and bulk_pct > 0:
            return bulk_pct, f'تخفیف آژانس {int(bulk_pct)}٪', bulk_pct, repeat_pct
        if repeat_pct > bulk_pct:
            return repeat_pct, f'تخفیف خرید مجدد {int(repeat_pct)}٪', bulk_pct, repeat_pct
        if repeat_pct > 0:
            return repeat_pct, f'تخفیف خرید مجدد {int(repeat_pct)}٪', bulk_pct, repeat_pct
        return Decimal('0'), '', bulk_pct, repeat_pct

    if repeat_pct > 0:
        return repeat_pct, f'تخفیف خرید مجدد {int(repeat_pct)}٪', Decimal('0'), repeat_pct
    return Decimal('0'), '', Decimal('0'), repeat_pct


def _renewal_quantity(plan: LicensePlan, quantity: int) -> int:
    """تعداد واقعی انتخاب‌شده برای تمدید — بدون bump به حداقل bulk."""
    qty = max(1, int(quantity or 1))
    if not getattr(plan, 'allow_bulk_purchase', False):
        return qty
    max_q = max(
        AGENCY_MIN_QUANTITY,
        int(getattr(plan, 'max_quantity', AGENCY_MAX_QUANTITY) or AGENCY_MAX_QUANTITY),
    )
    return min(max_q, qty)


def calculate_plan_pricing(
    plan: LicensePlan,
    product: Product,
    user,
    *,
    request: HttpRequest | None = None,
    quantity: int = 1,
    discount_code: DiscountCode | None = None,
    for_renewal: bool = False,
) -> dict:
    """
    محاسبه مرکزی قیمت — source of truth برای وب، API و checkout.

    bulk/repeat: applied = max(bulk, repeat) — بدون stack
    bulk روی plan.price محاسبه می‌شود، نه compare_at_price.
    for_renewal=True: tier حجمی فقط وقتی quantity >= min_quantity پلن آژانس.
    """
    from shop.models import Order

    qty = _renewal_quantity(plan, quantity) if for_renewal else clamp_quantity(plan, quantity)
    base_unit_price = plan_unit_sale_price(plan)
    unit_list = plan_unit_list_price(plan)

    has_previous_purchase = False
    if user and getattr(user, 'is_authenticated', False):
        has_previous_purchase = Order.objects.filter(
            user=user,
            product=product,
            status='paid',
        ).exists()

    repeat_pct = _repeat_discount_percent(product, user, has_previous_purchase=has_previous_purchase)
    if plan.allow_bulk_purchase:
        min_q = max(AGENCY_MIN_QUANTITY, int(getattr(plan, 'min_quantity', AGENCY_MIN_QUANTITY) or AGENCY_MIN_QUANTITY))
        if for_renewal and qty < min_q:
            bulk_pct = Decimal('0')
        else:
            bulk_pct = get_agency_bulk_discount_percent(qty)
    else:
        bulk_pct = Decimal('0')
    applied_pct, applied_reason, bulk_pct, repeat_pct = _applied_discount(
        plan,
        quantity=qty,
        bulk_pct=bulk_pct,
        repeat_pct=repeat_pct,
    )

    if plan.allow_bulk_purchase:
        original_price = base_unit_price * qty
        effective_unit_price = base_unit_price * (Decimal('100') - applied_pct) // Decimal('100')
        price_after_discounts = effective_unit_price * qty
    else:
        original_price = unit_list * qty
        unit_after_promo = base_unit_price
        subtotal = unit_after_promo * qty
        if applied_pct > 0:
            volume_off = subtotal * applied_pct // Decimal('100')
            price_after_discounts = subtotal - volume_off
            effective_unit_price = price_after_discounts // qty if qty else subtotal
        else:
            price_after_discounts = subtotal
            effective_unit_price = unit_after_promo

    discount_amount = max(Decimal('0'), original_price - price_after_discounts)
    discount_reasons: list[str] = []

    if plan.has_promo_offer() and not plan.allow_bulk_purchase:
        pct = plan.promo_discount_percent()
        if pct:
            discount_reasons.append(f'{pct}% آفر ویژه')

    if applied_reason:
        discount_reasons.append(applied_reason)

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
    max_act = int(getattr(plan, 'max_activations', 2) or 2)

    return {
        'quantity': qty,
        'base_unit_price': base_unit_price,
        'unit_list_price': unit_list,
        'unit_sale_price': base_unit_price,
        'bulk_discount_percent': int(bulk_pct),
        'repeat_discount_percent': int(repeat_pct),
        'applied_discount_percent': int(applied_pct),
        'applied_discount_reason': applied_reason,
        'effective_unit_price': effective_unit_price,
        'original_price': original_price,
        'discount_amount': discount_amount,
        'final_price': final_price,
        'total_price': final_price,
        'has_discount': discount_amount > 0,
        'has_promo_offer': plan.has_promo_offer() and not plan.allow_bulk_purchase,
        'has_repeat_discount': repeat_pct > 0,
        'has_bulk_discount': bulk_pct > 0,
        'repeat_discount_percentage': int(repeat_pct),
        'discount_reasons': discount_reasons,
        'licenses_count': qty,
        'total_activation_slots': qty * max_act,
    }


def calculate_plan_purchase_prices(
    plan: LicensePlan,
    product: Product,
    user,
    *,
    request: HttpRequest | None = None,
    quantity: int = 1,
    discount_code: DiscountCode | None = None,
) -> dict:
    """سازگاری با کد قدیمی — همان calculate_plan_pricing."""
    return calculate_plan_pricing(
        plan,
        product,
        user,
        request=request,
        quantity=quantity,
        discount_code=discount_code,
    )


def serialize_pricing_for_api(pricing: dict) -> dict:
    """خروجی JSON-safe برای API موبایل."""
    return {
        'quantity': int(pricing['quantity']),
        'base_unit_price': int(pricing['base_unit_price']),
        'unit_original_price': int(pricing['original_price'] // pricing['quantity']) if pricing['quantity'] else int(pricing['original_price']),
        'unit_final_price': int(pricing['effective_unit_price']),
        'effective_unit_price': int(pricing['effective_unit_price']),
        'original_price': int(pricing['original_price']),
        'discount_amount': int(pricing['discount_amount']),
        'final_price': int(pricing['final_price']),
        'total_price': int(pricing['final_price']),
        'bulk_discount_percent': int(pricing['bulk_discount_percent']),
        'repeat_discount_percent': int(pricing['repeat_discount_percent']),
        'applied_discount_percent': int(pricing['applied_discount_percent']),
        'applied_discount_reason': pricing['applied_discount_reason'] or '',
        'licenses_count': int(pricing['licenses_count']),
        'total_activation_slots': int(pricing['total_activation_slots']),
        'has_discount': bool(pricing['has_discount']),
    }
