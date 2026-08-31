"""پلن، سفارش و وضعیت پرداخت برای کلاینت موبایل — منطق فروشگاه وب."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from licenses.services.renewal import evaluate_license_renewal, get_renewable_license_for_user
from shop.bot_catalog import get_bot_product
from shop.models import DiscountCode, LicensePlan, Order, PaymentSettings
from shop.services.mobile_checkout import mark_mobile_checkout
from shop.services.plan_guards import evaluate_plan_purchase, is_daily_plan, is_plan_visible_in_catalog, user_has_purchased_daily_plan
from shop.services.plan_pricing import calculate_plan_purchase_prices, clamp_quantity
from shop.services import zibal as zibal_service


class MobileShopError(Exception):
    def __init__(self, message: str, *, code: str = 'SHOP_ERROR', status: int = 400):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(message)


def _plan_duration_label(plan: LicensePlan) -> str:
    days = int(getattr(plan, 'duration_days', 0) or 0)
    plan_type = (plan.plan_type or '').strip()
    if plan_type == 'daily':
        return '۷ روز'
    if plan_type == 'monthly':
        return '۱ ماه'
    if plan_type == 'quarterly':
        return '۳ ماه'
    if plan_type == 'yearly':
        return '۱ سال'
    if days:
        return f'{days} روز'
    return plan.get_plan_type_display() if hasattr(plan, 'get_plan_type_display') else plan_type


def _parse_quantity(plan: LicensePlan, raw, *, renewal: bool = False) -> int:
    if renewal:
        return 1
    try:
        qty = int(raw or 1)
    except (TypeError, ValueError):
        qty = 1
    return clamp_quantity(plan, qty)


def list_mobile_plans(user) -> Dict[str, Any]:
    product = get_bot_product()
    if product is None:
        product = (
            __import__('shop.models', fromlist=['Product']).Product.objects.filter(is_active=True).first()
        )
    if product is None:
        raise MobileShopError('محصول لایسنس در حال حاضر در دسترس نیست.', code='PRODUCT_UNAVAILABLE', status=404)

    plans = []
    for plan in product.plans.filter(is_active=True).order_by('order', 'price'):
        if not is_plan_visible_in_catalog(user, plan):
            continue
        purchase_ok, purchase_message, purchase_reason = evaluate_plan_purchase(user, plan)
        pricing = calculate_plan_purchase_prices(plan, product, user, quantity=1)
        plans.append({
            'id': plan.pk,
            'name': plan.name,
            'plan_type': plan.plan_type,
            'duration_days': plan.duration_days,
            'duration_label': _plan_duration_label(plan),
            'tagline': (plan.tagline or '').strip(),
            'features': plan.normalized_features() if hasattr(plan, 'normalized_features') else [],
            'original_price': int(pricing['original_price']),
            'final_price': int(pricing['final_price']),
            'unit_original_price': int(pricing['original_price']),
            'unit_final_price': int(pricing['final_price']),
            'discount_amount': int(pricing['discount_amount']),
            'has_discount': bool(pricing['has_discount']),
            'is_featured': bool(plan.is_featured),
            'offer_badge': (plan.offer_badge or '').strip(),
            'allow_bulk_purchase': bool(getattr(plan, 'allow_bulk_purchase', False)),
            'min_quantity': int(getattr(plan, 'min_quantity', 1) or 1),
            'max_quantity': int(getattr(plan, 'max_quantity', 1) or 1),
            'purchase_blocked': not purchase_ok,
            'purchase_block_message': purchase_message or '',
            'purchase_block_reason': purchase_reason or '',
        })

    renewable = None
    from workspace.services.access import _paid_license_qs

    lic = _paid_license_qs(user).select_related('plan', 'order').order_by('-expires_at').first()
    if lic:
        ok, _msg = evaluate_license_renewal(lic)
        if ok:
            renewable = {
                'license_id': lic.pk,
                'plan': lic.plan.name if lic.plan_id else None,
                'expires_at': lic.expires_at.isoformat() if lic.expires_at else None,
                'is_expired': lic.status == 'expired',
            }

    return {
        'product_slug': product.slug,
        'product_name': product.title,
        'plans': plans,
        'renewable_license': renewable,
        'phone_verified': bool(getattr(user, 'phone_verified', False)),
    }


def _reuse_pending_order(user, plan: LicensePlan, renewal_license, quantity: int = 1) -> Optional[Order]:
    since = timezone.now() - timedelta(hours=2)
    qs = Order.objects.filter(
        user=user,
        plan=plan,
        quantity=quantity,
        status='pending',
        created_at__gte=since,
        payment_method='zibal',
    )
    if renewal_license:
        qs = qs.filter(renewal_license=renewal_license)
    else:
        qs = qs.filter(renewal_license__isnull=True)
    return qs.order_by('-created_at').first()


def _resolve_discount_code(user, code: Optional[str]):
    raw = (code or '').strip().upper()
    if not raw:
        return None
    try:
        obj = DiscountCode.objects.get(code=raw)
    except DiscountCode.DoesNotExist:
        raise MobileShopError('کد تخفیف یافت نشد.', code='DISCOUNT_INVALID')
    is_valid, error_msg = obj.is_valid(user)
    if not is_valid:
        raise MobileShopError(error_msg or 'کد تخفیف نامعتبر است.', code='DISCOUNT_INVALID')
    return obj


def preview_plan_discount(user, *, plan_id: int, discount_code: str, quantity: int = 1, request=None) -> Dict[str, Any]:
    product = get_bot_product()
    if product is None:
        raise MobileShopError('محصول لایسنس در حال حاضر در دسترس نیست.', code='PRODUCT_UNAVAILABLE', status=404)
    plan = product.plans.filter(pk=plan_id, is_active=True).first()
    if plan is None:
        raise MobileShopError('پلن انتخاب‌شده معتبر نیست.', code='PLAN_NOT_FOUND', status=404)
    ok, message, reason = evaluate_plan_purchase(user, plan)
    if not ok:
        code = 'PHONE_VERIFY_REQUIRED' if reason == 'phone_verify' else 'PLAN_BLOCKED'
        raise MobileShopError(message or 'امکان خرید این پلن وجود ندارد.', code=code, status=403)

    discount_code_obj = _resolve_discount_code(user, discount_code)
    qty = _parse_quantity(plan, quantity)
    base_pricing = calculate_plan_purchase_prices(plan, product, user, request=request, quantity=qty)
    pricing = calculate_plan_purchase_prices(
        plan, product, user, request=request, quantity=qty, discount_code=discount_code_obj,
    )
    if discount_code_obj and pricing['final_price'] >= base_pricing['final_price']:
        raise MobileShopError('کد تخفیف قابل اعمال نیست.', code='DISCOUNT_INVALID')
    return {
        'plan_id': plan.pk,
        'quantity': qty,
        'code': discount_code_obj.code if discount_code_obj else '',
        'unit_original_price': int(pricing['original_price'] // qty) if qty else int(pricing['original_price']),
        'unit_final_price': int(base_pricing['final_price'] // qty) if qty else int(base_pricing['final_price']),
        'original_price': int(pricing['original_price']),
        'base_final_price': int(base_pricing['final_price']),
        'discount_amount': int(pricing['discount_amount']),
        'code_discount_amount': max(0, int(base_pricing['final_price']) - int(pricing['final_price'])),
        'final_price': int(pricing['final_price']),
        'has_discount': bool(pricing['has_discount']),
    }


def create_checkout(user, *, plan_id: int, renew_license_id: Optional[int] = None, discount_code: Optional[str] = None, quantity: int = 1, request=None) -> Dict[str, Any]:
    product = get_bot_product()
    if product is None:
        raise MobileShopError('محصول لایسنس در حال حاضر در دسترس نیست.', code='PRODUCT_UNAVAILABLE', status=404)

    plan = product.plans.filter(pk=plan_id, is_active=True).first()
    if plan is None:
        raise MobileShopError('پلن انتخاب‌شده معتبر نیست.', code='PLAN_NOT_FOUND', status=404)

    ok, message, reason = evaluate_plan_purchase(user, plan)
    if not ok:
        code = 'PHONE_VERIFY_REQUIRED' if reason == 'phone_verify' else 'PLAN_BLOCKED'
        raise MobileShopError(message or 'امکان خرید این پلن وجود ندارد.', code=code, status=403)

    renewal_license = None
    if renew_license_id:
        try:
            renewal_license = get_renewable_license_for_user(user, int(renew_license_id))
        except Exception:
            raise MobileShopError(
                'لایسنس انتخاب‌شده برای تمدید یافت نشد یا قابل تمدید نیست.',
                code='RENEW_INVALID',
                status=404,
            )
        if renewal_license.order.product_id != product.id:
            raise MobileShopError('این لایسنس متعلق به این محصول نیست.', code='RENEW_INVALID', status=400)

    discount_code_obj = _resolve_discount_code(user, discount_code) if discount_code else None
    qty = _parse_quantity(plan, quantity, renewal=bool(renew_license_id))

    with transaction.atomic():
        type(user).objects.select_for_update().filter(pk=user.pk).first()
        existing = None if discount_code_obj else _reuse_pending_order(user, plan, renewal_license, qty)
        if existing:
            mark_mobile_checkout(existing.id)
            order = existing
            reused = True
        else:
            pricing = calculate_plan_purchase_prices(
                plan, product, user, request=request, quantity=qty, discount_code=discount_code_obj,
            )
            if discount_code_obj:
                base_pricing = calculate_plan_purchase_prices(plan, product, user, request=request, quantity=qty)
                if pricing['final_price'] >= base_pricing['final_price']:
                    raise MobileShopError('کد تخفیف قابل اعمال نیست.', code='DISCOUNT_INVALID')
            pay_settings = PaymentSettings.load()
            available = pay_settings.available_methods()
            if not available:
                raise MobileShopError(
                    'در حال حاضر هیچ روش پرداختی فعال نیست. با پشتیبانی تماس بگیرید.',
                    code='PAYMENT_UNAVAILABLE',
                    status=503,
                )
            method = 'zibal' if 'zibal' in available else available[0]

            order = Order(
                user=user,
                product=product,
                plan=plan,
                quantity=qty,
                original_price=pricing['original_price'],
                discount_amount=pricing['discount_amount'],
                amount=pricing['final_price'],
                payment_method=method,
                status='pending',
            )
            if renewal_license:
                order.renewal_license = renewal_license
            if discount_code_obj:
                order.discount_code = discount_code_obj
            try:
                from affiliates.services import resolve_order_affiliate

                affiliate = resolve_order_affiliate(user, request)
                if affiliate:
                    order.affiliate = affiliate
            except Exception:
                pass
            order.save()
            if discount_code_obj:
                DiscountCode.objects.filter(pk=discount_code_obj.pk).update(
                    used_count=discount_code_obj.used_count + 1,
                )
            mark_mobile_checkout(order.id)
            reused = False

    if order.amount <= 0:
        from shop.services.order_fulfillment import fulfill_order_after_payment

        fulfill_order_after_payment(order)
        order.refresh_from_db()
        return order_status_payload(user, order.id)

    if order.payment_method != 'zibal':
        raise MobileShopError(
            'پرداخت آنلاین در اپ در دسترس نیست. لطفاً از میزکار وب ادامه دهید.',
            code='PAYMENT_WEB_ONLY',
            status=409,
        )

    return _initiate_or_payload(order, request=request, reused=reused)


def _initiate_or_payload(order: Order, *, request, reused: bool) -> Dict[str, Any]:
    from shop.payment_views import (
        _create_or_update_pending_transaction,
        _order_ready_for_online_payment,
        _reset_order_for_retry,
    )

    if order.status == 'paid':
        return order_status_payload(order.user, order.id)

    pay_settings = PaymentSettings.load()
    if not pay_settings.zibal_enabled:
        raise MobileShopError('در حال حاضر روش پرداخت آنلاین فعال نیست.', code='PAYMENT_UNAVAILABLE', status=503)
    if not _order_ready_for_online_payment(order):
        raise MobileShopError('این سفارش قابل پرداخت نیست.', code='ORDER_NOT_PAYABLE', status=409)

    _reset_order_for_retry(order)
    try:
        callback_url = zibal_service.build_callback_url(request)
        mobile = getattr(order.user, 'phone', '') or ''
        request_result = zibal_service.request_payment(
            order=order,
            callback_url=callback_url,
            mobile=mobile,
        )
    except zibal_service.ZibalConfigurationError:
        raise MobileShopError(
            'درگاه پرداخت هنوز پیکربندی نشده است.',
            code='PAYMENT_UNAVAILABLE',
            status=503,
        )
    except zibal_service.ZibalAPIError as exc:
        raise MobileShopError(exc.message, code='GATEWAY_ERROR', status=502)
    except Exception as exc:
        raise MobileShopError(
            'خطا در ارتباط با درگاه پرداخت. لطفاً دوباره تلاش کنید.',
            code='GATEWAY_ERROR',
            status=502,
        ) from exc

    _create_or_update_pending_transaction(order, request_result.track_id, request_result)
    pay_url = zibal_service.get_start_pay_bridge_url(request_result.track_id, request=request)
    mark_mobile_checkout(order.id)
    return {
        'order_id': str(order.id),
        'status': order.status,
        'amount': int(order.amount),
        'quantity': int(order.quantity or 1),
        'plan_name': order.plan.name if order.plan_id else '',
        'pay_url': pay_url,
        'reused': reused,
        'return_scheme': f'divarfiling://payment?order_id={order.id}',
    }


def order_status_payload(user, order_id) -> Dict[str, Any]:
    try:
        oid = order_id if isinstance(order_id, UUID) else UUID(str(order_id))
    except (ValueError, TypeError):
        raise MobileShopError('شناسه سفارش نامعتبر است.', code='VALIDATION_ERROR')
    order = Order.objects.select_related('plan').filter(id=oid, user=user).first()
    if not order:
        raise MobileShopError('سفارش یافت نشد.', code='ORDER_NOT_FOUND', status=404)
    return {
        'order_id': str(order.id),
        'status': order.status,
        'amount': int(order.amount),
        'plan_name': order.plan.name if order.plan_id else '',
        'paid_at': order.paid_at.isoformat() if order.paid_at else None,
        'is_renewal': bool(order.renewal_license_id),
    }


def verify_mobile_order(user, order_id) -> Dict[str, Any]:
    """وضعیت سفارش را از دیتابیس می‌خواند و در صورت pending بودن، verify درگاه را reuse می‌کند."""
    payload = order_status_payload(user, order_id)
    if payload['status'] == 'paid':
        from mobile_api.services.notification_service import dismiss_stale_license_alerts
        dismiss_stale_license_alerts(user)
        return payload

    order = Order.objects.select_related('transaction', 'plan').filter(
        id=payload['order_id'], user=user,
    ).first()
    if order is None or order.status != 'pending':
        return payload

    track_id = order.zibal_track_id or getattr(getattr(order, 'transaction', None), 'zibal_track_id', '') or ''
    if not track_id:
        return payload

    from shop.models import Transaction
    from shop.payment_views import _finalize_successful_payment

    try:
        expected_amount_rial = zibal_service.toman_to_rial(order.amount)
        verify_result = zibal_service.verify_payment(
            track_id=str(track_id),
            expected_amount_rial=expected_amount_rial,
        )
    except zibal_service.ZibalVerifyError:
        return order_status_payload(user, order.id)
    except Exception:
        return order_status_payload(user, order.id)

    try:
        txn = order.transaction
    except Transaction.DoesNotExist:
        txn = None
    if txn is None:
        return order_status_payload(user, order.id)

    _finalize_successful_payment(order, txn, verify_result)
    order.refresh_from_db()
    from mobile_api.services.notification_service import dismiss_stale_license_alerts
    dismiss_stale_license_alerts(user)
    return order_status_payload(user, order.id)

