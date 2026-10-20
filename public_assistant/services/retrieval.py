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
        if 'crm' in query_norm and any(w in query_norm for w in ('فایلینگ', 'استخراج', 'تفاوت', 'dataset', 'فرق')):
            boost += 5.5
    if article_id == 'extractor-windows' and 'ویندوز' in query_norm and any(
        w in query_norm for w in ('دانلود', 'استخراج', 'ربات')
    ):
        boost += 4.0
    if article_id == 'account-mobile-verify' and any(w in query_norm for w in ('پیامک', 'کد', 'موبایل', 'تأیید')):
        boost += 3.5
    if article_id == 'agency-vs-personal' and 'آژانس' in query_norm and any(
        w in query_norm for w in ('چند', 'خرید', 'لایسنس', 'حساب')
    ) and 'فایل شخصی' not in query_norm and not (
        'شخصی' in query_norm and 'فایل' in query_norm
    ):
        boost += 3.5
    if article_id == 'extractor-single-batch' and 'گروهی' in query_norm:
        boost += 4.0
    if article_id == 'extractor-to-filing' and 'میزکار' in query_norm and any(
        w in query_norm for w in ('نیست', 'نمی', 'همگام', 'نمیاد')
    ):
        boost += 4.0
    if article_id == 'crm-activities-reminders' and any(w in query_norm for w in ('پیگیری', 'یادآوری')):
        boost += 4.0
    if article_id == 'crm-activities-reminders' and 'یادآوری' in query_norm and 'تماس' in query_norm:
        boost += 2.0
    if article_id == 'crm-matching' and any(w in query_norm for w in ('تطبیق', 'مناسب', 'پیشنهاد فایل')):
        boost += 3.5
    if article_id == 'public-assistant-scope' and any(
        w in query_norm for w in (
            'api',
            'key',
            'مشتریان من',
            'اطلاعات مشتریان',
            'دسترسی',
            'ببینی',
            'می‌بینی',
            'میبینی',
            'حساب من',
            'خصوصی',
            'سیاست',
            'پزشک',
            'دستیار عمومی',
        )
    ):
        boost += 5.0
    if article_id == 'crm-contacts' and any(
        w in query_norm for w in ('مخاطب', 'مشتری', 'خریدار', 'تماس')
    ) and any(w in query_norm for w in ('ثبت', 'اضافه', 'چطور', 'چگونه', 'چجوری', 'جدید', 'ساخت')):
        boost += 7.0
    if article_id == 'crm-personal-properties' and (
        'فایل شخصی' in query_norm
        or 'املاک شخصی' in query_norm
        or ('شخصی' in query_norm and any(w in query_norm for w in ('فایل', 'ملک', 'داشته')))
        or ('شماره' in query_norm and 'فایل' in query_norm)
    ):
        boost += 7.5
    if article_id == 'share-public-file' and 'لینک' in query_norm and 'مشتری' in query_norm:
        if any(
            w in query_norm
            for w in ('چطور', 'چطوری', 'چگونه', 'بفرست', 'ارسال', 'بساز', 'ساخت', 'عمومی', 'share', 'اشتراک')
        ):
            boost += 12.0
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
    if article_id == 'plans-trial-vs-welcome' and any(
        w in query_norm for w in ('هدیه', 'آزمایشی', 'رایگان', 'تفاوت', 'فرق')
    ):
        boost += 5.0
    if article_id == 'plans-agency-pricing' and 'آژانس' in query_norm and any(
        w in query_norm for w in ('قیمت', 'تخفیف', 'چند', 'نفر', 'مشاور')
    ):
        boost += 4.5
    if article_id == 'plans-choose-advisor' and any(
        w in query_norm for w in ('پیشنهاد', 'کدوم', 'کدام', 'بخرم', 'مناسب')
    ):
        boost += 3.5
    if article_id == 'plans-personal-compare' and any(
        w in query_norm for w in ('ماهانه', 'سه', 'سالانه', 'به صرفه', 'مقایسه')
    ):
        boost += 3.5
    if article_id == 'plans-purchase-faq' and any(w in query_norm for w in ('تمدید', 'تمام شود', 'انقضا')):
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
        boost += 7.0
    if article_id == 'filing-divar-contact' and any(
        w in query_norm for w in ('شماره', 'تلفن', 'otp')
    ) and any(w in query_norm for w in ('دیوار', 'آگهی', 'مالک', 'استخراج', 'کشید')):
        boost += 4.5
    if article_id == 'intro-what-is-divar-filing' and 'فایلینگ' in query_norm and any(
        w in query_norm for w in ('چیست', 'چیه', 'معرفی')
    ):
        boost += 5.0
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
    if article_id == 'support-getting-started' and 'ثبت' in query_norm and any(
        w in query_norm for w in ('بعد', 'شروع', 'کار')
    ):
        boost += 4.0
    if article_id == 'support-common-errors' and 'پشتیبانی' in query_norm:
        boost += 4.5
    if article_id == 'academy-public' and 'آموزش' in query_norm:
        boost += 4.0
    if article_id == 'share-public-file' and 'share' in query_norm and 'فایل' in query_norm:
        boost += 3.0
    if article_id == 'extractor-overview' and any(w in query_norm for w in ('شماره', 'تماس', 'تلفن')):
        if not ('فایل شخصی' in query_norm or ('فایل' in query_norm and 'شخصی' in query_norm)):
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
    if article_id == 'crm-contacts' and 'پیگیری' in query_norm:
        penalty += 3.0
    if article_id == 'filing-collections' and any(
        w in query_norm for w in ('امکانات', 'چیست', 'چیه', 'تفاوت', 'فرق')
    ):
        penalty += 3.0
    if article_id == 'filing-divar-contact' and 'پشتیبانی' in query_norm:
        penalty += 6.0
    if article_id == 'public-assistant-scope' and any(
        w in query_norm for w in ('ثبت', 'چطور', 'چگونه', 'چجوری', 'اضافه', 'ساخت', 'بساز', 'جدید')
    ):
        penalty += 6.0
    if article_id == 'intro-crm-filing-extractor' and (
        'فایل شخصی' in query_norm or ('شخصی' in query_norm and 'فایل' in query_norm)
    ):
        penalty += 4.0
    if article_id == 'extractor-overview' and (
        'فایل شخصی' in query_norm or ('فایل' in query_norm and 'شخصی' in query_norm)
    ):
        penalty += 5.0
    if article_id == 'agency-vs-personal' and (
        'فایل شخصی' in query_norm or ('شخصی' in query_norm and 'فایل' in query_norm)
    ):
        penalty += 5.0
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


_RETRIEVAL_CANDIDATE_POOL = 400
_RETRIEVAL_CANDIDATE_CAP = 100


def _cap_candidates_by_token_hits(candidates: list, tokens: list[str], cap: int = _RETRIEVAL_CANDIDATE_CAP) -> list:
    """قبل از امتیازدهی، کاندیدها را بر اساس تطابق توکن مرتب کن (نه ترتیب تصادفی DB)."""
    if len(candidates) <= cap:
        return candidates
    probe = tokens[:14]

    def _hits(blob: str) -> int:
        return sum(1 for tok in probe if tok in blob)

    return sorted(
        candidates,
        key=lambda ch: (
            -_hits(ch.search_blob),
            ch.article.article_id,
            ch.chunk_index,
        ),
    )[:cap]


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
    candidates = list(qs.filter(q_filter)[:_RETRIEVAL_CANDIDATE_POOL])
    if not candidates:
        long_tokens = [t for t in tokens if len(t) >= 4][:8]
        q_filter = Q()
        for tok in long_tokens:
            q_filter |= Q(search_blob__icontains=tok)
        candidates = list(qs.filter(q_filter)[:_RETRIEVAL_CANDIDATE_POOL])
    candidates = _cap_candidates_by_token_hits(candidates, tokens)

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
