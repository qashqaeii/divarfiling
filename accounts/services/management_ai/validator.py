"""Validate and normalize Management AI LLM responses."""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from accounts.services.management_ai.schemas import (
    MAX_ACTIONS,
    MAX_INSIGHTS,
    MAX_OPPORTUNITIES,
    MAX_RISKS,
)


# Sales snapshot uses orders_pending target key; facts/LLM often say pending_orders.
_ACTION_TARGET_ALIASES: Dict[str, Tuple[str, ...]] = {
    'pending_orders': ('orders_pending',),
    'orders_pending': ('pending_orders',),
}


def _collect_fact_paths(snapshot: Dict[str, Any]) -> Set[str]:
    paths: Set[str] = set()
    for fact in snapshot.get('facts') or []:
        if isinstance(fact, dict):
            key = fact.get('key')
            if key:
                paths.add(f'facts.{key}')
    return paths


def _collect_allowed_refs(snapshot: Dict[str, Any]) -> Set[str]:
    return _collect_metric_paths(snapshot) | _collect_fact_paths(snapshot)


def _collect_metric_paths(snapshot: Dict[str, Any], prefix: str = 'metrics') -> Set[str]:
    paths: Set[str] = set()
    node = snapshot.get('metrics') if prefix == 'metrics' else snapshot
    if not isinstance(node, dict):
        return paths

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            if 'current' in obj or 'change_percent' in obj or 'unit' in obj:
                if path:
                    paths.add(path)
                return
            for k, v in obj.items():
                child = f'{path}.{k}' if path else k
                walk(v, child)
        elif isinstance(obj, list) and path:
            paths.add(path)

    for key, val in node.items():
        walk(val, f'{prefix}.{key}')
    return paths


def _valid_ref(ref: str, allowed: Set[str]) -> bool:
    if ref in allowed:
        return True
    # nested section metrics for executive e.g. metrics.users.users_new_period
    return any(ref.startswith(p + '.') for p in allowed)


def _normalize_action_target_ref(ref: Any, targets: Dict[str, Any]) -> str | None:
    if not ref or not isinstance(ref, str):
        return None
    text = ref.strip()
    if text.startswith('action_targets.'):
        text = text[len('action_targets.'):]
    if text in targets:
        return text
    for alt in _ACTION_TARGET_ALIASES.get(text, ()):
        if alt in targets:
            return alt
    return None


def _normalize_metric_ref(ref: str, allowed: Set[str]) -> str | None:
    """Map provider shorthand (e.g. retention_d30) to snapshot paths (metrics.retention_d30)."""
    if not ref:
        return None
    text = ref.strip()
    if text.startswith('facts.'):
        fact_key = text[6:]
        metric_path = f'metrics.{fact_key}'
        if metric_path in allowed:
            return metric_path
        if _valid_ref(text, allowed):
            return text
    if _valid_ref(text, allowed):
        return text
    if not text.startswith('metrics.'):
        prefixed = f'metrics.{text}'
        if _valid_ref(prefixed, allowed):
            return prefixed
    suffix_matches = [
        p for p in allowed
        if p == text or p.endswith(f'.{text}') or p.split('.')[-1] == text
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    if len(suffix_matches) > 1:
        preferred = f'metrics.{text}'
        if preferred in suffix_matches:
            return preferred
        return min(suffix_matches, key=len)
    return None


def _normalize_metric_refs(
    refs: Any,
    allowed: Set[str],
    ctx: str,
    errors: List[str],
) -> List[str]:
    if not refs:
        return []
    if not isinstance(refs, list):
        errors.append(f'{ctx}: metric_refs must be a list')
        return []
    normalized: List[str] = []
    for ref in refs:
        if not isinstance(ref, str):
            errors.append(f'{ctx}: metric_ref must be a string')
            continue
        canon = _normalize_metric_ref(ref, allowed)
        if canon:
            if canon not in normalized:
                normalized.append(canon)
        else:
            errors.append(f'{ctx}: invalid metric_ref {ref!r}')
    return normalized


def validate_analysis_response(
    data: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    allowed_refs = _collect_allowed_refs(snapshot)

    cleaned = {
        'summary': str(data.get('summary') or '').strip(),
        'status': data.get('status') or 'watch',
        'insights': [],
        'actions': [],
        'risks': [],
        'opportunities': [],
    }

    if cleaned['status'] not in ('good', 'watch', 'warning', 'critical'):
        cleaned['status'] = 'watch'

    insights = data.get('insights') or []
    if isinstance(insights, list):
        for i, item in enumerate(insights[:MAX_INSIGHTS]):
            if not isinstance(item, dict):
                continue
            metric_refs = _normalize_metric_refs(
                item.get('metric_refs'), allowed_refs, f'insights[{i}]', errors,
            )
            cleaned['insights'].append({
                'title': str(item.get('title') or ''),
                'description': str(item.get('description') or ''),
                'type': item.get('type') if item.get('type') in ('fact', 'interpretation', 'hypothesis') else 'interpretation',
                'metric_refs': metric_refs,
                'confidence': float(item.get('confidence') or 0),
            })

    actions = data.get('actions') or []
    targets = snapshot.get('action_targets') or {}
    if isinstance(actions, list):
        for i, item in enumerate(actions[:MAX_ACTIONS]):
            if not isinstance(item, dict):
                continue
            metric_refs = _normalize_metric_refs(
                item.get('metric_refs'), allowed_refs, f'actions[{i}]', errors,
            )
            raw_target = item.get('action_target_ref')
            target_ref = _normalize_action_target_ref(raw_target, targets) if raw_target else None
            if raw_target and not target_ref:
                errors.append(f'actions[{i}]: invalid action_target_ref {raw_target!r}')
            cleaned['actions'].append({
                'title': str(item.get('title') or ''),
                'description': str(item.get('description') or ''),
                'priority': item.get('priority') if item.get('priority') in ('critical', 'high', 'medium', 'low') else 'medium',
                'impact': item.get('impact') if item.get('impact') in ('high', 'medium', 'low') else 'medium',
                'effort': item.get('effort') if item.get('effort') in ('high', 'medium', 'low') else 'medium',
                'metric_refs': metric_refs,
                'action_target_ref': target_ref,
            })

    for block, max_n, key in (
        (data.get('risks'), MAX_RISKS, 'risks'),
        (data.get('opportunities'), MAX_OPPORTUNITIES, 'opportunities'),
    ):
        if not isinstance(block, list):
            continue
        for i, item in enumerate(block[:max_n]):
            if not isinstance(item, dict):
                continue
            metric_refs = _normalize_metric_refs(
                item.get('metric_refs'), allowed_refs, f'{key}[{i}]', errors,
            )
            entry = {
                'title': str(item.get('title') or ''),
                'description': str(item.get('description') or ''),
                'metric_refs': metric_refs,
            }
            if key == 'risks':
                entry['severity'] = item.get('severity') if item.get('severity') in ('critical', 'high', 'medium', 'low') else 'medium'
            else:
                entry['potential'] = item.get('potential') if item.get('potential') in ('high', 'medium', 'low') else 'medium'
            cleaned[key].append(entry)

    invalid_ratio = len(errors) / max(1, len(cleaned['insights']) + len(cleaned['actions']))
    if errors and invalid_ratio > 0.5:
        raise ValueError('Too many invalid metric_refs in AI response: ' + '; '.join(errors[:5]))

    return cleaned, errors
