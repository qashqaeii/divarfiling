"""Validate and normalize Management AI LLM responses."""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from accounts.services.management_ai.schemas import (
    MAX_ACTIONS,
    MAX_INSIGHTS,
    MAX_OPPORTUNITIES,
    MAX_RISKS,
)


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


def validate_analysis_response(
    data: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    allowed_refs = _collect_metric_paths(snapshot)

    def check_refs(refs: Any, ctx: str) -> None:
        if not refs:
            return
        if not isinstance(refs, list):
            errors.append(f'{ctx}: metric_refs must be a list')
            return
        for ref in refs:
            if not isinstance(ref, str) or not _valid_ref(ref, allowed_refs):
                errors.append(f'{ctx}: invalid metric_ref {ref!r}')

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
            check_refs(item.get('metric_refs'), f'insights[{i}]')
            cleaned['insights'].append({
                'title': str(item.get('title') or ''),
                'description': str(item.get('description') or ''),
                'type': item.get('type') if item.get('type') in ('fact', 'interpretation', 'hypothesis') else 'interpretation',
                'metric_refs': list(item.get('metric_refs') or []),
                'confidence': float(item.get('confidence') or 0),
            })

    actions = data.get('actions') or []
    targets = snapshot.get('action_targets') or {}
    if isinstance(actions, list):
        for i, item in enumerate(actions[:MAX_ACTIONS]):
            if not isinstance(item, dict):
                continue
            check_refs(item.get('metric_refs'), f'actions[{i}]')
            target_ref = item.get('action_target_ref')
            if target_ref and target_ref not in targets:
                errors.append(f'actions[{i}]: invalid action_target_ref {target_ref!r}')
            cleaned['actions'].append({
                'title': str(item.get('title') or ''),
                'description': str(item.get('description') or ''),
                'priority': item.get('priority') if item.get('priority') in ('critical', 'high', 'medium', 'low') else 'medium',
                'impact': item.get('impact') if item.get('impact') in ('high', 'medium', 'low') else 'medium',
                'effort': item.get('effort') if item.get('effort') in ('high', 'medium', 'low') else 'medium',
                'metric_refs': list(item.get('metric_refs') or []),
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
            check_refs(item.get('metric_refs'), f'{key}[{i}]')
            entry = {
                'title': str(item.get('title') or ''),
                'description': str(item.get('description') or ''),
                'metric_refs': list(item.get('metric_refs') or []),
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
