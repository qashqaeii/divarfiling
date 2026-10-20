"""ارزیابی عمق پوشش دانشنامه برای هر قابلیت."""
from __future__ import annotations

import re
from typing import Any

Depth = str  # none | overview | howto | full

_DIMENSIONS = (
    'intro_purpose',
    'ui_location',
    'howto_steps',
    'prerequisites_limits',
    'specialist_scenarios',
    'troubleshooting',
    'compare_similar',
    'faq_synonyms',
)


def _article_by_id(articles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {a['article_id']: a for a in articles}


def _load_article_bodies() -> dict[str, str]:
    from public_assistant.audit.paths import knowledge_articles_dir
    from public_assistant.services.knowledge_loader import parse_markdown_file

    bodies: dict[str, str] = {}
    root = knowledge_articles_dir()
    for path in sorted(root.glob('*.md')):
        parsed = parse_markdown_file(path)
        bodies[str(parsed.meta['id'])] = parsed.body
    return bodies


def score_article_coverage(article_id: str, meta: dict[str, Any], body: str) -> dict[str, bool]:
    norm = body.lower()
    headings = meta.get('headings') or []
    has_steps = bool(re.search(r'^\s*\d+\.\s', body, re.MULTILINE)) or 'مرحله' in body
    return {
        'intro_purpose': bool(meta.get('summary')) or 'چیست' in body or '## ' in body,
        'ui_location': '/workspace/' in body or 'مسیر' in body or '←' in body,
        'howto_steps': has_steps or 'چطور' in body,
        'prerequisites_limits': bool(meta.get('prerequisites')) or bool(meta.get('limitations')) or 'پیش' in norm,
        'specialist_scenarios': len(headings) >= 3 or body.count('##') >= 3,
        'troubleshooting': any(w in body for w in ('خطا', 'مشکل', 'کار نکرد', 'نمی')),
        'compare_similar': 'تفاوت' in body or '|' in body,
        'faq_synonyms': bool(meta.get('synonyms')) and len(meta.get('synonyms') or []) >= 2,
    }


def aggregate_depth(dimensions: dict[str, bool]) -> Depth:
    if not any(dimensions.values()):
        return 'none'
    true_count = sum(1 for v in dimensions.values() if v)
    if dimensions.get('howto_steps') and dimensions.get('ui_location') and true_count >= 6:
        return 'full'
    if dimensions.get('howto_steps') and dimensions.get('ui_location'):
        return 'howto'
    if true_count >= 2:
        return 'overview'
    return 'none'


def build_coverage_for_feature(
    feature: dict[str, Any],
    articles_index: dict[str, dict[str, Any]],
    bodies: dict[str, str],
) -> dict[str, Any]:
    article_ids = feature.get('knowledge_articles') or []
    help_ids = feature.get('help_section_ids') or []
    combined_dims = {d: False for d in _DIMENSIONS}
    article_depths: list[Depth] = []

    for aid in article_ids:
        meta = articles_index.get(aid)
        if not meta:
            continue
        body = bodies.get(aid, '')
        dims = score_article_coverage(aid, meta, body)
        for k, v in dims.items():
            combined_dims[k] = combined_dims[k] or v
        article_depths.append(aggregate_depth(dims))

    depth = aggregate_depth(combined_dims)
    if article_depths:
        order = {'none': 0, 'overview': 1, 'howto': 2, 'full': 3}
        depth = max(article_depths, key=lambda d: order.get(d, 0))
    elif help_ids and not article_ids:
        # راهنمای میزکار جایگزین مقاله دانشنامه نیست — سقف overview
        combined_dims['intro_purpose'] = True
        if depth == 'none':
            depth = 'overview'
        order = {'none': 0, 'overview': 1, 'howto': 2, 'full': 3}
        if order.get(depth, 0) > 1:
            depth = 'overview'

    return {
        'feature_id': feature['id'],
        'overall_depth': depth,
        'dimensions': combined_dims,
        'linked_articles': article_ids,
        'help_sections': help_ids,
    }


def coverage_rows(features: list[dict], articles: list[dict]) -> list[dict[str, Any]]:
    index = _article_by_id(articles)
    bodies = _load_article_bodies()
    rows = []
    for f in features:
        cov = build_coverage_for_feature(f, index, bodies)
        row = {
            'feature_id': f['id'],
            'domain': f.get('domain', ''),
            'title': f.get('title', ''),
            'overall_depth': cov['overall_depth'],
            **{f'dim_{k}': ('yes' if cov['dimensions'][k] else 'no') for k in _DIMENSIONS},
            'knowledge_articles': ';'.join(cov['linked_articles']),
            'help_sections': ';'.join(cov['help_sections']),
            'release_status': f.get('release_status', 'unverified'),
        }
        rows.append(row)
    return rows
