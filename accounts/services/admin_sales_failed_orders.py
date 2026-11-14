"""ردیف‌های نمایشی سفارش ناموفق برای مرکز سفارش — علت خوانا + داده مودال."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from shop.models import Order, PlanFunnelEvent
from shop.services.zibal import get_result_message

FAILURE_CATEGORY_LABELS = {
    'cancelled': 'لغو توسط کاربر',
    'gateway': 'خطای درگاه',
    'verify': 'خطای تأیید پرداخت',
    'card_rejected': 'رد رسید',
    'funnel': 'ناموفق در پرداخت',
    'unknown': 'علت ثبت‌نشده',
}

TRANSACTION_STATUS_LABELS = {
    'pending': 'در انتظار',
    'paid': 'موفق',
    'failed': 'ناموفق',
    'cancelled': 'لغوشده',
}


def _shorten(text: str, *, limit: int = 48) -> str:
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + '…'


def _funnel_reasons_by_order(order_ids: Sequence) -> Dict[Any, str]:
    if not order_ids:
        return {}
    reasons: Dict[Any, str] = {}
    events = (
        PlanFunnelEvent.objects.filter(
            order_id__in=order_ids,
            event_type='payment_failed',
        )
        .order_by('order_id', '-created_at')
        .only('order_id', 'metadata')
    )
    for event in events:
        if event.order_id in reasons:
            continue
        meta = event.metadata or {}
        reason = (meta.get('reason') or '').strip()
        if reason:
            reasons[event.order_id] = reason
    return reasons


def resolve_order_failure(*, order: Order, funnel_reason: str = '') -> Dict[str, Any]:
    """استخراج علت ناموفق بودن — اولویت: تراکنش، رویداد قیف، پیش‌فرض."""
    tx = None
    try:
        tx = order.transaction
    except Exception:
        tx = None

    category = 'unknown'
    reason_full = ''
    source_label = ''

    if tx is not None:
        reason_full = (tx.gateway_message or '').strip()
        if tx.gateway_result_code is not None and not reason_full:
            reason_full = get_result_message(tx.gateway_result_code, kind='verify')
            category = 'verify'
            source_label = 'کد نتیجه درگاه'
        if tx.status == 'cancelled':
            category = 'cancelled'
            if not reason_full:
                reason_full = 'پرداخت توسط کاربر لغو شد.'
            source_label = source_label or 'وضعیت تراکنش'
        elif tx.status == 'failed':
            category = category if category != 'unknown' else 'gateway'
            if not reason_full:
                reason_full = 'تأیید یا بازگشت از درگاه ناموفق بود.'
            source_label = source_label or 'پیام درگاه'
        elif reason_full:
            category = 'gateway'
            source_label = 'پیام درگاه'

    if not reason_full and funnel_reason:
        reason_full = funnel_reason
        category = 'funnel'
        source_label = 'ثبت سیستم هنگام بازگشت از درگاه'

    card = None
    try:
        card = order.card_transfer
    except Exception:
        card = None
    if card is not None and card.status == 'rejected':
        note = (card.admin_note or '').strip()
        reason_full = note or 'رسید کارت‌به‌کارت رد شد.'
        category = 'card_rejected'
        source_label = 'بررسی کارت‌به‌کارت'

    if not reason_full:
        if order.status == 'cancelled':
            reason_full = 'سفارش لغو شده است.'
            category = 'cancelled'
        else:
            reason_full = (
                'علت دقیق در سامانه ثبت نشده؛ '
                'معمولاً بازگشت از درگاه بدون تکمیل پرداخت است.'
            )
        source_label = source_label or '—'

    track_id = (order.zibal_track_id or '').strip()
    if not track_id and tx is not None:
        track_id = (tx.zibal_track_id or '').strip()

    tx_status = (tx.status or '').strip() if tx else ''
    tx_status_label = TRANSACTION_STATUS_LABELS.get(tx_status, tx_status or '—')

    return {
        'category': category,
        'category_label': FAILURE_CATEGORY_LABELS.get(category, FAILURE_CATEGORY_LABELS['unknown']),
        'reason_full': reason_full,
        'reason_short': _shorten(reason_full),
        'source_label': source_label,
        'gateway_code': tx.gateway_result_code if tx is not None else None,
        'track_id': track_id,
        'transaction_status': tx_status,
        'transaction_status_label': tx_status_label,
    }


def build_failed_order_rows(orders: Sequence[Order]) -> List[Dict[str, Any]]:
    order_list = list(orders)
    funnel_map = _funnel_reasons_by_order([o.pk for o in order_list])
    rows: List[Dict[str, Any]] = []
    for order in order_list:
        failure = resolve_order_failure(
            order=order,
            funnel_reason=funnel_map.get(order.pk, ''),
        )
        rows.append({'order': order, 'failure': failure})
    return rows