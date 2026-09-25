"""نرخ کاتالوگ Arvan AIaaS (تومان / ۱M توکن) — برای تخمین هزینه در Admin."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

# منبع: کاتالوگ مدل در پنل Arvan (به‌روزرسانی دستی هنگام تغییر قیمت)
ARVAN_MODEL_PRICING_TOMAN_PER_M: Dict[str, Dict[str, Any]] = {
    'gemini-2.5-flash-lite': {
        'label': 'Gemini-2.5-Flash-lite',
        'input_per_m': Decimal('21000'),
        'output_per_m': Decimal('84000'),
    },
    'deepseek-v4-flash': {
        'label': 'DeepSeek-V4-Flash',
        'input_per_m': Decimal('29400'),
        'output_per_m': Decimal('58800'),
    },
}

_MODEL_ALIASES = {
    'gemini-2-5-flash-lite': 'gemini-2.5-flash-lite',
    'gemini-2.5-flash-lite': 'gemini-2.5-flash-lite',
    'deepseek-v4-flash': 'deepseek-v4-flash',
    'deepseek-v3-flash': 'deepseek-v4-flash',
}

MILLION = Decimal('1000000')
COST_DISCLAIMER_FA = (
    'تخمین بر اساس نرخ کاتالوگ Arvan برای مدل‌های شناخته‌شده؛ '
    'بدون cache؛ مدل‌های بدون نرخ و providerهای غیر Arvan در جمع لحاظ نمی‌شوند.'
)


def normalize_model_key(model: str | None) -> str:
    raw = (model or '').strip().lower().replace('_', '-')
    if not raw or raw in ('—', '-', 'rule_based', 'cache'):
        return ''
    return _MODEL_ALIASES.get(raw, raw)


def lookup_model_pricing(model: str | None) -> Optional[Dict[str, Any]]:
    key = normalize_model_key(model)
    if not key:
        return None
    return ARVAN_MODEL_PRICING_TOMAN_PER_M.get(key)


def estimate_token_cost_toman(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
) -> Tuple[Decimal, bool]:
    """هزینه تومان برای یک aggregate؛ (مبلغ, آیا نرخ داشت)."""
    pricing = lookup_model_pricing(model)
    if not pricing:
        return Decimal('0'), False
    inp = max(0, int(input_tokens or 0))
    out = max(0, int(output_tokens or 0))
    if inp == 0 and out == 0:
        return Decimal('0'), True
    cost = (
        Decimal(inp) * pricing['input_per_m'] / MILLION
        + Decimal(out) * pricing['output_per_m'] / MILLION
    )
    return cost.quantize(Decimal('1'), rounding=ROUND_HALF_UP), True


def format_toman_amount(amount: Decimal | int | float) -> Dict[str, Any]:
    val = Decimal(amount or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    n = int(val)
    if n >= 1_000_000:
        display = f'{n / 1_000_000:.2f}'.rstrip('0').rstrip('.') + 'M'
    elif n >= 10_000:
        display = f'{n / 1_000:.1f}'.rstrip('0').rstrip('.') + 'K'
    else:
        display = f'{n:,}'
    return {'raw': n, 'exact': f'{n:,}', 'display': display}


def aggregate_cost_from_model_rows(
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    rows: هر آیتم شامل model, sum_input, sum_output (یا input_tokens/output_tokens).
    """
    total = Decimal('0')
    priced_in = priced_out = 0
    unpriced_in = unpriced_out = 0
    by_model: List[Dict[str, Any]] = []

    for row in rows:
        model = row.get('model') or ''
        inp = int(row.get('sum_input') or row.get('input_tokens') or 0)
        out = int(row.get('sum_output') or row.get('output_tokens') or 0)
        cost, priced = estimate_token_cost_toman(model=model, input_tokens=inp, output_tokens=out)
        pricing = lookup_model_pricing(model)
        if priced and pricing:
            total += cost
            priced_in += inp
            priced_out += out
            by_model.append({
                'model': model,
                'label': pricing['label'],
                'input_tokens': inp,
                'output_tokens': out,
                'cost_toman': int(cost),
                'cost_formatted': format_toman_amount(cost),
                'priced': True,
            })
        else:
            unpriced_in += inp
            unpriced_out += out
            if inp or out:
                by_model.append({
                    'model': model or '—',
                    'label': model or '—',
                    'input_tokens': inp,
                    'output_tokens': out,
                    'cost_toman': None,
                    'cost_formatted': None,
                    'priced': False,
                })

    billable_tokens = priced_in + priced_out + unpriced_in + unpriced_out
    priced_tokens = priced_in + priced_out
    coverage = round((priced_tokens / billable_tokens) * 100, 1) if billable_tokens else 0.0

    by_model.sort(key=lambda x: (not x['priced'], -(x.get('cost_toman') or 0)))

    total_int = int(total)
    return {
        'total_toman': total_int,
        'total_formatted': format_toman_amount(total),
        'priced_input_tokens': priced_in,
        'priced_output_tokens': priced_out,
        'unpriced_input_tokens': unpriced_in,
        'unpriced_output_tokens': unpriced_out,
        'coverage_pct': coverage,
        'by_model': by_model,
        'disclaimer': COST_DISCLAIMER_FA,
        'has_estimate': total_int > 0 or priced_tokens > 0,
        'catalog_models': list(ARVAN_MODEL_PRICING_TOMAN_PER_M.keys()),
    }
