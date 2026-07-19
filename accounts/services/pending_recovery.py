"""Resolver مخاطب Recovery + Runner Dry Run — بدون SMS؛ Simulation جدا از Delivery."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun
from shop.models import Order, PlanFunnelEvent
from shop.services.checkout_abandon import (
    has_newer_paid_same_product,
    has_payment_success_for_order,
    is_card_awaiting_verification,
    payment_method_label,
    resolve_checkout_detection_source,
    status_label,
)
from shop.services.plan_funnel import is_bi_production_order

FLOW_KEY = 'pending_recovery'
SIMULATION_BANNER = 'FLOW LIVE DISABLED — SIMULATION ONLY'

STEP_TOO_RECENT = 'too_recent'
STEP_RECOVERY_1 = 'recovery_step_1'
STEP_RECOVERY_1_LATE = 'recovery_step_1_late'
STEP_RECOVERY_2 = 'recovery_step_2'
STEP_WAITING_FOR_STEP_2 = 'waiting_for_step_2'
STEP_EXPIRED = 'recovery_expired'

STEP1_KEYS = (STEP_RECOVERY_1, STEP_RECOVERY_1_LATE)

SUPPRESS_NOT_PENDING = 'not_pending'
SUPPRESS_PENDING_VERIFICATION = 'pending_verification'
SUPPRESS_PAID = 'paid'
SUPPRESS_FAILED = 'failed'
SUPPRESS_CANCELLED = 'cancelled'
SUPPRESS_STAFF_OR_FAKE = 'staff_or_fake'
SUPPRESS_HAS_PAYMENT_SUCCESS = 'has_payment_success'
SUPPRESS_NEWER_PAID_SAME_PRODUCT = 'newer_paid_same_product'
SUPPRESS_NEWER_PENDING_SAME_PRODUCT = 'newer_pending_same_product'
SUPPRESS_INVALID_PHONE = 'invalid_phone'
SUPPRESS_OPT_OUT = 'opt_out'
SUPPRESS_OUTSIDE_WINDOW = 'outside_recovery_window'
SUPPRESS_ALREADY_RECEIVED_STEP = 'already_received_step'
SUPPRESS_FREQUENCY_CAP = 'frequency_cap'
SUPPRESS_FLOW_DISABLED = 'flow_disabled'
SUPPRESS_CARD_AWAITING = 'card_awaiting_verification'
SUPPRESS_WAITING_FOR_STEP_2 = 'waiting_for_step_2'

SUPPRESS_LABELS_FA = {
    SUPPRESS_NOT_PENDING: 'سفارش دیگر pending نیست',
    SUPPRESS_PENDING_VERIFICATION: 'در انتظار تأیید پرداخت',
    SUPPRESS_PAID: 'پرداخت شده',
    SUPPRESS_FAILED: 'ناموفق',
    SUPPRESS_CANCELLED: 'لغو شده',
    SUPPRESS_STAFF_OR_FAKE: 'سفارش تستی یا staff/superuser',
    SUPPRESS_HAS_PAYMENT_SUCCESS: 'Event پرداخت موفق',
    SUPPRESS_NEWER_PAID_SAME_PRODUCT: 'خرید موفق جدیدتر همان محصول',
    SUPPRESS_NEWER_PENDING_SAME_PRODUCT: 'سفارش pending جدیدتر همان محصول',
    SUPPRESS_INVALID_PHONE: 'شماره نامعتبر',
    SUPPRESS_OPT_OUT: 'Opt-out',
    SUPPRESS_OUTSIDE_WINDOW: 'خارج از پنجره Recovery',
    SUPPRESS_ALREADY_RECEIVED_STEP: 'قبلاً همین Step (ارسال واقعی)',
    SUPPRESS_FREQUENCY_CAP: 'Frequency Cap (ارسال واقعی)',
    SUPPRESS_FLOW_DISABLED: 'Flow غیرفعال',
    SUPPRESS_CARD_AWAITING: 'کارت‌به‌کارت در انتظار تأیید',
    SUPPRESS_WAITING_FOR_STEP_2: 'در انتظار فاصله Step 2 پس از Step 1',
}

STEP_LABELS_FA = {
    STEP_TOO_RECENT: 'کمتر از ۲ ساعت',
    STEP_RECOVERY_1: 'Recovery Step 1 (۲–۲۴ ساعت)',
    STEP_RECOVERY_1_LATE: 'Recovery Step 1 Late (۲۴–۷۲ ساعت، بدون پیام اول)',
    STEP_RECOVERY_2: 'Recovery Step 2 (پس از Step 1 واقعی + ۲۴h)',
    STEP_WAITING_FOR_STEP_2: 'Waiting for Step 2',
    STEP_EXPIRED: 'Expired (بیش از ۷۲ ساعت)',
}

REAL_DELIVERY_ACTIONS = (
    MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
    MarketingAutomationActionLog.Action.DELIVERED,
    MarketingAutomationActionLog.Action.SENT,  # legacy — قبل از فاز ۲.۲
)


def get_recovery_config(*, simulate_enabled: bool = False) -> dict[str, Any]:
    live_enabled = bool(getattr(settings, 'PENDING_RECOVERY_FLOW_ENABLED', False))
    return {
        'step_1_min_hours': int(getattr(settings, 'RECOVERY_STEP_1_MIN_HOURS', 2) or 2),
        'step_2_min_hours': int(getattr(settings, 'RECOVERY_STEP_2_MIN_HOURS', 24) or 24),
        'max_age_hours': int(getattr(settings, 'RECOVERY_MAX_AGE_HOURS', 72) or 72),
        'lookback_days': int(getattr(settings, 'RECOVERY_LOOKBACK_DAYS', 7) or 7),
        'frequency_cap_hours': int(getattr(settings, 'RECOVERY_FREQUENCY_CAP_HOURS', 24) or 24),
        'batch_limit': int(getattr(settings, 'RECOVERY_BATCH_LIMIT', 100) or 100),
        'flow_enabled': live_enabled,
        'simulate_enabled': simulate_enabled,
        'resolution_enabled': simulate_enabled or live_enabled,
    }


def _mask_phone(phone: str) -> str:
    raw = (phone or '').strip()
    if len(raw) < 7:
        return '***'
    return f'{raw[:4]}***{raw[-2:]}'


def hash_normalized_phone(phone: str) -> str:
    normalized = normalize_phone(phone or '')
    if not normalized:
        return ''
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:32]


def dry_run_decision_key(
    *,
    run_id: int,
    step_key: str,
    phone_hash: str,
    product_id: int | None,
    order_id,
) -> str:
    pid = product_id or 0
    return f'dry_run:{run_id}:{step_key}:{phone_hash}:{pid}:{order_id}'


def live_send_idempotency_key(
    *,
    step_key: str,
    phone_hash: str,
    product_id: int | None,
    order_id,
) -> str:
    pid = product_id or 0
    return f'live:{step_key}:{phone_hash}:{pid}:{order_id}'


def dedupe_key_for_order(order: Order, phone_norm: str) -> str:
    pid = order.product_id or 0
    if phone_norm:
        return f'phone:{phone_norm}:product:{pid}'
    return f'user:{order.user_id}:product:{pid}'


def classify_recovery_step(age_hours: float, cfg: dict[str, Any] | None = None) -> str:
    """فقط bucket سنی — برای سازگاری تست؛ Journey از resolve_recovery_journey استفاده می‌کند."""
    cfg = cfg or get_recovery_config()
    if age_hours < cfg['step_1_min_hours']:
        return STEP_TOO_RECENT
    if age_hours < cfg['step_2_min_hours']:
        return STEP_RECOVERY_1
    if age_hours <= cfg['max_age_hours']:
        return STEP_RECOVERY_1_LATE
    return STEP_EXPIRED


def is_marketing_opt_out(user) -> bool:
    return bool(getattr(user, 'marketing_sms_opt_out', False))


def has_newer_pending_same_product(order: Order) -> bool:
    if not order.user_id or not order.product_id:
        return False
    return Order.objects.filter(
        user_id=order.user_id,
        product_id=order.product_id,
        status='pending',
        created_at__gt=order.created_at,
    ).exclude(pk=order.pk).exists()


def _order_phone(order: Order) -> tuple[str, str, str, bool]:
    raw = getattr(order.user, 'phone', '') or ''
    phone_norm = normalize_phone(raw)
    phone_ok = is_valid_iran_mobile(phone_norm)
    return phone_norm, hash_normalized_phone(phone_norm), _mask_phone(phone_norm or raw), phone_ok


def _iso(dt) -> str:
    if dt is None:
        return ''
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _real_delivery_qs():
    """Send Guard — فقط تحویل واقعی؛ test: prefix و redirect از شمارش خارج."""
    return (
        MarketingAutomationActionLog.objects.filter(
            flow_key=FLOW_KEY,
            action__in=REAL_DELIVERY_ACTIONS,
        )
        .exclude(send_idempotency_key__startswith='test:')
        .filter(
            Q(metadata__send_target_redirected__isnull=True)
            | Q(metadata__send_target_redirected=False)
        )
    )


def _last_step1_real_sent(*, phone_hash: str, product_id: int | None):
    if not phone_hash:
        return None
    return (
        _real_delivery_qs()
        .filter(
            phone_hash=phone_hash,
            product_id=product_id,
            step_key__in=STEP1_KEYS,
        )
        .order_by('-created_at')
        .first()
    )


def _has_real_sent_for_step(*, step_key: str, phone_hash: str, product_id: int | None) -> bool:
    if not phone_hash:
        return False
    return _real_delivery_qs().filter(
        step_key=step_key,
        phone_hash=phone_hash,
        product_id=product_id,
    ).exists()


def _last_real_delivery(*, phone_hash: str, product_id: int | None):
    if not phone_hash:
        return None
    return (
        _real_delivery_qs()
        .filter(phone_hash=phone_hash, product_id=product_id)
        .order_by('-created_at')
        .first()
    )


def _in_frequency_cap(*, phone_hash: str, product_id: int | None, cfg: dict[str, Any], now) -> bool:
    cap_hours = cfg.get('frequency_cap_hours') or 0
    if not phone_hash or cap_hours <= 0:
        return False
    since = now - timedelta(hours=cap_hours)
    return _real_delivery_qs().filter(
        phone_hash=phone_hash,
        product_id=product_id,
        created_at__gte=since,
    ).exists()


def resolve_recovery_journey(
    *,
    age_hours: float,
    phone_hash: str,
    product_id: int | None,
    now,
    cfg: dict[str, Any],
) -> tuple[str, str | None]:
    """
    Step پیشنهادی + دلیل Journey-level suppress (بدون Send Guard).
    Send Guard جداگانه در evaluate_order_suppression اعمال می‌شود.
    """
    if age_hours < cfg['step_1_min_hours']:
        return STEP_TOO_RECENT, SUPPRESS_OUTSIDE_WINDOW
    if age_hours > cfg['max_age_hours']:
        return STEP_EXPIRED, SUPPRESS_OUTSIDE_WINDOW

    step1_sent = _last_step1_real_sent(phone_hash=phone_hash, product_id=product_id)
    if step1_sent:
        hours_since_step1 = (now - step1_sent.created_at).total_seconds() / 3600.0
        if hours_since_step1 < cfg['step_2_min_hours']:
            return STEP_WAITING_FOR_STEP_2, SUPPRESS_WAITING_FOR_STEP_2
        return STEP_RECOVERY_2, None

    if age_hours < cfg['step_2_min_hours']:
        return STEP_RECOVERY_1, None
    return STEP_RECOVERY_1_LATE, None


def evaluate_order_suppression(
    order: Order,
    *,
    now=None,
    cfg: dict[str, Any] | None = None,
    dedupe_winner: bool = True,
    dedupe_loser: bool = False,
) -> tuple[str | None, str]:
    """(suppress_reason یا None, step_key)"""
    cfg = cfg or get_recovery_config()
    now = now or timezone.now()
    status = order.status or ''

    if status == 'pending_verification':
        return SUPPRESS_PENDING_VERIFICATION, STEP_TOO_RECENT
    if status == 'paid':
        return SUPPRESS_PAID, STEP_TOO_RECENT
    if status == 'failed':
        return SUPPRESS_FAILED, STEP_TOO_RECENT
    if status == 'cancelled':
        return SUPPRESS_CANCELLED, STEP_TOO_RECENT
    if status != 'pending':
        return SUPPRESS_NOT_PENDING, STEP_TOO_RECENT
    if not is_bi_production_order(order):
        return SUPPRESS_STAFF_OR_FAKE, STEP_TOO_RECENT
    if is_card_awaiting_verification(order):
        return SUPPRESS_CARD_AWAITING, STEP_TOO_RECENT
    if has_payment_success_for_order(order.pk):
        return SUPPRESS_HAS_PAYMENT_SUCCESS, STEP_TOO_RECENT
    if has_newer_paid_same_product(order):
        return SUPPRESS_NEWER_PAID_SAME_PRODUCT, STEP_TOO_RECENT
    if dedupe_loser or (dedupe_winner and has_newer_pending_same_product(order)):
        return SUPPRESS_NEWER_PENDING_SAME_PRODUCT, STEP_TOO_RECENT

    phone_norm, phone_hash, _masked, phone_ok = _order_phone(order)
    if not phone_ok:
        return SUPPRESS_INVALID_PHONE, STEP_TOO_RECENT
    if is_marketing_opt_out(order.user):
        return SUPPRESS_OPT_OUT, STEP_TOO_RECENT

    age_hours = max(0.0, (now - order.created_at).total_seconds() / 3600.0)
    step_key, journey_suppress = resolve_recovery_journey(
        age_hours=age_hours,
        phone_hash=phone_hash,
        product_id=order.product_id,
        now=now,
        cfg=cfg,
    )
    if journey_suppress:
        return journey_suppress, step_key

    if not cfg.get('resolution_enabled'):
        return SUPPRESS_FLOW_DISABLED, step_key

    if step_key in STEP1_KEYS and _last_step1_real_sent(
        phone_hash=phone_hash, product_id=order.product_id,
    ):
        return SUPPRESS_ALREADY_RECEIVED_STEP, step_key
    if step_key == STEP_RECOVERY_2 and _has_real_sent_for_step(
        step_key=STEP_RECOVERY_2,
        phone_hash=phone_hash,
        product_id=order.product_id,
    ):
        return SUPPRESS_ALREADY_RECEIVED_STEP, step_key

    if _in_frequency_cap(
        phone_hash=phone_hash,
        product_id=order.product_id,
        cfg=cfg,
        now=now,
    ):
        return SUPPRESS_FREQUENCY_CAP, step_key

    return None, step_key


@dataclass
class RecoveryResolution:
    event: PlanFunnelEvent
    order: Order
    age_hours: float = 0.0
    step_key: str = ''
    dedupe_key: str = ''
    phone_norm: str = ''
    phone_hash: str = ''
    masked_phone: str = ''
    is_dedupe_winner: bool = True
    suppress_reason: str | None = None
    would_send: bool = False
    raw_orders_in_group: int = 1
    suppressed_order_ids: list[str] = field(default_factory=list)
    selected_order_id: str | None = None


def resolve_pending_recovery_audience(
    *,
    batch_limit: int | None = None,
    lookback_days: int | None = None,
    now=None,
    simulate_enabled: bool = False,
) -> dict[str, Any]:
    now = now or timezone.now()
    cfg = get_recovery_config(simulate_enabled=simulate_enabled)
    limit = batch_limit if batch_limit is not None else cfg['batch_limit']
    lookback = lookback_days if lookback_days is not None else cfg['lookback_days']
    lookback_since = now - timedelta(days=max(1, lookback))

    events_qs = (
        PlanFunnelEvent.objects.filter(
            event_type='checkout_abandon',
            created_at__gte=lookback_since,
        )
        .select_related('order', 'order__user', 'product', 'plan', 'user')
        .order_by('-created_at')
    )
    events = list(events_qs[: max(limit * 3, limit)])

    pending_by_dedupe: dict[str, list[Order]] = {}
    for ev in events:
        order = ev.order
        if order is None or order.status != 'pending':
            continue
        phone_norm, _, _, _ = _order_phone(order)
        dkey = dedupe_key_for_order(order, phone_norm)
        pending_by_dedupe.setdefault(dkey, []).append(order)

    winner_order_ids: set[str] = set()
    loser_order_ids: set[str] = set()
    group_meta: dict[str, dict[str, Any]] = {}
    for dkey, orders in pending_by_dedupe.items():
        sorted_orders = sorted(orders, key=lambda o: o.created_at, reverse=True)
        winner = sorted_orders[0]
        losers = sorted_orders[1:]
        winner_order_ids.add(str(winner.pk))
        for lo in losers:
            loser_order_ids.add(str(lo.pk))
        group_meta[dkey] = {
            'winner_id': str(winner.pk),
            'loser_ids': [str(o.pk) for o in losers],
            'raw_count': len(sorted_orders),
        }

    resolutions: list[RecoveryResolution] = []
    stats = {
        'raw_abandon_events': len(events),
        'examined': 0,
        'unique_recipients': 0,
        'step_1_recipients': 0,
        'step_1_late_recipients': 0,
        'step_2_recipients': 0,
        'waiting_for_step_2': 0,
        'expired_recipients': 0,
        'too_recent_recipients': 0,
        'would_send': 0,
        'suppressed': 0,
        'suppressed_duplicates': 0,
        'suppressed_paid': 0,
        'suppressed_verification': 0,
        'suppressed_invalid_phone': 0,
        'suppressed_frequency_cap': 0,
        'suppressed_opt_out': 0,
        'suppressed_outside_window': 0,
        'suppressed_flow_disabled': 0,
        'suppressed_already_step': 0,
        'suppressed_waiting_step_2': 0,
        'suppress_breakdown': {},
        'simulate_enabled': simulate_enabled,
        'flow_live_enabled': cfg['flow_enabled'],
    }

    seen_dedupe_winners: set[str] = set()

    for ev in events[:limit]:
        order = ev.order
        if order is None:
            continue
        stats['examined'] += 1
        phone_norm, phone_hash, masked, _phone_ok = _order_phone(order)
        dkey = dedupe_key_for_order(order, phone_norm)
        age_hours = round(
            max(0.0, (now - order.created_at).total_seconds() / 3600.0),
            2,
        )
        oid = str(order.pk)
        is_winner = oid in winner_order_ids
        is_loser = oid in loser_order_ids
        gmeta = group_meta.get(dkey, {})

        suppress, step_key = evaluate_order_suppression(
            order,
            now=now,
            cfg=cfg,
            dedupe_winner=is_winner,
            dedupe_loser=is_loser,
        )

        resolution = RecoveryResolution(
            event=ev,
            order=order,
            age_hours=age_hours,
            step_key=step_key,
            dedupe_key=dkey,
            phone_norm=phone_norm,
            phone_hash=phone_hash,
            masked_phone=masked,
            is_dedupe_winner=is_winner or not is_loser,
            raw_orders_in_group=gmeta.get('raw_count', 1),
            suppressed_order_ids=list(gmeta.get('loser_ids') or []),
            selected_order_id=gmeta.get('winner_id'),
            suppress_reason=suppress,
        )

        if is_winner:
            if step_key == STEP_RECOVERY_1:
                stats['step_1_recipients'] += 1
            elif step_key == STEP_RECOVERY_1_LATE:
                stats['step_1_late_recipients'] += 1
            elif step_key == STEP_RECOVERY_2:
                stats['step_2_recipients'] += 1
            elif step_key == STEP_WAITING_FOR_STEP_2:
                stats['waiting_for_step_2'] += 1
            elif step_key == STEP_EXPIRED:
                stats['expired_recipients'] += 1
            elif step_key == STEP_TOO_RECENT:
                stats['too_recent_recipients'] += 1

        if suppress:
            stats['suppressed'] += 1
            stats['suppress_breakdown'][suppress] = stats['suppress_breakdown'].get(suppress, 0) + 1
            if suppress == SUPPRESS_NEWER_PENDING_SAME_PRODUCT:
                stats['suppressed_duplicates'] += 1
            elif suppress in (SUPPRESS_NEWER_PAID_SAME_PRODUCT, SUPPRESS_PAID, SUPPRESS_HAS_PAYMENT_SUCCESS):
                stats['suppressed_paid'] += 1
            elif suppress in (SUPPRESS_PENDING_VERIFICATION, SUPPRESS_CARD_AWAITING):
                stats['suppressed_verification'] += 1
            elif suppress == SUPPRESS_INVALID_PHONE:
                stats['suppressed_invalid_phone'] += 1
            elif suppress == SUPPRESS_FREQUENCY_CAP:
                stats['suppressed_frequency_cap'] += 1
            elif suppress == SUPPRESS_OPT_OUT:
                stats['suppressed_opt_out'] += 1
            elif suppress == SUPPRESS_OUTSIDE_WINDOW:
                stats['suppressed_outside_window'] += 1
            elif suppress == SUPPRESS_FLOW_DISABLED:
                stats['suppressed_flow_disabled'] += 1
            elif suppress == SUPPRESS_ALREADY_RECEIVED_STEP:
                stats['suppressed_already_step'] += 1
            elif suppress == SUPPRESS_WAITING_FOR_STEP_2:
                stats['suppressed_waiting_step_2'] += 1
        else:
            resolution.would_send = True
            stats['would_send'] += 1
            if dkey not in seen_dedupe_winners:
                seen_dedupe_winners.add(dkey)
                stats['unique_recipients'] += 1

        resolutions.append(resolution)

    return {
        'flow_key': FLOW_KEY,
        'config': cfg,
        'stats': stats,
        'resolutions': resolutions,
        'recipients': _build_recipient_rows(resolutions, now=now, cfg=cfg),
        'suppressed_rows': _build_suppressed_rows(resolutions),
    }


def _build_recipient_rows(
    resolutions: list[RecoveryResolution],
    *,
    now,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for res in resolutions:
        if not res.would_send:
            continue
        if res.dedupe_key in seen_keys:
            continue
        seen_keys.add(res.dedupe_key)
        order = res.order
        detection = resolve_checkout_detection_source(order)
        eligible_since = order.created_at + timedelta(hours=cfg['step_1_min_hours'])
        last_real = _last_real_delivery(
            phone_hash=res.phone_hash,
            product_id=order.product_id,
        )
        rows.append({
            'masked_phone': res.masked_phone,
            'user_id': order.user_id,
            'selected_order_id': str(order.pk),
            'raw_event_count': res.raw_orders_in_group,
            'suppressed_order_ids': res.suppressed_order_ids,
            'product': order.product.title if order.product_id else '',
            'plan': order.plan.name if order.plan_id else '',
            'amount': int(order.amount or 0),
            'payment_method': payment_method_label(order),
            'status': order.status,
            'status_label': status_label(order),
            'age_hours': res.age_hours,
            'step_key': res.step_key,
            'step_label': STEP_LABELS_FA.get(res.step_key, res.step_key),
            'entry_reason': detection.get('label') or 'order_created_at',
            'eligible_action_at': eligible_since,
            'eligible_action_at_iso': _iso(eligible_since),
            'last_real_delivery_at_iso': _iso(last_real.created_at if last_real else None),
            'would_send': True,
        })
    return rows


def _build_suppressed_rows(resolutions: list[RecoveryResolution]) -> list[dict[str, Any]]:
    rows = []
    for res in resolutions:
        if not res.suppress_reason:
            continue
        order = res.order
        rows.append({
            'order_id': str(order.pk),
            'user_id': order.user_id,
            'masked_phone': res.masked_phone,
            'step_key': res.step_key,
            'step_label': STEP_LABELS_FA.get(res.step_key, res.step_key),
            'suppress_reason': res.suppress_reason,
            'suppress_reason_label': SUPPRESS_LABELS_FA.get(res.suppress_reason, res.suppress_reason),
            'is_dedupe_winner': res.is_dedupe_winner,
            'selected_order_id': res.selected_order_id,
            'age_hours': res.age_hours,
        })
    return rows


def build_pending_recovery_preview(
    *,
    batch_limit: int | None = None,
    lookback_days: int | None = None,
) -> dict[str, Any]:
    data = resolve_pending_recovery_audience(
        batch_limit=batch_limit,
        lookback_days=lookback_days,
        simulate_enabled=True,
    )
    stats = data['stats']
    cfg = data['config']
    recipients = data['recipients']

    return {
        'key': 'abandoned_checkout',
        'title': 'رها کردن Checkout — Recovery Audience',
        'description': (
            f'Resolver مخاطب Recovery — Step1 از {cfg["step_1_min_hours"]}h، '
            f'Step1 Late از {cfg["step_2_min_hours"]}h، Step2 پس از ارسال واقعی Step1 + '
            f'{cfg["step_2_min_hours"]}h. فقط پیش‌نمایش؛ ارسال غیرفعال.'
        ),
        'preview_only': True,
        'send_enabled': False,
        'simulation_banner': SIMULATION_BANNER,
        'recipients': [],
        'recovery_stats': stats,
        'recovery_recipients': recipients,
        'recovery_suppressed': data['suppressed_rows'],
        'config': cfg,
        'count': stats['would_send'],
        'eligible': recipients,
        'excluded': data['suppressed_rows'],
        'excluded_count': stats['suppressed'],
        'hours': cfg['step_1_min_hours'],
        'lookback_days': cfg['lookback_days'],
        'capped_count': stats['would_send'],
        'batch_limit': batch_limit or cfg['batch_limit'],
        'sample': [
            {
                'phone': r['masked_phone'],
                'name': '',
                'name_part': '',
                'product': r['product'],
                'plan': r['plan'],
                'amount': f'{r["amount"]:,}',
                'link': '',
                'order_id': r['selected_order_id'],
                'code': '',
            }
            for r in recipients[:10]
        ],
        'default_template': '',
    }


def run_pending_recovery(
    *,
    dry_run: bool = True,
    simulate_enabled: bool = False,
    batch_limit: int | None = None,
    lookback_days: int | None = None,
) -> dict[str, Any]:
    if not dry_run:
        raise ValueError(
            'اجرای واقعی pending_recovery هنوز فعال نیست. فقط --dry-run مجاز است.'
        )

    cfg = get_recovery_config(simulate_enabled=simulate_enabled)
    if not simulate_enabled and not cfg['flow_enabled']:
        raise ValueError(
            'Flow Live غیرفعال است. برای Dry Run از --simulate-enabled استفاده کنید.'
        )

    now = timezone.now()
    run = MarketingAutomationRun.objects.create(
        flow_key=FLOW_KEY,
        mode=MarketingAutomationRun.Mode.DRY_RUN,
        status=MarketingAutomationRun.Status.RUNNING,
        config_snapshot=cfg,
    )

    result_stats = {
        'dry_run': True,
        'simulate_enabled': simulate_enabled,
        'flow_live_enabled': cfg['flow_enabled'],
        'simulation_banner': SIMULATION_BANNER,
        'flow_key': FLOW_KEY,
        'run_id': run.pk,
        'examined': 0,
        'eligible': 0,
        'suppressed': 0,
        'would_send': 0,
        'actions_created': 0,
        'errors': 0,
        'config': cfg,
    }

    try:
        data = resolve_pending_recovery_audience(
            batch_limit=batch_limit,
            lookback_days=lookback_days,
            now=now,
            simulate_enabled=simulate_enabled,
        )
        stats = data['stats']
        result_stats.update({
            'examined': stats['examined'],
            'eligible': stats['unique_recipients'],
            'suppressed': stats['suppressed'],
            'would_send': stats['would_send'],
            'recovery_stats': stats,
        })

        for res in data['resolutions']:
            if not res.would_send:
                continue
            order = res.order
            decision_key = dry_run_decision_key(
                run_id=run.pk,
                step_key=res.step_key,
                phone_hash=res.phone_hash,
                product_id=order.product_id,
                order_id=order.pk,
            )
            detection = resolve_checkout_detection_source(order)
            try:
                with transaction.atomic():
                    MarketingAutomationActionLog.objects.create(
                        run=run,
                        flow_key=FLOW_KEY,
                        step_key=res.step_key,
                        user=order.user,
                        phone_hash=res.phone_hash,
                        masked_phone=res.masked_phone,
                        order=order,
                        product=order.product,
                        action=MarketingAutomationActionLog.Action.WOULD_SEND,
                        reason=detection.get('label') or 'order_created_at',
                        decision_key=decision_key,
                        send_idempotency_key=None,
                        metadata={
                            'raw_event_count': res.raw_orders_in_group,
                            'suppressed_order_ids': res.suppressed_order_ids,
                            'age_hours': res.age_hours,
                            'amount': int(order.amount or 0),
                            'simulation_only': True,
                        },
                    )
                result_stats['actions_created'] += 1
            except Exception:
                result_stats['errors'] += 1

        run.examined_count = stats['examined']
        run.eligible_count = stats['unique_recipients']
        run.suppressed_count = stats['suppressed']
        run.would_send_count = stats['would_send']
        run.error_count = result_stats['errors']
        run.status = (
            MarketingAutomationRun.Status.FAILED
            if result_stats['errors']
            else MarketingAutomationRun.Status.COMPLETED
        )
        run.finished_at = timezone.now()
        run.save()
    except Exception:
        run.status = MarketingAutomationRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_count = 1
        run.save(update_fields=['status', 'finished_at', 'error_count'])
        raise

    return result_stats
