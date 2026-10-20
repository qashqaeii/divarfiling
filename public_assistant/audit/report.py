"""تولید audit_report.md — Phase 1.1"""
from __future__ import annotations

from typing import Any


def build_audit_report(
    catalog: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    retrieval: dict[str, Any],
    gaps: list[dict[str, Any]],
    source_index: dict[str, Any],
    stats: dict[str, Any] | None = None,
) -> str:
    stats = stats or {}
    heuristic_counts: dict[str, int] = {}
    verified_counts: dict[str, int] = {}
    for r in coverage_rows:
        h = r.get('heuristic_coverage', 'none')
        v = r.get('verified_coverage', 'none')
        heuristic_counts[h] = heuristic_counts.get(h, 0) + 1
        verified_counts[v] = verified_counts.get(v, 0) + 1

    verified_features = sum(
        1
        for f in catalog.get('features', [])
        if f.get('entity_type') == 'feature' and f.get('verification_status') == 'code_reviewed'
    )
    logical = stats.get('logical_feature_count') or catalog.get('logical_feature_count', 0)

    eval_block = retrieval.get('eval_dataset', {})
    ood = retrieval.get('out_of_scope_eval', {})
    plat = catalog.get('platforms_audit', {})
    android = plat.get('android', {})
    windows = plat.get('windows', {})

    lines = [
        '# گزارش ممیزی دانش محصول — Phase 1.1 (Audit Hardening)',
        '',
        f"**تاریخ:** {catalog.get('generated_at')}",
        '',
        '## ۱. کاتالوگ',
        '',
        f"- ورودی‌های کاتالوگ (همه entityها): **{catalog.get('entry_count', catalog.get('feature_count'))}**",
        f"- قابلیت‌های منطقی (`entity_type=feature`): **{logical}**",
        f"- توزیع entity: {catalog.get('entity_type_counts')}",
        f"- وضعیت انتشار: {catalog.get('release_status_counts')}",
        f"- تأیید `code_reviewed` (feature): **{verified_features}**",
        '',
        '### پلتفرم‌ها',
        '',
        f"- URL inventory (parsed): {plat.get('url_inventory_summary')}",
        f"- **اندروید:** {android.get('route_count', 0)} route — {android.get('note')}",
        f"- **ویندوز:** {windows.get('note', '')}",
        '',
        '## ۲. پوشش دانشنامه',
        '',
        '### heuristic_coverage (تخمین ساختار متن)',
        '',
        '| عمق | تعداد |',
        '|-----|------:|',
    ]
    for k in ('howto', 'overview', 'none'):
        lines.append(f"| `{k}` | {heuristic_counts.get(k, 0)} |")

    lines.extend(
        [
            '',
            '### verified_coverage (تأییدشده / نیازمند بازبینی)',
            '',
            '| وضعیت | تعداد |',
            '|--------|------:|',
        ]
    )
    for k in ('full', 'howto', 'overview', 'needs_review', 'none', 'unverified'):
        if verified_counts.get(k):
            lines.append(f"| `{k}` | {verified_counts.get(k, 0)} |")

    lines.extend(
        [
            '',
            f"- **full تأییدشده:** {stats.get('verified_full_count', verified_counts.get('full', 0))}",
            f"- **needs_review:** {stats.get('needs_review_count', verified_counts.get('needs_review', 0))}",
            '',
            '> وضعیت `full` فقط با `code_reviewed` + `last_verified_at` + `technical_refs` + مراحل واقعی مجاز است.',
            '',
            '## ۳. بازیابی (offline markdown — بدون تغییر DB)',
            '',
            f"- mode: **{retrieval.get('mode', retrieval.get('skipped', 'n/a'))}**",
            f"- سؤالات eval: **{eval_block.get('query_count', 0)}**",
            '',
            '| معیار | Article (dedup) | Chunk |',
            '|-------|----------------:|------:|',
            f"| hit@1 | {eval_block.get('article_hit_at_1', 0):.1%} | {eval_block.get('chunk_hit_at_1', 0):.1%} |",
            f"| hit@3 | {eval_block.get('article_hit_at_3', 0):.1%} | {eval_block.get('chunk_hit_at_3', 0):.1%} |",
            f"| hit@5 | {eval_block.get('article_hit_at_5', 0):.1%} | {eval_block.get('chunk_hit_at_5', 0):.1%} |",
            '',
            f"- out-of-scope accuracy: **{ood.get('accuracy', 0):.1%}** ({ood.get('query_count', 0)} سؤال)",
            f"- scenario how-to hit@5: **{retrieval.get('scenario_eval', {}).get('howto_hit_at_5', 0)}**",
            '',
            '## ۴. Gap backlog (فقط feature)',
            '',
            f"- P0: **{stats.get('p0_count', 0)}** | P1: **{stats.get('p1_count', 0)}** | P2: **{stats.get('p2_count', 0)}**",
            '',
            '## ۵. Source index',
            '',
            f"- missing files: **{source_index.get('missing_source_files', 0)}**",
            f"- feature بدون article/path: **{source_index.get('features_without_article_or_path', 0)}**",
            '',
            '## ۶. Staleness',
            '',
            'فایل `staleness_registry.yaml` + `staleness_diff.json` — diff نسبت به snapshot قبلی.',
            '',
            '## ۷. محدودیت‌ها / QA دستی',
            '',
            '- رفتار UI اندروید/ویندوز و feature flagهای production',
            '- تطبیق `documented_in_help` با نسخه اجرایی',
            '- تأیید `needs_review` → `full` در فاز ۲',
            '',
        ]
    )
    return '\n'.join(lines)
