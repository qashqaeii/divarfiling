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
from public_assistant.services.persian_text import normalize_persian
from public_assistant.services.retrieval import RetrievedChunk, retrieve
from public_assistant.services.public_copy import (
    asks_internal_implementation,
    deflect_internal_question,
    format_public_fallback,
    polish_public_answer,
)
from public_assistant.services.security import (
    filter_sources,
    looks_like_prompt_injection,
    sanitize_user_message,
)

SYSTEM_PROMPT = """تو دستیار رسمی و عمومی «فایلینگ دیوار» هستی — مانند کارشناس محصول و پشتیبان آموزشی برای مشاوران املاک.

فقط بر اساس «منابع دانشنامه» پاسخ بده. اگر منبع کافی نیست، کوتاه بگو اطلاعات تأییدشده کافی نداری و به `/contact/` یا صفحات رسمی ارجاع بده.
هرگز قیمت، URL، قابلیت یا شرایطی را از خودت نساز.
به داده‌های خصوصی حساب کاربران (مخاطبین، فایل‌ها، لایسنس شخصی) دسترسی نداری.

ممنوع در پاسخ کاربر:
- نام متغیرهای ENV، Feature Flag، مسیر فایل Python، نام مدل/تابع Django، تنظیمات سرور
- توضیح پیاده‌سازی Backend به‌جای رفتار قابل مشاهده محصول
- ارجاع عددی [1] یا بخش «منابع:» در متن (لینک‌ها جدا نمایش داده می‌شود)

مجاز: CRM، API عمومی مستندشده، نام پلتفرم‌ها — وقتی برای کاربر مفید است.

قالب (مارک‌داون ساده، فارسی روان):
- تیتر کوتاه **bold**
- مراحل: 1. 2. 3. هر مرحله در خط جدا
- نکته‌ها: «نکته: ...» یا bullet
- محدودیت واقعی را شفاف بگو؛ برای همه کاربران تضمین نکن مگر منبع صریح گفته باشد
- لحن حرفه‌ای، مستقیم و کاربردی — نه رباتیک"""


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


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for ch in chunks:
        parts.append(
            f'عنوان: {ch.title}\n'
            f'دسته: {ch.category}\n'
            f'بخش: {ch.heading or "—"}\n'
            f'دسترسی/اشتراک: {_public_subscription_note(ch.subscription_note)}\n'
            f'متن:\n{ch.body}\n'
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


def _collect_sources(chunks: list[RetrievedChunk]) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for ch in chunks:
        for link in filter_sources(ch.related_links):
            url = link['url']
            if url in seen:
                continue
            seen.add(url)
            out.append(link)
    return out[:8]


def _fallback_from_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return format_public_fallback([])
    return format_public_fallback(chunks)


def _low_confidence_answer() -> str:
    return format_public_fallback([])


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

    chunks = retrieve(user_text)

    if asks_internal_implementation(user_text):
        return {
            'ok': True,
            'answer': deflect_internal_question(),
            'sources': _collect_sources(chunks) if chunks else [],
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

    if not _has_relevant_knowledge(chunks):
        return {
            'ok': True,
            'answer': _low_confidence_answer(),
            'sources': [],
            'session_id': str(session.id),
            'low_confidence': True,
        }

    sources = _collect_sources(chunks)
    context = _format_context(chunks)
    history = _history_lines(session)

    user_prompt = (
        f'سابقه گفتگو:\n{history or "—"}\n\n'
        f'سؤال کاربر:\n{user_text}\n\n'
        f'منابع دانشنامه:\n{context}\n\n'
        'فقط بر اساس منابع بالا پاسخ بده. اگر منبع کافی نیست صریح بگو مطمئن نیستی.'
    )

    text, provider, model, latency, in_tok, out_tok = llm.complete(SYSTEM_PROMPT, user_prompt)
    status = PublicAssistantUsageLog.STATUS_OK

    if not text:
        status = PublicAssistantUsageLog.STATUS_FALLBACK
        text = _fallback_from_chunks(chunks)
    else:
        text = polish_public_answer(text, chunks=chunks)

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
