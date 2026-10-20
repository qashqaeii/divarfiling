"""Snapshot و diff برای staleness — بدون تغییر DB."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from public_assistant.audit.paths import audit_output_dir, django_root, monorepo_root


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_ref_path(ref: str) -> Path | None:
    ref = ref.split('#')[0].strip()
    for base in (django_root(), monorepo_root()):
        p = base / ref
        if p.is_file():
            return p
    return None


def _registry_path() -> Path:
    return audit_output_dir() / 'staleness_registry.yaml'


def load_previous_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.is_file():
        return {'version': 2, 'snapshots': []}
    return yaml.safe_load(path.read_text(encoding='utf-8')) or {'version': 2, 'snapshots': []}


def build_staleness_plan(
    source_index: dict[str, Any],
    catalog_features: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    feature_articles = {
        f['id']: list(f.get('knowledge_articles') or [])
        for f in (catalog_features or [])
    }
    snapshots: list[dict[str, Any]] = []
    for entry in source_index.get('entries') or []:
        article_ids = entry.get('knowledge_article_ids') or feature_articles.get(entry['feature_id'], [])
        for ref_item in entry.get('source_refs') or []:
            ref = ref_item.get('ref')
            if not ref or ref_item.get('kind') == 'knowledge_article':
                continue
            path = resolve_ref_path(ref)
            if not path:
                continue
            snapshots.append(
                {
                    'feature_id': entry['feature_id'],
                    'ref': ref,
                    'content_sha256': _file_sha256(path),
                    'article_ids': article_ids,
                    'linkage': ref_item.get('linkage'),
                }
            )

    previous = load_previous_registry()
    prev_map = {
        (s.get('feature_id'), s.get('ref')): s.get('content_sha256')
        for s in previous.get('snapshots') or []
    }
    changes: list[dict[str, Any]] = []
    for s in snapshots:
        key = (s['feature_id'], s['ref'])
        old_hash = prev_map.get(key)
        if old_hash and old_hash != s['content_sha256']:
            changes.append(
                {
                    'feature_id': s['feature_id'],
                    'ref': s['ref'],
                    'article_ids': s['article_ids'],
                    'previous_sha256': old_hash,
                    'current_sha256': s['content_sha256'],
                }
            )
        elif old_hash is None and prev_map:
            changes.append(
                {
                    'feature_id': s['feature_id'],
                    'ref': s['ref'],
                    'article_ids': s['article_ids'],
                    'change': 'new_ref_tracked',
                }
            )

    return {
        'version': 2,
        'snapshot_count': len(snapshots),
        'snapshots': snapshots,
        'diff': {
            'previous_snapshot_count': len(prev_map),
            'changed_count': len(changes),
            'changes': changes,
        },
    }


def write_staleness_registry(plan: dict[str, Any]) -> Path:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    history_path = audit_output_dir() / 'staleness_diff.json'
    import json

    history_path.write_text(json.dumps(plan.get('diff', {}), ensure_ascii=False, indent=2), encoding='utf-8')
    to_save = {k: v for k, v in plan.items() if k != 'diff'}
    to_save['last_diff_summary'] = plan.get('diff', {})
    path.write_text(yaml.safe_dump(to_save, allow_unicode=True, sort_keys=False), encoding='utf-8')
    return path
