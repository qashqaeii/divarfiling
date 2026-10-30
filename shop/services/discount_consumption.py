"""رزرو و مصرف اتمیک کد تخفیف — جلوگیری از race و over-use."""
from __future__ import annotations

from django.db import transaction
from django.db.models import F

from shop.models import DiscountCode, Order


class DiscountCapacityError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def order_payment_amount_locked(order: Order) -> bool:
    """پس از شروع تراکنش درگاه، مبلغ سفارش نباید تغییر کند."""
    if (getattr(order, 'zibal_track_id', None) or '').strip():
        return True
    try:
        tx = order.transaction
    except Exception:
        return False
    return bool(tx and tx.status in ('pending', 'paid'))


def _pending_statuses():
    return ('pending', 'pending_verification', 'failed')


def assert_discount_capacity(
    discount_code: DiscountCode,
    *,
    user,
    order: Order | None = None,
) -> None:
    """بررسی ظرفیت کد با قفل row — قبل از attach به سفارش."""
    is_valid, message = discount_code.is_valid(user)
    if not is_valid:
        raise DiscountCapacityError('invalid', message)

    with transaction.atomic():
        dc = DiscountCode.objects.select_for_update().get(pk=discount_code.pk)
        exclude_pk = order.pk if order else None
        other_holders = Order.objects.filter(
            discount_code_id=dc.pk,
            status__in=_pending_statuses(),
        )
        if exclude_pk:
            other_holders = other_holders.exclude(pk=exclude_pk)
        pending_holders = other_holders.count()

        if dc.max_uses is not None:
            if dc.used_count + pending_holders >= dc.max_uses:
                raise DiscountCapacityError(
                    'exhausted',
                    'کد تخفیف به پایان رسیده است.',
                )
            if dc.max_uses == 1 and pending_holders > 0:
                raise DiscountCapacityError(
                    'exhausted',
                    'این کد تخفیف روی سفارش دیگری در حال استفاده است.',
                )


def finalize_discount_consumption(order: Order) -> None:
    """مصرف نهایی کد پس از paid — با قفل row."""
    if not order.discount_code_id:
        return

    with transaction.atomic():
        dc = DiscountCode.objects.select_for_update().get(pk=order.discount_code_id)
        if dc.max_uses is not None and dc.used_count >= dc.max_uses:
            raise DiscountCapacityError(
                'exhausted_at_pay',
                'کد تخفیف دیگر قابل مصرف نیست.',
            )
        DiscountCode.objects.filter(pk=dc.pk).update(used_count=F('used_count') + 1)
