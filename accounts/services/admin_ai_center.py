"""مرکز هوش مصنوعی — observability مصرف AI از AIUsageLog و AIQuota."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import (
    Avg,
    Count,
    Exists,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_user_profile_url import admin_user_profile_url
from accounts.services.admin_dashboard import (
    CHART_COLORS,
    _date_range,
    _fill_daily_series,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
    _today,
    is_all_time_range,
)
from ai_workspace.arvan_model_pricing import (
    aggregate_cost_from_model_rows,
    estimate_token_cost_toman,
    format_toman_amount,
)
from ai_workspace.constants import FEATURE_LABELS
from ai_workspace.models import AIQuota, AIUsageLog
from licenses.models import License

User = get_user_model()

AI_CENTER_CACHE_SECONDS = 120
RECENT_LOGS_LIMIT = 50
TOP_USERS_LIMIT = 5
NEAR_QUOTA_RATIO = 0.8

STATUS_PROVIDER_SUCCESS = (AIUsageLog.STATUS_OK, AIUsageLog.STATUS_FALLBACK)
CACHE_HIT_Q = Q(cache_hit=True) | Q(status=AIUsageLog.STATUS_CACHED)
PROVIDER_SUCCESS_Q = Q(status__in=STATUS_PROVIDER_SUCCESS) & ~Q(cache_hit=True)
LATENCY_ELIGIBLE_Q = ~CACHE_HIT_Q & Q(latency_ms__gt=0)
# توکن LLM قابل‌قیمت‌گذاری — بدون کش (مصرف provider واقعی نیست)
BILLABLE_TOKEN_Q = ~CACHE_HIT_Q

TOP_USER_MODES = (
    ('tokens', 'بر اساس توکن'),
    ('requests', 'بر اساس درخواست'),
    ('nl_command', 'فرمان هوشمند'),
)

LOG_FILTER_FEATURES = tuple(FEATURE_LABELS.keys())
LOG_FILTER_STATUSES = (
    AIUsageLog.STATUS_OK,
    AIUsageLog.STATUS_FALLBACK,
    AIUsageLog.STATUS_CACHED,
    AIUsageLog.STATUS_ERROR,
    AIUsageLog.STATUS_QUOTA,
)

ExportSheet = Tuple[str, List[str], List[Dict[str, Any]]]


def _effective_tokens_expr():
    return Coalesce(
        F('total_tokens'),
        Coalesce(F('input_tokens'), Value(0)) + Coalesce(F('output_tokens'), Value(0)),
        Value(0),
        output_field=IntegerField(),
    )


def _active_license_exists():
    now = timezone.now()
    return License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def _license_label(has_active: bool) -> str:
    return 'فعال' if has_active else 'بدون لایسنس فعال'


def format_latency_seconds(ms: int | None) -> Dict[str, str]:
    """تأخیر برای جدول لاگ — مثلاً 2s یا 3.4s."""
    raw = int(ms or 0)
    if raw <= 0:
        return {'display': '—', 'title': ''}
    sec = raw / 1000.0
    if sec >= 100:
        display = f'{sec:.0f}s'
    elif sec >= 1:
        rounded = round(sec, 1)
        display = f'{int(rounded)}s' if rounded == int(rounded) else f'{rounded}s'
    else:
        display = f'{round(sec, 1)}s'
    return {'display': display, 'title': f'{raw:,} ms'}


def format_latency_ms(value: float | int | None) -> Dict[str, Any]:
    ms = float(value or 0)
    if ms <= 0:
        return {'display': '—', 'exact': '0', 'unit': '', 'raw': 0}
    if ms >= 60_000:
        sec = ms / 1000
        return {'display': f'{sec:.1f}', 'exact': f'{ms:,.0f} ms', 'unit': 'ثانیه', 'raw': ms}
    if ms >= 1000:
        return {'display': f'{ms / 1000:.2f}'.rstrip('0').rstrip('.'), 'exact': f'{ms:,.0f} ms', 'unit': 'ثانیه', 'raw': ms}
    return {'display': f'{ms:.0f}', 'exact': f'{ms:,.0f} ms', 'unit': 'ms', 'raw': ms}


def format_token_count(value: int | None) -> Dict[str, Any]:
    n = int(value or 0)
    exact = f'{n:,}'
    if n >= 1_000_000:
        display = f'{n / 1_000_000:.2f}'.rstrip('0').rstrip('.') + 'M'
    elif n >= 10_000:
        display = f'{n / 1_000:.1f}'.rstrip('0').rstrip('.') + 'K'
    else:
        display = exact
    return {'raw': n, 'exact': exact, 'display': display}


def _safe_user_display(user) -> str:
    if not user:
        return '—'
    return user.get_full_name() or user.username or 'کاربر'


def _logs_in_range(days: int):
    start, end = _date_range(days)
    return AIUsageLog.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    )


def _cost_rows_from_queryset(qs) -> List[Dict[str, Any]]:
    billable = qs.filter(BILLABLE_TOKEN_Q)
    rows = billable.values('model').annotate(
        sum_input=Sum(Coalesce(F('input_tokens'), Value(0))),
        sum_output=Sum(Coalesce(F('output_tokens'), Value(0))),
    )
    return [{'model': r['model'], 'sum_input': r['sum_input'], 'sum_output': r['sum_output']} for r in rows]


def compute_ai_usage_cost_estimate(qs) -> Dict[str, Any]:
    return aggregate_cost_from_model_rows(_cost_rows_from_queryset(qs))


def _apply_log_filters(qs, *, feature: str | None, status: str | None, provider: str | None, user_id: int | None):
    if feature and feature in FEATURE_LABELS:
        qs = qs.filter(feature_code=feature)
    if status and status in LOG_FILTER_STATUSES:
        qs = qs.filter(status=status)
    if provider:
        qs = qs.filter(provider=provider)
    if user_id:
        qs = qs.filter(user_id=user_id)
    return qs


def _aggregate_kpis(qs) -> Dict[str, Any]:
    agg = qs.aggregate(
        total_requests=Count('id'),
        provider_success=Count('id', filter=PROVIDER_SUCCESS_Q),
        cache_hits=Count('id', filter=CACHE_HIT_Q),
        quota_exceeded=Count('id', filter=Q(status=AIUsageLog.STATUS_QUOTA)),
        errors=Count('id', filter=Q(status=AIUsageLog.STATUS_ERROR)),
        fallback_requests=Count('id', filter=Q(status=AIUsageLog.STATUS_FALLBACK)),
        sum_input_tokens=Sum(Coalesce(F('input_tokens'), Value(0))),
        sum_output_tokens=Sum(Coalesce(F('output_tokens'), Value(0))),
        sum_total_tokens=Sum(_effective_tokens_expr()),
        active_users=Count('user_id', distinct=True),
        avg_latency=Avg('latency_ms', filter=LATENCY_ELIGIBLE_Q),
    )
    total_requests = int(agg['total_requests'] or 0)
    fallback = int(agg['fallback_requests'] or 0)
    errors = int(agg['errors'] or 0)
    total_tokens = int(agg['sum_total_tokens'] or 0)
    input_tok = int(agg['sum_input_tokens'] or 0)
    output_tok = int(agg['sum_output_tokens'] or 0)
    return {
        'total_requests': total_requests,
        'provider_success': int(agg['provider_success'] or 0),
        'cache_hits': int(agg['cache_hits'] or 0),
        'quota_exceeded': int(agg['quota_exceeded'] or 0),
        'errors': errors,
        'fallback_requests': fallback,
        'fallback_rate': round((fallback / total_requests) * 100, 1) if total_requests else 0.0,
        'error_rate': round((errors / total_requests) * 100, 1) if total_requests else 0.0,
        'input_tokens': input_tok,
        'output_tokens': output_tok,
        'total_tokens': total_tokens,
        'active_users': int(agg['active_users'] or 0),
        'avg_latency_ms': round(float(agg['avg_latency'] or 0), 1) if agg['avg_latency'] is not None else None,
        'latency_formatted': format_latency_ms(
            round(float(agg['avg_latency'] or 0), 1) if agg['avg_latency'] is not None else None
        ),
        'tokens_formatted': format_token_count(total_tokens),
        'input_tokens_formatted': format_token_count(input_tok),
        'output_tokens_formatted': format_token_count(output_tok),
    }


def get_ai_kpis(days: int, compare: bool = False) -> Dict[str, Any]:
    qs = _logs_in_range(days)
    current = _aggregate_kpis(qs)
    cost = compute_ai_usage_cost_estimate(qs)
    current['cost_estimate'] = cost
    deltas: Dict[str, float | None] = {}
    if compare:
        prev_start, prev_end = _previous_period_bounds(days)
        prev_qs = AIUsageLog.objects.filter(
            created_at__date__gte=prev_start,
            created_at__date__lte=prev_end,
        )
        prev = _aggregate_kpis(prev_qs)
        prev_cost = compute_ai_usage_cost_estimate(prev_qs)
        for key in ('total_requests', 'total_tokens', 'active_users', 'errors'):
            deltas[key] = _pct_change(current[key], prev[key])
        deltas['estimated_cost_toman'] = _pct_change(
            cost['total_toman'],
            prev_cost['total_toman'],
        )
    current['deltas'] = deltas
    return current


def get_ai_daily_series(days: int) -> Dict[str, Any]:
    start, end = _date_range(days)
    base = AIUsageLog.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    req_rows = (
        base.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    tok_rows = (
        base.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum(_effective_tokens_expr()))
        .order_by('day')
    )
    in_rows = (
        base.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum(Coalesce(F('input_tokens'), Value(0))))
        .order_by('day')
    )
    out_rows = (
        base.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum(Coalesce(F('output_tokens'), Value(0))))
        .order_by('day')
    )
    labels, req_values = _fill_daily_series(start, end, req_rows, days=days)
    _, tok_values = _fill_daily_series(start, end, tok_rows, value_key='total', days=days)
    _, in_values = _fill_daily_series(start, end, in_rows, value_key='total', days=days)
    _, out_values = _fill_daily_series(start, end, out_rows, value_key='total', days=days)
    return {
        'labels': labels,
        'requests': req_values,
        'tokens': tok_values,
        'input_tokens': in_values,
        'output_tokens': out_values,
    }


def get_ai_feature_breakdown(days: int) -> List[Dict[str, Any]]:
    qs = _logs_in_range(days)
    totals = qs.aggregate(
        all_requests=Count('id'),
        all_tokens=Sum(_effective_tokens_expr()),
    )
    total_requests = int(totals['all_requests'] or 0) or 1
    total_tokens = int(totals['all_tokens'] or 0) or 1
    rows = (
        qs.values('feature_code')
        .annotate(
            requests=Count('id'),
            sum_input=Sum(Coalesce(F('input_tokens'), Value(0))),
            sum_output=Sum(Coalesce(F('output_tokens'), Value(0))),
            sum_tokens=Sum(_effective_tokens_expr()),
            avg_latency=Avg('latency_ms', filter=LATENCY_ELIGIBLE_Q),
            errors=Count('id', filter=Q(status=AIUsageLog.STATUS_ERROR)),
            cache_hits=Count('id', filter=CACHE_HIT_Q),
        )
        .order_by('-sum_tokens')
    )
    result = []
    for row in rows:
        req = int(row['requests'] or 0)
        tok = int(row['sum_tokens'] or 0)
        err = int(row['errors'] or 0)
        result.append({
            'feature_code': row['feature_code'],
            'label': FEATURE_LABELS.get(row['feature_code'], row['feature_code']),
            'requests': req,
            'input_tokens': int(row['sum_input'] or 0),
            'output_tokens': int(row['sum_output'] or 0),
            'total_tokens': tok,
            'total_tokens_formatted': format_token_count(tok),
            'avg_latency_ms': round(float(row['avg_latency'] or 0), 1) if row['avg_latency'] else None,
            'errors': err,
            'error_rate': round((err / req) * 100, 1) if req else 0.0,
            'cache_hits': int(row['cache_hits'] or 0),
            'request_share_pct': round((req / total_requests) * 100, 1),
            'token_share_pct': round((tok / total_tokens) * 100, 1),
        })
    return result


def get_ai_provider_breakdown(days: int) -> List[Dict[str, Any]]:
    qs = _logs_in_range(days)
    rows = (
        qs.values('provider', 'model')
        .annotate(
            requests=Count('id'),
            sum_tokens=Sum(_effective_tokens_expr()),
            sum_input=Sum(Coalesce(F('input_tokens'), Value(0)), filter=BILLABLE_TOKEN_Q),
            sum_output=Sum(Coalesce(F('output_tokens'), Value(0)), filter=BILLABLE_TOKEN_Q),
            avg_latency=Avg('latency_ms', filter=LATENCY_ELIGIBLE_Q),
            errors=Count('id', filter=Q(status=AIUsageLog.STATUS_ERROR)),
            fallbacks=Count('id', filter=Q(status=AIUsageLog.STATUS_FALLBACK)),
            max_attempt=Count('id', filter=Q(provider_attempt__gt=0)),
        )
        .order_by('-requests', 'provider', 'model')
    )
    result = []
    for row in rows:
        req = int(row['requests'] or 0)
        err = int(row['errors'] or 0)
        inp = int(row['sum_input'] or 0)
        out = int(row['sum_output'] or 0)
        cost_amount, priced = estimate_token_cost_toman(
            model=row['model'],
            input_tokens=inp,
            output_tokens=out,
        )
        result.append({
            'provider': row['provider'] or '—',
            'model': row['model'] or '—',
            'requests': req,
            'input_tokens': inp,
            'output_tokens': out,
            'total_tokens': int(row['sum_tokens'] or 0),
            'total_tokens_formatted': format_token_count(int(row['sum_tokens'] or 0)),
            'avg_latency_ms': round(float(row['avg_latency'] or 0), 1) if row['avg_latency'] else None,
            'error_rate': round((err / req) * 100, 1) if req else 0.0,
            'fallbacks': int(row['fallbacks'] or 0),
            'provider_attempt_rows': int(row['max_attempt'] or 0),
            'cost_toman': int(cost_amount) if priced else None,
            'cost_formatted': format_toman_amount(cost_amount) if priced else None,
            'cost_priced': priced and (inp or out),
        })
    return result


def get_ai_fallback_summary(days: int) -> Dict[str, Any]:
    qs = _logs_in_range(days).filter(status=AIUsageLog.STATUS_FALLBACK)
    total = _logs_in_range(days).count()
    count = qs.count()
    by_provider = list(
        qs.values('provider', 'model')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    return {
        'total': count,
        'rate_pct': round((count / total) * 100, 1) if total else 0.0,
        'by_provider_model': by_provider,
    }


def get_ai_top_users(days: int, mode: str = 'tokens', limit: int = TOP_USERS_LIMIT) -> List[Dict[str, Any]]:
    if mode not in {m[0] for m in TOP_USER_MODES}:
        mode = 'tokens'
    qs = _logs_in_range(days)
    if mode == 'nl_command':
        qs = qs.filter(feature_code='nl_command')
    annotated = (
        qs.values('user_id')
        .annotate(
            requests=Count('id'),
            sum_tokens=Sum(_effective_tokens_expr()),
            last_used_at=Max('created_at'),
        )
    )
    if mode == 'requests':
        annotated = annotated.order_by('-requests', '-sum_tokens')
    elif mode == 'nl_command':
        annotated = annotated.order_by('-requests', '-sum_tokens')
    else:
        annotated = annotated.order_by('-sum_tokens', '-requests')
    top_rows = list(annotated[:limit])
    if not top_rows:
        return []

    user_ids = [r['user_id'] for r in top_rows]
    total_tokens_all = int(_logs_in_range(days).aggregate(t=Sum(_effective_tokens_expr()))['t'] or 0) or 1
    users = {
        u.pk: u
        for u in User.objects.filter(pk__in=user_ids).annotate(
            has_active_license=Exists(_active_license_exists()),
        )
    }
    result = []
    for rank, row in enumerate(top_rows, 1):
        user = users.get(row['user_id'])
        tok = int(row['sum_tokens'] or 0)
        result.append({
            'rank': rank,
            'user_id': row['user_id'],
            'username': user.username if user else '—',
            'display_name': _safe_user_display(user),
            'phone': user.phone if user else '—',
            'requests': int(row['requests'] or 0),
            'total_tokens': tok,
            'total_tokens_formatted': format_token_count(tok),
            'token_share_pct': round((tok / total_tokens_all) * 100, 1),
            'last_used_at': row['last_used_at'],
            'license_label': _license_label(bool(user and user.has_active_license)),
            'user_admin_url': admin_user_profile_url(row['user_id']),
        })
    return result


def get_ai_recent_logs(
    days: int,
    *,
    feature: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    user_id: int | None = None,
    limit: int = RECENT_LOGS_LIMIT,
) -> List[Dict[str, Any]]:
    qs = _apply_log_filters(
        _logs_in_range(days),
        feature=feature,
        status=status,
        provider=provider,
        user_id=user_id,
    )
    logs = qs.select_related('user').order_by('-created_at')[:limit]
    rows = []
    for log in logs:
        eff = log.total_tokens
        if eff is None:
            eff = (log.input_tokens or 0) + (log.output_tokens or 0)
        inp = int(log.input_tokens or 0)
        out = int(log.output_tokens or 0)
        billable = not log.cache_hit and log.status != AIUsageLog.STATUS_CACHED
        cost_toman = 0
        cost_formatted = None
        if billable:
            cost_amount, priced = estimate_token_cost_toman(
                model=log.model,
                input_tokens=inp,
                output_tokens=out,
            )
            if priced and (inp or out):
                cost_toman = int(cost_amount)
                cost_formatted = format_toman_amount(cost_amount)
        latency = format_latency_seconds(log.latency_ms)
        rows.append({
            'id': log.pk,
            'created_at': log.created_at,
            'user_display': _safe_user_display(log.user),
            'user_admin_url': admin_user_profile_url(log.user_id),
            'feature_code': log.feature_code,
            'feature_label': FEATURE_LABELS.get(log.feature_code, log.feature_code),
            'provider': log.provider,
            'model': log.model or '—',
            'input_tokens': log.input_tokens,
            'output_tokens': log.output_tokens,
            'total_tokens': eff,
            'status': log.status,
            'latency_ms': log.latency_ms,
            'latency_label': latency['display'],
            'latency_title': latency['title'],
            'cost_toman': cost_toman if cost_formatted else None,
            'cost_formatted': cost_formatted,
            'cache_hit': log.cache_hit,
            'provider_attempt': log.provider_attempt,
            'prompt_hash': log.prompt_hash[:12] + '…' if log.prompt_hash else '',
        })
    return rows


def _global_cap_usage_today() -> Dict[str, Any]:
    from ai_workspace.services.gateway import _http_provider_count

    cap = int(getattr(settings, 'AI_GLOBAL_DAILY_CAP', 0) or 0)
    if cap <= 0:
        return {'enabled': False, 'cap': 0, 'used': 0, 'pct': 0}
    today = _today()
    max_attempt = _http_provider_count()
    used = AIUsageLog.objects.filter(
        created_at__date=today,
        cache_hit=False,
        status__in=STATUS_PROVIDER_SUCCESS,
        provider_attempt__gte=1,
        provider_attempt__lte=max_attempt,
    ).count()
    return {
        'enabled': True,
        'cap': cap,
        'used': used,
        'pct': min(100, round((used / cap) * 100, 1)) if cap else 0,
        'unit': 'request',
    }


def get_ai_quota_snapshot() -> Dict[str, Any]:
    today = _today()
    qs = AIQuota.objects.filter(reset_date=today)
    with_usage = qs.filter(Q(used_today__gt=0) | Q(tokens_used_today__gt=0))
    agg = with_usage.aggregate(
        users=Count('id'),
        used_today_sum=Sum('used_today'),
        tokens_sum=Sum('tokens_used_today'),
    )
    limited = list(
        qs.filter(is_unlimited=False, daily_limit__gt=0).values('used_today', 'daily_limit')
    )
    near = sum(
        1
        for row in limited
        if row['used_today'] >= int(row['daily_limit'] * NEAR_QUOTA_RATIO)
        and row['used_today'] < row['daily_limit']
    )
    exhausted = qs.filter(is_unlimited=False, daily_limit__gt=0, used_today__gte=F('daily_limit')).count()
    return {
        'date': today,
        'users_with_usage': int(agg['users'] or 0),
        'used_today_aggregate': int(agg['used_today_sum'] or 0),
        'tokens_used_today_aggregate': int(agg['tokens_sum'] or 0),
        'near_quota_users': near,
        'exhausted_users': exhausted,
        'global_cap': _global_cap_usage_today(),
    }


def _model_share_for_chart(days: int, limit: int = 6) -> Dict[str, Any]:
    rows = sorted(
        get_ai_provider_breakdown(days),
        key=lambda r: int(r.get('total_tokens') or 0),
        reverse=True,
    )
    top = rows[:limit]
    other_tokens = sum(int(r.get('total_tokens') or 0) for r in rows[limit:])
    labels = []
    values = []
    for row in top:
        model = (row.get('model') or '—')[:28]
        provider = (row.get('provider') or '')[:12]
        labels.append(f'{provider} · {model}' if provider else model)
        values.append(int(row.get('total_tokens') or 0))
    if other_tokens > 0:
        labels.append('سایر')
        values.append(other_tokens)
    total = sum(values) or 0
    return {
        'labels': labels,
        'values': values,
        'total_tokens': total,
        'total_formatted': format_token_count(total),
    }


def _build_charts(days: int) -> Dict[str, Any]:
    series = get_ai_daily_series(days)
    if sum(series['requests']) == 0 and sum(series['tokens']) == 0:
        return {}
    charts: Dict[str, Any] = {
        'ai_usage_trend': {
            'type': 'bar',
            'labels': series['labels'],
            'datasets': [
                {
                    'label': 'درخواست',
                    'data': series['requests'],
                    'backgroundColor': 'rgba(124, 58, 237, 0.55)',
                    'borderRadius': 6,
                },
            ],
            'axis': 'count',
        },
        'ai_token_consumption': {
            'type': 'line',
            'labels': series['labels'],
            'datasets': [
                {
                    'label': 'توکن ورودی',
                    'data': series['input_tokens'],
                    'borderColor': 'rgba(245, 158, 11, 1)',
                    'backgroundColor': 'rgba(245, 158, 11, 0.12)',
                    'fill': True,
                    'tension': 0.35,
                },
                {
                    'label': 'توکن خروجی',
                    'data': series['output_tokens'],
                    'borderColor': 'rgba(20, 184, 166, 1)',
                    'backgroundColor': 'rgba(20, 184, 166, 0.12)',
                    'fill': True,
                    'tension': 0.35,
                },
            ],
            'axis': 'count',
        },
    }
    share = _model_share_for_chart(days)
    if share['total_tokens'] > 0:
        charts['ai_model_share'] = {
            'type': 'doughnut',
            'labels': share['labels'],
            'datasets': [{
                'data': share['values'],
                'backgroundColor': CHART_COLORS[: len(share['values'])],
                'borderWidth': 0,
            }],
            'axis': 'count',
            'centerTotal': share['total_formatted']['display'],
            'centerLabel': 'توکن مجموع',
        }
    return charts


def _build_range_kpi_cards(kpis: Dict[str, Any], *, days: int, compare: bool) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)
    deltas = kpis.get('deltas') or {}

    def card(key, label, value, icon, accent, fmt='count', delta_key=None, sub=None):
        return {
            'key': key,
            'kind': 'range',
            'label': label,
            'sublabel': sub or range_label,
            'value': value,
            'format': fmt,
            'delta': deltas.get(delta_key) if compare and delta_key else None,
            'delta_label': 'نسبت دوره قبل',
            'icon': icon,
            'accent': accent,
            'status': 'ok',
        }

    tok = kpis['tokens_formatted']
    cost = kpis.get('cost_estimate') or {}
    cards = [
        card('ai_requests', 'درخواست AI', kpis['total_requests'], 'fa-bolt', 'violet', delta_key='total_requests'),
        card(
            'ai_tokens',
            'توکن مصرف‌شده',
            tok['raw'],
            'fa-microchip',
            'blue',
            fmt='token',
            delta_key='total_tokens',
            sub=f"ورودی {kpis['input_tokens_formatted']['display']} · خروجی {kpis['output_tokens_formatted']['display']}",
        ),
        card(
            'ai_estimated_cost',
            'هزینه تخمینی',
            cost.get('total_toman', 0),
            'fa-coins',
            'amber',
            fmt='toman',
            delta_key='estimated_cost_toman',
            sub=f"پوشش نرخ {cost.get('coverage_pct', 0)}٪ · Arvan catalog",
        ),
    ]
    cards.extend([
        card('ai_active_users', 'کاربران فعال AI', kpis['active_users'], 'fa-users', 'indigo', delta_key='active_users'),
        card('ai_cache', 'پاسخ از کش', kpis['cache_hits'], 'fa-database', 'cyan'),
        card('ai_errors', 'خطا', kpis['errors'], 'fa-triangle-exclamation', 'rose', delta_key='errors'),
        card(
            'ai_latency',
            'میانگین تأخیر',
            kpis['avg_latency_ms'] or 0,
            'fa-gauge',
            'amber',
            fmt='latency',
        ),
        card('ai_provider_ok', 'موفق Provider', kpis['provider_success'], 'fa-circle-check', 'emerald'),
        card('ai_quota', 'رد سهمیه', kpis['quota_exceeded'], 'fa-ban', 'red'),
    ])
    return cards


def _cache_key(
    days: int,
    compare: bool,
    *,
    feature: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    user_id: int | None = None,
    top_mode: str | None = None,
) -> str:
    parts = f'{days}|{int(compare)}|{feature or ""}|{status or ""}|{provider or ""}|{user_id or ""}|{top_mode or "tokens"}'
    digest = hashlib.md5(parts.encode()).hexdigest()[:12]
    return f'admin:ai_center:v2:{digest}'


def _build_query_suffix(
    days: int,
    compare: bool = False,
    *,
    top_mode: str | None = None,
    feature: str | None = None,
    status: str | None = None,
    provider: str | None = None,
) -> str:
    params: Dict[str, str] = {'days': str(days)}
    if compare:
        params['compare'] = '1'
    if top_mode and top_mode != 'tokens':
        params['top_mode'] = top_mode
    if feature:
        params['feature'] = feature
    if status:
        params['status'] = status
    if provider:
        params['provider'] = provider
    return '?' + urlencode(params)


def build_ai_center_context(
    *,
    days: int = 30,
    compare: bool = False,
    top_mode: str = 'tokens',
    log_filters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    log_filters = log_filters or {}
    cache_key = _cache_key(
        days,
        compare,
        feature=log_filters.get('feature'),
        status=log_filters.get('status'),
        provider=log_filters.get('provider'),
        user_id=log_filters.get('user_id'),
        top_mode=top_mode,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    kpis = get_ai_kpis(days, compare=compare)
    features = get_ai_feature_breakdown(days)
    providers = get_ai_provider_breakdown(days)
    fallback = get_ai_fallback_summary(days)
    top_users = get_ai_top_users(days, mode=top_mode)
    recent_logs = get_ai_recent_logs(
        days,
        feature=log_filters.get('feature'),
        status=log_filters.get('status'),
        provider=log_filters.get('provider'),
        user_id=log_filters.get('user_id'),
    )
    quota = get_ai_quota_snapshot()
    charts = _build_charts(days)
    provider_choices = list(
        _logs_in_range(days).values_list('provider', flat=True).distinct().order_by('provider')
    )

    ctx = {
        'range_label': _range_label_fa(days),
        'days': days,
        'compare': compare,
        'kpis': kpis,
        'range_kpi_cards': _build_range_kpi_cards(kpis, days=days, compare=compare),
        'feature_breakdown': features,
        'provider_breakdown': providers,
        'fallback_summary': fallback,
        'top_users': top_users,
        'top_user_modes': TOP_USER_MODES,
        'top_mode': top_mode,
        'recent_logs': recent_logs,
        'quota_snapshot': quota,
        'charts': charts,
        'charts_enabled': bool(charts),
        'model_share': _model_share_for_chart(days),
        'log_filters': log_filters,
        'log_filter_features': LOG_FILTER_FEATURES,
        'feature_filter_choices': [(k, FEATURE_LABELS.get(k, k)) for k in LOG_FILTER_FEATURES],
        'log_filter_statuses': LOG_FILTER_STATUSES,
        'provider_choices': [p for p in provider_choices if p],
        'query_suffix': _build_query_suffix(days, compare, top_mode=top_mode, **{
            k: log_filters.get(k) for k in ('feature', 'status', 'provider') if log_filters.get(k)
        }),
        'export_url': reverse('admin_panel_export', args=['ai_usage'])
        + f'?format=xlsx&days={"all" if is_all_time_range(days) else days}',
        'admin_list_url': reverse('admin:ai_workspace_aiusagelog_changelist'),
        'cost_estimate': kpis.get('cost_estimate') or compute_ai_usage_cost_estimate(_logs_in_range(days)),
        'help_note_nl_command': (
            'درخواست‌های «فرمان هوشمند» فقط parseهای AI را نشان می‌دهند؛ '
            'تأیید/Resolve ممکن است LLM نباشد و با اقدامات CRM یکی نیست.'
        ),
    }
    cache.set(cache_key, ctx, AI_CENTER_CACHE_SECONDS)
    return ctx


def build_ai_stats_json(
    *,
    days: int = 30,
    compare: bool = False,
    top_mode: str = 'tokens',
    log_filters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    log_filters = log_filters or {}
    cache_key = (
        _cache_key(
            days,
            compare,
            feature=log_filters.get('feature'),
            status=log_filters.get('status'),
            provider=log_filters.get('provider'),
            user_id=log_filters.get('user_id'),
            top_mode=top_mode,
        )
        + ':json'
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = {
        'days': days,
        'compare': compare,
        'range_label': _range_label_fa(days),
        'kpis': get_ai_kpis(days, compare=compare),
        'features': get_ai_feature_breakdown(days),
        'providers': get_ai_provider_breakdown(days),
        'fallback': get_ai_fallback_summary(days),
        'top_users': get_ai_top_users(days, mode=top_mode),
        'daily_series': get_ai_daily_series(days),
        'quota_snapshot': get_ai_quota_snapshot(),
        'recent_logs': get_ai_recent_logs(
            days,
            feature=log_filters.get('feature'),
            status=log_filters.get('status'),
            provider=log_filters.get('provider'),
            user_id=log_filters.get('user_id'),
        ),
    }
    cache.set(cache_key, payload, AI_CENTER_CACHE_SECONDS)
    return payload


def ai_usage_export_sheets(days: int) -> List[ExportSheet]:
    """خروجی چندبرگه Excel — بدون prompt."""
    kpis = get_ai_kpis(days, compare=False)
    features = get_ai_feature_breakdown(days)
    providers = get_ai_provider_breakdown(days)
    top_users = get_ai_top_users(days, mode='tokens', limit=50)
    logs = get_ai_recent_logs(days, limit=500)

    summary_headers = ['شاخص', 'مقدار']
    summary_rows = [
        {'شاخص': 'کل درخواست‌ها', 'مقدار': kpis['total_requests']},
        {'شاخص': 'موفق Provider', 'مقدار': kpis['provider_success']},
        {'شاخص': 'کش', 'مقدار': kpis['cache_hits']},
        {'شاخص': 'خطا', 'مقدار': kpis['errors']},
        {'شاخص': 'رد سهمیه', 'مقدار': kpis['quota_exceeded']},
        {'شاخص': 'Fallback', 'مقدار': kpis['fallback_requests']},
        {'شاخص': 'توکن ورودی', 'مقدار': kpis['input_tokens']},
        {'شاخص': 'توکن خروجی', 'مقدار': kpis['output_tokens']},
        {'شاخص': 'مجموع توکن', 'مقدار': kpis['total_tokens']},
        {'شاخص': 'کاربران فعال', 'مقدار': kpis['active_users']},
        {'شاخص': 'هزینه تخمینی (تومان)', 'مقدار': kpis.get('cost_estimate', {}).get('total_toman', 0)},
        {'شاخص': 'پوشش نرخ Arvan (٪)', 'مقدار': kpis.get('cost_estimate', {}).get('coverage_pct', 0)},
    ]

    feat_headers = [
        'قابلیت', 'درخواست', 'توکن ورودی', 'توکن خروجی', 'مجموع توکن',
        'میانگین تأخیر', 'خطا', 'نرخ خطا٪', 'کش', 'سهم درخواست٪', 'سهم توکن٪',
    ]
    feat_rows = [
        {
            'قابلیت': f['label'],
            'درخواست': f['requests'],
            'توکن ورودی': f['input_tokens'],
            'توکن خروجی': f['output_tokens'],
            'مجموع توکن': f['total_tokens'],
            'میانگین تأخیر': f['avg_latency_ms'] or '',
            'خطا': f['errors'],
            'نرخ خطا٪': f['error_rate'],
            'کش': f['cache_hits'],
            'سهم درخواست٪': f['request_share_pct'],
            'سهم توکن٪': f['token_share_pct'],
        }
        for f in features
    ]

    model_headers = [
        'Provider', 'Model', 'درخواست', 'توکن', 'میانگین تأخیر', 'نرخ خطا٪', 'Fallback',
    ]
    model_rows = [
        {
            'Provider': p['provider'],
            'Model': p['model'],
            'درخواست': p['requests'],
            'توکن': p['total_tokens'],
            'میانگین تأخیر': p['avg_latency_ms'] or '',
            'نرخ خطا٪': p['error_rate'],
            'Fallback': p['fallbacks'],
        }
        for p in providers
    ]

    user_headers = [
        'رتبه', 'کاربر', 'نام', 'موبایل', 'درخواست', 'توکن', 'سهم توکن٪', 'آخرین استفاده', 'لایسنس',
    ]
    user_rows = [
        {
            'رتبه': u['rank'],
            'کاربر': u['username'],
            'نام': u['display_name'],
            'موبایل': u['phone'],
            'درخواست': u['requests'],
            'توکن': u['total_tokens'],
            'سهم توکن٪': u['token_share_pct'],
            'آخرین استفاده': u['last_used_at'],
            'لایسنس': u['license_label'],
        }
        for u in top_users
    ]

    log_headers = [
        'زمان', 'کاربر', 'قابلیت', 'Provider', 'Model',
        'ورودی', 'خروجی', 'مجموع', 'هزینه تخمینی (تومان)', 'وضعیت', 'تأخیر', 'کش', 'تلاش Provider',
    ]
    log_rows = [
        {
            'زمان': r['created_at'],
            'کاربر': r['user_display'],
            'قابلیت': r['feature_label'],
            'Provider': r['provider'],
            'Model': r['model'],
            'ورودی': r['input_tokens'],
            'خروجی': r['output_tokens'],
            'مجموع': r['total_tokens'],
            'هزینه تخمینی (تومان)': r['cost_toman'] if r.get('cost_formatted') else '',
            'وضعیت': r['status'],
            'تأخیر': r.get('latency_label') or '—',
            'کش': 'بله' if r['cache_hit'] else 'خیر',
            'تلاش Provider': r['provider_attempt'],
        }
        for r in logs
    ]

    return [
        ('خلاصه', summary_headers, summary_rows),
        ('قابلیت‌ها', feat_headers, feat_rows),
        ('مدل‌ها', model_headers, model_rows),
        ('کاربران برتر', user_headers, user_rows),
        ('لاگ مصرف', log_headers, log_rows),
    ]
