"""اعمال کد تخفیف روی سفارش معلق — server-side."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.db import transaction

from shop.models import DiscountCode, Order
from shop.services.discount_consumption import (
    DiscountCapacityError,
    assert_discount_capacity,
    order_payment_amount_locked,
)
from shop.services.plan_pricing import calculate_plan_pricing


class OrderDiscountError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _paid_revenue_statuses():
    return ('paid',)


def preview_discount_code_for_order(
    order: Order,
    user,
    code_str: str,
    *,
    request=None,
) -> Dict[str, Any]:
    """پیش‌نمایش قیمت — بدون تغییر سفارش."""
    code_str = (code_str or '').strip().upper()
    if not code_str:
        raise OrderDiscountError('empty_code', 'کد تخفیف وارد نشده است.')
    if order.user_id != getattr(user, 'pk', None):
        raise OrderDiscountError('forbidden', 'این سفارش متعلق به شما نیست.')
    try:
        discount_code = DiscountCode.objects.get(code=code_str)
    except DiscountCode.DoesNotExist:
        raise OrderDiscountError('not_found', 'کد تخفیف یافت نشد.')
    is_valid, message = discount_code.is_valid(user)
    if not is_valid:
        raise OrderDiscountError('invalid', message)
    base_pricing = calculate_plan_pricing(
        order.plan, order.product, user,
        request=request, quantity=order.quantity or 1,
    )
    pricing = calculate_plan_pricing(
        order.plan, order.product, user,
        request=request, quantity=order.quantity or 1,
        discount_code=discount_code,
    )
    if pricing['final_price'] >= base_pricing['final_price']:
        raise OrderDiscountError('no_effect', 'کد تخفیف قابل اعمال نیست.')
    return {
        'code': discount_code.code,
        'final_price': int(pricing['final_price']),
        'discount_amount': int(pricing['discount_amount']),
        'original_price': int(pricing['original_price']),
    }


def apply_discount_code_to_pending_order(
    order: Order,
    user,
    code_str: str,
    *,
    request=None,
) -> Tuple[Order, bool]:
    """
    قیمت سفارش pending/failed را با کد تخفیف به‌روز می‌کند.
    Returns (order, changed).
    """
    code_str = (code_str or '').strip().upper()
    if not code_str:
        raise OrderDiscountError('empty_code', 'کد تخفیف وارد نشده است.')

    if order.user_id != getattr(user, 'pk', None):
        raise OrderDiscountError('forbidden', 'این سفارش متعلق به شما نیست.')

    if order.status in _paid_revenue_statuses():
        raise OrderDiscountError('paid', 'سفارش پرداخت‌شده قابل تغییر نیست.')

    if order.status == 'pending_verification':
        raise OrderDiscountError(
            'pending_verification',
            'سفارش در انتظار تأیید کارت‌به‌کارت است؛ ابتدا وضعیت پرداخت را مشخص کنید.',
        )

    if order.status not in ('pending', 'failed'):
        raise OrderDiscountError('not_payable', 'این سفارش قابل اعمال تخفیف نیست.')

    try:
        discount_code = DiscountCode.objects.get(code=code_str)
    except DiscountCode.DoesNotExist:
        raise OrderDiscountError('not_found', 'کد تخفیف یافت نشد.')

    preview = preview_discount_code_for_order(order, user, code_str, request=request)

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status in _paid_revenue_statuses():
            raise OrderDiscountError('paid', 'سفارش پرداخت‌شده قابل تغییر نیست.')
        if locked.status not in ('pending', 'failed'):
            raise OrderDiscountError('not_payable', 'این سفارش قابل اعمال تخفیف نیست.')
        if order_payment_amount_locked(locked):
            raise OrderDiscountError(
                'payment_locked',
                'پس از شروع پرداخت درگاه، امکان تغییر مبلغ یا کد تخفیف وجود ندارد.',
            )

        try:
            assert_discount_capacity(discount_code, user=user, order=locked)
        except DiscountCapacityError as exc:
            raise OrderDiscountError(exc.code, exc.message) from exc

        locked.original_price = preview['original_price']
        locked.discount_amount = preview['discount_amount']
        locked.amount = preview['final_price']
        locked.discount_code = discount_code
        if locked.status == 'failed':
            locked.status = 'pending'
        locked.save(
            update_fields=[
                'original_price',
                'discount_amount',
                'amount',
                'discount_code',
                'status',
            ],
        )
    locked.refresh_from_db()
    return locked, True


def resolve_discount_code_for_buy(
    user,
    code_str: str,
) -> Tuple[Optional[DiscountCode], str]:
    """اعتبارسنجی کد برای صفحه خرید (بدون سفارش)."""
    code_str = (code_str or '').strip().upper()
    if not code_str:
        return None, ''
    try:
        discount_code = DiscountCode.objects.get(code=code_str)
    except DiscountCode.DoesNotExist:
        return None, 'کد تخفیف یافت نشد.'
    is_valid, message = discount_code.is_valid(user)
    if not is_valid:
        return None, message
    return discount_code, ''
