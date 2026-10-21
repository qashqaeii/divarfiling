"""اصلاح خودکار محدود جملات با ادعای عددی غیرقابل‌تأیید."""
from __future__ import annotations

import re

from blog.models import MarketArticleRun
from blog.services.market_article_ai_polish import apply_polished_texts, split_html_parts

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?؟؛])\s+')


def _sentence_contains_token(sentence: str, token: str) -> bool:
    if not token:
        return False
    norm_sentence = sentence.replace('\u200c', '')
    return token in sentence or token.replace('٪', '%') in norm_sentence


def remediate_unverified_numeric_sentences(
    run: MarketArticleRun,
    unverified_tokens: list[str],
) -> bool:
    """حذف جملات حاوی اعداد غیرقابل‌تأیید — بدون ساخت عدد جایگزین."""
    if not unverified_tokens:
        return False
    html = run.content_html or ''
    parts = split_html_parts(html)
    changed = False
    polished: dict[int, str] = {}
    for idx, (kind, content) in enumerate(parts):
        if kind != 'text' or not content.strip():
            continue
        sentences = _SENTENCE_SPLIT_RE.split(content)
        kept: list[str] = []
        for sentence in sentences:
            if any(_sentence_contains_token(sentence, tok) for tok in unverified_tokens):
                changed = True
                continue
            kept.append(sentence)
        new_text = ' '.join(s for s in kept if s).strip()
        if new_text != content:
            polished[idx] = new_text if new_text else content
            changed = True
    if not changed:
        return False
    run.content_html = apply_polished_texts(parts, polished)
    run.save(update_fields=['content_html', 'updated_at'])
    return True
