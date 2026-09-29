"""Shared helpers for snapshot builders."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def kpi_metrics(
    cards: List[Dict[str, Any]],
    keys: List[str],
    *,
    include_comparison: bool,
) -> Dict[str, Any]:
    by_key = {c['key']: c for c in cards if c.get('key')}
    metrics: Dict[str, Any] = {}
    for key in keys:
        card = by_key.get(key)
        if not card:
            continue
        entry: Dict[str, Any] = {'current': card.get('value')}
        fmt = card.get('format')
        if fmt == 'percent':
            entry['unit'] = 'percent'
        elif fmt == 'money':
            entry['unit'] = 'toman'
        if include_comparison and card.get('delta') is not None:
            entry['change_percent'] = card.get('delta')
        metrics[key] = entry
    return metrics


def trend_summary(charts: Dict[str, Any], chart_key: str) -> Optional[Dict[str, Any]]:
    block = charts.get(chart_key) or {}
    values = block.get('values') or block.get('counts')
    if not values and isinstance(block.get('datasets'), list) and block['datasets']:
        values = block['datasets'][0].get('data')
    values = values or []
    if not isinstance(values, list) or not values:
        return None
    nums = [int(v or 0) for v in values]
    return {
        'points': len(nums),
        'total': sum(nums),
        'last': nums[-1],
    }
