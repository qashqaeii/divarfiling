"""پولیش هوش مصنوعی متن مقاله سیستماتیک — پیش از انتشار."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from ai_workspace.providers.base import ProviderError
from ai_workspace.providers.registry import get_http_provider_chain
from ai_workspace.services.generation import get_feature_generation
from blog.models import MarketArticleRun
from blog.services.market_article_quality_gates import _extract_report_numbers

logger = logging.getLogger(__name__)

FEATURE = 'market_article_polish'

_PLACEHOLDER_RE = re.compile(
    r'lorem\s+ipsum|متن\s*نمونه|placeholder|\[TODO\]|ساختگی',
    re.I,
)
_JSON_FENCE_RE = re.compile(r'^```(?:json)?\s*|\s*```$', re.I | re.M)
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_TABLE_RE = re.compile(r'<table\b', re.I)


class AIPolishError(Exception):
    """خطای غیرقابل‌بازیابی — اعتبارسنجی خروجی."""


class AIPolishRecoverableError(Exception):
    """همه providerها شکست خوردند — تلاش مجدد مجاز است."""


@dataclass
class PolishResult:
    applied: bool
    provider: str
    model: str
    latency_ms: int
    report: dict[str, Any]


def _generation() -> dict[str, Any]:
    return get_feature_generation(FEATURE)


def _protected_number_tokens(run: MarketArticleRun) -> list[str]:
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    inner = blob.get('report') if isinstance(blob.get('report'), dict) else {}
    tokens: list[str] = []
    metrics = blob.get('metrics') if isinstance(blob.get('metrics'), dict) else {}
    if metrics.get('valid_count'):
        tokens.append(str(metrics['valid_count']))
    if run.valid_count:
        tokens.append(str(run.valid_count))
    for fmt in _extract_report_numbers(inner)[:20]:
        if len(fmt) >= 3:
            tokens.append(fmt)
    unique = list(dict.fromkeys(tokens))
    haystack = (run.content_html or '') + str((run.seo_json or {}).get('excerpt') or '')
    return [t for t in unique if t in haystack]


def _extract_urls(pattern: re.Pattern[str], html: str) -> list[str]:
    return list(dict.fromkeys(pattern.findall(html or '')))


def validate_polished_html(
    *,
    original_html: str,
    polished_html: str,
    protected_numbers: list[str],
) -> list[str]:
    """لیست خطاهای اعتبارسنجی — خالی یعنی قابل قبول."""
    errors: list[str] = []
    if not (polished_html or '').strip():
        errors.append('خروجی AI خالی است.')
        return errors

    if _PLACEHOLDER_RE.search(polished_html):
        errors.append('متن ساختگی یا placeholder در خروجی AI.')

    orig_words = len(re.sub(r'<[^>]+>', ' ', original_html or '').split())
    new_words = len(re.sub(r'<[^>]+>', ' ', polished_html).split())
    if orig_words and new_words < int(orig_words * 0.75):
        errors.append('طول متن پس از پولیش بیش از حد کاهش یافته است.')

    missing_nums = []
    for token in protected_numbers:
        if token not in polished_html:
            missing_nums.append(token)
    if missing_nums:
        errors.append(f'{len(missing_nums)} عدد آماری از خروجی حذف شده است.')

    for src in _extract_urls(_IMG_SRC_RE, original_html):
        if src not in polished_html:
            errors.append('تصویر یا src در HTML حفظ نشده است.')
            break

    orig_hrefs = _extract_urls(_HREF_RE, original_html)
    for href in orig_hrefs:
        if href.startswith('#'):
            continue
        if href not in polished_html:
            errors.append('لینک‌های HTML حفظ نشده‌اند.')
            break

    orig_tables = len(_TABLE_RE.findall(original_html or ''))
    new_tables = len(_TABLE_RE.findall(polished_html))
    if orig_tables and new_tables < orig_tables:
        errors.append('ساختار جدول در HTML ناقص است.')

    if 'mk-market' not in polished_html:
        errors.append('ساختار اصلی مقاله (mk-market) در HTML نیست.')

    return errors


def _parse_polish_json(raw: str) -> dict[str, Any]:
    text = (raw or '').strip()
    text = _JSON_FENCE_RE.sub('', text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIPolishError(f'پاسخ AI JSON معتبر نیست: {exc}') from exc
    if not isinstance(data, dict):
        raise AIPolishError('پاسخ AI باید شیء JSON باشد.')
    return data


def _call_llm(system: str, user: str) -> tuple[str, str, str, int]:
    generation = _generation()
    chain = get_http_provider_chain()
    last_code = ''
    for provider in chain:
        try:
            result = provider.complete(
                system=system,
                user=user,
                json_mode=True,
                generation=generation,
            )
            text = (result.text or '').strip()
            if text:
                return text, result.provider, result.model, result.latency_ms
        except ProviderError as exc:
            last_code = exc.code or 'provider_error'
            logger.warning('market_article_polish provider failed: %s %s', provider.name, last_code)
            continue
    raise AIPolishRecoverableError(f'همه providerهای AI شکست خوردند ({last_code}).')


def polish_market_article_run(run: MarketArticleRun) -> PolishResult:
    """
    پولیش محتوا با AI؛ در صورت موفقیت run را به‌روز می‌کند.
    خروجی بدون اعتبارسنجی هرگز جایگزین نمی‌شود.
    """
    original_html = run.content_html or ''
    seo = dict(run.seo_json or {})
    protected = _protected_number_tokens(run)

    system = (
        'تو ویراستار حرفه‌ای مقالات تحلیل بازار املاک ایران هستی. '
        'فقط JSON برگردان با کلیدهای: title, excerpt, content_html. '
        'قوانین: لحن فارسی مناسب مشاوران املاک؛ روان و طبیعی؛ جملات بلند را کوتاه کن؛ '
        'تکرار غیرضروری را حذف کن؛ مقدمه، تیترها و نتیجه‌گیری را بهبود بده. '
        'هرگز اعداد، درصدها، قیمت‌ها و آمار را تغییر نده. '
        'تگ‌های HTML، لینک‌ها، src تصاویر، جدول‌ها و classهای موجود را حفظ کن. '
        'ساختار کلی مقاله و بخش‌های mk-market را دست نزن؛ فقط متن داخل تگ‌ها را بهبود بده.'
    )
    user = json.dumps(
        {
            'title': seo.get('title') or '',
            'excerpt': seo.get('excerpt') or '',
            'content_html': original_html,
            'protected_numbers_sample': protected[:15],
        },
        ensure_ascii=False,
    )

    raw, provider, model, latency_ms = _call_llm(system, user)
    data = _parse_polish_json(raw)

    new_html = str(data.get('content_html') or '').strip()
    new_title = str(data.get('title') or seo.get('title') or '').strip()
    new_excerpt = str(data.get('excerpt') or seo.get('excerpt') or '').strip()

    validation_errors = validate_polished_html(
        original_html=original_html,
        polished_html=new_html,
        protected_numbers=protected,
    )
    if validation_errors:
        raise AIPolishError('; '.join(validation_errors))

    run.content_html = new_html
    run.seo_json = {
        **seo,
        'title': new_title[:200],
        'excerpt': new_excerpt[:300],
    }
    run.save(update_fields=['content_html', 'seo_json', 'updated_at'])

    report = {
        'ok': True,
        'provider': provider,
        'model': model,
        'latency_ms': latency_ms,
        'protected_numbers_count': len(protected),
        'validation_errors': [],
    }
    return PolishResult(applied=True, provider=provider, model=model, latency_ms=latency_ms, report=report)
