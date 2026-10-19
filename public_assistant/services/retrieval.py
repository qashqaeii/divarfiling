"""جست‌وجوی بخش‌های مرتبط در دانشنامه."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch, Q

from public_assistant.constants import MAX_RETRIEVAL_CHUNKS, MIN_RETRIEVAL_SCORE
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
    summary: str = ''


def _intent_boost(query_norm: str, article_id: str) -> float:
    boost = 0.0
    if article_id == 'intro-crm-filing-extractor':
        if 'crm' in query_norm and any(w in query_norm for w in ('فایلینگ', 'استخراج', 'تفاوت', 'dataset')):
            boost += 4.0
    if article_id == 'extractor-windows' and 'ویندوز' in query_norm and any(
        w in query_norm for w in ('دانلود', 'استخراج', 'ربات')
    ):
        boost += 4.0
    if article_id == 'account-mobile-verify' and any(w in query_norm for w in ('پیامک', 'کد', 'موبایل', 'تأیید')):
        boost += 3.5
    if article_id == 'agency-vs-personal' and 'آژانس' in query_norm and any(
        w in query_norm for w in ('چند', 'شخصی', 'خرید', 'لایسنس')
    ):
        boost += 3.5
    if article_id == 'extractor-single-batch' and 'گروهی' in query_norm:
        boost += 4.0
    if article_id == 'extractor-to-filing' and 'میزکار' in query_norm and any(
        w in query_norm for w in ('نیست', 'نمی', 'همگام', 'نمیاد')
    ):
        boost += 4.0
    if article_id == 'crm-activities-reminders' and any(w in query_norm for w in ('پیگیری', 'یادآوری', 'تماس')):
        boost += 2.5
    if article_id == 'crm-matching' and any(w in query_norm for w in ('تطبیق', 'مناسب', 'پیشنهاد فایل')):
        boost += 3.5
    if article_id == 'public-assistant-scope' and any(
        w in query_norm for w in (
            'api',
            'key',
            'مشتریان',
            'مشتریان من',
            'اطلاعات',
            'مخاطب',
            'حساب',
            'خصوصی',
            'ببینی',
            'سیاست',
            'پزشک',
            'دستیار',
        )
    ):
        boost += 5.0
    if article_id == 'agency-create-roles' and 'آژانس' in query_norm and any(
        w in query_norm for w in ('ساخت', 'نقش', 'مالک', 'منشی')
    ):
        boost += 4.0
    if article_id == 'support-common-errors' and any(w in query_norm for w in ('مشکل', 'خطا', 'نمی')):
        boost += 3.0
    if article_id == 'share-public-file' and 'share' in query_norm:
        boost += 5.0
    if article_id == 'academy-public' and 'آموزش' in query_norm:
        boost += 3.5
    if article_id == 'extractor-single-batch' and 'گروهی' in query_norm:
        boost += 5.0
    if article_id == 'plans-overview' and any(w in query_norm for w in ('قیمت', 'پلن', 'چنده', 'هزینه', 'خرید')):
        boost += 4.0
    if article_id == 'plans-trial-7d' and any(w in query_norm for w in ('هدیه', 'هفت', 'آزمایشی', 'رایگان', 'trial')):
        boost += 4.5
    if article_id == 'intro-what-is-divar-filing' and any(
        w in query_norm for w in ('چیست', 'چیه', 'معرفی', 'مناسب', 'مشاور')
    ):
        boost += 3.0
    if article_id == 'extractor-overview' and any(
        w in query_norm for w in ('استخراج', 'چطور', 'چگونه', 'ربات', 'اسکرپ', 'کشیدن')
    ):
        boost += 3.5
    if article_id == 'extractor-to-filing' and any(
        w in query_norm for w in ('استخراج', 'چطور', 'چگونه', 'میزکار', 'همگام')
    ):
        boost += 2.0
    if article_id == 'intro-what-is-divar-filing' and any(
        w in query_norm for w in ('چیست', 'چیه', 'معرفی', 'مناسب', 'مشاور')
    ):
        boost += 3.5
    if article_id == 'workspace-product-map' and any(
        w in query_norm for w in ('امکانات', 'قابلیت', 'چه دارد', 'چی دارد', 'امکان', 'مسیر', 'منو', 'میزکار')
    ):
        boost += 5.5
    if article_id == 'filing-divar-contact' and any(
        w in query_norm for w in ('شماره', 'تماس', 'تلفن', 'otp', 'دیوار')
    ):
        boost += 4.0
    if article_id == 'intro-crm-filing-extractor' and 'crm' in query_norm and any(
        w in query_norm for w in ('کمک', 'فایده', 'چرا', 'مشاور', 'چه میکند', 'چه می')
    ):
        boost += 4.5
    if article_id == 'crm-advisor-guide' and 'crm' in query_norm and any(
        w in query_norm for w in ('کمک', 'فایده', 'چرا', 'مشاور', 'مدیریت', 'پیگیری', 'چه میکند', 'چه می')
    ):
        boost += 5.5
    if article_id == 'filing-collections' and any(
        w in query_norm for w in ('مجموعه فایل', 'dataset', 'دیتاست', 'فایلینگ', 'بانک فایل')
    ):
        boost += 3.0
    if article_id == 'support-getting-started' and any(
        w in query_norm for w in ('شروع', 'اولین', 'تازه', 'ثبت نام', 'onboarding')
    ):
        boost += 3.5
    if article_id == 'extractor-overview' and any(w in query_norm for w in ('شماره', 'تماس', 'تلفن')):
        boost += 4.5
    if article_id == 'filing-detail-map' and 'نقشه' in query_norm:
        boost += 4.0
    if article_id == 'ai-nl-command' and any(w in query_norm for w in ('فرمان', 'دستور', 'nl')):
        boost += 3.5
    if article_id == 'crm-deals' and any(w in query_norm for w in ('معامله', 'deal', 'قرارداد')):
        boost += 3.0
    if article_id == 'license-activation' and any(w in query_norm for w in ('فعال', 'کلید', 'لایسنس')):
        boost += 2.5
    return boost


def _intent_penalty(query_norm: str, article_id: str) -> float:
    penalty = 0.0
    if article_id == 'extractor-overview' and 'ویندوز' in query_norm and 'دانلود' in query_norm:
        penalty += 3.0
    if article_id == 'extractor-overview' and 'گروهی' in query_norm:
        penalty += 3.0
    if article_id == 'intro-crm-filing-extractor' and 'تطبیق' in query_norm:
        penalty += 2.5
    if article_id == 'crm-contacts' and 'پیگیری' in query_norm and 'مشتری' not in query_norm:
        penalty += 2.0
    return penalty


def _score_chunk(
    tokens: list[str],
    blob: str,
    title_norm: str,
    article_id: str,
    synonyms_norm: str,
    query_norm: str,
) -> float:
    if not tokens:
        return 0.0
    score = 0.0
    matched = 0
    for tok in tokens:
        if tok in blob:
            score += 1.0
            matched += 1
        if tok in title_norm:
            score += 2.0
        if tok in synonyms_norm:
            score += 0.75
        if tok in article_id.replace('-', ' '):
            score += 1.25
    if matched == 0:
        return 0.0
    # پوشش: چند توکن مهم باید بمانند
    coverage = matched / max(len(tokens), 1)
    score += coverage * 1.5
    score += _intent_boost(query_norm, article_id)
    score -= _intent_penalty(query_norm, article_id)
    return score


def retrieve(query: str, limit: int = MAX_RETRIEVAL_CHUNKS) -> list[RetrievedChunk]:
    query_norm = normalize_persian(query)
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
            'article__synonyms',
            'article__summary',
        )
    )

    q_filter = Q()
    for tok in tokens[:14]:
        q_filter |= Q(search_blob__icontains=tok)
    candidates = list(qs.filter(q_filter)[:100])
    if not candidates:
        long_tokens = [t for t in tokens if len(t) >= 4][:8]
        q_filter = Q()
        for tok in long_tokens:
            q_filter |= Q(search_blob__icontains=tok)
        candidates = list(qs.filter(q_filter)[:100])

    scored: list[RetrievedChunk] = []
    for ch in candidates:
        art = ch.article
        title_norm = normalize_persian(art.title)
        syn_list = art.synonyms or []
        synonyms_norm = normalize_persian(' '.join(str(s) for s in syn_list))
        s = _score_chunk(tokens, ch.search_blob, title_norm, art.article_id, synonyms_norm, query_norm)
        if s < MIN_RETRIEVAL_SCORE:
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
                summary=art.summary or '',
            )
        )

    scored.sort(key=lambda x: (-x.score, x.title))
    picked: list[RetrievedChunk] = []
    per_article: dict[str, int] = {}
    max_per_article = 2
    for ch in scored:
        count = per_article.get(ch.article_id, 0)
        if count >= max_per_article:
            continue
        picked.append(ch)
        per_article[ch.article_id] = count + 1
        if len(picked) >= limit:
            break
    return picked


def prefetch_articles_for_admin():
    return KnowledgeArticle.objects.prefetch_related(
        Prefetch('chunks', queryset=KnowledgeChunk.objects.order_by('chunk_index'))
    )
