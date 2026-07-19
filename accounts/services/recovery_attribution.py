"""Recovery Attribution — Strict/Assisted matchers with immutable decision records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, RecoveryAttribution
from accounts.services.pending_recovery import FLOW_KEY, REAL_DELIVERY_ACTIONS
from accounts.services.pending_recovery_live import TEST_SEND_KEY_PREFIX
from shop.models import Order, PlanFunnelEvent

ATTRIBUTION_WINDOW_HOURS = 72
STRICT_RULE_VERSION = 'strict_v1'
ASSISTED_RULE_VERSION = 'assisted_v1'
BACKFILL_DEFAULT_DAYS = 30
BACKFILL_BATCH_LIMIT = 200


@dataclass(frozen=True)
class AttributionMatch:
    attribution_model: str
    status: str
    paid_order: Order | None
    paid_at: Any
    lag_hours: float | None
    revenue_amount: int | None
    rule_version: str


def is_production_recovery_send(log: MarketingAutomationActionLog) -> bool:
    if log.action not in REAL_DELIVERY_ACTIONS:
        return False
    if log.action == MarketingAutomationActionLog.Action.TEST_PROVIDER_ACCEPTED:
        return False
    send_key = log.send_idempotency_key or ''
    if send_key.startswith(TEST_SEND_KEY_PREFIX):
        return False
    if (log.metadata or {}).get('send_target_redirected'):
        return False
    return True


def is_delivered_recovery_send(log: MarketingAutomationActionLog) -> bool:
    if not is_production_recovery_send(log):
        return False
    if log.action == MarketingAutomationActionLog.Action.DELIVERED:
        return True
    if log.sms_log_id and log.sms_log.status == log.sms_log.Status.SENT:
        return True
    return log.action in (
        MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
        MarketingAutomationActionLog.Action.SENT,
    )


def _sms_time(log: MarketingAutomationActionLog):
    return log.created_at


def _payment_time(order: Order):
    if order.status != 'paid':
        return None
    return order.paid_at or order.created_at


def _lag_hours(sms_time, paid_time) -> float | None:
    if not sms_time or not paid_time or paid_time <= sms_time:
        return None
    return round((paid_time - sms_time).total_seconds() / 3600, 1)


def _order_amount(order: Order) -> int:
    try:
        return int(order.amount or 0)
    except (TypeError, ValueError):
        return 0


def had_prior_paid(*, user_id, product_id, before) -> bool:
    if not user_id or not product_id or not before:
        return False
    return (
        Order.objects.filter(user_id=user_id, product_id=product_id, status='paid')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .filter(effective_paid__lt=before)
        .exists()
    )


def _payment_in_window(*, paid_time, sms_time, window_hours: int = ATTRIBUTION_WINDOW_HOURS) -> bool:
    if not paid_time or not sms_time:
        return False
    if paid_time <= sms_time:
        return False
    return paid_time <= sms_time + timedelta(hours=window_hours)


def _attribution_window_open(sms_time, *, now=None) -> bool:
    now = now or timezone.now()
    return now <= sms_time + timedelta(hours=ATTRIBUTION_WINDOW_HOURS)


def _linked_abandon_exists(*, user_id, product_id, abandon_order_id) -> bool:
    if abandon_order_id:
        return PlanFunnelEvent.objects.filter(
            event_type='checkout_abandon',
            order_id=abandon_order_id,
        ).exists()
    if user_id and product_id:
        return PlanFunnelEvent.objects.filter(
            event_type='checkout_abandon',
            user_id=user_id,
            product_id=product_id,
        ).exists()
    return False


def match_strict(action_log: MarketingAutomationActionLog) -> AttributionMatch | None:
    if not is_production_recovery_send(action_log):
        return None

    abandon_order = action_log.order
    if abandon_order is None:
        return None

    sms_time = _sms_time(action_log)
    user_id = action_log.user_id or abandon_order.user_id
    product_id = action_log.product_id or abandon_order.product_id

    if had_prior_paid(user_id=user_id, product_id=product_id, before=sms_time):
        return AttributionMatch(
            attribution_model='',
            status=RecoveryAttribution.Status.NO_MATCH,
            paid_order=None,
            paid_at=None,
            lag_hours=None,
            revenue_amount=None,
            rule_version=STRICT_RULE_VERSION,
        )

    paid_time = _payment_time(abandon_order)
    if paid_time and _payment_in_window(paid_time=paid_time, sms_time=sms_time):
        return AttributionMatch(
            attribution_model=RecoveryAttribution.AttributionModel.STRICT,
            status=RecoveryAttribution.Status.MATCHED,
            paid_order=abandon_order,
            paid_at=paid_time,
            lag_hours=_lag_hours(sms_time, paid_time),
            revenue_amount=_order_amount(abandon_order),
            rule_version=STRICT_RULE_VERSION,
        )

    if _attribution_window_open(sms_time):
        return AttributionMatch(
            attribution_model='',
            status=RecoveryAttribution.Status.PENDING,
            paid_order=None,
            paid_at=None,
            lag_hours=None,
            revenue_amount=None,
            rule_version=STRICT_RULE_VERSION,
        )

    return AttributionMatch(
        attribution_model='',
        status=RecoveryAttribution.Status.NO_MATCH,
        paid_order=None,
        paid_at=None,
        lag_hours=None,
        revenue_amount=None,
        rule_version=STRICT_RULE_VERSION,
    )


def match_assisted(action_log: MarketingAutomationActionLog) -> AttributionMatch | None:
    if not is_production_recovery_send(action_log):
        return None

    sms_time = _sms_time(action_log)
    user_id = action_log.user_id or (action_log.order.user_id if action_log.order_id else None)
    product_id = action_log.product_id or (action_log.order.product_id if action_log.order_id else None)
    abandon_order_id = action_log.order_id

    if not user_id or not product_id:
        return None

    if had_prior_paid(user_id=user_id, product_id=product_id, before=sms_time):
        return None

    if not _linked_abandon_exists(
        user_id=user_id,
        product_id=product_id,
        abandon_order_id=abandon_order_id,
    ):
        return None

    window_end = sms_time + timedelta(hours=ATTRIBUTION_WINDOW_HOURS)
    candidates = (
        Order.objects.filter(
            user_id=user_id,
            product_id=product_id,
            status='paid',
        )
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .filter(effective_paid__gt=sms_time, effective_paid__lte=window_end)
        .exclude(pk=abandon_order_id)
        .order_by('effective_paid')
    )

    paid_order = candidates.first()
    if paid_order:
        paid_time = paid_order.paid_at or paid_order.created_at
        return AttributionMatch(
            attribution_model=RecoveryAttribution.AttributionModel.ASSISTED,
            status=RecoveryAttribution.Status.MATCHED,
            paid_order=paid_order,
            paid_at=paid_time,
            lag_hours=_lag_hours(sms_time, paid_time),
            revenue_amount=_order_amount(paid_order),
            rule_version=ASSISTED_RULE_VERSION,
        )

    if _attribution_window_open(sms_time):
        return AttributionMatch(
            attribution_model='',
            status=RecoveryAttribution.Status.PENDING,
            paid_order=None,
            paid_at=None,
            lag_hours=None,
            revenue_amount=None,
            rule_version=ASSISTED_RULE_VERSION,
        )

    return AttributionMatch(
        attribution_model='',
        status=RecoveryAttribution.Status.NO_MATCH,
        paid_order=None,
        paid_at=None,
        lag_hours=None,
        revenue_amount=None,
        rule_version=ASSISTED_RULE_VERSION,
    )


def evaluate_attribution(action_log: MarketingAutomationActionLog) -> AttributionMatch | None:
    if not is_production_recovery_send(action_log):
        return None

    strict = match_strict(action_log)
    if strict and strict.status == RecoveryAttribution.Status.MATCHED:
        return strict
    if strict and strict.status == RecoveryAttribution.Status.PENDING:
        return strict

    assisted = match_assisted(action_log)
    if assisted and assisted.status == RecoveryAttribution.Status.MATCHED:
        return assisted
    if assisted and assisted.status == RecoveryAttribution.Status.PENDING:
        return assisted

    return strict or assisted


def _apply_match_to_row(row: RecoveryAttribution, match: AttributionMatch, *, now) -> None:
    row.attribution_model = match.attribution_model or ''
    row.status = match.status
    row.paid_order = match.paid_order
    row.paid_at = match.paid_at
    row.lag_hours = Decimal(str(match.lag_hours)) if match.lag_hours is not None else None
    row.revenue_amount = match.revenue_amount
    row.rule_version = match.rule_version
    if match.status == RecoveryAttribution.Status.MATCHED and row.matched_at is None:
        row.matched_at = now


def build_attribution(
    action_log: MarketingAutomationActionLog,
    *,
    persist: bool = True,
) -> RecoveryAttribution | None:
    """ساخت/به‌روزرسانی سابقه نسبت‌دهی — matched/no_match immutable."""
    action_log = (
        MarketingAutomationActionLog.objects.select_related('order', 'user', 'product')
        .get(pk=action_log.pk)
    )
    if not is_production_recovery_send(action_log):
        return None

    match = evaluate_attribution(action_log)
    if match is None:
        return None

    now = timezone.now()
    user_id = action_log.user_id or (action_log.order.user_id if action_log.order_id else None)
    abandon_order = action_log.order

    if not persist:
        return RecoveryAttribution(
            action_log=action_log,
            user_id=user_id,
            abandon_order=abandon_order,
            attribution_model=match.attribution_model or '',
            status=match.status,
            paid_order=match.paid_order,
            paid_at=match.paid_at,
            lag_hours=Decimal(str(match.lag_hours)) if match.lag_hours is not None else None,
            revenue_amount=match.revenue_amount,
            matched_at=now if match.status == RecoveryAttribution.Status.MATCHED else None,
            rule_version=match.rule_version,
        )

    with transaction.atomic():
        existing = (
            RecoveryAttribution.objects.select_for_update()
            .filter(action_log=action_log)
            .first()
        )
        if existing and existing.status in (
            RecoveryAttribution.Status.MATCHED,
            RecoveryAttribution.Status.NO_MATCH,
        ):
            return existing

        if existing:
            if existing.status == RecoveryAttribution.Status.PENDING:
                _apply_match_to_row(existing, match, now=now)
                existing.save()
            return existing

        row = RecoveryAttribution(
            action_log=action_log,
            user_id=user_id,
            abandon_order=abandon_order,
        )
        _apply_match_to_row(row, match, now=now)
        try:
            row.save()
        except IntegrityError:
            return RecoveryAttribution.objects.filter(action_log=action_log).first()
        return row


def backfill_attributions(
    *,
    since=None,
    limit: int = BACKFILL_BATCH_LIMIT,
    refresh_pending: bool = True,
) -> dict[str, int]:
    """Backfill محدود — فقط production sends؛ idempotent."""
    since = since or (timezone.now() - timedelta(days=BACKFILL_DEFAULT_DAYS))
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'examined': 0}

    logs = (
        MarketingAutomationActionLog.objects.filter(
            flow_key=FLOW_KEY,
            created_at__gte=since,
        )
        .select_related('order', 'user', 'product')
        .order_by('created_at')[:limit]
    )

    for log in logs:
        if not is_production_recovery_send(log):
            stats['skipped'] += 1
            continue
        stats['examined'] += 1
        before_id = getattr(log, 'recovery_attribution', None)
        before_pk = before_id.pk if before_id else None
        before_status = before_id.status if before_id else None
        row = build_attribution(log, persist=True)
        if row is None:
            stats['skipped'] += 1
            continue
        if before_pk is None:
            stats['created'] += 1
        elif before_status == RecoveryAttribution.Status.PENDING and row.status != before_status:
            stats['updated'] += 1
        else:
            stats['skipped'] += 1

    if refresh_pending:
        pending_rows = (
            RecoveryAttribution.objects.filter(
                status=RecoveryAttribution.Status.PENDING,
                action_log__created_at__gte=since,
            )
            .select_related('action_log', 'action_log__order', 'action_log__user')
            .order_by('created_at')[:limit]
        )
        for row in pending_rows:
            stats['examined'] += 1
            before_status = row.status
            updated = build_attribution(row.action_log, persist=True)
            if updated and updated.status != before_status:
                stats['updated'] += 1

    return stats


def strict_matched_qs(*, since=None, until=None):
    qs = RecoveryAttribution.objects.filter(
        attribution_model=RecoveryAttribution.AttributionModel.STRICT,
        status=RecoveryAttribution.Status.MATCHED,
        action_log__flow_key=FLOW_KEY,
    )
    if since:
        qs = qs.filter(action_log__created_at__gte=since)
    if until:
        qs = qs.filter(action_log__created_at__lt=until)
    return qs


def executive_attribution_summary(*, since, until=None) -> dict[str, Any]:
    qs = strict_matched_qs(since=since, until=until)
    recovered = qs.count()
    revenue = sum(int(r.revenue_amount or 0) for r in qs.only('revenue_amount'))
    return {'recovered': recovered, 'recovery_revenue': revenue}


def journey_attribution_counts(*, since, step_key: str) -> dict[str, Any]:
    qs = strict_matched_qs(since=since).filter(action_log__step_key=step_key)
    paid = qs.count()
    return {'paid': paid}


def count_duplicate_strict_attributions(*, since=None) -> int:
    dupes = (
        strict_matched_qs(since=since)
        .exclude(paid_order__isnull=True)
        .values('paid_order_id')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    return sum(item['c'] - 1 for item in dupes)


def attribution_map_for_logs(log_ids: list[int]) -> dict[int, RecoveryAttribution]:
    if not log_ids:
        return {}
    rows = RecoveryAttribution.objects.filter(action_log_id__in=log_ids).select_related(
        'paid_order',
    )
    return {row.action_log_id: row for row in rows}


def serialize_attribution_for_explorer(row: RecoveryAttribution | None) -> dict[str, Any]:
    if row is None:
        return {
            'attribution_status': 'pending',
            'attribution_status_label': 'در انتظار',
            'attribution_model': None,
            'lag_hours': None,
            'revenue': None,
        }
    status_labels = {
        RecoveryAttribution.Status.PENDING: 'در انتظار',
        RecoveryAttribution.Status.MATCHED: 'منطبق',
        RecoveryAttribution.Status.NO_MATCH: 'بدون انطباق',
    }
    model_labels = {
        RecoveryAttribution.AttributionModel.STRICT: 'strict',
        RecoveryAttribution.AttributionModel.ASSISTED: 'assisted',
    }
    return {
        'attribution_status': row.status,
        'attribution_status_label': status_labels.get(row.status, row.status),
        'attribution_model': model_labels.get(row.attribution_model) or None,
        'lag_hours': float(row.lag_hours) if row.lag_hours is not None else None,
        'revenue': row.revenue_amount,
        'paid_order_id': str(row.paid_order_id) if row.paid_order_id else None,
    }
