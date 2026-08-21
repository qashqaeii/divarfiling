"""پلن، سفارش و وضعیت پرداخت برای کلاینت موبایل — منطق فروشگاه وب."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from licenses.services.renewal import evaluate_license_renewal, get_renewable_license_for_user
from shop.bot_catalog import get_bot_product
from shop.models import LicensePlan, Order, PaymentSettings
from shop.services.mobile_checkout import mark_mobile_checkout
from shop.services.plan_guards import evaluate_plan_purchase
from shop.services.plan_pricing import calculate_plan_purchase_prices
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
            'discount_amount': int(pricing['discount_amount']),
            'has_discount': bool(pricing['has_discount']),
            'is_featured': bool(plan.is_featured),
            'offer_badge': (plan.offer_badge or '').strip(),
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


def _reuse_pending_order(user, plan: LicensePlan, renewal_license) -> Optional[Order]:
    since = timezone.now() - timedelta(hours=2)
    qs = Order.objects.filter(
        user=user,
        plan=plan,
        status='pending',
        created_at__gte=since,
        payment_method='zibal',
    )
    if renewal_license:
        qs = qs.filter(renewal_license=renewal_license)
    else:
        qs = qs.filter(renewal_license__isnull=True)
    return qs.order_by('-created_at').first()


def create_checkout(user, *, plan_id: int, renew_license_id: Optional[int] = None, request=None) -> Dict[str, Any]:
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

    with transaction.atomic():
        type(user).objects.select_for_update().filter(pk=user.pk).first()
        existing = _reuse_pending_order(user, plan, renewal_license)
        if existing:
            mark_mobile_checkout(existing.id)
            order = existing
            reused = True
        else:
            pricing = calculate_plan_purchase_prices(plan, product, user, request=request, quantity=1)
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
                quantity=1,
                original_price=pricing['original_price'],
                discount_amount=pricing['discount_amount'],
                amount=pricing['final_price'],
                payment_method=method,
                status='pending',
            )
            if renewal_license:
                order.renewal_license = renewal_license
            try:
                from affiliates.services import resolve_order_affiliate

                affiliate = resolve_order_affiliate(user, request)
                if affiliate:
                    order.affiliate = affiliate
            except Exception:
                pass
            order.save()
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
    pay_url = zibal_service.get_start_pay_url(request_result.track_id)
    mark_mobile_checkout(order.id)
    return {
        'order_id': str(order.id),
        'status': order.status,
        'amount': int(order.amount),
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
