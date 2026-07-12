"""سفارش‌های پرداخت‌نشده — کوئری مشترک با حذف تکرار کاربر."""
from __future__ import annotations

from django.db.models import F, OuterRef, QuerySet, Subquery

from shop.models import Order

PENDING_ORDER_STATUSES = ('pending', 'pending_verification')


def pending_orders_queryset(*, dedupe_by_user: bool = True) -> QuerySet:
    """
    سفارش‌های معلق.

    dedupe_by_user=True فقط **آخرین سفارش معلق** هر کاربر را برمی‌گرداند
    تا یک کاربر چندبار در لیست داشبورد دیده نشود.
    """
    qs = Order.objects.filter(status__in=PENDING_ORDER_STATUSES)
    if not dedupe_by_user:
        return qs

    latest_for_user = (
        Order.objects.filter(
            status__in=PENDING_ORDER_STATUSES,
            user=OuterRef('user'),
        )
        .order_by('-created_at')
        .values('id')[:1]
    )
    return qs.annotate(_latest_pending_id=Subquery(latest_for_user)).filter(
        id=F('_latest_pending_id'),
    )


def get_pending_orders_for_display(limit: int = 20) -> QuerySet:
    """لیست نمایش داشبورد — یک ردیف به ازای هر کاربر."""
    return (
        pending_orders_queryset(dedupe_by_user=True)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:limit]
    )
