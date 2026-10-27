"""متن عمومی دستیار — بدون نشت جزئیات پیاده‌سازی داخلی."""
from __future__ import annotations

import re

from public_assistant.services.public_links import contact_link, license_guide_link
from public_assistant.services.retrieval import RetrievedChunk

# الگوهایی که در پاسخ کاربر عمومی نباید دیده شوند (مسیرهای عمومی مثل `/workspace/` مجازند)
_INTERNAL_LEAK_RE = re.compile(
    r'(?i)'
    r'(SIGNUP_[A-Z0-9_]+|'
    r'FEATURE_DAILY_LIMITS|AI_LICENSED_UNLIMITED|'
    r'has_active_bot_license|agency_rbac_v2|'
    r'LicensePlan|PaymentSettings|'
    r'unique_together|'
    r'\bForeignKey\b|\bManyToMany\b|'
    r'feature\s*flag|'
    r'\b[a-z_]+/[a-z_]+\.py\b|'
    r'\bmodels\.py\b|'
    r'\bsettings\.py\b|'
    r'\bnl_command\b|\blisting_summary\b|\bcrm_message\b|'
    r'\bupload_brief\b|\bmanagement_analysis\b|'
    r'\bmax_activations\b|\ballow_bulk_purchase\b)'
)

# کد داخلی داخل بک‌تیک — نه URL/مسیر محصول
_INTERNAL_BACKTICK_CODE_RE = re.compile(
    r'`(?:[a-z][a-z0-9_]{2,}(?:\.py)?|SIGNUP_[A-Z0-9_]+)`'
)

_CITATION_RE = re.compile(r'\s*\[\d+\]')
_SOURCES_TAIL_RE = re.compile(r'\n+منابع:\s*[\s\S]*$', re.IGNORECASE)

# نکتهٔ تجمیعی استخراج که در راهنمای «چطور» نباید به‌صورت خودکار تکرار شود
_EXTRACTOR_AUTO_DISCLAIMER_RE = re.compile(
    r'(?:^|\n)\s*(?:>\s*)?[«"]?نکته:\s*استخراج مستقیم از مرورگر[\s\S]*?'
    r'همگام‌سازی با میزکار انجام نمی‌شود[\.»"]?\s*',
    re.IGNORECASE,
)

def _insufficient_info() -> str:
    return (
        'برای این مورد اطلاعات تأییدشدهٔ کافی در راهنمای فعلی ندارم. '
        f'می‌توانید سؤال را دقیق‌تر بپرسید یا از {contact_link()} با پشتیبانی فایلینگ دیوار '
        'در ارتباط باشید.'
    )


_INSUFFICIENT_INFO = _insufficient_info()

_INTERNAL_QUESTION_RE = re.compile(
    r'(?i)(feature\s*flag|متغیر\s*محیط|env\b|django|'
    r'signup_welcome|تنظیمات\s*سرور|کد\s*سرور|backend|'
    r'پیاده\s*سازی\s*داخلی|api\s*داخلی)'
)


def asks_internal_implementation(query: str) -> bool:
    return bool(_INTERNAL_QUESTION_RE.search(query or ''))


def deflect_internal_question() -> str:
    return (
        '**راهنمای محصول فایلینگ دیوار**\n\n'
        'من برای توضیح **نحوه استفاده**، **شرایط طرح‌ها** و **محدودیت‌های واقعی** محصول اینجا هستم؛ '
        'جزئیات فنی سرور یا پیاده‌سازی داخلی را در اختیار کاربران عمومی قرار نمی‌دهم.\n\n'
        'اگر درباره **هدیه ۷ روزه**، **لایسنس** یا **شروع کار** سؤال دارید، همان را بپرسید — '
        f'یا از {license_guide_link()} و {contact_link()} کمک بگیرید.'
    )


def contains_internal_leak(text: str) -> bool:
    if not text:
        return False
    if _INTERNAL_LEAK_RE.search(text):
        return True
    return bool(_INTERNAL_BACKTICK_CODE_RE.search(text))


def _strip_citations(text: str) -> str:
    text = _CITATION_RE.sub('', text or '')
    text = _SOURCES_TAIL_RE.sub('', text)
    text = _EXTRACTOR_AUTO_DISCLAIMER_RE.sub('\n', text)
    return text.strip()


def sanitize_public_knowledge_text(text: str) -> str:
    """زبان کاربر — بدون اصطلاحات پیاده‌سازی دیتابیس."""
    if not text:
        return text
    out = text
    replacements = (
        (re.compile(r'`unique_together[^`]*`', re.I), 'شناسه یکتا همان آگهی در یک مجموعه فایل'),
        (re.compile(r'unique_together[^\n)\]]*', re.I), ''),
        (re.compile(r'\bper[- ]dataset\b', re.I), 'در هر مجموعه فایل'),
        (re.compile(r'\bper[- ]user\b', re.I), 'برای هر کاربر'),
        (re.compile(r'\bdataset\+token\b', re.I), 'مجموعه فایل و شناسه آگهی'),
    )
    for pat, repl in replacements:
        out = pat.sub(repl, out)
    out = re.sub(r'\(\s*\)', '', out)
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()


def format_public_fallback(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return _INSUFFICIENT_INFO
    parts: list[str] = []
    for ch in chunks[:3]:
        body = sanitize_public_knowledge_text((ch.body or '').strip())
        if not body or contains_internal_leak(body):
            continue
        heading = f' — {ch.heading}' if ch.heading else ''
        parts.append(f'**{ch.title}{heading}**\n\n{body}')
    if not parts:
        return _INSUFFICIENT_INFO
    text = '\n\n'.join(parts)
    note = (chunks[0].subscription_note or '').strip()
    if note and not contains_internal_leak(note):
        text += f'\n\nنکته: {note}'
    return text


def polish_public_answer(text: str, *, chunks: list[RetrievedChunk] | None = None) -> str:
    cleaned = sanitize_public_knowledge_text(_strip_citations(text))
    if not cleaned:
        return _INSUFFICIENT_INFO if not chunks else format_public_fallback(chunks)
    if contains_internal_leak(cleaned):
        if chunks:
            return format_public_fallback(chunks)
        return _INSUFFICIENT_INFO
    return finalize_public_answer(cleaned)


def finalize_public_answer(text: str) -> str:
    from public_assistant.services.public_links import normalize_public_answer_links

    return normalize_public_answer_links((text or '').strip())


_SUBSCRIPTION_BUY_URL_RE = re.compile(r'/products/divar-extraction-bot/buy/', re.I)
_SUBSCRIPTION_PLAN_LINE_RE = re.compile(
    r'پلن\s+\*\*|خرید اشتراک|لایسنس\s+یک|برای کار\s+\*\*تک‌نفره\*\*|تخفیف حجمی آژانس|'
    r'مقایسه\s+\*\*سه‌ماهه\*\*|۳×\s*ماهانه|پلن\s+آزمایشی|اشتراک\s+ماهانه',
    re.I,
)
_PLAN_PRICE_SNIPPET_RE = re.compile(
    r'۹۹۰٬۰۰۰|۲٬۵۰۰٬۰۰۰|۲٬۹۷۰٬۰۰۰|۸٬۰۰۰٬۰۰۰|۴۷۰٬۰۰۰|۲۵۰٬۰۰۰',
)
_PLAN_PITCH_PARAGRAPH_RE = re.compile(
    r'(divar-extraction-bot|تک‌نفره|سه‌ماهه\s+شخصی|یک‌ماهه\s+شخصی|'
    r'خرید\s+اشتراک|مقایسه\s+\*\*|۳×\s*ماهانه|پلن\s+\*\*)',
    re.I,
)


def strip_unsolicited_subscription_pitch(text: str) -> str:
    """حذف تبلیغ پلن از پاسخ سؤالات عملیاتی محصول."""
    if not text:
        return text
    paragraphs = re.split(r'\n\s*\n', text.strip())
    kept: list[str] = []
    for para in paragraphs:
        if _SUBSCRIPTION_BUY_URL_RE.search(para):
            continue
        if _PLAN_PITCH_PARAGRAPH_RE.search(para) and (
            _PLAN_PRICE_SNIPPET_RE.search(para) or 'تومان' in para
        ):
            continue
        lines = []
        for line in para.splitlines():
            if _SUBSCRIPTION_BUY_URL_RE.search(line):
                continue
            if _SUBSCRIPTION_PLAN_LINE_RE.search(line) and 'تومان' in line:
                continue
            if 'برای کار **تک‌نفره**' in line or 'برای کار تک‌نفره' in line:
                continue
            if _PLAN_PRICE_SNIPPET_RE.search(line) and _SUBSCRIPTION_PLAN_LINE_RE.search(line):
                continue
            lines.append(line)
        block = '\n'.join(lines).strip()
        if block:
            kept.append(block)
    return '\n\n'.join(kept).strip()
