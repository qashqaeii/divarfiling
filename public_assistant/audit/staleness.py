"""طراحی بررسی stale شدن مقالات — بدون تغییر DB در فاز ۱."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from public_assistant.audit.paths import django_root, monorepo_root


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


def build_staleness_plan(source_index: dict[str, Any]) -> dict[str, Any]:
    """
    خروجی برای staleness_registry.yaml — snapshot هش فایل‌های مرجع.
    فاز ۲: با مقایسه snapshot قبلی، article stale می‌شود.
    """
    snapshots: list[dict[str, Any]] = []
    for entry in source_index.get('entries') or []:
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
                    'article_ids': [],
                }
            )
    return {'version': 1, 'snapshot_count': len(snapshots), 'snapshots': snapshots}
