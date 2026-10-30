"""ثبت امن Event رها کردن Checkout و Preview سگمنت — بدون ارسال SMS."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.plan_bi import (
    CHECKOUT_ABANDON_BATCH_DEFAULT,
    CHECKOUT_ABANDON_HOURS_DEFAULT,
)
from shop.models import Order, PlanFunnelEvent
from shop.services.plan_funnel import (
    checkout_abandon_idempotency_key,
    is_excluded_staff_fake_or_grant_order,
    should_emit_funnel_for_order,
)

# دلایل حذف از سگمنت فعال Recovery
EXCLUDE_PENDING_VERIFICATION = 'pending_verification'
EXCLUDE_PAID = 'paid'
EXCLUDE_FAILED = 'failed'
EXCLUDE_CANCELLED = 'cancelled'
EXCLUDE_TOO_RECENT = 'too_recent'
EXCLUDE_STAFF_OR_FAKE = 'staff_or_fake'
EXCLUDE_CARD_AWAITING = 'card_awaiting_verification'
EXCLUDE_HAS_PAYMENT_SUCCESS = 'has_payment_success'
EXCLUDE_NEWER_PAID_SAME_PRODUCT = 'newer_paid_same_product'
EXCLUDE_INVALID_PHONE = 'invalid_phone'
EXCLUDE_NOT_PENDING = 'not_pending'
EXCLUDE_ALREADY_RECORDED = 'already_recorded'  # فقط آمار Job

INCLUDE_PENDING_STALE = 'pending_stale_no_payment'

EXCLUDE_LABELS_FA = {
    EXCLUDE_PENDING_VERIFICATION: 'در انتظار تأیید پرداخت (pending_verification)',
    EXCLUDE_PAID: 'پرداخت شده (paid)',
    EXCLUDE_FAILED: 'ناموفق (failed) — مربوط به سگمنت failed_retry است',
    EXCLUDE_CANCELLED: 'لغو شده (cancelled)',
    EXCLUDE_TOO_RECENT: 'هنوز زمان انتظار نگذشته',
    EXCLUDE_STAFF_OR_FAKE: 'سفارش تستی یا staff/superuser',
    EXCLUDE_CARD_AWAITING: 'کارت‌به‌کارت در انتظار تأیید',
    EXCLUDE_HAS_PAYMENT_SUCCESS: 'Event پرداخت موفق برای همین سفارش وجود دارد',
    EXCLUDE_NEWER_PAID_SAME_PRODUCT: 'خرید جدیدتر برای همان محصول',
    EXCLUDE_INVALID_PHONE: 'شماره نامعتبر',
    EXCLUDE_NOT_PENDING: 'وضعیت سفارش pending نیست',
    EXCLUDE_ALREADY_RECORDED: 'Event رها کردن قبلاً ثبت شده',
}

INCLUDE_LABELS_FA = {
    INCLUDE_PENDING_STALE: 'سفارش pending قدیمی‌تر از آستانه بدون payment_success',
}

CHECKOUT_SOURCE_LINKED = 'linked_checkout_event'
CHECKOUT_SOURCE_ORDER = 'order_created_at'


def get_abandon_hours(override: int | None = None) -> int:
    if override is not None and override > 0:
        return int(override)
    return int(getattr(settings, 'CHECKOUT_ABANDON_HOURS', CHECKOUT_ABANDON_HOURS_DEFAULT) or CHECKOUT_ABANDON_HOURS_DEFAULT)


def get_abandon_batch_limit(override: int | None = None) -> int:
    if override is not None and override > 0:
        return int(override)
    return int(
        getattr(settings, 'CHECKOUT_ABANDON_BATCH_LIMIT', CHECKOUT_ABANDON_BATCH_DEFAULT)
        or CHECKOUT_ABANDON_BATCH_DEFAULT
    )


def _mask_phone(phone: str) -> str:
    raw = (phone or '').strip()
    if len(raw) < 7:
        return '***'
    return f'{raw[:4]}***{raw[-2:]}'


def _format_amount(amount) -> str:
    try:
        return f'{int(amount):,}'
    except (TypeError, ValueError):
        return str(amount or '')


def payment_method_label(order: Order) -> str:
    method = order.payment_method or ''
    mapping = dict(Order.PAYMENT_METHOD_CHOICES)
    return mapping.get(method, method or '—')


def status_label(order: Order) -> str:
    mapping = dict(Order.STATUS_CHOICES)
    return mapping.get(order.status, order.status or '—')


def has_payment_success_for_order(order_id) -> bool:
    oid = str(order_id)
    if PlanFunnelEvent.objects.filter(
        event_type='payment_success',
        order_id=order_id,
    ).exists():
        return True
    return PlanFunnelEvent.objects.filter(
        event_type='payment_success',
        metadata__order_id=oid,
    ).exists()


def has_checkout_abandon_for_order(order_id) -> bool:
    return PlanFunnelEvent.objects.filter(
        idempotency_key=checkout_abandon_idempotency_key(order_id),
    ).exists()


def is_card_awaiting_verification(order: Order) -> bool:
    """کارت‌به‌کارت در انتظار تأیید — وارد Abandon نمی‌شود."""
    if order.status == 'pending_verification':
        return True
    if order.payment_method != 'card_transfer':
        return False
    try:
        card = order.card_transfer
    except Exception:
        return False
    return bool(card and getattr(card, 'status', None) == 'pending')


def has_newer_paid_same_product(order: Order) -> bool:
    if not order.user_id or not order.product_id:
        return False
    return Order.objects.filter(
        user_id=order.user_id,
        product_id=order.product_id,
        status='paid',
        created_at__gt=order.created_at,
    ).exclude(pk=order.pk).exists()


def resolve_checkout_detection_source(order: Order) -> dict[str, Any]:
    """
    اتصال Checkout به Order.

    checkout_view در BuyView GET قبل از ایجاد Order ثبت می‌شود و order_id ندارد.
    بنابراین اتصال حدسی فقط با user_id ممنوع است. منبع پیش‌فرض و معتبر:
    order_created_at (ساخته‌شدن Order = ورود معتبر به Checkout پس از فرم خرید).

    linked_checkout_event فقط وقتی که Event صریحاً به همین order وصل باشد
    (FK order یا metadata.order_id).
    """
    linked = (
        PlanFunnelEvent.objects.filter(event_type='checkout_view')
        .filter(
            Q(order_id=order.pk)
            | Q(metadata__order_id=str(order.pk))
        )
        .order_by('created_at')
        .first()
    )
    if linked is not None:
        return {
            'source': CHECKOUT_SOURCE_LINKED,
            'label': 'linked_checkout_event',
            'checkout_event_id': linked.pk,
            'checkout_at': linked.created_at,
        }
    return {
        'source': CHECKOUT_SOURCE_ORDER,
        'label': 'order_created_at',
        'checkout_event_id': None,
        'checkout_at': order.created_at,
    }


@dataclass
class AbandonEvaluation:
    order: Order
    eligible_for_event: bool = False
    eligible_for_active_segment: bool = False
    exclude_reason: str | None = None
    include_reason: str | None = None
    age_hours: float = 0.0
    eligible_since: Any = None
    checkout_source: dict[str, Any] = field(default_factory=dict)
    has_abandon_event: bool = False
    phone_ok: bool = False
    masked_phone: str = ''


def evaluate_order_for_abandon(
    order: Order,
    *,
    hours: int | None = None,
    now=None,
    require_valid_phone_for_segment: bool = True,
) -> AbandonEvaluation:
    """ارزیابی یک Order برای Event و سگمنت فعال Recovery."""
    now = now or timezone.now()
    wait_hours = get_abandon_hours(hours)
    threshold = now - timedelta(hours=wait_hours)
    age_hours = max(0.0, (now - order.created_at).total_seconds() / 3600.0)
    eligible_since = order.created_at + timedelta(hours=wait_hours)
    checkout_source = resolve_checkout_detection_source(order)
    has_event = has_checkout_abandon_for_order(order.pk)

    raw_phone = getattr(order.user, 'phone', '') or ''
    phone = normalize_phone(raw_phone)
    phone_ok = is_valid_iran_mobile(phone)
    masked = _mask_phone(phone or raw_phone)

    result = AbandonEvaluation(
        order=order,
        age_hours=round(age_hours, 2),
        eligible_since=eligible_since,
        checkout_source=checkout_source,
        has_abandon_event=has_event,
        phone_ok=phone_ok,
        masked_phone=masked,
    )

    status = order.status or ''
    if status == 'pending_verification':
        result.exclude_reason = EXCLUDE_PENDING_VERIFICATION
        return result
    if status == 'paid':
        result.exclude_reason = EXCLUDE_PAID
        return result
    if status == 'failed':
        result.exclude_reason = EXCLUDE_FAILED
        return result
    if status == 'cancelled':
        result.exclude_reason = EXCLUDE_CANCELLED
        return result
    if status != 'pending':
        result.exclude_reason = EXCLUDE_NOT_PENDING
        return result

    if is_excluded_staff_fake_or_grant_order(order):
        result.exclude_reason = EXCLUDE_STAFF_OR_FAKE
        return result

    if is_card_awaiting_verification(order):
        result.exclude_reason = EXCLUDE_CARD_AWAITING
        return result

    if order.created_at > threshold:
        result.exclude_reason = EXCLUDE_TOO_RECENT
        return result

    if has_payment_success_for_order(order.pk):
        result.exclude_reason = EXCLUDE_HAS_PAYMENT_SUCCESS
        return result

    if has_newer_paid_same_product(order):
        result.exclude_reason = EXCLUDE_NEWER_PAID_SAME_PRODUCT
        return result

    # واجد Event (بدون نیاز به شماره)
    result.eligible_for_event = True
    result.include_reason = INCLUDE_PENDING_STALE

    if require_valid_phone_for_segment and not phone_ok:
        result.exclude_reason = EXCLUDE_INVALID_PHONE
        result.eligible_for_active_segment = False
        return result

    result.eligible_for_active_segment = True
    return result


def ensure_checkout_abandon_event(order: Order) -> PlanFunnelEvent | None:
    """یک Event checkout_abandon به ازای order_id — idempotent."""
    if not should_emit_funnel_for_order(order):
        return None
    if order.status != 'pending':
        return None

    order_id = str(order.pk)
    detection = resolve_checkout_detection_source(order)
    meta: dict[str, Any] = {
        'order_id': order_id,
        'user_id': order.user_id,
        'amount': int(order.amount or 0),
        'payment_method': order.payment_method or '',
        'plan_id': order.plan_id,
        'product_id': order.product_id,
        'checkout_source': detection['source'],
        'order_created_at': order.created_at.isoformat(),
    }
    idem_key = checkout_abandon_idempotency_key(order_id)
    try:
        with transaction.atomic():
            obj, created = PlanFunnelEvent.objects.get_or_create(
                idempotency_key=idem_key,
                defaults={
                    'event_type': 'checkout_abandon',
                    'user': order.user,
                    'session_key': f'order:{order_id}',
                    'product': order.product,
                    'plan': order.plan,
                    'order': order,
                    'metadata': meta,
                },
            )
            if created and order.user_id:
                try:
                    from accounts.services.growth_journey import on_checkout_start
                    on_checkout_start(user=order.user, order=order)
                except Exception:
                    pass
            return obj
    except IntegrityError:
        return PlanFunnelEvent.objects.filter(idempotency_key=idem_key).first()


def process_checkout_abandons(
    *,
    hours: int | None = None,
    batch_limit: int | None = None,
    dry_run: bool = False,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """
    Job ثبت Event — بدون ارسال پیامک.
    فقط سفارش‌های pending قدیمی‌تر از آستانه را بررسی می‌کند.
    """
    now = timezone.now()
    wait_hours = get_abandon_hours(hours)
    limit = get_abandon_batch_limit(batch_limit)
    lookback_since = now - timedelta(days=max(1, lookback_days))
    threshold = now - timedelta(hours=wait_hours)

    qs = (
        Order.objects.filter(
            status='pending',
            created_at__gte=lookback_since,
            created_at__lte=threshold,
        )
        .select_related('user', 'product', 'plan')
        .order_by('created_at')[:limit]
    )
    orders = list(qs)

    stats = {
        'examined': 0,
        'eligible': 0,
        'created': 0,
        'already_recorded': 0,
        'excluded': 0,
        'errors': 0,
        'dry_run': dry_run,
        'hours': wait_hours,
        'batch_limit': limit,
        'exclude_breakdown': {},
    }

    for order in orders:
        stats['examined'] += 1
        try:
            ev = evaluate_order_for_abandon(order, hours=wait_hours, now=now, require_valid_phone_for_segment=False)
            if not ev.eligible_for_event:
                stats['excluded'] += 1
                reason = ev.exclude_reason or 'unknown'
                stats['exclude_breakdown'][reason] = stats['exclude_breakdown'].get(reason, 0) + 1
                continue

            stats['eligible'] += 1
            if has_checkout_abandon_for_order(order.pk):
                stats['already_recorded'] += 1
                continue

            if dry_run:
                stats['created'] += 1  # would create
                continue

            created = ensure_checkout_abandon_event(order)
            if created is not None:
                stats['created'] += 1
            else:
                stats['errors'] += 1
        except Exception:
            stats['errors'] += 1

    return stats


def _last_marketing_sms_at(phone: str):
    if not phone:
        return None
    from accounts.models import SmsMessageLog

    return (
        SmsMessageLog.objects.filter(
            phone=phone,
            purpose='marketing',
            status__in=('sent', 'fake'),
        )
        .order_by('-created_at')
        .values_list('created_at', flat=True)
        .first()
    )


def _iso(dt) -> str:
    if dt is None:
        return ''
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _row_from_evaluation(ev: AbandonEvaluation) -> dict[str, Any]:
    order = ev.order
    phone_norm = normalize_phone(getattr(order.user, 'phone', '') or '')
    last_sms = _last_marketing_sms_at(phone_norm) if ev.phone_ok else None
    exclude_code = ev.exclude_reason
    include_code = ev.include_reason if ev.eligible_for_active_segment else None

    # Event تاریخی ممکن است باشد ولی از سگمنت فعال خارج شده باشد
    note = ''
    if ev.has_abandon_event and not ev.eligible_for_active_segment and exclude_code:
        note = 'Event تاریخی Abandon باقی مانده؛ از سگمنت فعال حذف شد.'

    return {
        'masked_phone': ev.masked_phone,
        'user_id': order.user_id,
        'order_id': str(order.pk),
        'product': order.product.title if order.product_id else '',
        'plan': order.plan.name if order.plan_id else '',
        'amount': _format_amount(order.amount),
        'payment_method': payment_method_label(order),
        'status': order.status,
        'status_label': status_label(order),
        'order_created_at': order.created_at,
        'order_created_at_iso': _iso(order.created_at),
        'age_hours': ev.age_hours,
        'eligible_since': ev.eligible_since,
        'eligible_since_iso': _iso(ev.eligible_since),
        'checkout_source': ev.checkout_source.get('label') or CHECKOUT_SOURCE_ORDER,
        'has_abandon_event': ev.has_abandon_event,
        'last_marketing_sms_at': last_sms,
        'last_marketing_sms_at_iso': _iso(last_sms),
        'include_reason': include_code,
        'include_reason_label': INCLUDE_LABELS_FA.get(include_code or '', include_code or ''),
        'exclude_reason': exclude_code,
        'exclude_reason_label': EXCLUDE_LABELS_FA.get(exclude_code or '', exclude_code or ''),
        'note': note,
        'phone': phone_norm if ev.phone_ok else '',
    }


def build_abandoned_checkout_preview(
    *,
    hours: int | None = None,
    product_id: int | None = None,
    lookback_days: int = 30,
    limit: int = 200,
) -> dict[str, Any]:
    """
    Preview مدیریتی: واجدان شرایط فعلی + حذف‌شده‌ها با دلیل.
    هیچ SMS ارسال نمی‌کند.
    """
    now = timezone.now()
    wait_hours = get_abandon_hours(hours)
    lookback_since = now - timedelta(days=max(1, lookback_days))

    base = Order.objects.filter(created_at__gte=lookback_since).select_related(
        'user', 'product', 'plan',
    )
    if product_id:
        base = base.filter(product_id=product_id)

    # کاندیداها: pending اخیر + سفارش‌هایی با Event abandon در بازه
    abandon_order_ids = list(
        PlanFunnelEvent.objects.filter(
            event_type='checkout_abandon',
            created_at__gte=lookback_since,
        ).values_list('order_id', flat=True)
    )
    candidates = (
        base.filter(
            Q(status__in=('pending', 'pending_verification', 'failed', 'cancelled', 'paid'))
            | Q(pk__in=[oid for oid in abandon_order_ids if oid])
        )
        .order_by('-created_at')[: max(limit * 3, 300)]
    )

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen: set[str] = set()

    for order in candidates:
        oid = str(order.pk)
        if oid in seen:
            continue
        seen.add(oid)
        ev = evaluate_order_for_abandon(order, hours=wait_hours, now=now)
        row = _row_from_evaluation(ev)
        if ev.eligible_for_active_segment:
            eligible.append(row)
        else:
            # فقط موارد مرتبط با recovery را در حذف‌شده‌ها نگه دار
            # (همه pending نزدیک آستانه، یا دارای Event، یا وضعیت‌های نزدیک به checkout)
            if (
                ev.has_abandon_event
                or order.status in ('pending', 'pending_verification')
                or (order.status in ('paid', 'failed', 'cancelled') and ev.age_hours >= wait_hours * 0.5)
            ):
                excluded.append(row)

        if len(eligible) >= limit and len(excluded) >= limit:
            break

    eligible = eligible[:limit]
    excluded = excluded[:limit]

    return {
        'key': 'abandoned_checkout',
        'title': 'رها کردن Checkout',
        'description': (
            f'سفارش‌های pending قدیمی‌تر از {wait_hours} ساعت — فقط پیش‌نمایش؛ ارسال غیرفعال است.'
        ),
        'hours': wait_hours,
        'lookback_days': lookback_days,
        'eligible': eligible,
        'excluded': excluded,
        'count': len(eligible),
        'excluded_count': len(excluded),
        'capped_count': len(eligible),
        'batch_limit': limit,
        'preview_only': True,
        'send_enabled': False,
        'stats': {
            'eligible': len(eligible),
            'excluded': len(excluded),
            'with_abandon_event': sum(1 for r in eligible if r['has_abandon_event']),
            'excluded_with_historical_event': sum(
                1 for r in excluded if r['has_abandon_event']
            ),
        },
        # سازگاری با preview_segment عمومی
        'sample': [
            {
                'phone': r['masked_phone'],
                'name': '',
                'name_part': '',
                'product': r['product'],
                'plan': r['plan'],
                'amount': r['amount'],
                'link': '',
                'order_id': r['order_id'],
                'code': '',
            }
            for r in eligible[:10]
        ],
        'recipients': [],  # ارسال ممنوع — لیست گیرنده خالی
        'default_template': '',
    }
