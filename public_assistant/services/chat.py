"""موتور پاسخ‌گویی RAG دستیار عمومی."""
from __future__ import annotations

from typing import Any

from public_assistant.constants import (
    MAX_HISTORY_MESSAGES,
    MAX_USER_MESSAGE_LENGTH,
    MIN_RETRIEVAL_SCORE,
    OFF_TOPIC_HINTS,
)
from public_assistant.models import (
    PublicAssistantUsageLog,
    PublicChatMessage,
    PublicChatSession,
)
from public_assistant.services import llm
from public_assistant.services.persian_text import normalize_persian, tokenize_query
from public_assistant.services.retrieval import RetrievedChunk, retrieve
from public_assistant.services.public_copy import (
    asks_internal_implementation,
    deflect_internal_question,
    finalize_public_answer,
    format_public_fallback,
    polish_public_answer,
    reconcile_escalation_paths,
    sanitize_public_knowledge_text,
    strip_unsolicited_subscription_pitch,
)
from public_assistant.services.public_links import LINK_STYLE_PROMPT
from public_assistant.services.plan_advisor import (
    PLAN_ADVISOR_SYSTEM_ADDENDUM,
    build_plan_advisor_context,
    compose_no_catalog_answer,
    compose_subscription_answer,
)
from public_assistant.services.plan_answer_guard import (
    reconcile_subscription_answer,
    strip_unverified_subscription_prices,
)
from public_assistant.services.plan_intent import (
    analyze_subscription_query,
    is_independent_user_turn,
    is_product_operations_topic,
)
from public_assistant.services.public_plans import load_public_plan_catalog
from public_assistant.services.public_paths import is_commerce_path, scrub_commerce_links_from_answer
from public_assistant.services.security import (
    filter_sources,
    looks_like_prompt_injection,
    sanitize_user_message,
)

SYSTEM_PROMPT = """تو دستیار رسمی و عمومی «فایلینگ دیوار» هستی — مانند کارشناس محصول و پشتیبان آموزشی برای مشاوران املاک.

فقط بر اساس «منابع دانشنامه» پاسخ بده. اگر منبع کافی نیست، کوتاه بگو اطلاعات تأییدشده کافی نداری و با لینک فارسی به تماس یا صفحات رسمی ارجاع بده.
هرگز قیمت، URL، قابلیت یا شرایطی را از خودت نساز.
به داده‌های خصوصی حساب کاربران (مخاطبین، فایل‌ها، لایسنس شخصی) دسترسی نداری.

ممنوع در پاسخ کاربر:
- نام متغیرهای ENV، Feature Flag، مسیر فایل Python، نام مدل/تابع Django، تنظیمات سرور
- توضیح پیاده‌سازی Backend به‌جای رفتار قابل مشاهده محصول
- ارجاع عددی [1] یا بخش «منابع:» در متن (لینک‌ها جدا نمایش داده می‌شود)

مجاز: CRM، API عمومی مستندشده، نام پلتفرم‌ها — وقتی برای کاربر مفید است.

قالب پاسخ حرفه‌ای (مارک‌داون ساده، فارسی روان):
1. **یک جمله مستقیم** که همان سؤال را جواب می‌دهد.
2. بدنه ساختارمند: تیتر **bold** کوتاه، سپس bullet یا شماره‌گذاری 1. 2. 3. (هر مرحله در خط جدا).
3. اگر سؤال «چطور / چگونه» است، **مراحل عملی** از منبع را کامل و به‌ترتیب بیاور (پلتفرم، مسیر میزکار، لینک رسمی).
4. اگر منبع «امکانات» یا «تفاوت» دارد، دسته‌بندی منطقی (فایلینگ، CRM، استخراج، …) را حفظ کن.
5. در پایان در صورت وجود در منبع، **قدم بعدی** با لینک مارک‌داون فارسی در جمله (بدون ساخت URL جدید).

""" + LINK_STYLE_PROMPT + """

کیفیت:
- وقتی منبع جزئیات دارد، از پاسخ یک‌خطی یا فهرست ناقص خودداری کن.
- هر ادعا باید در منابع پشتیبانی شود؛ حدس نزن.
- نکته‌ها: «نکته: ...» — فقط اگر در منبع آمده یا کاربر مستقیم درباره محدودیت پرسیده.
- در پاسخ «چطور استخراج کنم»، مراحل و پلتفرم‌ها را بگو؛ بدون نکتهٔ پایانی تجمیعی درباره مرورگر، نرخ دیوار یا قطع اینترنت مگر در منبع باشد.
- لحن مشاور محصول: حرفه‌ای، دقیق، قابل‌اعتماد — نه رباتیک و نه تبلیغاتی.
- برای سؤالات آموزشی («چطور»، «چه امکاناتی»، «چه کمکی») معمولاً حداقل **۱۲۰–۲۲۰ کلمه** مفید بنویس اگر منبع محتوا دارد؛ خالی‌گویی نکن.
- اگر سؤال درباره CRM، فایلینگ، تطبیق، آگهی یا ملک است، **قیمت یا لینک خرید پلن/اشتراک** را در پاسخ نیاور مگر کاربر مستقیماً درباره اشتراک پرسیده باشد."""


def _compose_retrieval_query(session: PublicChatSession, message: str) -> str:
    """سؤال‌های کوتاه/ادامه‌دار را با موضوع نوبت قبل غنی می‌کند."""
    if is_independent_user_turn(message):
        return message
    norm = normalize_persian(message)
    tokens = tokenize_query(message)
    followup_hint = len(tokens) <= 4 or any(
        w in norm for w in ('کجا', 'همون', 'همین', 'اون', 'همان')
    )
    if not followup_hint:
        return message
    prev = (
        session.messages.filter(role=PublicChatMessage.ROLE_USER)
        .order_by('-created_at')
        .first()
    )
    if not prev:
        return message
    prev_norm = normalize_persian(prev.content)
    if prev_norm in norm or norm in prev_norm:
        return message
    return f'{prev.content} — {message}'


def _is_probably_off_topic(query: str, chunks: list[RetrievedChunk]) -> bool:
    if chunks:
        return False
    norm = normalize_persian(query)
    product_hints = (
        'فایلینگ',
        'دیوار',
        'crm',
        'مشتری',
        'مخاطب',
        'آگهی',
        'استخراج',
        'لایسنس',
        'اشتراک',
        'میزکار',
        'workspace',
        'آژانس',
        'مشاور',
        'املاک',
        'ثبت',
        'ورود',
        'اندروید',
        'ویندوز',
        'هوش',
        'ai',
        'پلن',
        'خرید',
    )
    if any(h in norm for h in product_hints):
        return False
    return any(h in norm for h in OFF_TOPIC_HINTS)


def _has_relevant_knowledge(chunks: list[RetrievedChunk]) -> bool:
    return bool(chunks) and chunks[0].score >= MIN_RETRIEVAL_SCORE


def _public_subscription_note(note: str) -> str:
    note = (note or '').strip()
    if not note:
        return 'طبق محصول'
    from public_assistant.services.public_copy import contains_internal_leak

    if contains_internal_leak(note):
        return 'طبق محصول'
    return note


def _format_context_links(links: list) -> str:
    if not links:
        return ''
    lines = []
    for item in links[:6]:
        if not isinstance(item, dict):
            continue
        label = (item.get('label') or '').strip()
        url = (item.get('url') or '').strip()
        if label and url:
            lines.append(f'- [{label}]({url})')
    if not lines:
        return ''
    return 'لینک‌های رسمی این مقاله:\n' + '\n'.join(lines)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for ch in chunks:
        safe_links = filter_sources(ch.related_links or [])
        link_block = _format_context_links(safe_links)
        summary = (ch.summary or '').strip()
        parts.append(
            f'عنوان: {ch.title}\n'
            f'دسته: {ch.category}\n'
            f'بخش: {ch.heading or "—"}\n'
            f'خلاصه: {summary or "—"}\n'
            f'دسترسی/اشتراک: {_public_subscription_note(ch.subscription_note)}\n'
            f'متن:\n{sanitize_public_knowledge_text(ch.body or "")}\n'
            + (f'{link_block}\n' if link_block else '')
        )
    return '\n---\n'.join(parts)


def _history_lines(session: PublicChatSession) -> str:
    msgs = list(session.messages.order_by('-created_at')[:MAX_HISTORY_MESSAGES])
    msgs.reverse()
    lines = []
    for m in msgs:
        role = 'کاربر' if m.role == PublicChatMessage.ROLE_USER else 'دستیار'
        snippet = m.content[:500]
        if m.role == PublicChatMessage.ROLE_ASSISTANT:
            snippet = polish_public_answer(snippet)
        lines.append(f'{role}: {snippet}')
    return '\n'.join(lines)


def _collect_sources(
    chunks: list[RetrievedChunk],
    *,
    allow_commerce: bool = False,
    max_score_gap: float = 5.0,
) -> list[dict]:
    seen = set()
    out: list[dict] = []
    if not chunks:
        return out
    top_score = chunks[0].score
    for ch in chunks:
        if ch.score < top_score - max_score_gap:
            continue
        for link in filter_sources(ch.related_links):
            url = link['url']
            if not allow_commerce and is_commerce_path(url):
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append(link)
    return out[:8]


def _fallback_from_chunks(chunks: list[RetrievedChunk], *, query: str = '') -> str:
    if not chunks:
        return format_public_fallback([], query=query)
    return format_public_fallback(chunks, query=query)


def _low_confidence_answer(query: str = '') -> str:
    return format_public_fallback([], query=query)


def answer_question(
    *,
    session: PublicChatSession,
    message: str,
) -> dict[str, Any]:
    user_text = sanitize_user_message(message, MAX_USER_MESSAGE_LENGTH)
    if not user_text:
        return {'ok': False, 'error': 'پیام خالی است.', 'answer': ''}

    if looks_like_prompt_injection(user_text):
        return {
            'ok': True,
            'answer': 'فقط می‌توانم درباره فایلینگ دیوار و امکانات عمومی محصول راهنمایی کنم.',
            'sources': [],
            'session_id': str(session.id),
        }

    retrieval_query = _compose_retrieval_query(session, user_text)
    chunks = retrieve(retrieval_query)
    sub_ctx = analyze_subscription_query(user_text, session)
    plan_catalog = load_public_plan_catalog() if sub_ctx.is_subscription else None
    plan_live_context = (
        build_plan_advisor_context(sub_ctx, plan_catalog)
        if plan_catalog and sub_ctx.is_subscription
        else ''
    )

    if asks_internal_implementation(user_text):
        return {
            'ok': True,
            'answer': finalize_public_answer(deflect_internal_question()),
            'sources': _collect_sources(chunks, allow_commerce=sub_ctx.is_subscription) if chunks else [],
            'session_id': str(session.id),
        }

    if _is_probably_off_topic(user_text, chunks):
        return {
            'ok': True,
            'answer': (
                'من دستیار رسمی فایلینگ دیوار هستم و درباره محصول، امکانات، آموزش و '
                'محدودیت‌های واقعی آن راهنمایی می‌کنم. لطفاً سؤال خود را در این زمینه بپرسید.'
            ),
            'sources': [],
            'session_id': str(session.id),
        }

    has_plan_data = bool(plan_live_context)
    if not _has_relevant_knowledge(chunks) and not (sub_ctx.is_subscription and has_plan_data):
        if sub_ctx.is_subscription and not plan_catalog:
            return {
                'ok': True,
                'answer': finalize_public_answer(compose_no_catalog_answer()),
                'sources': _collect_sources(chunks, allow_commerce=sub_ctx.is_subscription) if chunks else [],
                'session_id': str(session.id),
            }
        return {
            'ok': True,
            'answer': finalize_public_answer(_low_confidence_answer(user_text)),
            'sources': [],
            'session_id': str(session.id),
            'low_confidence': True,
        }

    sources = _collect_sources(chunks, allow_commerce=sub_ctx.is_subscription)
    context = _format_context(chunks)
    history = _history_lines(session)

    user_prompt_parts = [
        f'سابقه گفتگو:\n{history or "—"}',
        f'سؤال کاربر:\n{user_text}',
    ]
    if plan_live_context:
        user_prompt_parts.append(f'داده فروشگاه زنده (قیمت معتبر):\n{plan_live_context}')
    if context.strip():
        user_prompt_parts.append(f'منابع دانشنامه:\n{context}')
    user_prompt_parts.append(
        'پاسخ را کامل و کاربردی بنویس. برای قیمت و مدت پلن، داده فروشگاه زنده اولویت دارد. '
        'اگر منبع کافی نیست صریح بگو مطمئن نیستی.'
    )
    user_prompt = '\n\n'.join(user_prompt_parts)

    system_prompt = SYSTEM_PROMPT
    if plan_live_context:
        system_prompt = f'{SYSTEM_PROMPT}\n\n{PLAN_ADVISOR_SYSTEM_ADDENDUM}'

    text, provider, model, latency, in_tok, out_tok = llm.complete(system_prompt, user_prompt)
    status = PublicAssistantUsageLog.STATUS_OK

    if not text:
        status = PublicAssistantUsageLog.STATUS_FALLBACK
        product_ops = is_product_operations_topic(normalize_persian(user_text))
        if plan_catalog and sub_ctx.is_subscription and not product_ops:
            text = compose_subscription_answer(sub_ctx, plan_catalog)
        if not text:
            text = _fallback_from_chunks(chunks, query=user_text)
    else:
        text = polish_public_answer(text, chunks=chunks, query=user_text)
        if sub_ctx.is_subscription:
            text = reconcile_subscription_answer(text, sub_ctx, plan_catalog)
            text = strip_unverified_subscription_prices(text, sub_ctx, plan_catalog)
        else:
            text = strip_unsolicited_subscription_pitch(text)
    if sub_ctx.is_subscription and not plan_catalog and not text:
        text = compose_no_catalog_answer()

    PublicAssistantUsageLog.objects.create(
        session=session,
        provider=provider,
        model=model,
        status=status,
        latency_ms=latency,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )

    PublicChatMessage.objects.create(
        session=session,
        role=PublicChatMessage.ROLE_USER,
        content=user_text,
    )
    if not sub_ctx.is_subscription:
        text = strip_unsolicited_subscription_pitch(text or '')
    text = sanitize_public_knowledge_text(text or '')
    text = reconcile_escalation_paths(text or '', user_text)
    text = finalize_public_answer(text)
    if not sub_ctx.is_subscription:
        text = scrub_commerce_links_from_answer(text)

    PublicChatMessage.objects.create(
        session=session,
        role=PublicChatMessage.ROLE_ASSISTANT,
        content=text,
    )
    session.message_count += 2
    session.save(update_fields=['message_count', 'updated_at'])

    return {
        'ok': True,
        'answer': text,
        'sources': sources,
        'session_id': str(session.id),
        'from_fallback': status == PublicAssistantUsageLog.STATUS_FALLBACK,
    }
