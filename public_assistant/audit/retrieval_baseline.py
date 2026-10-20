"""ارزیابی بازیابی فعلی — بدون تغییر الگوریتم."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from public_assistant.tests.eval_dataset import EVAL_QUESTIONS


@dataclass
class RetrievalEvalRow:
    query: str
    expected_article_id: str
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    rank: int | None
    top_ids: list[str]


def _rank_expected(hits: list, expected: str) -> int | None:
    for i, h in enumerate(hits):
        if h.article_id == expected:
            return i + 1
    return None


def evaluate_retrieval(retrieve_fn, queries: list[tuple[str, str]]) -> dict[str, Any]:
    rows: list[RetrievalEvalRow] = []
    for query, expected in queries:
        hits = retrieve_fn(query)
        top_ids = [h.article_id for h in hits[:8]]
        rank = _rank_expected(hits, expected)
        rows.append(
            RetrievalEvalRow(
                query=query,
                expected_article_id=expected,
                hit_at_1=rank == 1 if rank else False,
                hit_at_3=rank is not None and rank <= 3,
                hit_at_5=rank is not None and rank <= 5,
                rank=rank,
                top_ids=top_ids[:5],
            )
        )

    n = len(rows) or 1
    return {
        'query_count': len(rows),
        'hit_at_1': sum(1 for r in rows if r.hit_at_1) / n,
        'hit_at_3': sum(1 for r in rows if r.hit_at_3) / n,
        'hit_at_3_note': 'test_hardening uses hits[:3] — same cutoff as hit@3 here',
        'hit_at_5': sum(1 for r in rows if r.hit_at_5) / n,
        'misses': [
            {
                'query': r.query,
                'expected': r.expected_article_id,
                'rank': r.rank,
                'top_5': r.top_ids,
            }
            for r in rows
            if not r.hit_at_5
        ],
        'results': [
            {
                'query': r.query,
                'expected': r.expected_article_id,
                'rank': r.rank,
                'hit_at_1': r.hit_at_1,
                'hit_at_3': r.hit_at_3,
                'hit_at_5': r.hit_at_5,
                'top_5': r.top_ids,
            }
            for r in rows
        ],
    }


def scenario_eval_questions() -> list[dict[str, Any]]:
    """مجموعه سناریومحور برای فاز بعد — برخی بدون expected تأییدشده."""
    return [
        {
            'query': 'شماره مالک رو کجا بزنم توی فایل شخصی',
            'expected': 'crm-personal-properties',
            'type': 'howto',
        },
        {
            'query': 'پوشه بندی ملک شخصی',
            'expected': None,
            'type': 'howto',
            'note': 'نیاز به مقاله مستقل — در کاتالوگ پوشش none',
        },
        {
            'query': 'کمیسیون معامله رو کجا ثبت کنم',
            'expected': 'crm-deals',
            'type': 'howto',
        },
        {
            'query': 'قرارداد PDF بگیرم',
            'expected': 'contracts-overview',
            'type': 'howto',
        },
        {
            'query': 'بعد از تماس مشتری چیکار کنم اندروید',
            'expected': None,
            'type': 'android_post_call',
        },
        {
            'query': 'زمان بندی استخراج ویندوز',
            'expected': 'extractor-windows',
            'type': 'windows_scheduler',
        },
        {
            'query': 'ادغام دو مخاطب تکراری',
            'expected': None,
            'type': 'crm_contacts',
        },
        {
            'query': 'فضای آژانس فایل رو چطور منتشر کنم',
            'expected': 'agency-space-sharing',
            'type': 'howto',
        },
        # چندمرحله‌ای / تغییر موضوع — برای فاز ۳ (بدون اجرای چت در این فاز)
        {
            'query': 'اول ثبت نام بعد استخراج',
            'expected': 'support-getting-started',
            'type': 'multi_topic',
            'note': 'retrieval تک‌مرحله‌ای؛ ارزیابی مکالمه در فاز ۳',
        },
        {
            'query': 'قیمت پلن رو گفتید حالا لایسنس ویندوز',
            'expected': 'license-activation',
            'type': 'topic_shift',
            'note': 'retrieval تک‌مرحله‌ای',
        },
    ]


def evaluate_scenarios(retrieve_fn) -> dict[str, Any]:
    scenarios = scenario_eval_questions()
    evaluated = []
    for s in scenarios:
        hits = retrieve_fn(s['query'])
        top = [h.article_id for h in hits[:5]]
        expected = s.get('expected')
        rank = None
        if expected:
            for i, h in enumerate(hits):
                if h.article_id == expected:
                    rank = i + 1
                    break
        evaluated.append({**s, 'rank': rank, 'top_5': top, 'hit_at_5': rank is not None and rank <= 5})
    with_expected = [e for e in evaluated if e.get('expected')]
    n = len(with_expected) or 1
    return {
        'scenarios': evaluated,
        'hit_at_5_with_expected': sum(1 for e in with_expected if e['hit_at_5']) / n,
        'count': len(evaluated),
    }


def run_full_baseline(retrieve_fn) -> dict[str, Any]:
    eval_main = evaluate_retrieval(retrieve_fn, EVAL_QUESTIONS)
    scenarios = evaluate_scenarios(retrieve_fn)
    return {
        'eval_dataset': eval_main,
        'scenario_eval': scenarios,
        'generated_by': 'public_assistant.audit.retrieval_baseline',
    }
