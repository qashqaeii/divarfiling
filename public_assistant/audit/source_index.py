"""Source Index — نگاشت قابلیت به فایل‌های پروژه."""
from __future__ import annotations

from typing import Any


def build_source_index(catalog: dict[str, Any], articles: list[dict[str, Any]]) -> dict[str, Any]:
    article_map = {a['article_id']: a for a in articles}
    entries: list[dict[str, Any]] = []

    for f in catalog.get('features') or []:
        refs = []
        for r in f.get('source_refs') or []:
            resolved = next(
                (x for x in (f.get('source_refs_resolved') or []) if x.get('ref') == r),
                {'ref': r, 'exists': None},
            )
            refs.append(resolved)

        for aid in f.get('knowledge_articles') or []:
            art = article_map.get(aid)
            if art and art.get('source_path'):
                refs.append({'ref': art['source_path'], 'exists': True, 'kind': 'knowledge_article'})

        entries.append(
            {
                'feature_id': f['id'],
                'title': f.get('title'),
                'domain': f.get('domain'),
                'source_refs': refs,
                'web_paths': f.get('web_paths') or [],
                'platforms': f.get('platforms') or [],
                'conflicts': f.get('verification_notes') or [],
            }
        )

    missing_refs = sum(
        1
        for e in entries
        for r in e['source_refs']
        if r.get('exists') is False
    )

    return {
        'entry_count': len(entries),
        'missing_source_files': missing_refs,
        'priority_order_documented': [
            'executable_code_and_permissions',
            'templates_ui',
            'tests',
            'internal_guides',
        ],
        'entries': entries,
    }
