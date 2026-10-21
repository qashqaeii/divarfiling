"""پولیش هوش مصنوعی متن مقاله سیستماتیک — پیش از انتشار."""
from __future__ import annotations

import json
import logging
import re
import time
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

BATCH_MAX_SEGMENTS = 5
BATCH_MAX_CHARS = 2800
BATCH_MAX_ATTEMPTS = 3
SEO_MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.5

_POLISH_STATE_KEY = 'autopublish_polish_state'

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
_TRAILING_COMMA_RE = re.compile(r',\s*([}\]])')


class AIPolishError(Exception):
    """خطای غیرقابل‌بازیابی — اعتبارسنجی خروجی."""


class AIPolishRecoverableError(Exception):
    """خطای موقت provider — تلاش مجدد مجاز است."""


class AIPolishJsonError(AIPolishRecoverableError):
    """JSON نامعتبر یا ناقص — repair/retry."""


@dataclass
class PolishResult:
    applied: bool
    provider: str
    model: str
    latency_ms: int
    report: dict[str, Any]


@dataclass
class StatisticalProtection:
    tokens: list[str] = field(default_factory=list)

    def all_present_in(self, *blobs: str) -> list[str]:
        haystack = '\n'.join(blobs)
        return [t for t in self.tokens if t and t not in haystack]


def split_html_parts(html: str) -> list[tuple[_PlaceKind, str]]:
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


def batch_text_segments(segments: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """دسته‌بندی segmentها برای پاسخ JSON کوچک‌تر."""
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    char_count = 0
    for seg in segments:
        text = str(seg.get('text') or '')
        seg_len = len(text)
        if current and (
            len(current) >= BATCH_MAX_SEGMENTS
            or char_count + seg_len > BATCH_MAX_CHARS
        ):
            batches.append(current)
            current = []
            char_count = 0
        current.append(seg)
        char_count += seg_len
    if current:
        batches.append(current)
    return batches


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


def _locked_attributes(html: str) -> list[tuple[str, str]]:
    locked: list[tuple[str, str]] = []
    for match in _LOCKED_ATTR_RE.finditer(html or ''):
        attr = match.group(1).lower()
        value = match.group(3) if match.group(3) is not None else (match.group(4) or '')
        locked.append((attr, value))
    return locked


def _chart_asset_srcs(html: str) -> set[str]:
    srcs = set(_IMG_SRC_RE.findall(html or ''))
    return {s for s in srcs if _CHART_SRC_HINT.search(s)}


def validate_markup_unchanged(original_html: str, candidate_html: str) -> list[str]:
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

    if _table_counts(original_html) != _table_counts(candidate_html):
        errors.append('ساختار جدول (table/tr/cell) تغییر کرده است.')

    if _chart_asset_srcs(original_html) != _chart_asset_srcs(candidate_html):
        errors.append('src نمودار/دارایی chart تغییر کرده است.')

    if sorted(_locked_attributes(original_html)) != sorted(_locked_attributes(candidate_html)):
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


def validate_segment_numbers(original: str, polished: str, protection: StatisticalProtection) -> list[str]:
    missing = [t for t in protection.tokens if t in original and t not in polished]
    if missing:
        return [f'اعداد segment حذف شده: {len(missing)}']
    return []


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


def _extract_outer_json_object(text: str) -> str:
    start = text.find('{')
    if start < 0:
        return text.strip()
    depth = 0
    in_str = False
    escape = False
    quote = ''
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == quote:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:].strip()


def repair_json_text(text: str) -> str:
    """ترمیم محدود و امن — بدون اجرای کد."""
    cleaned = _JSON_FENCE_RE.sub('', (text or '').strip()).strip()
    cleaned = _extract_outer_json_object(cleaned)
    cleaned = _TRAILING_COMMA_RE.sub(r'\1', cleaned)
    return cleaned


def parse_polish_json(raw: str) -> dict[str, Any]:
    """json.loads + repair محدود؛ خطا → AIPolishJsonError (recoverable)."""
    attempts = [(raw or '').strip(), repair_json_text(raw or '')]
    last_exc: json.JSONDecodeError | None = None
    for candidate in attempts:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_exc = exc
            continue
        if not isinstance(data, dict):
            raise AIPolishError('پاسخ AI باید شیء JSON باشد.')
        return data
    raise AIPolishJsonError(f'پاسخ AI JSON معتبر نیست: {last_exc}')


def _generation() -> dict[str, Any]:
    gen = get_feature_generation(FEATURE)
    if int(gen.get('max_tokens', 0)) < 4000:
        gen = {**gen, 'max_tokens': max(4000, int(gen.get('max_tokens', 1200)))}
    return gen


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


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(12.0, BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1))))


def _coerce_batch_texts(
    data: dict[str, Any],
    allowed_ids: set[int],
) -> dict[int, str]:
    texts = data.get('texts')
    if not isinstance(texts, list):
        raise AIPolishJsonError('کلید texts در JSON الزامی است.')

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

    if set(polished.keys()) != allowed_ids:
        missing = allowed_ids - set(polished.keys())
        raise AIPolishJsonError(f'{len(missing)} segment در پاسخ AI نیست (پاسخ ناقص).')
    return polished


def _load_polish_state(run: MarketArticleRun) -> dict[str, Any]:
    chart = run.chart_assets if isinstance(run.chart_assets, dict) else {}
    state = chart.get(_POLISH_STATE_KEY)
    return dict(state) if isinstance(state, dict) else {}


def _save_polish_state(run: MarketArticleRun, state: dict[str, Any]) -> None:
    chart = dict(run.chart_assets or {})
    chart[_POLISH_STATE_KEY] = state
    run.chart_assets = chart
    run.save(update_fields=['chart_assets', 'updated_at'])


def _clear_polish_state(run: MarketArticleRun) -> None:
    chart = dict(run.chart_assets or {})
    chart.pop(_POLISH_STATE_KEY, None)
    run.chart_assets = chart
    run.save(update_fields=['chart_assets', 'updated_at'])


def _polish_seo(
    *,
    original_title: str,
    original_excerpt: str,
    protection: StatisticalProtection,
) -> tuple[str, str, str, str, int, list[dict[str, Any]]]:
    system = (
        'ویراستار SEO فارسی. فقط JSON: {"title":"...","excerpt":"..."}. '
        'اعداد و آمار را عیناً حفظ کن. HTML برنگردان.'
    )
    user = json.dumps(
        {'title': original_title, 'excerpt': original_excerpt},
        ensure_ascii=False,
    )
    attempts_log: list[dict[str, Any]] = []
    last_error = ''
    for attempt in range(1, SEO_MAX_ATTEMPTS + 1):
        try:
            raw, provider, model, latency = _call_llm(system, user)
            data = parse_polish_json(raw)
            title = str(data.get('title') or original_title).strip()
            excerpt = str(data.get('excerpt') or original_excerpt).strip()
            seo_errors = validate_seo_fields(
                original_title=original_title,
                original_excerpt=original_excerpt,
                new_title=title,
                new_excerpt=excerpt,
                protection=protection,
            )
            if seo_errors:
                raise AIPolishError('; '.join(seo_errors))
            attempts_log.append({'phase': 'seo', 'attempt': attempt, 'status': 'ok'})
            return title, excerpt, provider, model, latency, attempts_log
        except (AIPolishJsonError, AIPolishRecoverableError) as exc:
            last_error = str(exc)
            attempts_log.append({'phase': 'seo', 'attempt': attempt, 'status': 'retry', 'error': last_error})
            _sleep_backoff(attempt)
        except AIPolishError:
            raise
    raise AIPolishJsonError(last_error or 'SEO polish failed')


def _polish_text_batch(
    batch_index: int,
    batch: list[dict[str, Any]],
    *,
    protection: StatisticalProtection,
) -> tuple[dict[int, str], str, str, int, list[dict[str, Any]]]:
    allowed_ids = {int(s['id']) for s in batch}
    originals = {int(s['id']): str(s['text']) for s in batch}
    system = (
        'ویراستار متن مقاله املاک ایران. فقط JSON: {"texts":[{"id":NUMBER,"text":"..."}]}. '
        'فقط idهای درخواستی را برگردان. اعداد/قیمت/درصد را حفظ کن. HTML برنگردان.'
    )
    user = json.dumps({'texts': batch}, ensure_ascii=False)
    attempts_log: list[dict[str, Any]] = []
    last_error = ''
    for attempt in range(1, BATCH_MAX_ATTEMPTS + 1):
        try:
            raw, provider, model, latency = _call_llm(system, user)
            data = parse_polish_json(raw)
            polished = _coerce_batch_texts(data, allowed_ids)
            for seg_id, new_text in polished.items():
                seg_errors = validate_segment_numbers(
                    originals[seg_id],
                    new_text,
                    protection,
                )
                if seg_errors:
                    raise AIPolishError('; '.join(seg_errors))
            attempts_log.append({
                'phase': 'batch',
                'batch_index': batch_index,
                'attempt': attempt,
                'status': 'ok',
                'segment_ids': sorted(allowed_ids),
            })
            return polished, provider, model, latency, attempts_log
        except (AIPolishJsonError, AIPolishRecoverableError) as exc:
            last_error = str(exc)
            attempts_log.append({
                'phase': 'batch',
                'batch_index': batch_index,
                'attempt': attempt,
                'status': 'retry',
                'error': last_error,
            })
            _sleep_backoff(attempt)
        except AIPolishError:
            raise
    raise AIPolishJsonError(last_error or f'batch {batch_index} failed')


def polish_market_article_run(
    run: MarketArticleRun,
    *,
    resume: bool = True,
) -> PolishResult:
    """
    پولیش مرحله‌ای؛ پیشرفت در chart_assets ذخیره می‌شود (Resume بدون ساخت مجدد نقشه).
    """
    original_html = run.content_html or ''
    seo = dict(run.seo_json or {})
    original_title = str(seo.get('title') or '').strip()
    original_excerpt = str(seo.get('excerpt') or '').strip()

    parts = split_html_parts(original_html)
    segments = text_segment_payload(parts)
    batches = batch_text_segments(segments)
    protection = collect_statistical_protection(
        run,
        title=original_title,
        excerpt=original_excerpt,
        html=original_html,
    )

    state = _load_polish_state(run) if resume else {}
    polished_map: dict[int, str] = {
        int(k): v for k, v in (state.get('polished_by_id') or {}).items()
    }
    completed_batches = set(state.get('completed_batches') or [])
    new_title = str(state.get('title') or original_title)
    new_excerpt = str(state.get('excerpt') or original_excerpt)
    seo_done = bool(state.get('seo_done'))

    batch_logs: list[dict[str, Any]] = list(state.get('batch_logs') or [])
    provider = str(state.get('provider') or '')
    model = str(state.get('model') or '')
    total_latency = int(state.get('latency_ms') or 0)

    if not seo_done:
        title, excerpt, provider, model, latency, logs = _polish_seo(
            original_title=original_title,
            original_excerpt=original_excerpt,
            protection=protection,
        )
        new_title, new_excerpt = title, excerpt
        seo_done = True
        batch_logs.extend(logs)
        total_latency += latency
        _save_polish_state(
            run,
            {
                'seo_done': True,
                'title': new_title,
                'excerpt': new_excerpt,
                'polished_by_id': polished_map,
                'completed_batches': sorted(completed_batches),
                'batch_logs': batch_logs,
                'provider': provider,
                'model': model,
                'latency_ms': total_latency,
            },
        )

    for batch_index, batch in enumerate(batches):
        if batch_index in completed_batches:
            continue
        polished_batch, provider, model, latency, logs = _polish_text_batch(
            batch_index,
            batch,
            protection=protection,
        )
        polished_map.update(polished_batch)
        completed_batches.add(batch_index)
        batch_logs.extend(logs)
        total_latency += latency
        _save_polish_state(
            run,
            {
                'seo_done': True,
                'title': new_title,
                'excerpt': new_excerpt,
                'polished_by_id': polished_map,
                'completed_batches': sorted(completed_batches),
                'batch_logs': batch_logs,
                'provider': provider,
                'model': model,
                'latency_ms': total_latency,
            },
        )

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
    _clear_polish_state(run)

    report = {
        'ok': True,
        'provider': provider,
        'model': model,
        'latency_ms': total_latency,
        'text_segments': len(segments),
        'batch_count': len(batches),
        'batch_logs': batch_logs,
        'resumed': bool(state),
        'validation_errors': [],
    }
    return PolishResult(
        applied=True,
        provider=provider,
        model=model,
        latency_ms=total_latency,
        report=report,
    )
