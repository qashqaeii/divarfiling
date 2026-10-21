"""پولیش هوش مصنوعی متن مقاله سیستماتیک — پیش از انتشار."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from ai_workspace.providers.base import ProviderError
from ai_workspace.providers.registry import get_http_provider_chain
from ai_workspace.services.generation import get_feature_generation
from blog.models import MarketArticleRun
from blog.services.market_article_autopublish_config import get_autopublish_settings
from blog.services.market_article_quality_gates import _extract_report_numbers, run_quality_gates

logger = logging.getLogger(__name__)

FEATURE = 'market_article_polish'

_PlaceKind = Literal['markup', 'text']

_PLACEHOLDER_RE = re.compile(
    r'lorem\s+ipsum|متن\s*نمونه|placeholder|\[TODO\]|ساختگی',
    re.I,
)
_JSON_FENCE_RE = re.compile(r'^```(?:json)?\s*|\s*```$', re.I | re.M)
_NUM_FMT_RE = re.compile(
    r'[\d۰-۹]{1,3}(?:[,\،][\d۰-۹]{3})+(?:\s*(?:میلیون|میلیارد|تومان|متر|%|٪))?|[\d۰-۹]+(?:[\.٫][\d۰-۹]+)?\s*٪',
    re.U,
)
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_LOCKED_ATTR_RE = re.compile(
    r'\b(src|href|class|id)=("([^"]*)"|\'([^\']*)\')',
    re.I,
)
_CHART_SRC_HINT = re.compile(r'chart_|mk-chart|canvas', re.I)


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


@dataclass
class StatisticalProtection:
    """توکن‌های آماری که نباید در خروجی حذف یا دستکاری شوند."""
    tokens: list[str] = field(default_factory=list)

    def all_present_in(self, *blobs: str) -> list[str]:
        haystack = '\n'.join(blobs)
        return [t for t in self.tokens if t and t not in haystack]


def split_html_parts(html: str) -> list[tuple[_PlaceKind, str]]:
    """تفکیک markup و text — markup هرگز به AI نمی‌رود."""
    parts: list[tuple[_PlaceKind, str]] = []
    for chunk in re.split(r'(<[^>]+>)', html or ''):
        if not chunk:
            continue
        if chunk.startswith('<'):
            parts.append(('markup', chunk))
        else:
            parts.append(('text', chunk))
    return parts


def text_segment_payload(parts: list[tuple[_PlaceKind, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, (kind, content) in enumerate(parts):
        if kind == 'text' and content.strip():
            out.append({'id': idx, 'text': content})
    return out


def apply_polished_texts(
    parts: list[tuple[_PlaceKind, str]],
    polished_by_id: dict[int, str],
) -> str:
    rebuilt: list[str] = []
    for idx, (kind, content) in enumerate(parts):
        if kind == 'markup':
            rebuilt.append(content)
        else:
            rebuilt.append(polished_by_id.get(idx, content))
    return ''.join(rebuilt)


def collect_statistical_protection(
    run: MarketArticleRun,
    *,
    title: str,
    excerpt: str,
    html: str,
) -> StatisticalProtection:
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    inner = blob.get('report') if isinstance(blob.get('report'), dict) else {}
    metrics = blob.get('metrics') if isinstance(blob.get('metrics'), dict) else {}
    tokens: list[str] = []

    if metrics.get('valid_count'):
        tokens.append(str(metrics['valid_count']))
    if run.valid_count:
        tokens.append(str(run.valid_count))
    for fmt in _extract_report_numbers(inner)[:24]:
        if len(fmt) >= 3:
            tokens.append(fmt)

    haystack = '\n'.join([title or '', excerpt or '', html or ''])
    for match in _NUM_FMT_RE.findall(haystack):
        if len(match) >= 2:
            tokens.append(match.strip())

    unique = list(dict.fromkeys(tokens))
    return StatisticalProtection(tokens=[t for t in unique if t in haystack])


def _table_counts(html: str) -> tuple[int, int, int]:
    return (
        len(re.findall(r'<table\b', html or '', re.I)),
        len(re.findall(r'<tr\b', html or '', re.I)),
        len(re.findall(r'<td\b', html or '', re.I)) + len(re.findall(r'<th\b', html or '', re.I)),
    )


def _locked_attributes(html: str) -> list[tuple[str, str, str]]:
    locked: list[tuple[str, str, str]] = []
    for match in _LOCKED_ATTR_RE.finditer(html or ''):
        attr = match.group(1).lower()
        value = match.group(3) if match.group(3) is not None else (match.group(4) or '')
        locked.append((attr, value))
    return locked


def _chart_asset_srcs(html: str) -> set[str]:
    srcs = set(_IMG_SRC_RE.findall(html or ''))
    return {s for s in srcs if _CHART_SRC_HINT.search(s)}


def validate_markup_unchanged(original_html: str, candidate_html: str) -> list[str]:
    """Markup (تگ‌ها و src/href/class/id) باید عیناً حفظ شود — فقط متن عوض می‌شود."""
    errors: list[str] = []
    orig_parts = split_html_parts(original_html)
    cand_parts = split_html_parts(candidate_html)
    if len(orig_parts) != len(cand_parts):
        errors.append('تعداد بخش‌های HTML پس از پولیش تغییر کرده است.')
        return errors

    for idx, ((ok, oc), (ck, cc)) in enumerate(zip(orig_parts, cand_parts)):
        if ok != ck:
            errors.append(f'نوع بخش HTML در موقعیت {idx} تغییر کرده است.')
            break
        if ok == 'markup' and oc != cc:
            errors.append('تگ یا attribute (src/href/class/id) تغییر کرده است.')
            break

    o_tables = _table_counts(original_html)
    n_tables = _table_counts(candidate_html)
    if o_tables != n_tables:
        errors.append('ساختار جدول (table/tr/cell) تغییر کرده است.')

    o_charts = _chart_asset_srcs(original_html)
    n_charts = _chart_asset_srcs(candidate_html)
    if o_charts != n_charts:
        errors.append('src نمودار/دارایی chart تغییر کرده است.')

    o_locked = sorted(_locked_attributes(original_html))
    n_locked = sorted(_locked_attributes(candidate_html))
    if o_locked != n_locked:
        errors.append('attributeهای قفل‌شده (src/href/class/id) با نسخه اصلی یکی نیست.')

    return errors


def validate_seo_fields(
    *,
    original_title: str,
    original_excerpt: str,
    new_title: str,
    new_excerpt: str,
    protection: StatisticalProtection,
) -> list[str]:
    errors: list[str] = []
    if not (new_title or '').strip():
        errors.append('عنوان پس از پولیش خالی است.')
    if len((new_title or '').strip()) < 10:
        errors.append('عنوان پس از پولیش بسیار کوتاه است.')
    if not (new_excerpt or '').strip():
        errors.append('Meta Description پس از پولیش خالی است.')

    title_missing = [t for t in protection.tokens if t in (original_title or '') and t not in (new_title or '')]
    if title_missing:
        errors.append(f'{len(title_missing)} عدد آماری از عنوان حذف شده است.')

    excerpt_missing = [
        t for t in protection.tokens if t in (original_excerpt or '') and t not in (new_excerpt or '')
    ]
    if excerpt_missing:
        errors.append(f'{len(excerpt_missing)} عدد آماری از Meta Description حذف شده است.')

    return errors


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

    missing_nums = [token for token in protected_numbers if token not in polished_html]
    if missing_nums:
        errors.append(f'{len(missing_nums)} عدد آماری از بدنه HTML حذف شده است.')

    errors.extend(validate_markup_unchanged(original_html, polished_html))

    if 'mk-market' not in polished_html:
        errors.append('ساختار اصلی مقاله (mk-market) در HTML نیست.')

    return errors


def validate_polished_article(
    run: MarketArticleRun,
    *,
    original_html: str,
    polished_html: str,
    original_title: str,
    original_excerpt: str,
    new_title: str,
    new_excerpt: str,
) -> list[str]:
    protection = collect_statistical_protection(
        run,
        title='\n'.join([original_title, new_title]),
        excerpt='\n'.join([original_excerpt, new_excerpt]),
        html='\n'.join([original_html, polished_html]),
    )
    errors = validate_seo_fields(
        original_title=original_title,
        original_excerpt=original_excerpt,
        new_title=new_title,
        new_excerpt=new_excerpt,
        protection=protection,
    )
    errors.extend(
        validate_polished_html(
            original_html=original_html,
            polished_html=polished_html,
            protected_numbers=protection.tokens,
        ),
    )

    saved_html = run.content_html
    saved_seo = dict(run.seo_json or {})
    run.content_html = polished_html
    run.seo_json = {
        **saved_seo,
        'title': new_title[:200],
        'excerpt': new_excerpt[:300],
    }
    try:
        qa = run_quality_gates(run, get_autopublish_settings())
        if qa.critical_errors > 0:
            errors.append(f'QA پس از پولیش: {qa.critical_errors} خطای بحرانی')
            errors.extend(qa.failure_reasons[:5])
    finally:
        run.content_html = saved_html
        run.seo_json = saved_seo

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


def _generation() -> dict[str, Any]:
    return get_feature_generation(FEATURE)


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


def _coerce_polished_texts(
    data: dict[str, Any],
    parts: list[tuple[_PlaceKind, str]],
) -> dict[int, str]:
    allowed_ids = {idx for idx, (k, c) in enumerate(parts) if k == 'text' and c.strip()}
    texts = data.get('texts')
    if not isinstance(texts, list):
        raise AIPolishError('کلید texts در JSON الزامی است.')

    polished: dict[int, str] = {}
    for item in texts:
        if not isinstance(item, dict):
            continue
        try:
            seg_id = int(item.get('id'))
        except (TypeError, ValueError):
            continue
        if seg_id not in allowed_ids:
            raise AIPolishError(f'segment id نامعتبر: {seg_id}')
        polished[seg_id] = str(item.get('text') or '')

    if not polished:
        raise AIPolishError('هیچ segment متنی از AI برنگشت.')
    if set(polished.keys()) != allowed_ids:
        missing = allowed_ids - set(polished.keys())
        raise AIPolishError(f'{len(missing)} segment متنی در پاسخ AI نیست.')

    return polished


def polish_market_article_run(run: MarketArticleRun) -> PolishResult:
    """
    پولیش محتوا با AI؛ فقط متن و SEO — markup ثابت می‌ماند.
    خروجی بدون اعتبارسنجی هرگز جایگزین نمی‌شود.
    """
    original_html = run.content_html or ''
    seo = dict(run.seo_json or {})
    original_title = str(seo.get('title') or '').strip()
    original_excerpt = str(seo.get('excerpt') or '').strip()

    parts = split_html_parts(original_html)
    segments = text_segment_payload(parts)

    system = (
        'تو ویراستار حرفه‌ای مقالات تحلیل بازار املاک ایران هستی. '
        'فقط JSON برگردان با کلیدهای: title, excerpt, texts (آرایه {id, text}). '
        'فقط فیلد text هر segment را ویرایش کن — id را عوض نکن. '
        'هرگز HTML، تگ، src، href، class، id یا جدول برنگردان. '
        'اعداد، قیمت‌ها، درصدها و آمار را در هر segment دقیقاً حفظ کن. '
        'لحن مناسب مشاوران املاک؛ روان؛ بدون تکرار؛ مقدمه و نتیجه‌گیری بهتر.'
    )
    user = json.dumps(
        {
            'title': original_title,
            'excerpt': original_excerpt,
            'texts': segments,
            'rules': 'Do not invent numbers. Do not remove statistical tokens.',
        },
        ensure_ascii=False,
    )

    raw, provider, model, latency_ms = _call_llm(system, user)
    data = _parse_polish_json(raw)

    new_title = str(data.get('title') or original_title).strip()
    new_excerpt = str(data.get('excerpt') or original_excerpt).strip()
    polished_map = _coerce_polished_texts(data, parts)
    new_html = apply_polished_texts(parts, polished_map)

    validation_errors = validate_polished_article(
        run,
        original_html=original_html,
        polished_html=new_html,
        original_title=original_title,
        original_excerpt=original_excerpt,
        new_title=new_title,
        new_excerpt=new_excerpt,
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
        'text_segments': len(segments),
        'validation_errors': [],
    }
    return PolishResult(applied=True, provider=provider, model=model, latency_ms=latency_ms, report=report)
