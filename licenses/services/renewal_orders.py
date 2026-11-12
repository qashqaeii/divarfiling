"""تمدید چندلایسنسی — سفارش، قیمت، fulfillment و همگام‌سازی آژانس."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Sequence

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from licenses.models import AuditLog, License
from licenses.services.renewal import (
    _reactivate_status,
    _renewal_already_fulfilled,
    compute_renewed_expires_at,
    evaluate_license_renewal,
)
from shop.models import DiscountCode, Order, OrderRenewalItem
from shop.services.plan_pricing import calculate_plan_pricing


class RenewalOrderError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class RenewalFulfillmentError(Exception):
    """هیچ آیتم تمدیدی اعمال نشد — برای بازیابی از retry_renewal_fulfillment استفاده شود."""


def order_has_renewal_items(order: Order) -> bool:
    return OrderRenewalItem.objects.filter(order_id=order.pk).exists()


def order_is_renewal_commerce(order: Order) -> bool:
    """سفارش تمدید — نباید provisioning خرید آژانس روی آن اجرا شود."""
    if order.renewal_license_id:
        return True
    return order_has_renewal_items(order)


def licenses_renewable_qs(source_order: Order):
    return (
        License.objects.filter(order=source_order)
        .select_related('plan', 'order__product', 'assigned_user', 'agency_subscription')
        .order_by('sequence', 'pk')
    )


def list_renewable_licenses_for_source_order(user, source_order_id) -> dict[str, Any]:
    source_order = get_object_or_404(
        Order.objects.select_related('product', 'plan'),
        pk=source_order_id,
        user=user,
        status='paid',
    )
    rows = []
    renewable_ids = []
    for lic in licenses_renewable_qs(source_order):
        ok, message = evaluate_license_renewal(lic)
        rows.append({
            'id': lic.pk,
            'sequence': lic.sequence,
            'key_masked': _mask_key(lic.license_key),
            'status': lic.status,
            'expires_at': lic.expires_at,
            'can_renew': ok,
            'renew_block_reason': message if not ok else '',
            'assigned_user_id': lic.assigned_user_id,
            'assigned_name': (
                (lic.assigned_user.get_full_name() or lic.assigned_user.username)
                if lic.assigned_user_id else None
            ),
            'plan_name': lic.plan.name if lic.plan_id else source_order.plan.name,
        })
        if ok:
            renewable_ids.append(lic.pk)
    return {
        'source_order_id': str(source_order.id),
        'product_slug': source_order.product.slug,
        'product_title': source_order.product.title,
        'default_plan_id': source_order.plan_id,
        'license_count': len(rows),
        'renewable_count': len(renewable_ids),
        'licenses': rows,
        'is_agency_bulk_origin': bool(source_order.plan.allow_bulk_purchase),
    }


def _mask_key(key: str) -> str:
    key = (key or '').strip()
    if len(key) <= 8:
        return key
    return f'{key[:4]}…{key[-4:]}'


def _validate_license_selection(
    user,
    source_order: Order,
    license_ids: Sequence[int],
) -> list[License]:
    if not license_ids:
        raise RenewalOrderError('empty_selection', 'حداقل یک لایسنس انتخاب کنید.')
    unique_ids = sorted({int(x) for x in license_ids})
    licenses = list(
        License.objects.filter(
            pk__in=unique_ids,
            order=source_order,
            order__user=user,
            order__status='paid',
        ).select_related('plan', 'order__product', 'agency_subscription')
    )
    if len(licenses) != len(unique_ids):
        raise RenewalOrderError('invalid_selection', 'برخی لایسنس‌های انتخاب‌شده معتبر نیستند.')

    blocked = []
    for lic in licenses:
        ok, message = evaluate_license_renewal(lic)
        if not ok:
            blocked.append(message)
    if blocked:
        raise RenewalOrderError('not_renewable', blocked[0])
    return licenses


def quote_renewal_order(
    user,
    source_order_id,
    *,
    license_ids: Sequence[int],
    plan_id: int | None = None,
    discount_code_str: str = '',
    request=None,
) -> dict[str, Any]:
    source_order = get_object_or_404(
        Order.objects.select_related('product', 'plan'),
        pk=source_order_id,
        user=user,
        status='paid',
    )
    licenses = _validate_license_selection(user, source_order, license_ids)
    plan = source_order.plan
    if plan_id:
        plan = get_object_or_404(
            source_order.product.plans.filter(is_active=True),
            pk=int(plan_id),
        )
    if plan.product_id != source_order.product_id:
        raise RenewalOrderError('plan_mismatch', 'پلن با محصول سفارش همخوانی ندارد.')

    qty = len(licenses)
    discount_code = None
    code_str = (discount_code_str or '').strip().upper()
    if code_str:
        try:
            discount_code = DiscountCode.objects.get(code=code_str)
        except DiscountCode.DoesNotExist:
            raise RenewalOrderError('discount_not_found', 'کد تخفیف یافت نشد.')
        is_valid, message = discount_code.is_valid(user)
        if not is_valid:
            raise RenewalOrderError('discount_invalid', message)

    pricing = calculate_plan_pricing(
        plan,
        source_order.product,
        user,
        request=request,
        quantity=qty,
        discount_code=discount_code,
        for_renewal=True,
    )

    unit_orig = pricing['original_price'] // qty
    unit_disc = pricing['discount_amount'] // qty
    unit_final = pricing['final_price'] // qty
    items_preview = []
    for lic in licenses:
        new_expires = compute_renewed_expires_at(lic, plan)
        items_preview.append({
            'license_id': lic.pk,
            'sequence': lic.sequence,
            'key_masked': _mask_key(lic.license_key),
            'previous_expires_at': lic.expires_at,
            'new_expires_at': new_expires,
            'expires_is_estimate': True,
        })

    all_renewable = [
        lic.pk for lic in licenses_renewable_qs(source_order)
        if evaluate_license_renewal(lic)[0]
    ]
    selected_ids = {lic.pk for lic in licenses}
    is_full = bool(all_renewable) and selected_ids >= set(all_renewable)

    return {
        'source_order_id': str(source_order.id),
        'plan_id': plan.pk,
        'plan_name': plan.name,
        'quantity': qty,
        'pricing': {
            'original_price': int(pricing['original_price']),
            'discount_amount': int(pricing['discount_amount']),
            'final_price': int(pricing['final_price']),
            'unit_original_price': int(unit_orig),
            'unit_discount_amount': int(unit_disc),
            'unit_final_price': int(unit_final),
            'discount_reasons': pricing.get('discount_reasons') or [],
        },
        'items': items_preview,
        'is_full_source_order_renewal': is_full,
    }


def _split_amount(total: Decimal, count: int) -> list[Decimal]:
    """تقسیم مبلغ به واحدها — باقی‌مانده روی آخرین آیتم."""
    if count <= 0:
        return []
    base = total // count
    remainder = int(total - base * count)
    parts = [base] * count
    if remainder and count:
        parts[-1] += remainder
    return parts


@transaction.atomic
def create_renewal_order(
    user,
    source_order_id,
    *,
    license_ids: Sequence[int],
    plan_id: int | None = None,
    discount_code_str: str = '',
    request=None,
) -> Order:
    quote = quote_renewal_order(
        user,
        source_order_id,
        license_ids=license_ids,
        plan_id=plan_id,
        discount_code_str=discount_code_str,
        request=request,
    )
    source_order = Order.objects.select_related('product', 'plan').get(pk=source_order_id)
    licenses = _validate_license_selection(user, source_order, license_ids)
    plan = source_order.product.plans.get(pk=quote['plan_id'])

    discount_code = None
    code_str = (discount_code_str or '').strip().upper()
    if code_str:
        discount_code = DiscountCode.objects.get(code=code_str)
        is_valid, message = discount_code.is_valid(user)
        if not is_valid:
            raise RenewalOrderError('discount_invalid', message)

    qty = len(licenses)
    pricing = calculate_plan_pricing(
        plan,
        source_order.product,
        user,
        request=request,
        quantity=qty,
        discount_code=discount_code,
        for_renewal=True,
    )

    orig_parts = _split_amount(pricing['original_price'], qty)
    disc_parts = _split_amount(pricing['discount_amount'], qty)
    final_parts = _split_amount(pricing['final_price'], qty)

    order = Order.objects.create(
        user=user,
        product=source_order.product,
        plan=plan,
        quantity=qty,
        amount=pricing['final_price'],
        original_price=pricing['original_price'],
        discount_amount=pricing['discount_amount'],
        status='pending',
        discount_code=discount_code,
    )

    for idx, lic in enumerate(licenses):
        OrderRenewalItem.objects.create(
            order=order,
            license=lic,
            unit_original_price=orig_parts[idx],
            unit_discount_amount=disc_parts[idx],
            unit_final_price=final_parts[idx],
            previous_expires_at=lic.expires_at,
            # تخمین UI — تاریخ قطعی هنگام تأیید پرداخت با قفل لایسنس محاسبه می‌شود.
            new_expires_at=compute_renewed_expires_at(lic, plan),
        )
    return order


def _apply_renewal_to_license(
    order: Order,
    license_obj: License,
    *,
    new_expires,
) -> None:
    previous_expires = license_obj.expires_at
    previous_plan_id = license_obj.plan_id
    license_obj.plan = order.plan
    license_obj.max_activations = order.plan.max_activations
    license_obj.expires_at = new_expires
    if license_obj.status == 'expired':
        license_obj.status = _reactivate_status(license_obj)
    license_obj.save(update_fields=['plan', 'max_activations', 'expires_at', 'status'])
    AuditLog.objects.create(
        license=license_obj,
        action_type='activation',
        details={
            'event': 'license_renewed',
            'order_id': str(order.pk),
            'plan': order.plan.name,
            'previous_plan_id': previous_plan_id,
            'previous_expires_at': previous_expires.isoformat() if previous_expires else None,
            'new_expires_at': new_expires.isoformat() if new_expires else None,
            'renewal_mode': 'multi_item',
        },
    )


def sync_agency_subscription_after_renewal(
    order: Order,
    applied_items: Iterable[OrderRenewalItem],
) -> None:
    """
    پس از اعمال موفق تمدید: اشتراک آژانس = max(انقضای فعلی اشتراک، بیشترین انقضای اعمال‌شده).
    صندلی‌های تمدیدنشده تغییر نمی‌کنند؛ فقط تاریخ مدیریت برای مالک هم‌راستا می‌شود.
    """
    from collections import defaultdict

    from workspace.models import AgencySubscription
    from workspace.services.agency_entitlement import sync_agency_management_status

    by_sub: dict[int, list[OrderRenewalItem]] = defaultdict(list)
    for item in applied_items:
        if item.apply_status != OrderRenewalItem.ApplyStatus.APPLIED:
            continue
        sub_id = item.license.agency_subscription_id
        if sub_id and item.new_expires_at:
            by_sub[sub_id].append(item)

    now = timezone.now()
    for sub_id, group in by_sub.items():
        peak = max(i.new_expires_at for i in group if i.new_expires_at)
        sub = AgencySubscription.objects.select_for_update().get(pk=sub_id)
        if sub.owner_id != order.user_id:
            continue
        next_expires = peak
        if sub.expires_at:
            next_expires = max(sub.expires_at, peak)
        if next_expires <= sub.expires_at and sub.status == AgencySubscription.STATUS_ACTIVE:
            continue
        sub.expires_at = next_expires
        if next_expires > now:
            sub.status = AgencySubscription.STATUS_ACTIVE
        sub.save(update_fields=['expires_at', 'status', 'updated_at'])
        if sub.agency_id:
            sync_agency_management_status(sub.agency)


def _apply_single_renewal_item(
    locked_order: Order,
    item: OrderRenewalItem,
) -> License:
    license_obj = License.objects.select_for_update().get(pk=item.license_id)
    if locked_order.user_id != license_obj.order.user_id:
        raise PermissionDenied('سفارش تمدید به کاربر لایسنس تعلق ندارد.')

    if _renewal_already_fulfilled(locked_order, license_obj):
        if item.apply_status != OrderRenewalItem.ApplyStatus.APPLIED:
            item.apply_status = OrderRenewalItem.ApplyStatus.APPLIED
            item.applied_at = item.applied_at or timezone.now()
            item.apply_error = ''
            item.save(update_fields=['apply_status', 'applied_at', 'apply_error'])
        return license_obj

    new_expires = compute_renewed_expires_at(license_obj, locked_order.plan)
    _apply_renewal_to_license(locked_order, license_obj, new_expires=new_expires)
    item.apply_status = OrderRenewalItem.ApplyStatus.APPLIED
    item.applied_at = timezone.now()
    item.new_expires_at = new_expires
    item.apply_error = ''
    item.save(update_fields=[
        'apply_status', 'applied_at', 'new_expires_at', 'apply_error',
    ])
    return license_obj


@transaction.atomic
def fulfill_multi_renewal_for_paid_order(order: Order) -> list[License]:
    if order.status != 'paid':
        return []
    if not order_has_renewal_items(order):
        return []

    locked_order = Order.objects.select_for_update().get(pk=order.pk)
    items = list(
        OrderRenewalItem.objects.select_for_update()
        .filter(order=locked_order)
        .select_related('license', 'license__order', 'license__agency_subscription')
        .order_by('license_id')
    )
    if not items:
        return []

    renewed: list[License] = []
    had_actionable = False
    for item in items:
        if item.apply_status == OrderRenewalItem.ApplyStatus.APPLIED and item.applied_at:
            renewed.append(item.license)
            continue

        had_actionable = True
        sp = transaction.savepoint()
        try:
            lic = _apply_single_renewal_item(locked_order, item)
            transaction.savepoint_commit(sp)
            renewed.append(lic)
        except Exception as exc:
            transaction.savepoint_rollback(sp)
            OrderRenewalItem.objects.filter(pk=item.pk).update(
                apply_status=OrderRenewalItem.ApplyStatus.FAILED,
                apply_error=str(exc)[:500],
            )

    applied_items = list(
        OrderRenewalItem.objects.filter(
            order=locked_order,
            apply_status=OrderRenewalItem.ApplyStatus.APPLIED,
        ).select_related('license', 'license__agency_subscription')
    )
    if applied_items:
        sync_agency_subscription_after_renewal(locked_order, applied_items)

    if had_actionable and not renewed:
        raise RenewalFulfillmentError(
            'هیچ لایسنسی تمدید نشد؛ سفارش برای بازیابی قابل تلاش مجدد است.'
        )
    return renewed


def retry_renewal_fulfillment(order: Order) -> list[License]:
    """بازیابی امن تمدید — فقط آیتم‌های pending/failed؛ idempotent."""
    OrderRenewalItem.objects.filter(
        order=order,
        apply_status=OrderRenewalItem.ApplyStatus.FAILED,
    ).update(
        apply_status=OrderRenewalItem.ApplyStatus.PENDING,
        apply_error='',
    )
    return fulfill_multi_renewal_for_paid_order(order)
