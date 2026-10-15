"""وضعیت سفارش‌هایی که حق استفاده از لایسنس می‌دهند — بدون شمارش به‌عنوان خرید پولی."""
from __future__ import annotations

from shop.models import Order

# paid: خرید واقعی | granted: هدیه/کمپین (بدون درآمد و بدون has_purchased_bot_license)
LICENSE_ACCESS_ORDER_STATUSES = ('paid', 'granted')


def order_grants_license_access(order: Order | None) -> bool:
    if not order:
        return False
    return (order.status or '') in LICENSE_ACCESS_ORDER_STATUSES


def is_paid_commerce_order(order: Order | None) -> bool:
    """سفارش با پرداخت واقعی — برای BI، کمیسیون و has_purchased."""
    return bool(order and order.status == 'paid')
