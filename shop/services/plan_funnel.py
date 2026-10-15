"""ثبت رویدادهای قیف خرید پلن — با پشتیبانی Idempotency."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.utils import timezone

from shop.models import LicensePlan, Order, PlanFunnelEvent, Product


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ''


def payment_success_idempotency_key(order_id) -> str:
    return f'payment_success:{order_id}'


def checkout_abandon_idempotency_key(order_id) -> str:
    return f'checkout_abandon:{order_id}'


def payment_failed_idempotency_key(order_id, attempt_id: str) -> str:
    """
    هر تلاش ناموفق واقعی یک کلید جدا.
    attempt_id ترجیحاً Transaction.pk یا zibal_track_id است.
    """
    safe = (attempt_id or 'unknown').strip() or 'unknown'
    return f'payment_failed:{order_id}:{safe}'


def is_bi_production_order(order: Order) -> bool:
    """
    سفارش‌های قابل‌شمارش در BI Production.
    حذف: staff/superuser، سفارش فیک (پیشوند FAKE-)، هدیه کمپین (granted / GRANT-).
    """
    if (getattr(order, 'status', None) or '') != 'paid':
        return False
    user = getattr(order, 'user', None)
    if user is not None and (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
        return False
    track = (getattr(order, 'zibal_track_id', None) or '').strip().upper()
    if track.startswith('FAKE-') or track.startswith('GRANT-'):
        return False
    # آینده: اگر Order فیلد/متادیتای تست گرفت
    return True


def should_emit_funnel_for_order(order: Order) -> bool:
    return is_bi_production_order(order)


def record_plan_funnel_event(
    request,
    event_type: str,
    *,
    product: Product | None = None,
    plan: LicensePlan | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_minutes: int = 30,
) -> PlanFunnelEvent | None:
    """ثبت رویداد با جلوگیری از تکرار پشت‌سرهم در یک نشست."""
    session_key = _session_key(request)
    since = timezone.now() - timedelta(minutes=dedupe_minutes)

    qs = PlanFunnelEvent.objects.filter(
        event_type=event_type,
        session_key=session_key,
        created_at__gte=since,
    )
    if product is not None:
        qs = qs.filter(product=product)
    if plan is not None and event_type in ('checkout_view', 'payment_success', 'payment_failed'):
        qs = qs.filter(plan=plan)
    if qs.exists():
        return None

    return PlanFunnelEvent.objects.create(
        event_type=event_type,
        user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
        session_key=session_key,
        product=product,
        plan=plan,
        metadata=metadata or {},
    )


def record_plan_funnel_for_order(
    event_type: str,
    *,
    user: AbstractBaseUser | None = None,
    product: Product | None = None,
    plan: LicensePlan | None = None,
    metadata: dict[str, Any] | None = None,
    order_id: str | None = None,
    order: Order | None = None,
    idempotency_key: str | None = None,
) -> PlanFunnelEvent | None:
    """
    ثبت رویداد سمت سرور.
    اگر idempotency_key داده شود → get_or_create (تکرار نمی‌سازد).
    """
    meta = dict(metadata or {})
    order_obj = order
    oid = str(order_id or (order_obj.pk if order_obj is not None else '') or '')
    if oid:
        meta.setdefault('order_id', oid)

    defaults = {
        'event_type': event_type,
        'user': user if user and getattr(user, 'is_authenticated', True) else None,
        'session_key': f'order:{oid}' if oid else '',
        'product': product,
        'plan': plan,
        'order': order_obj,
        'metadata': meta,
    }

    if not idempotency_key:
        return PlanFunnelEvent.objects.create(**defaults, idempotency_key=None)

    try:
        with transaction.atomic():
            obj, _created = PlanFunnelEvent.objects.get_or_create(
                idempotency_key=idempotency_key,
                defaults=defaults,
            )
            return obj
    except IntegrityError:
        return PlanFunnelEvent.objects.filter(idempotency_key=idempotency_key).first()


def ensure_payment_success_event(order: Order) -> PlanFunnelEvent | None:
    """یک Event payment_success به ازای هر order_id — فقط سفارش‌های Production."""
    if not should_emit_funnel_for_order(order):
        return None

    order_id = str(order.pk)
    tx = getattr(order, 'transaction', None)
    try:
        if tx is None:
            from shop.models import Transaction
            tx = Transaction.objects.filter(order_id=order.pk).first()
    except Exception:
        tx = None

    meta: dict[str, Any] = {
        'order_id': order_id,
        'user_id': order.user_id,
        'amount': int(order.amount or 0),
        'payment_method': order.payment_method or '',
        'plan_id': order.plan_id,
        'product_id': order.product_id,
    }
    if tx is not None:
        meta['transaction_id'] = str(tx.pk)
        if getattr(tx, 'zibal_track_id', None):
            meta['zibal_track_id'] = tx.zibal_track_id
        if getattr(tx, 'zibal_ref_number', None):
            meta['zibal_ref_number'] = tx.zibal_ref_number

    idem_key = payment_success_idempotency_key(order_id)
    try:
        with transaction.atomic():
            obj, created = PlanFunnelEvent.objects.get_or_create(
                idempotency_key=idem_key,
                defaults={
                    'event_type': 'payment_success',
                    'user': order.user,
                    'session_key': f'order:{order_id}',
                    'product': order.product,
                    'plan': order.plan,
                    'order': order,
                    'metadata': meta,
                },
            )
            if not created:
                merged = dict(obj.metadata or {})
                changed = False
                for k, v in meta.items():
                    if v in (None, ''):
                        continue
                    if merged.get(k) in (None, ''):
                        merged[k] = v
                        changed = True
                update_fields = []
                if changed:
                    obj.metadata = merged
                    update_fields.append('metadata')
                if obj.order_id is None:
                    obj.order = order
                    update_fields.append('order')
                if update_fields:
                    obj.save(update_fields=update_fields)
            return obj
    except IntegrityError:
        return PlanFunnelEvent.objects.filter(idempotency_key=idem_key).first()



def record_payment_failed_event(
    order: Order,
    *,
    reason: str = '',
    attempt_id: str | None = None,
) -> PlanFunnelEvent | None:
    """ثبت تلاش ناموفق — هر attempt_id یک Event جدا (نه یکتا فقط با order_id)."""
    if not should_emit_funnel_for_order(order):
        return None

    order_id = str(order.pk)
    tx = None
    try:
        from shop.models import Transaction
        tx = Transaction.objects.filter(order_id=order.pk).first()
    except Exception:
        pass

    attempt = (attempt_id or '').strip()
    if not attempt and tx is not None:
        attempt = str(tx.zibal_track_id or tx.pk)
    if not attempt:
        # بدون شناسه Attempt: کلید زمانی تا تلاش‌های واقعی حذف نشوند
        # (طراحی موقت — در گزارش ذکر می‌شود)
        attempt = f'ts:{int(timezone.now().timestamp())}'

    meta = {
        'order_id': order_id,
        'user_id': order.user_id,
        'reason': reason,
        'attempt_id': attempt,
        'payment_method': order.payment_method or '',
    }
    if tx is not None:
        meta['transaction_id'] = str(tx.pk)

    return record_plan_funnel_for_order(
        'payment_failed',
        user=order.user,
        product=order.product,
        plan=order.plan,
        order=order,
        order_id=order_id,
        metadata=meta,
        idempotency_key=payment_failed_idempotency_key(order_id, attempt),
    )
