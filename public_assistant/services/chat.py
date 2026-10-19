"""موتور پاسخ‌گویی RAG دستیار عمومی."""
from __future__ import annotations

from typing import Any

from public_assistant.constants import (
    MAX_HISTORY_MESSAGES,
    MAX_USER_MESSAGE_LENGTH,
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
from public_assistant.services.security import (
    filter_sources,
    looks_like_prompt_injection,
    sanitize_user_message,
)

SYSTEM_PROMPT = """تو دستیار رسمی و عمومی «فایلینگ دیوار» هستی.
فقط بر اساس «منابع دانشنامه» پاسخ بده. اگر منبع کافی نیست، صریح بگو و کاربر را به پشتیبانی یا صفحات رسمی هدایت کن.
هرگز قیمت، URL، قابلیت یا دستورالعملی را از خودت نساز.
به داده‌های خصوصی کاربران، CRM، لایسنس دیگران، API Key و اطلاعات داخلی سرور دسترسی نداری و نباید ادعای دسترسی کنی.
اگر سؤال خارج از حوزه فایلینگ دیوار است، مودبانه محدودیت خود را بگو.
پاسخ را فارسی، روان، حرفه‌ای و در صورت نیاز مرحله‌به‌مرحله بنویس.
در پایان اگر منبع مرتبط داری، با عنوان «منابع:» لیست کن (فقط لینک‌های داده‌شده در منابع)."""


def _is_probably_off_topic(query: str, chunks: list[RetrievedChunk]) -> bool:
    if chunks:
        return False
    norm = normalize_persian(query)
    product_hints = (
        'فایلینگ',
        'دیوار',
        'crm',
        'مشتری',
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
    )
    if any(h in norm for h in product_hints):
        return False
    return any(h in norm for h in OFF_TOPIC_HINTS)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for i, ch in enumerate(chunks, 1):
        parts.append(
            f'[{i}] عنوان: {ch.title}\n'
            f'دسته: {ch.category}\n'
            f'بخش: {ch.heading or "—"}\n'
            f'اشتراک/نقش: {ch.subscription_note or "عمومی/طبق محصول"}\n'
            f'متن:\n{ch.body}\n'
        )
    return '\n---\n'.join(parts)


def _history_lines(session: PublicChatSession) -> str:
    msgs = list(
        session.messages.order_by('-created_at')[:MAX_HISTORY_MESSAGES]
    )
    msgs.reverse()
    lines = []
    for m in msgs:
        role = 'کاربر' if m.role == PublicChatMessage.ROLE_USER else 'دستیار'
        lines.append(f'{role}: {m.content[:500]}')
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
        return (
            'در حال حاضر پاسخ خودکار در دسترس نیست. '
            'می‌توانید از صفحه «تماس با ما» یا راهنمای سایت کمک بگیرید.'
        )
    ch = chunks[0]
    text = f'**{ch.title}**\n\n{ch.body}'
    if ch.subscription_note:
        text += f'\n\n_نیاز اشتراک/دسترسی:_ {ch.subscription_note}'
    return text


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

    sources = _collect_sources(chunks)
    context = _format_context(chunks)
    history = _history_lines(session)

    user_prompt = (
        f'سابقه گفتگو:\n{history or "—"}\n\n'
        f'سؤال کاربر:\n{user_text}\n\n'
        f'منابع دانشنامه:\n{context or "—"}\n\n'
        'پاسخ را بر اساس منابع بنویس. اگر منبع کافی نیست، نگو که مطمئنی.'
    )

    text, provider, model, latency, in_tok, out_tok = llm.complete(SYSTEM_PROMPT, user_prompt)
    status = PublicAssistantUsageLog.STATUS_OK

    if not text:
        status = PublicAssistantUsageLog.STATUS_FALLBACK
        text = _fallback_from_chunks(chunks)
    elif not chunks:
        status = PublicAssistantUsageLog.STATUS_FALLBACK

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
