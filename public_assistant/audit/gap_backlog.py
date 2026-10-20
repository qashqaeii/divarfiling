"""Gap Backlog — اولویت‌بندی بر اساس شکاف پوشش و دامنه."""
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

P1_DOMAINS = {
    'crm_scheduling',
    'crm_automation',
    'analysis',
    'account',
    'licensing',
    'onboarding',
}

DEPTH_ORDER = {'none': 0, 'overview': 1, 'howto': 2, 'full': 3}


def _priority(feature: dict, depth: str) -> str:
    domain = feature.get('domain', '')
    if domain in P0_DOMAINS and DEPTH_ORDER.get(depth, 0) < 2:
        return 'P0'
    if domain in P1_DOMAINS and DEPTH_ORDER.get(depth, 0) < 2:
        return 'P1'
    if DEPTH_ORDER.get(depth, 0) < 2:
        return 'P2'
    return 'P3'


def build_gap_backlog(
    features: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    depth_by_id = {r['feature_id']: r['overall_depth'] for r in coverage_rows}
    gaps: list[dict[str, Any]] = []

    for f in features:
        fid = f['id']
        depth = depth_by_id.get(fid, 'none')
        if DEPTH_ORDER.get(depth, 0) >= 3:
            continue
        pri = _priority(f, depth)
        missing_dims = []
        row = next((r for r in coverage_rows if r['feature_id'] == fid), {})
        for k, v in row.items():
            if k.startswith('dim_') and v == 'no':
                missing_dims.append(k.replace('dim_', ''))

        gaps.append(
            {
                'priority': pri,
                'feature_id': fid,
                'title': f.get('title'),
                'domain': f.get('domain'),
                'current_depth': depth,
                'missing_dimensions': missing_dims,
                'knowledge_articles': f.get('knowledge_articles') or [],
                'release_status': f.get('release_status'),
                'phase2_recommendation': 'split_article'
                if depth == 'overview' and len(missing_dims) >= 4
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
        f"تولید خودکار — {stats.get('generated_at', '')}",
        '',
        '## خلاصه',
        '',
        f"- قابلیت‌های کاتالوگ: **{stats.get('feature_count', 0)}**",
        f"- P0: **{stats.get('p0_count', 0)}** | P1: **{stats.get('p1_count', 0)}** | P2: **{stats.get('p2_count', 0)}**",
        '',
        '## فهرست (اولویت نزولی)',
        '',
    ]
    for g in gaps:
        if g['priority'] not in ('P0', 'P1', 'P2'):
            continue
        lines.append(
            f"- **{g['priority']}** `{g['feature_id']}` — {g['title']} "
            f"(عمق: `{g['current_depth']}`، دامنه: `{g['domain']}`)"
        )
        if g['missing_dimensions']:
            lines.append(f"  - کمبود: {', '.join(g['missing_dimensions'])}")
        if g['phase2_recommendation'] == 'split_article':
            lines.append('  - فاز ۲: مقاله(های) مستقل پیشنهاد می‌شود')
    lines.append('')
    return '\n'.join(lines)
