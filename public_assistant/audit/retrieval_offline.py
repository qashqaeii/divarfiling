"""بازیابی read-only از Markdown — بدون نوشتن در دیتابیس."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from public_assistant.constants import MAX_RETRIEVAL_CHUNKS, MIN_RETRIEVAL_SCORE
from public_assistant.services.knowledge_loader import (
    build_search_blob,
    chunk_body,
    iter_article_files,
    parse_markdown_file,
)
from public_assistant.services.persian_text import normalize_persian, tokenize_query
from public_assistant.services.retrieval import RetrievedChunk, _score_chunk


@dataclass
class _OfflineChunk:
    chunk: RetrievedChunk
    search_blob: str
    chunk_index: int
    synonyms_norm: str


@lru_cache(maxsize=1)
def _load_offline_chunks() -> list[_OfflineChunk]:
    items: list[_OfflineChunk] = []
    for path in iter_article_files():
        parsed = parse_markdown_file(path)
        meta = parsed.meta
        if not meta.get('is_public', True) or not meta.get('is_active', True):
            continue
        article_id = str(meta['id'])
        title = meta['title']
        category = meta['category']
        links = meta.get('links') or meta.get('related_links') or []
        subscription_note = meta.get('subscription_note') or ''
        summary = meta.get('summary') or ''
        syn_list = meta.get('synonyms') or []
        synonyms_norm = normalize_persian(' '.join(str(s) for s in syn_list))
        for idx, (heading, body) in enumerate(chunk_body(parsed.body)):
            blob = build_search_blob(meta, heading, body)
            items.append(
                _OfflineChunk(
                    chunk=RetrievedChunk(
                        article_id=article_id,
                        title=title,
                        category=category,
                        heading=heading,
                        body=body,
                        score=0.0,
                        related_links=links,
                        subscription_note=subscription_note,
                        summary=summary,
                    ),
                    search_blob=blob,
                    chunk_index=idx,
                    synonyms_norm=synonyms_norm,
                )
            )
    return items


def offline_retrieve(query: str, limit: int = MAX_RETRIEVAL_CHUNKS) -> list[RetrievedChunk]:
    """همان منطق `retrieve()` با دادهٔ بارگذاری‌شده از فایل."""
    query_norm = normalize_persian(query)
    tokens = tokenize_query(query)
    if not tokens:
        return []

    all_chunks = _load_offline_chunks()
    candidates: list[_OfflineChunk] = []
    for ch in all_chunks:
        blob = ch.search_blob
        if any(tok in blob for tok in tokens[:14]):
            candidates.append(ch)

    if not candidates:
        long_tokens = [t for t in tokens if len(t) >= 4][:8]
        for ch in all_chunks:
            if any(tok in ch.search_blob for tok in long_tokens):
                candidates.append(ch)

    if len(candidates) > 100:
        probe = tokens[:14]

        def _token_hits(ch: _OfflineChunk) -> int:
            return sum(1 for tok in probe if tok in ch.search_blob)

        candidates.sort(
            key=lambda ch: (
                -_token_hits(ch),
                ch.chunk.article_id,
                ch.chunk_index,
            )
        )
        candidates = candidates[:100]

    scored: list[RetrievedChunk] = []
    for ch in candidates:
        art = ch.chunk
        title_norm = normalize_persian(art.title)
        s = _score_chunk(
            tokens,
            ch.search_blob,
            title_norm,
            art.article_id,
            ch.synonyms_norm,
            query_norm,
        )
        if s < MIN_RETRIEVAL_SCORE:
            continue
        scored.append(
            RetrievedChunk(
                article_id=art.article_id,
                title=art.title,
                category=art.category,
                heading=art.heading,
                body=art.body,
                score=s,
                related_links=art.related_links,
                subscription_note=art.subscription_note,
                summary=art.summary,
            )
        )

    scored.sort(key=lambda x: (-x.score, x.title))
    picked: list[RetrievedChunk] = []
    per_article: dict[str, int] = {}
    for ch in scored:
        count = per_article.get(ch.article_id, 0)
        if count >= 2:
            continue
        picked.append(ch)
        per_article[ch.article_id] = count + 1
        if len(picked) >= limit:
            break
    return picked


def make_offline_retrieve_fn() -> Callable[[str], list[RetrievedChunk]]:
    return offline_retrieve
