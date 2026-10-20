"""ارزیابی پوشش: heuristic_coverage و verified_coverage جدا."""
from __future__ import annotations

import re
from typing import Any

HeuristicDepth = str  # none | overview | howto
VerifiedDepth = str  # none | overview | howto | full | needs_review

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


def _numbered_step_count(body: str) -> int:
    return len(re.findall(r'^\s*\d+\.\s', body, re.MULTILINE))


def score_article_heuristic_dims(article_id: str, meta: dict[str, Any], body: str) -> dict[str, bool]:
    headings = meta.get('headings') or []
    steps = _numbered_step_count(body)
    has_steps = steps >= 1 or ('چطور' in body and '## ' in body)
    strict_steps = steps >= 2
    tech_refs = meta.get('technical_refs') or []
    return {
        'intro_purpose': bool(meta.get('summary')) or body.strip().startswith('**') or '## ' in body,
        'ui_location': '/workspace/' in body or ('مسیر' in body and 'http' not in body[:20]),
        'howto_steps': strict_steps or (has_steps and '/workspace/' in body),
        'prerequisites_limits': bool(str(meta.get('prerequisites') or '').strip())
        or bool(str(meta.get('limitations') or '').strip()),
        'specialist_scenarios': len(headings) >= 3,
        'troubleshooting': any(w in body for w in ('خطا', 'مشکل', 'کار نکرد', 'نمی‌آید', 'نمیاد')),
        'compare_similar': 'تفاوت' in body and '|' in body,
        'faq_synonyms': len(meta.get('synonyms') or []) >= 2,
        '_strict_steps': strict_steps,
        '_has_technical_refs': len(tech_refs) > 0,
        '_reviewed_at': bool(meta.get('reviewed_at')),
    }


def aggregate_heuristic_depth(dimensions: dict[str, bool]) -> HeuristicDepth:
    core = {k: dimensions[k] for k in _DIMENSIONS if k in dimensions}
    if not any(core.values()):
        return 'none'
    if core.get('howto_steps') and core.get('ui_location'):
        return 'howto'
    if sum(1 for v in core.values() if v) >= 2:
        return 'overview'
    return 'none'


def compute_verified_coverage(
    feature: dict[str, Any],
    combined_dims: dict[str, bool],
    article_metas: list[dict[str, Any]],
    heuristic_depth: HeuristicDepth,
) -> VerifiedDepth:
    entity = feature.get('entity_type', 'feature')
    if entity in ('help_topic', 'help_section', 'internal_endpoint'):
        return 'unverified' if heuristic_depth == 'none' else 'needs_review'

    if heuristic_depth == 'none':
        return 'none'

    verified_feature = feature.get('verification_status') == 'code_reviewed' and bool(
        feature.get('last_verified_at')
    )
    articles_verified = bool(article_metas) and all(
        (m.get('technical_refs') or []) and m.get('reviewed_at') for m in article_metas
    )

    strict_full_dims = all(combined_dims.get(k) for k in _DIMENSIONS)
    strict_steps = all(m.get('_strict_steps') for m in article_metas) if article_metas else False

    if (
        verified_feature
        and articles_verified
        and strict_full_dims
        and strict_steps
        and combined_dims.get('prerequisites_limits')
    ):
        return 'full'

    if heuristic_depth in ('howto', 'overview') and (not verified_feature or not articles_verified):
        return 'needs_review'

    if heuristic_depth == 'howto' and verified_feature:
        return 'howto'

    return 'overview' if heuristic_depth != 'none' else 'none'


def build_coverage_for_feature(
    feature: dict[str, Any],
    articles_index: dict[str, dict[str, Any]],
    bodies: dict[str, str],
) -> dict[str, Any]:
    article_ids = feature.get('knowledge_articles') or []
    help_ids = feature.get('help_section_ids') or []
    combined_dims = {d: False for d in _DIMENSIONS}
    article_metas: list[dict[str, Any]] = []
    heuristic_depths: list[HeuristicDepth] = []

    for aid in article_ids:
        meta = articles_index.get(aid)
        if not meta:
            continue
        body = bodies.get(aid, '')
        dims = score_article_heuristic_dims(aid, meta, body)
        article_metas.append({**meta, **dims})
        for k in _DIMENSIONS:
            combined_dims[k] = combined_dims[k] or dims.get(k, False)
        heuristic_depths.append(aggregate_heuristic_depth(dims))

    heuristic_depth = 'none'
    if heuristic_depths:
        order = {'none': 0, 'overview': 1, 'howto': 2}
        heuristic_depth = max(heuristic_depths, key=lambda d: order.get(d, 0))
    elif help_ids and not article_ids:
        combined_dims['intro_purpose'] = True
        heuristic_depth = 'overview'

    verified_depth = compute_verified_coverage(
        feature, combined_dims, article_metas, heuristic_depth
    )

    return {
        'feature_id': feature['id'],
        'heuristic_coverage': heuristic_depth,
        'verified_coverage': verified_depth,
        'dimensions': combined_dims,
        'linked_articles': article_ids,
        'help_sections': help_ids,
    }


def coverage_rows(features: list[dict], articles: list[dict]) -> list[dict[str, Any]]:
    index = _article_by_id(articles)
    bodies = _load_article_bodies()
    rows = []
    for f in features:
        if f.get('entity_type') == 'help_topic' and f.get('catalog_role') == 'child_only':
            continue
        cov = build_coverage_for_feature(f, index, bodies)
        row = {
            'feature_id': f['id'],
            'entity_type': f.get('entity_type', 'feature'),
            'domain': f.get('domain', ''),
            'title': f.get('title', ''),
            'heuristic_coverage': cov['heuristic_coverage'],
            'verified_coverage': cov['verified_coverage'],
            **{f'dim_{k}': ('yes' if cov['dimensions'][k] else 'no') for k in _DIMENSIONS},
            'knowledge_articles': ';'.join(cov['linked_articles']),
            'help_sections': ';'.join(cov['help_sections']),
            'release_status': f.get('release_status', 'unverified'),
            'verification_status': f.get('verification_status', 'unverified'),
        }
        rows.append(row)
    return rows
