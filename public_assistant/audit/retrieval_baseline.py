"""ارزیابی بازیابی — Article/Chunk جدا، بدون sync DB."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from public_assistant.tests.eval_dataset import EVAL_QUESTIONS

OUT_OF_SCOPE_QUESTIONS: list[tuple[str, str | None]] = [
    ('آب و هوای تهران امروز', 'public-assistant-scope'),
    ('کد پایتون برای وب‌اسکرپینگ', 'public-assistant-scope'),
    ('داروی سرماخوردگی', 'public-assistant-scope'),
    ('قیمت بیت کوین', 'public-assistant-scope'),
]


def _dedupe_articles(hits: list) -> list:
    seen: set[str] = set()
    out = []
    for h in hits:
        if h.article_id in seen:
            continue
        seen.add(h.article_id)
        out.append(h)
    return out


def _rank_article(hits: list, expected: str) -> int | None:
    for i, h in enumerate(_dedupe_articles(hits)):
        if h.article_id == expected:
            return i + 1
    return None


def _rank_chunk(hits: list, expected: str) -> int | None:
    for i, h in enumerate(hits):
        if h.article_id == expected:
            return i + 1
    return None


def _hit_rates(ranks: list[int | None], k: int) -> float:
    if not ranks:
        return 0.0
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)


def _domain_for_expected(article_id: str) -> str:
    if article_id.startswith('crm-'):
        return 'crm'
    if article_id.startswith('extractor') or 'filing' in article_id:
        return 'filing_extractor'
    if article_id.startswith('agency') or 'agency' in article_id:
        return 'agency'
    if article_id.startswith('ai-'):
        return 'ai'
    if article_id.startswith('account') or 'plans' in article_id or 'license' in article_id:
        return 'account_licensing'
    if article_id.startswith('intro') or article_id.startswith('workspace'):
        return 'product_intro'
    if article_id.startswith('support'):
        return 'support'
    return 'other'


def evaluate_retrieval(retrieve_fn, queries: list[tuple[str, str]]) -> dict[str, Any]:
    article_ranks: list[int | None] = []
    chunk_ranks: list[int | None] = []
    rows: list[dict[str, Any]] = []
    misses_by_domain: dict[str, list] = defaultdict(list)

    for query, expected in queries:
        hits = retrieve_fn(query)
        a_rank = _rank_article(hits, expected)
        c_rank = _rank_chunk(hits, expected)
        article_ranks.append(a_rank)
        chunk_ranks.append(c_rank)
        top_chunks = [h.article_id for h in hits[:5]]
        top_articles = [h.article_id for h in _dedupe_articles(hits)[:5]]
        row = {
            'query': query,
            'expected': expected,
            'domain': _domain_for_expected(expected),
            'article_rank': a_rank,
            'chunk_rank': c_rank,
            'article_hit_at_1': a_rank == 1,
            'article_hit_at_3': a_rank is not None and a_rank <= 3,
            'article_hit_at_5': a_rank is not None and a_rank <= 5,
            'chunk_hit_at_1': c_rank == 1,
            'chunk_hit_at_3': c_rank is not None and c_rank <= 3,
            'chunk_hit_at_5': c_rank is not None and c_rank <= 5,
            'top_articles_deduped': top_articles,
            'top_chunks': top_chunks,
        }
        rows.append(row)
        if not row['article_hit_at_5']:
            misses_by_domain[row['domain']].append(
                {'query': query, 'expected': expected, 'top_articles': top_articles}
            )

    n = len(rows) or 1
    return {
        'query_count': len(rows),
        'hit_at_1': _hit_rates(article_ranks, 1),
        'hit_at_3': _hit_rates(article_ranks, 3),
        'hit_at_3_note': 'legacy alias of article_hit_at_3 (deduped by article_id)',
        'hit_at_5': _hit_rates(article_ranks, 5),
        'article_hit_at_1': _hit_rates(article_ranks, 1),
        'article_hit_at_3': _hit_rates(article_ranks, 3),
        'article_hit_at_5': _hit_rates(article_ranks, 5),
        'chunk_hit_at_1': _hit_rates(chunk_ranks, 1),
        'chunk_hit_at_3': _hit_rates(chunk_ranks, 3),
        'chunk_hit_at_5': _hit_rates(chunk_ranks, 5),
        'misses': [r for r in rows if not r['article_hit_at_5']],
        'misses_by_domain': dict(misses_by_domain),
        'results': rows,
    }


def evaluate_out_of_scope(retrieve_fn) -> dict[str, Any]:
    rows = []
    for query, expected in OUT_OF_SCOPE_QUESTIONS:
        hits = retrieve_fn(query)
        top = _dedupe_articles(hits)[:3]
        top_ids = [h.article_id for h in top]
        ok = expected in top_ids if expected else len(top_ids) == 0
        rows.append({'query': query, 'expected': expected, 'top_articles': top_ids, 'ok': ok})
    return {
        'query_count': len(rows),
        'accuracy': sum(1 for r in rows if r['ok']) / (len(rows) or 1),
        'results': rows,
    }


def scenario_eval_questions() -> list[dict[str, Any]]:
    return [
        {'query': 'شماره مالک رو کجا بزنم توی فایل شخصی', 'expected': 'crm-personal-properties', 'type': 'howto'},
        {'query': 'پوشه بندی ملک شخصی', 'expected': None, 'type': 'howto'},
        {'query': 'کمیسیون معامله رو کجا ثبت کنم', 'expected': 'crm-deals', 'type': 'howto'},
        {'query': 'قرارداد PDF بگیرم', 'expected': 'contracts-overview', 'type': 'howto'},
        {'query': 'بعد از تماس مشتری چیکار کنم اندروید', 'expected': None, 'type': 'android_post_call'},
        {'query': 'زمان بندی استخراج ویندوز', 'expected': 'extractor-windows', 'type': 'windows_scheduler'},
        {'query': 'ادغام دو مخاطب تکراری', 'expected': None, 'type': 'howto'},
        {'query': 'فضای آژانس فایل رو چطور منتشر کنم', 'expected': 'agency-space-sharing', 'type': 'howto'},
        {'query': 'اول ثبت نام بعد استخراج', 'expected': 'support-getting-started', 'type': 'multi_topic'},
        {'query': 'قیمت پلن رو گفتید حالا لایسنس ویندوز', 'expected': 'license-activation', 'type': 'topic_shift'},
    ]


def evaluate_scenarios(retrieve_fn) -> dict[str, Any]:
    scenarios = scenario_eval_questions()
    evaluated = []
    for s in scenarios:
        hits = retrieve_fn(s['query'])
        expected = s.get('expected')
        a_rank = _rank_article(hits, expected) if expected else None
        evaluated.append(
            {
                **s,
                'article_rank': a_rank,
                'top_articles': [h.article_id for h in _dedupe_articles(hits)[:5]],
                'article_hit_at_5': a_rank is not None and a_rank <= 5 if expected else None,
            }
        )

    def _rate(subset):
        with_exp = [e for e in subset if e.get('expected')]
        if not with_exp:
            return None
        return sum(1 for e in with_exp if e.get('article_hit_at_5')) / len(with_exp)

    howto_eval = [e for e in evaluated if e.get('type') == 'howto']
    multi_eval = [e for e in evaluated if e.get('type') in ('multi_topic', 'topic_shift')]

    return {
        'scenarios': evaluated,
        'hit_at_5_with_expected': _rate(evaluated),
        'howto_hit_at_5': _rate(howto_eval),
        'multi_topic_hit_at_5': _rate(multi_eval),
        'count': len(evaluated),
    }


def run_full_baseline(retrieve_fn) -> dict[str, Any]:
    eval_main = evaluate_retrieval(retrieve_fn, EVAL_QUESTIONS)
    scenarios = evaluate_scenarios(retrieve_fn)
    ood = evaluate_out_of_scope(retrieve_fn)
    return {
        'mode': 'offline_markdown',
        'eval_dataset': eval_main,
        'scenario_eval': scenarios,
        'out_of_scope_eval': ood,
        'generated_by': 'public_assistant.audit.retrieval_baseline',
    }
