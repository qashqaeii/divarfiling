"""بازیابی تکمیل سفارش پس از پرداخت — جدا از ثبت paid."""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from licenses.models import License
from licenses.services.renewal_orders import (
    RenewalFulfillmentError,
    order_has_renewal_items,
    order_is_renewal_commerce,
    refresh_fulfillment_status,
    retry_renewal_fulfillment,
)
from shop.models import Order, OrderRenewalItem, Transaction

logger = logging.getLogger(__name__)


def _needs_fulfillment_tracking(order: Order) -> bool:
    return order_is_renewal_commerce(order)


def mark_order_paid_after_gateway(
    order: Order,
    *,
    record_funnel: bool = True,
) -> Order:
    """ثبت paid و اقدامات مالی — بدون صدور لایسنس (همیشه commit)."""
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        already_paid = locked.status == 'paid'

        if not already_paid:
            locked.status = 'paid'
            locked.paid_at = timezone.now()
            if _needs_fulfillment_tracking(locked):
                locked.fulfillment_status = Order.FulfillmentStatus.PENDING
                locked.fulfillment_error = ''
            else:
                locked.fulfillment_status = Order.FulfillmentStatus.PENDING
            locked.save(update_fields=[
                'status', 'paid_at', 'fulfillment_status', 'fulfillment_error',
            ])

            if locked.discount_code_id:
                from shop.services.discount_consumption import (
                    DiscountCapacityError,
                    finalize_discount_consumption,
                )

                try:
                    finalize_discount_consumption(locked)
                except DiscountCapacityError:
                    raise

            from affiliates.services.commission import (
                ensure_buyer_affiliate_account,
                record_affiliate_commission,
            )

            record_affiliate_commission(locked)
            ensure_buyer_affiliate_account(locked.user)

        if record_funnel:
            from shop.services.plan_funnel import ensure_payment_success_event
            ensure_payment_success_event(locked)

        return locked


def complete_order_fulfillment(order: Order) -> Optional[License]:
    """
    صدور لایسنس / تمدید — idempotent.
    paid از قبل commit شده؛ خطا وضعیت fulfillment را به‌روز می‌کند، paid را برنمی‌گرداند.
    """
    from licenses.services.claim import issue_license_for_paid_order
    from workspace.services.agency_entitlement import (
        is_agency_plan_order,
        provision_subscription_from_paid_order,
    )

    order = Order.objects.select_related('plan', 'product').get(pk=order.pk)
    if order.status != 'paid':
        return None

    if order.fulfillment_status == Order.FulfillmentStatus.COMPLETE:
        return issue_license_for_paid_order(order)

    license_obj: Optional[License] = None
    error_message = ''

    try:
        license_obj = issue_license_for_paid_order(order)
        if is_agency_plan_order(order) and not order_is_renewal_commerce(order):
            provision_subscription_from_paid_order(order)
    except RenewalFulfillmentError as exc:
        error_message = str(exc)
        logger.error('renewal fulfillment incomplete order_id=%s: %s', order.pk, exc)
    except Exception:
        error_message = 'خطا در تکمیل سفارش'
        logger.exception('order fulfillment failed order_id=%s', order.pk)

    refresh_fulfillment_status(order, error_message=error_message)
    order.refresh_from_db(fields=['fulfillment_status', 'fulfillment_error'])
    if order.fulfillment_status == Order.FulfillmentStatus.COMPLETE:
        return license_obj or issue_license_for_paid_order(order)
    return license_obj


def _first_license_from_list(licenses: list[License]) -> Optional[License]:
    return licenses[0] if licenses else None


def orders_needing_fulfillment_reconcile_qs():
    return Order.objects.filter(
        status='paid',
        fulfillment_status__in=[
            Order.FulfillmentStatus.PENDING,
            Order.FulfillmentStatus.PARTIAL,
            Order.FulfillmentStatus.FAILED,
        ],
    ).order_by('paid_at', 'pk')


def reconcile_order_fulfillment(order: Order) -> Optional[License]:
    """تلاش مجدد تکمیل — برای کرون یا ادمین."""
    from licenses.services.claim import issue_license_for_paid_order

    if order.status != 'paid':
        return None
    if order.fulfillment_status == Order.FulfillmentStatus.COMPLETE:
        return issue_license_for_paid_order(order)
    if order_has_renewal_items(order):
        try:
            renewed = retry_renewal_fulfillment(order)
            refresh_fulfillment_status(order)
            return _first_license_from_list(renewed)
        except RenewalFulfillmentError as exc:
            refresh_fulfillment_status(order, error_message=str(exc))
            logger.error('reconcile renewal failed order_id=%s', order.pk)
            return None
    return complete_order_fulfillment(order)


def reconcile_gateway_payment_mismatch(*, limit: int = 50) -> int:
    """
    تراکنش درگاه paid ولی سفارش هنوز paid نشده — verify مجدد و همگام‌سازی.
    """
    from shop.services import zibal as zibal_service

    qs = (
        Transaction.objects.filter(status='paid', order__payment_method='zibal')
        .exclude(order__status='paid')
        .exclude(zibal_track_id__startswith='CARD-')
        .select_related('order')
        .order_by('created_at', 'pk')[:limit]
    )
    fixed = 0
    for tx in qs:
        order = tx.order
        try:
            expected = zibal_service.toman_to_rial(order.amount)
            zibal_service.verify_payment(track_id=tx.zibal_track_id, expected_amount_rial=expected)
        except zibal_service.ZibalVerifyError:
            logger.warning(
                'reconcile skip: gateway not successful order_id=%s track=%s',
                order.pk, tx.zibal_track_id,
            )
            continue
        except Exception:
            logger.exception('reconcile verify failed order_id=%s', order.pk)
            continue

        try:
            mark_order_paid_after_gateway(order, record_funnel=False)
            tx.verified_at = tx.verified_at or timezone.now()
            tx.save(update_fields=['verified_at'])
        except Exception:
            logger.exception('reconcile payment update failed order_id=%s', order.pk)
            continue

        # The payment state is now repaired. A provisioning failure must not
        # hide that fact or stop reconciliation of other paid transactions.
        fixed += 1
        try:
            complete_order_fulfillment(order)
        except Exception:
            logger.exception('reconcile fulfillment failed order_id=%s', order.pk)
    return fixed


def run_fulfillment_reconcile_batch(*, limit: int = 100) -> dict[str, int]:
    """اجرای دوره‌ای: ناهمگامی درگاه + سفارش‌های paid ناقص."""
    stats = {
        'gateway_mismatch_fixed': reconcile_gateway_payment_mismatch(limit=min(limit, 50)),
        'fulfillment_retried': 0,
        'fulfillment_completed': 0,
    }
    for order in orders_needing_fulfillment_reconcile_qs()[:limit]:
        before = order.fulfillment_status
        # Count attempts even when one order fails; never let a malformed
        # legacy renewal prevent subsequent paid customers from receiving
        # their entitlements. Leave failed orders for the next bounded run.
        stats['fulfillment_retried'] += 1
        try:
            reconcile_order_fulfillment(order)
            order.refresh_from_db(fields=['fulfillment_status'])
        except Exception:
            logger.exception('fulfillment reconcile failed order_id=%s', order.pk)
            continue
        if order.fulfillment_status == Order.FulfillmentStatus.COMPLETE and before != Order.FulfillmentStatus.COMPLETE:
            stats['fulfillment_completed'] += 1
    return stats
