"""Gap Backlog — فقط entity_type=feature، بر اساس verified_coverage."""
from __future__ import annotations

from typing import Any

P0_DOMAINS = {
    'crm_contacts',
    'crm_personal_properties',
    'filing',
    'extractor',
    'sharing',
    'crm_deals',
    'contracts',
    'agency',
    'ai',
    'android',
    'windows',
    'support',
}

VERIFIED_GAP = {'none', 'overview', 'needs_review', 'unverified'}
VERIFIED_OK = {'howto', 'full'}


def _priority(feature: dict, verified: str) -> str | None:
    if feature.get('entity_type') != 'feature':
        return None
    if verified in VERIFIED_OK:
        return None

    impact = feature.get('user_impact', 'medium')
    domain = feature.get('domain', '')
    ambiguity = verified in ('needs_review', 'unverified')

    if impact == 'high' and domain in P0_DOMAINS:
        return 'P0'
    if impact == 'high' or (domain in P0_DOMAINS and verified == 'none'):
        return 'P1'
    if ambiguity and domain in P0_DOMAINS:
        return 'P1'
    if verified in VERIFIED_GAP:
        return 'P2'
    return 'P3'


def build_gap_backlog(
    features: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    verified_by_id = {r['feature_id']: r.get('verified_coverage', 'none') for r in coverage_rows}
    gaps: list[dict[str, Any]] = []

    for f in features:
        fid = f['id']
        verified = verified_by_id.get(fid, 'none')
        pri = _priority(f, verified)
        if pri is None:
            continue

        row = next((r for r in coverage_rows if r['feature_id'] == fid), {})
        missing_dims = [
            k.replace('dim_', '')
            for k, v in row.items()
            if k.startswith('dim_') and v == 'no'
        ]

        gaps.append(
            {
                'priority': pri,
                'feature_id': fid,
                'title': f.get('title'),
                'domain': f.get('domain'),
                'user_impact': f.get('user_impact'),
                'heuristic_coverage': row.get('heuristic_coverage'),
                'verified_coverage': verified,
                'missing_dimensions': missing_dims,
                'knowledge_articles': f.get('knowledge_articles') or [],
                'release_status': f.get('release_status'),
                'phase2_recommendation': 'split_article'
                if verified in ('overview', 'needs_review') and len(missing_dims) >= 4
                else 'deepen_existing',
            }
        )

    order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    gaps.sort(key=lambda g: (order.get(g['priority'], 9), g['feature_id']))
    return gaps


def gap_backlog_markdown(gaps: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    lines = [
        '# Knowledge Gap Backlog',
        '',
        f"تولید خودکار — {stats.get('generated_at', '')} (Phase 1.1)",
        '',
        '## خلاصه',
        '',
        f"- قابلیت‌های منطقی (`entity_type=feature`): **{stats.get('logical_feature_count', 0)}**",
        f"- P0: **{stats.get('p0_count', 0)}** | P1: **{stats.get('p1_count', 0)}** | P2: **{stats.get('p2_count', 0)}**",
        '',
        '> topicهای help در backlog نیستند؛ زیر قابلیت والد در کاتالوگ با `catalog_role=child_only` ثبت شده‌اند.',
        '',
        '## فهرست (اولویت نزولی)',
        '',
    ]
    for g in gaps:
        if g['priority'] not in ('P0', 'P1', 'P2'):
            continue
        lines.append(
            f"- **{g['priority']}** `{g['feature_id']}` — {g['title']} "
            f"(verified: `{g['verified_coverage']}`, impact: `{g.get('user_impact')}`)"
        )
        if g['missing_dimensions']:
            lines.append(f"  - کمبود heuristic: {', '.join(g['missing_dimensions'][:6])}")
    lines.append('')
    return '\n'.join(lines)
