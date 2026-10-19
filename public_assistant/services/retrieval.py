"""جست‌وجوی بخش‌های مرتبط در دانشنامه."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch

from public_assistant.constants import MAX_RETRIEVAL_CHUNKS
from public_assistant.models import KnowledgeArticle, KnowledgeChunk
from public_assistant.services.persian_text import normalize_persian, tokenize_query


@dataclass
class RetrievedChunk:
    article_id: str
    title: str
    category: str
    heading: str
    body: str
    score: float
    related_links: list
    subscription_note: str


def _score_chunk(tokens: list[str], blob: str, title_norm: str) -> float:
    if not tokens:
        return 0.0
    score = 0.0
    for tok in tokens:
        if tok in blob:
            score += 1.0
        if tok in title_norm:
            score += 1.5
    return score


def retrieve(query: str, limit: int = MAX_RETRIEVAL_CHUNKS) -> list[RetrievedChunk]:
    tokens = tokenize_query(query)
    if not tokens:
        return []

    qs = (
        KnowledgeChunk.objects.filter(article__is_active=True, article__is_public=True)
        .select_related('article')
        .only(
            'heading',
            'body',
            'search_blob',
            'chunk_index',
            'article__article_id',
            'article__title',
            'article__category',
            'article__related_links',
            'article__subscription_note',
        )
    )

    # پیش‌فیلتر: حداقل یک توکن در blob
    from django.db.models import Q

    q_filter = Q()
    for tok in tokens[:12]:
        q_filter |= Q(search_blob__icontains=tok)
    candidates = list(qs.filter(q_filter)[:80])
    if not candidates and len(tokens) > 2:
        # fallback: توکن‌های بلندتر
        long_tokens = [t for t in tokens if len(t) >= 4][:6]
        q_filter = Q()
        for tok in long_tokens:
            q_filter |= Q(search_blob__icontains=tok)
        candidates = list(qs.filter(q_filter)[:80])

    scored: list[RetrievedChunk] = []
    for ch in candidates:
        art = ch.article
        title_norm = normalize_persian(art.title)
        s = _score_chunk(tokens, ch.search_blob, title_norm)
        if s <= 0:
            continue
        scored.append(
            RetrievedChunk(
                article_id=art.article_id,
                title=art.title,
                category=art.category,
                heading=ch.heading,
                body=ch.body,
                score=s,
                related_links=art.related_links or [],
                subscription_note=art.subscription_note or '',
            )
        )

    scored.sort(key=lambda x: (-x.score, x.title))
    return scored[:limit]


def prefetch_articles_for_admin():
    return KnowledgeArticle.objects.prefetch_related(
        Prefetch('chunks', queryset=KnowledgeChunk.objects.order_by('chunk_index'))
    )
