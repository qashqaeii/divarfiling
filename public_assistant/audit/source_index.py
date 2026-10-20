"""Source Index — ارتباط قابل ردیابی با قابلیت."""
from __future__ import annotations

from typing import Any

_LINKAGE_FOR_TYPE = {
    'feature': 'product_capability',
    'help_topic': 'help_content_topic',
    'help_section': 'help_content_section',
    'operation': 'ui_operation',
    'internal_endpoint': 'api_or_internal',
}


def build_source_index(catalog: dict[str, Any], articles: list[dict[str, Any]]) -> dict[str, Any]:
    article_map = {a['article_id']: a for a in articles}
    entries: list[dict[str, Any]] = []

    for f in catalog.get('features') or []:
        entity = f.get('entity_type', 'feature')
        linkage = f.get('source_linkage') or _LINKAGE_FOR_TYPE.get(entity, 'unknown')
        refs = []
        for r in f.get('source_refs') or []:
            resolved = next(
                (x for x in (f.get('source_refs_resolved') or []) if x.get('ref') == r),
                {'ref': r, 'exists': None},
            )
            refs.append(
                {
                    **resolved,
                    'linkage': linkage,
                    'relevance': 'primary' if entity == 'feature' else 'supporting',
                    'trace': f"feature:{f['id']}->{r}",
                }
            )

        for aid in f.get('knowledge_articles') or []:
            art = article_map.get(aid)
            if art and art.get('source_path'):
                refs.append(
                    {
                        'ref': art['source_path'],
                        'exists': True,
                        'kind': 'knowledge_article',
                        'linkage': 'knowledge_article',
                        'relevance': 'primary',
                        'article_id': aid,
                        'trace': f"feature:{f['id']}->article:{aid}",
                    }
                )

        entries.append(
            {
                'feature_id': f['id'],
                'entity_type': entity,
                'title': f.get('title'),
                'domain': f.get('domain'),
                'parent_id': f.get('parent_id'),
                'knowledge_article_ids': f.get('knowledge_articles') or [],
                'source_refs': refs,
                'web_paths': f.get('web_paths') or [],
                'platforms': f.get('platforms') or [],
                'conflicts': f.get('verification_notes') or [],
            }
        )

    missing_refs = sum(
        1 for e in entries for r in e['source_refs'] if r.get('exists') is False
    )
    weak_trace = sum(
        1
        for e in entries
        if e.get('entity_type') == 'feature'
        and not e.get('knowledge_article_ids')
        and not e.get('web_paths')
    )

    return {
        'entry_count': len(entries),
        'missing_source_files': missing_refs,
        'features_without_article_or_path': weak_trace,
        'priority_order_documented': [
            'executable_code_and_permissions',
            'templates_ui',
            'tests',
            'internal_guides',
        ],
        'entries': entries,
    }
