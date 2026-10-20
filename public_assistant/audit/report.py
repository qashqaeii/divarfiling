"""تولید audit_report.md"""
from __future__ import annotations

from typing import Any


def build_audit_report(
    catalog: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    retrieval: dict[str, Any],
    gaps: list[dict[str, Any]],
    source_index: dict[str, Any],
) -> str:
    depth_counts = {'none': 0, 'overview': 0, 'howto': 0, 'full': 0}
    for r in coverage_rows:
        d = r.get('overall_depth', 'none')
        depth_counts[d] = depth_counts.get(d, 0) + 1

    verified = sum(
        1 for f in catalog.get('features', []) if f.get('verification_status') == 'code_reviewed'
    )
    unverified = len(catalog.get('features', [])) - verified

    eval_block = retrieval.get('eval_dataset', {})
    p0 = sum(1 for g in gaps if g['priority'] == 'P0')

    plat = catalog.get('platforms_audit', {})
    android = plat.get('android', {})
    windows = plat.get('windows', {})

    lines = [
        '# گزارش ممیزی دانش محصول — دستیار عمومی فایلینگ دیوار',
        '',
        f"**تاریخ:** {catalog.get('generated_at')}",
        '',
        '## ۱. قابلیت‌های کاربرمحور',
        '',
        f"- تعداد ورودی کاتالوگ: **{catalog.get('feature_count')}** (قابلیت منطقی، نه تعداد URL)",
        f"- وضعیت انتشار (از seed): {catalog.get('release_status_counts')}",
        f"- تأیید `code_reviewed`: **{verified}** | سایر/نیازمند تأیید: **{unverified}**",
        '',
        '### پلتفرم‌ها',
        '',
        f"- **وب (Django):** {plat.get('django_workspace_routes')} مسیر در `workspace/urls.py`",
        f"- **راهنمای میزکار:** {plat.get('help_sections')} بخش در `help_content.py`",
        f"- **اندروید:** {'در دسترس در monorepo' if android.get('available') else 'غیرقابل دسترس'} "
        f"— {android.get('route_count', 0)} route در `Routes` ({android.get('note')})",
        f"- **ویندوز:** {'src موجود' if windows.get('available') else 'غیرقابل دسترس'} — "
        f"{windows.get('note', '')}",
        '',
        '> برای قابلیت‌های اندروید/ویندوز بدون مقاله یا help وب، پوشش دانشنامه **نباید** از روی API وب استنتاج شود.',
        '',
        '## ۲. پوشش دانشنامه',
        '',
        f"| عمق | تعداد |",
        f"|-----|------:|",
    ]
    for k in ('full', 'howto', 'overview', 'none'):
        lines.append(f"| `{k}` | {depth_counts.get(k, 0)} |")

    lines.extend(
        [
            '',
            '## ۳. بازیابی RAG (baseline — بدون تغییر retrieval)',
            '',
            f"- سؤالات `eval_dataset`: **{eval_block.get('query_count', 0)}**",
            f"- hit@1: **{eval_block.get('hit_at_1', 0):.1%}**",
            f"- hit@3: **{eval_block.get('hit_at_3', 0):.1%}** (همان cutoff تست `test_hardening` با `hits[:3]`)",
            f"- hit@5: **{eval_block.get('hit_at_5', 0):.1%}**",
            f"- تعداد miss در hit@5: **{len(eval_block.get('misses', []))}**",
            '',
            '### موانع کیفیت پاسخ (مشاهده‌شده)',
            '',
            '- سقف ۱۰۰ نامزد قبل از امتیازدهی در `retrieval.py`',
            '- وابستگی شدید به `_intent_boost` / `_intent_penalty`',
            '- مقالات overview برای سؤالات how-to تخصصی',
            '- `technical_refs` خالی در اکثر مقالات — نگهداری ضعیف',
            '',
            '## ۴. شکاف‌ها و فاز ۲',
            '',
            f"- آیتم P0 در backlog: **{p0}**",
            '- جزئیات: `knowledge_gap_backlog.md`',
            '',
            '## ۵. Source Index',
            '',
            f"- مراجع فایل گم‌شده (exists=false): **{source_index.get('missing_source_files', 0)}**",
            '',
            '## ۶. زیرساخت نگهداری',
            '',
            'طراحی در `knowledge/audit/staleness_registry.yaml` و قالب مقاله در '
            '`knowledge/templates/article_specialist_template.md`. '
            'بدون migration در این فاز.',
            '',
        ]
    )
    return '\n'.join(lines)
