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

BATCH_PLAN_VERSION = 2
BATCH_MAX_SEGMENTS = 2
BATCH_MAX_CHARS = 1200
_BATCH_PLANS: dict[int, dict[str, int]] = {
    1: {'max_segments': 2, 'max_chars': 1200},
    2: {'max_segments': 2, 'max_chars': 1200},
}
_NUM_SHIELD_TOKEN = '⟦DFN:{idx}⟧'
_STAT_PHRASE_RE = re.compile(
    r'[\d۰-۹]{1,3}(?:[,\،][\d۰-۹]{3})+(?:\s*(?:میلیون|میلیارد|تومان|متر(?:\s*/\s*متر)?|%|٪))?'
    r'|[\d۰-۹]+(?:\s*(?:میلیون|میلیارد))(?:\s*(?:تومان|متر(?:\s*/\s*متر)?))?'
    r'|[\d۰-۹]+(?:[\.٫][\d۰-۹]+)?\s*٪',
    re.U,
)
BATCH_MAX_ATTEMPTS = 4
SEO_MAX_ATTEMPTS = 4
SEGMENT_NUMERIC_MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.5
MAX_NUMERIC_SAFETY_FALLBACK_RATIO = 0.25
SCHEMA_SEO = 'seo'
SCHEMA_BATCH = 'batch'
_PROVIDER_SKIP_CODES = frozenset({
    'geo_blocked',
    'auth_error',
    'client_error',
    '403',
    'no_key',
})

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
_PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
_ASCII_DIGITS = '0123456789'
_DIGIT_TRANS = str.maketrans(_PERSIAN_DIGITS, _ASCII_DIGITS)


class AIPolishError(Exception):
    """خطای غیرقابل‌بازیابی — اعتبارسنجی خروجی."""


class AIPolishRecoverableError(Exception):
    """خطای موقت provider — تلاش مجدد مجاز است."""


class AIPolishNumericError(AIPolishRecoverableError):
    """حذف/تغییر عدد در segment — retry تک‌segment."""

    def __init__(
        self,
        message: str,
        *,
        segment_id: int,
        missing_tokens: list[str],
        error_type: str = 'numeric_mismatch',
    ):
        super().__init__(message)
        self.segment_id = segment_id
        self.missing_tokens = missing_tokens
        self.error_type = error_type


class AIPolishJsonError(AIPolishRecoverableError):
    """JSON نامعتبر یا ناقص — repair/retry."""

    def __init__(self, message: str, *, error_type: str = 'json_error'):
        super().__init__(message)
        self.error_type = error_type


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


def segment_is_low_value_for_ai(text: str) -> bool:
    """تیتر کوتاه یا متن کم‌ارزش — بدون فراخوانی AI."""
    t = (text or '').strip()
    if len(t) < 12:
        return True
    words = [w for w in re.split(r'\s+', t) if w]
    if len(words) <= 5 and len(t) < 72 and not re.search(r'[.!؟؛]', t):
        return True
    if len(t) < 24 and not _STAT_PHRASE_RE.search(t):
        return True
    return False


def segment_eligible_for_polish(text: str) -> bool:
    """متن‌های خیلی کوتاه یا صرفاً عددی به AI نمی‌روند."""
    t = (text or '').strip()
    if segment_is_low_value_for_ai(t):
        return False
    if len(t) < 8:
        return False
    if '<' in t or 'script' in t.lower() or 'style=' in t.lower():
        return False
    if re.fullmatch(r'[\d\s\.,،٪%\-–—:+]+', t):
        return False
    return True


def text_segment_payload(parts: list[tuple[_PlaceKind, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, (kind, content) in enumerate(parts):
        if kind == 'text' and content.strip():
            out.append({'id': idx, 'text': content})
    return out


def batch_text_segments(
    segments: list[dict[str, Any]],
    *,
    plan_version: int | None = None,
) -> list[list[dict[str, Any]]]:
    """دسته‌بندی segmentها برای پاسخ JSON کوچک‌تر."""
    version = plan_version if plan_version is not None else BATCH_PLAN_VERSION
    plan = _BATCH_PLANS.get(version, _BATCH_PLANS[BATCH_PLAN_VERSION])
    max_segments = int(plan['max_segments'])
    max_chars = int(plan['max_chars'])
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    char_count = 0
    for seg in segments:
        text = str(seg.get('text') or '')
        seg_len = len(text)
        if current and (
            len(current) >= max_segments
            or char_count + seg_len > max_chars
        ):
            batches.append(current)
            current = []
            char_count = 0
        current.append(seg)
        char_count += seg_len
    if current:
        batches.append(current)
    return batches


def shield_numeric_spans(text: str) -> tuple[str, dict[str, str]]:
    """جایگزینی عبارات آماری با placeholder داخلی ⟦DFN:n⟧."""
    if not text:
        return '', {}
    matches = list(_STAT_PHRASE_RE.finditer(text))
    if not matches:
        return text, {}
    mapping: dict[str, str] = {}
    chunks: list[str] = []
    cursor = 0
    for idx, match in enumerate(matches):
        token = _NUM_SHIELD_TOKEN.format(idx=idx)
        mapping[token] = match.group()
        chunks.append(text[cursor : match.start()])
        chunks.append(token)
        cursor = match.end()
    chunks.append(text[cursor:])
    return ''.join(chunks), mapping


def unshield_numeric_spans(text: str, mapping: dict[str, str]) -> str:
    out = text or ''
    for token, original in mapping.items():
        out = out.replace(token, original)
    return out


def validate_shield_tokens(text: str, mapping: dict[str, str]) -> list[str]:
    if not mapping:
        return []
    errors: list[str] = []
    for token in mapping:
        count = (text or '').count(token)
        if count != 1:
            errors.append(f'placeholder {token} count={count}')
    return errors


def shield_segment_for_llm(text: str) -> tuple[str, dict[str, str]]:
    return shield_numeric_spans(text)


def unshield_and_validate_segment(
    seg_id: int,
    original: str,
    llm_text: str,
    shield_map: dict[str, str],
    protection: StatisticalProtection,
) -> tuple[str, list[str]]:
    shield_errors = validate_shield_tokens(llm_text, shield_map)
    if shield_errors:
        return llm_text, [f'segment {seg_id}: shield: {"; ".join(shield_errors)}']
    restored = unshield_numeric_spans(llm_text, shield_map)
    numeric_errors = validate_segment_numbers(seg_id, original, restored, protection)
    return restored, numeric_errors


def migrate_polish_state(
    state: dict[str, Any],
    segments: list[dict[str, Any]],
    *,
    plan_version: int,
) -> dict[str, Any]:
    """سازگاری Resume — segment_id محور + نسخه batch plan."""
    migrated = dict(state)
    if not migrated.get('batch_plan_version'):
        migrated['batch_plan_version'] = plan_version if migrated.get('completed_batches') else BATCH_PLAN_VERSION
    if migrated.get('completed_segment_ids'):
        migrated['completed_segment_ids'] = [int(x) for x in migrated['completed_segment_ids']]
        return migrated
    completed_ids: set[int] = set()
    for key in migrated.get('polished_by_id') or {}:
        try:
            completed_ids.add(int(key))
        except (TypeError, ValueError):
            continue
    batches = batch_text_segments(segments, plan_version=int(migrated['batch_plan_version']))
    for batch_index in migrated.get('completed_batches') or []:
        if 0 <= int(batch_index) < len(batches):
            for seg in batches[int(batch_index)]:
                completed_ids.add(int(seg['id']))
    migrated['completed_segment_ids'] = sorted(completed_ids)
    if 'segment_outcomes' not in migrated:
        migrated['segment_outcomes'] = {}
    return migrated


def batch_segments_done(batch: list[dict[str, Any]], completed_segment_ids: set[int]) -> bool:
    ids = {int(s['id']) for s in batch}
    return ids.issubset(completed_segment_ids)


def build_polish_state_payload(
    *,
    seo_done: bool,
    title: str,
    excerpt: str,
    polished_map: dict[int, str],
    completed_batches: set[int],
    completed_segment_ids: set[int],
    batch_logs: list[dict[str, Any]],
    provider: str,
    model: str,
    latency_ms: int,
    batch_plan_version: int,
    segment_outcomes: dict[str, str],
) -> dict[str, Any]:
    return {
        'batch_plan_version': batch_plan_version,
        'seo_done': seo_done,
        'title': title,
        'excerpt': excerpt,
        'polished_by_id': polished_map,
        'completed_batches': sorted(completed_batches),
        'completed_segment_ids': sorted(completed_segment_ids),
        'segment_outcomes': segment_outcomes,
        'batch_logs': batch_logs,
        'provider': provider,
        'model': model,
        'latency_ms': latency_ms,
    }


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


def normalize_number_text(text: str) -> str:
    """یکسان‌سازی ارقام فارسی/انگلیسی و جداکننده‌ها برای مقایسه امن."""
    if not text:
        return ''
    t = text.translate(_DIGIT_TRANS)
    t = t.replace('\u200c', '').replace('\u00a0', '')
    t = t.replace('،', ',').replace('٬', ',').replace('٫', '.')
    t = t.replace('٪', '%')
    return t


def token_present_in_text(token: str, text: str) -> bool:
    nt = normalize_number_text(token).strip()
    if not nt or len(nt) < 2:
        return token in (text or '')
    return nt in normalize_number_text(text or '')


def protection_tokens_relevant_to_text(text: str, protection: StatisticalProtection) -> list[str]:
    return [t for t in protection.tokens if t and token_present_in_text(t, text)]


def extract_normalized_number_spans(text: str) -> set[str]:
    spans: set[str] = set()
    for match in _NUM_FMT_RE.findall(text or ''):
        normalized = normalize_number_text(match.strip())
        if len(normalized) >= 2:
            spans.add(normalized)
    return spans


def find_missing_numeric_tokens(
    original: str,
    polished: str,
    protection: StatisticalProtection,
) -> list[str]:
    missing: list[str] = []
    for token in protection_tokens_relevant_to_text(original, protection):
        if not token_present_in_text(token, polished):
            missing.append(token)
    return missing


def find_new_numeric_claims(original: str, polished: str) -> list[str]:
    """اعداد تازه در خروجی که در متن اصلی segment نبودند."""
    orig = extract_normalized_number_spans(original)
    new_spans = extract_normalized_number_spans(polished) - orig
    return sorted(new_spans)


def segment_numeric_issues(
    seg_id: int,
    original: str,
    polished: str,
    protection: StatisticalProtection,
) -> dict[str, Any]:
    missing = find_missing_numeric_tokens(original, polished, protection)
    invented = find_new_numeric_claims(original, polished)
    return {
        'segment_id': seg_id,
        'missing_tokens': missing,
        'invented_numbers': invented,
        'ok': not missing and not invented,
    }


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

    title_missing = find_missing_numeric_tokens(original_title or '', new_title or '', protection)
    if title_missing:
        errors.append(f'{len(title_missing)} عدد آماری از عنوان حذف شده است.')

    excerpt_missing = find_missing_numeric_tokens(original_excerpt or '', new_excerpt or '', protection)
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

    prot = StatisticalProtection(tokens=protected_numbers)
    missing_nums = find_missing_numeric_tokens(original_html, polished_html, prot)
    if missing_nums:
        errors.append(f'{len(missing_nums)} عدد آماری از بدنه HTML حذف شده است.')

    errors.extend(validate_markup_unchanged(original_html, polished_html))

    if 'mk-market' not in polished_html:
        errors.append('ساختار اصلی مقاله (mk-market) در HTML نیست.')

    return errors


def validate_segment_numbers(
    seg_id: int,
    original: str,
    polished: str,
    protection: StatisticalProtection,
) -> list[str]:
    issues = segment_numeric_issues(seg_id, original, polished, protection)
    if issues['ok']:
        return []
    parts: list[str] = []
    if issues['missing_tokens']:
        sample = ','.join(issues['missing_tokens'][:3])
        parts.append(
            f'segment {seg_id}: حذف عدد ({len(issues["missing_tokens"])}): {sample}',
        )
    if issues['invented_numbers']:
        sample = ','.join(issues['invented_numbers'][:3])
        parts.append(
            f'segment {seg_id}: عدد جدید ({len(issues["invented_numbers"])}): {sample}',
        )
    return parts


def compute_polish_coverage_metrics(
    *,
    segments: list[dict[str, Any]],
    polished_map: dict[int, str],
    originals_by_id: dict[int, str],
    batch_logs: list[dict[str, Any]],
    segment_outcomes: dict[str, str] | None = None,
) -> dict[str, Any]:
    eligible_ids = {int(s['id']) for s in segments}
    outcomes = segment_outcomes or {}
    polished_count = sum(1 for sid in eligible_ids if outcomes.get(str(sid)) == 'polished')
    unchanged_count = sum(1 for sid in eligible_ids if outcomes.get(str(sid)) == 'unchanged')
    identity_fb = sum(1 for sid in eligible_ids if outcomes.get(str(sid)) == 'identity_fallback')
    numeric_fb = sum(1 for sid in eligible_ids if outcomes.get(str(sid)) == 'numeric_safety_fallback')
    if not outcomes:
        identity_fb = sum(1 for e in batch_logs if e.get('status') == 'identity_fallback')
        numeric_fb = sum(
            1 for e in batch_logs if e.get('status') == 'numeric_safety_fallback'
        )
    changed = 0
    for seg_id in eligible_ids:
        orig = originals_by_id.get(seg_id, '')
        new = polished_map.get(seg_id, orig)
        if (new or '').strip() != (orig or '').strip():
            changed += 1
    eligible = len(eligible_ids) or 1
    fb_total = identity_fb + numeric_fb
    return {
        'eligible_segments': len(eligible_ids),
        'polished_segments': polished_count,
        'unchanged_segments': unchanged_count,
        'polished_segments_changed': changed,
        'polish_change_ratio': round(changed / eligible, 4),
        'identity_fallback_count': identity_fb,
        'numeric_safety_fallback_count': numeric_fb,
        'fallback_ratio': round(fb_total / eligible, 4),
    }


def assert_polish_coverage_acceptable(metrics: dict[str, Any]) -> None:
    eligible = int(metrics.get('eligible_segments') or 0)
    if eligible <= 0:
        return
    if metrics.get('fallback_ratio', 0) > MAX_NUMERIC_SAFETY_FALLBACK_RATIO:
        raise AIPolishError(
            f'نسبت fallback پولیش ({metrics["fallback_ratio"]}) از حد مجاز بیشتر است.',
        )
    changed = int(metrics.get('polished_segments_changed') or 0)
    fallbacks = int(metrics.get('identity_fallback_count') or 0) + int(
        metrics.get('numeric_safety_fallback_count') or 0,
    )
    if fallbacks >= eligible and changed == 0:
        raise AIPolishError('پولیش AI هیچ segment معتبری تولید نکرد (همه fallback).')


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


def normalize_parsed_payload(parsed: Any, schema: str) -> dict[str, Any]:
    if schema == SCHEMA_SEO:
        if isinstance(parsed, dict) and ('title' in parsed or 'excerpt' in parsed):
            return parsed
        raise AIPolishJsonError('قرارداد SEO نقض شد.', error_type='seo_schema_mismatch')

    if schema == SCHEMA_BATCH:
        if isinstance(parsed, list):
            return {'texts': parsed}
        if isinstance(parsed, dict):
            texts = parsed.get('texts')
            if isinstance(texts, list):
                return parsed
            for alt in ('segments', 'items', 'data', 'results'):
                alt_list = parsed.get(alt)
                if isinstance(alt_list, list):
                    return {'texts': alt_list}
            if 'id' in parsed and 'text' in parsed:
                return {'texts': [parsed]}
        raise AIPolishJsonError('کلید texts در JSON الزامی است.', error_type='missing_texts')

    raise AIPolishJsonError('schema نامعتبر', error_type='invalid_schema')


def parse_llm_response(raw: str, schema: str) -> dict[str, Any]:
    """Parse + normalize — همه خطاهای قالب‌بندی recoverable هستند."""
    stripped = (raw or '').strip()
    if not stripped:
        raise AIPolishJsonError('پاسخ AI خالی است.', error_type='empty_response')
    if stripped[0] not in '{[':
        raise AIPolishJsonError('خروجی متنی به‌جای JSON.', error_type='plain_text')

    candidates = [stripped, repair_json_text(stripped)]
    last_exc: json.JSONDecodeError | None = None
    parsed: Any = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            break
        except json.JSONDecodeError as exc:
            last_exc = exc
    if parsed is None:
        raise AIPolishJsonError(
            f'پاسخ AI JSON معتبر نیست: {last_exc}',
            error_type='json_malformed',
        )

    try:
        return normalize_parsed_payload(parsed, schema)
    except AIPolishJsonError:
        raise
    except Exception as exc:
        raise AIPolishJsonError(str(exc), error_type='schema_error') from exc


def parse_polish_json(raw: str) -> dict[str, Any]:
    return parse_llm_response(raw, SCHEMA_BATCH)


def _generation() -> dict[str, Any]:
    gen = get_feature_generation(FEATURE)
    if int(gen.get('max_tokens', 0)) < 6000:
        gen = {**gen, 'max_tokens': max(6000, int(gen.get('max_tokens', 1200)))}
    return gen


@dataclass
class LLMCallResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None


def _call_llm(
    system: str,
    user: str,
    *,
    blocked_providers: set[str] | None = None,
) -> LLMCallResult:
    generation = _generation()
    chain = get_http_provider_chain()
    blocked = blocked_providers or set()
    last_code = ''
    for provider in chain:
        if provider.name in blocked:
            continue
        try:
            result = provider.complete(
                system=system,
                user=user,
                json_mode=True,
                generation=generation,
            )
            text = (result.text or '').strip()
            if text:
                return LLMCallResult(
                    text=text,
                    provider=result.provider,
                    model=result.model,
                    latency_ms=result.latency_ms,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
        except ProviderError as exc:
            last_code = exc.code or 'provider_error'
            logger.warning('market_article_polish provider failed: %s %s', provider.name, last_code)
            if last_code in _PROVIDER_SKIP_CODES or not exc.retryable:
                blocked.add(provider.name)
            continue
    raise AIPolishRecoverableError(
        f'همه providerهای AI شکست خوردند ({last_code}).',
    )


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(12.0, BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1))))


def _coerce_batch_texts(
    data: dict[str, Any],
    allowed_ids: set[int],
) -> dict[int, str]:
    texts = data.get('texts')
    if not isinstance(texts, list):
        raise AIPolishJsonError('کلید texts در JSON الزامی است.', error_type='missing_texts')

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
        raise AIPolishJsonError(
            f'{len(missing)} segment در پاسخ AI نیست (پاسخ ناقص).',
            error_type='incomplete_ids',
        )
    return polished


def _log_attempt(
    attempts_log: list[dict[str, Any]],
    *,
    phase: str,
    status: str,
    attempt: int,
    error_type: str = '',
    error: str = '',
    batch_index: int | None = None,
    segment_count: int = 0,
    llm: LLMCallResult | None = None,
    validation: str = '',
) -> None:
    entry: dict[str, Any] = {
        'phase': phase,
        'status': status,
        'attempt': attempt,
    }
    if batch_index is not None:
        entry['batch_index'] = batch_index
    if segment_count:
        entry['segment_count'] = segment_count
    if error_type:
        entry['error_type'] = error_type
    if error:
        entry['error'] = error[:240]
    if validation:
        entry['validation'] = validation
    if llm:
        entry['provider'] = llm.provider
        entry['model'] = llm.model
        entry['latency_ms'] = llm.latency_ms
        entry['input_tokens'] = llm.input_tokens
        entry['output_tokens'] = llm.output_tokens
    attempts_log.append(entry)


def _load_polish_state(run: MarketArticleRun) -> dict[str, Any]:
    chart = run.chart_assets if isinstance(run.chart_assets, dict) else {}
    state = chart.get(_POLISH_STATE_KEY)
    return dict(state) if isinstance(state, dict) else {}


def polish_failure_snapshot(run: MarketArticleRun) -> dict[str, Any]:
    """خلاصه پیشرفت پولیش برای گزارش خطا — بدون متن مقاله."""
    state = _load_polish_state(run)
    if not state:
        return {}
    return {
        'seo_done': bool(state.get('seo_done')),
        'completed_batches': list(state.get('completed_batches') or []),
        'batch_logs': list(state.get('batch_logs') or []),
        'batch_count_done': len(state.get('completed_batches') or []),
    }


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
        'ویراستار SEO فارسی. خروجی فقط یک JSON object با دقیقاً دو کلید: title و excerpt. '
        'بدون کلید اضافه. اعداد و آمار را عیناً حفظ کن. HTML برنگردان.'
    )
    user = json.dumps(
        {'title': original_title, 'excerpt': original_excerpt},
        ensure_ascii=False,
    )
    attempts_log: list[dict[str, Any]] = []
    blocked: set[str] = set()
    last_error = ''
    last_type = 'json_error'
    for attempt in range(1, SEO_MAX_ATTEMPTS + 1):
        try:
            llm = _call_llm(system, user, blocked_providers=blocked)
            data = parse_llm_response(llm.text, SCHEMA_SEO)
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
            _log_attempt(attempts_log, phase='seo', status='ok', attempt=attempt, llm=llm, validation='passed')
            return title, excerpt, llm.provider, llm.model, llm.latency_ms, attempts_log
        except AIPolishError:
            raise
        except (AIPolishJsonError, AIPolishRecoverableError) as exc:
            last_error = str(exc)
            last_type = getattr(exc, 'error_type', 'json_error')
            _log_attempt(
                attempts_log,
                phase='seo',
                status='retry',
                attempt=attempt,
                error=last_error,
                error_type=last_type,
            )
            _sleep_backoff(attempt)
    raise AIPolishJsonError(last_error or 'SEO polish failed', error_type=last_type)


def _batch_system_prompt(id_list: list[int]) -> str:
    return (
        'ویراستار متن مقاله املاک ایران. خروجی فقط JSON object با یک کلید texts. '
        'فرمت: {"texts":[{"id":NUMBER,"text":"..."}]}. '
        f'باید دقیقاً این idها را برگردانی: {id_list}. '
        'توکن‌های ⟦DFN:n⟧ را عیناً و یک‌بار در همان متن نگه دار؛ حذف یا تغییر ممنوع. '
        'عدد جدید یا قیمت ساختگی اضافه نکن. HTML برنگردان.'
    )


def _segments_with_numeric_issues(
    polished: dict[int, str],
    originals: dict[int, str],
    allowed_ids: set[int],
    protection: StatisticalProtection,
) -> dict[int, dict[str, Any]]:
    bad: dict[int, dict[str, Any]] = {}
    for seg_id in allowed_ids:
        issue = segment_numeric_issues(seg_id, originals[seg_id], polished[seg_id], protection)
        if not issue['ok']:
            bad[seg_id] = issue
    return bad


def _polish_single_segment_numeric(
    seg_id: int,
    original_text: str,
    *,
    batch_index: int,
    protection: StatisticalProtection,
    attempts_log: list[dict[str, Any]],
    blocked: set[str],
) -> tuple[str, str, str, int]:
    shielded, shield_map = shield_segment_for_llm(original_text)
    batch = [{'id': seg_id, 'text': shielded}]
    system = _batch_system_prompt([seg_id])
    user = json.dumps({'texts': batch}, ensure_ascii=False)
    last_issue: dict[str, Any] = {}
    for attempt in range(1, SEGMENT_NUMERIC_MAX_ATTEMPTS + 1):
        try:
            llm = _call_llm(system, user, blocked_providers=blocked)
            data = parse_llm_response(llm.text, SCHEMA_BATCH)
            polished = _coerce_batch_texts(data, {seg_id})
            candidate, val_errors = unshield_and_validate_segment(
                seg_id,
                original_text,
                polished[seg_id],
                shield_map,
                protection,
            )
            if not val_errors:
                _log_attempt(
                    attempts_log,
                    phase='segment_numeric_retry',
                    status='ok',
                    attempt=attempt,
                    batch_index=batch_index,
                    segment_count=1,
                    llm=llm,
                    validation='passed',
                )
                return candidate, llm.provider, llm.model, llm.latency_ms
            last_issue = segment_numeric_issues(seg_id, original_text, candidate, protection)
            _log_attempt(
                attempts_log,
                phase='segment_numeric_retry',
                status='retry',
                attempt=attempt,
                batch_index=batch_index,
                segment_count=1,
                error_type='numeric_mismatch',
                error='; '.join(val_errors),
                llm=llm,
            )
            _sleep_backoff(attempt)
        except (AIPolishJsonError, AIPolishRecoverableError) as exc:
            _log_attempt(
                attempts_log,
                phase='segment_numeric_retry',
                status='retry',
                attempt=attempt,
                batch_index=batch_index,
                segment_count=1,
                error=str(exc),
                error_type=getattr(exc, 'error_type', 'json_error'),
            )
            _sleep_backoff(attempt)
    _log_attempt(
        attempts_log,
        phase='segment_numeric_retry',
        status='numeric_safety_fallback',
        attempt=SEGMENT_NUMERIC_MAX_ATTEMPTS,
        batch_index=batch_index,
        segment_count=1,
        error_type='numeric_mismatch',
        error=json.dumps(
            {
                'segment_id': seg_id,
                'missing_tokens': last_issue.get('missing_tokens', [])[:5],
                'invented_numbers': last_issue.get('invented_numbers', [])[:5],
            },
            ensure_ascii=False,
        ),
    )
    attempts_log[-1]['segment_id'] = seg_id
    return original_text, 'numeric_safety', 'passthrough', 0


def _apply_numeric_safety_to_batch(
    polished: dict[int, str],
    originals: dict[int, str],
    allowed_ids: set[int],
    *,
    batch_index: int,
    protection: StatisticalProtection,
    attempts_log: list[dict[str, Any]],
    blocked: set[str],
) -> tuple[dict[int, str], str, str, int]:
    result = dict(polished)
    provider, model, latency = 'arvan', '', 0
    bad = _segments_with_numeric_issues(result, originals, allowed_ids, protection)
    for seg_id, issue in bad.items():
        fixed, provider, model, seg_latency = _polish_single_segment_numeric(
            seg_id,
            originals[seg_id],
            batch_index=batch_index,
            protection=protection,
            attempts_log=attempts_log,
            blocked=blocked,
        )
        result[seg_id] = fixed
        latency += seg_latency
    return result, provider, model, latency


def _prepare_shielded_batch(
    batch: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, str]]]:
    shield_maps: dict[int, dict[str, str]] = {}
    shielded_batch: list[dict[str, Any]] = []
    for seg in batch:
        seg_id = int(seg['id'])
        text = str(seg.get('text') or '')
        shielded, shield_map = shield_segment_for_llm(text)
        shield_maps[seg_id] = shield_map
        shielded_batch.append({'id': seg_id, 'text': shielded})
    return shielded_batch, shield_maps


def _record_segment_outcomes(
    segment_outcomes: dict[str, str],
    originals: dict[int, str],
    final: dict[int, str],
    *,
    fallback_kinds: dict[int, str],
) -> None:
    for seg_id, original in originals.items():
        new_text = final.get(seg_id, original)
        key = str(seg_id)
        kind = fallback_kinds.get(seg_id)
        if kind:
            segment_outcomes[key] = kind
        elif (new_text or '').strip() == (original or '').strip():
            segment_outcomes[key] = 'unchanged'
        else:
            segment_outcomes[key] = 'polished'


def _polish_text_batch(
    batch_index: int,
    batch: list[dict[str, Any]],
    *,
    protection: StatisticalProtection,
    segment_outcomes: dict[str, str],
) -> tuple[dict[int, str], str, str, int, list[dict[str, Any]]]:
    allowed_ids = {int(s['id']) for s in batch}
    originals = {int(s['id']): str(s['text']) for s in batch}
    id_list = sorted(allowed_ids)
    shielded_batch, shield_maps = _prepare_shielded_batch(batch)
    system = _batch_system_prompt(id_list)
    user = json.dumps({'texts': shielded_batch}, ensure_ascii=False)
    attempts_log: list[dict[str, Any]] = []
    blocked: set[str] = set()
    last_error = ''
    last_type = 'json_error'
    for attempt in range(1, BATCH_MAX_ATTEMPTS + 1):
        try:
            llm = _call_llm(system, user, blocked_providers=blocked)
            data = parse_llm_response(llm.text, SCHEMA_BATCH)
            polished_raw = _coerce_batch_texts(data, allowed_ids)
            final: dict[int, str] = {}
            bad_ids: list[int] = []
            for seg_id in allowed_ids:
                restored, errors = unshield_and_validate_segment(
                    seg_id,
                    originals[seg_id],
                    polished_raw[seg_id],
                    shield_maps[seg_id],
                    protection,
                )
                if errors:
                    bad_ids.append(seg_id)
                    _log_attempt(
                        attempts_log,
                        phase='batch',
                        status='segment_retry',
                        attempt=attempt,
                        batch_index=batch_index,
                        segment_count=1,
                        error='; '.join(errors),
                        error_type='numeric_mismatch',
                        llm=llm,
                    )
                else:
                    final[seg_id] = restored
            extra_latency = 0
            provider, model = llm.provider, llm.model
            fallback_kinds: dict[int, str] = {}
            for seg_id in bad_ids:
                fixed, provider, model, seg_latency = _polish_single_segment_numeric(
                    seg_id,
                    originals[seg_id],
                    batch_index=batch_index,
                    protection=protection,
                    attempts_log=attempts_log,
                    blocked=blocked,
                )
                final[seg_id] = fixed
                extra_latency += seg_latency
                if (fixed or '').strip() == (originals[seg_id] or '').strip():
                    fallback_kinds[seg_id] = 'numeric_safety_fallback'
            _record_segment_outcomes(
                segment_outcomes,
                originals,
                final,
                fallback_kinds=fallback_kinds,
            )
            validation = 'passed' if not bad_ids else 'numeric_safety_applied'
            _log_attempt(
                attempts_log,
                phase='batch',
                status='ok',
                attempt=attempt,
                batch_index=batch_index,
                segment_count=len(batch),
                llm=llm,
                validation=validation,
            )
            return final, provider, model, llm.latency_ms + extra_latency, attempts_log
        except (AIPolishJsonError, AIPolishRecoverableError) as exc:
            last_error = str(exc)
            last_type = getattr(exc, 'error_type', 'json_error')
            _log_attempt(
                attempts_log,
                phase='batch',
                status='retry',
                attempt=attempt,
                batch_index=batch_index,
                segment_count=len(batch),
                error=last_error,
                error_type=last_type,
            )
            _sleep_backoff(attempt)

    _log_attempt(
        attempts_log,
        phase='batch',
        status='identity_fallback',
        attempt=BATCH_MAX_ATTEMPTS,
        batch_index=batch_index,
        segment_count=len(batch),
        error_type=last_type,
        error=last_error,
    )
    for seg_id, original in originals.items():
        segment_outcomes[str(seg_id)] = 'identity_fallback'
    return originals, 'identity', 'passthrough', 0, attempts_log


def repair_polished_map_numeric_safety(
    segments: list[dict[str, Any]],
    originals_by_id: dict[int, str],
    polished_map: dict[int, str],
    *,
    protection: StatisticalProtection,
    attempts_log: list[dict[str, Any]],
) -> dict[int, str]:
    """پس از Resume — segmentهای مشکل‌دار عددی را تک‌به‌تک اصلاح می‌کند."""
    blocked: set[str] = set()
    updated = dict(polished_map)
    for seg in segments:
        seg_id = int(seg['id'])
        original = originals_by_id.get(seg_id, str(seg.get('text') or ''))
        current = updated.get(seg_id, original)
        issue = segment_numeric_issues(seg_id, original, current, protection)
        if issue['ok']:
            continue
        fixed, _, _, _ = _polish_single_segment_numeric(
            seg_id,
            original,
            batch_index=-1,
            protection=protection,
            attempts_log=attempts_log,
            blocked=blocked,
        )
        updated[seg_id] = fixed
    return updated


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
    all_segments = text_segment_payload(parts)
    auto_passthrough: dict[int, str] = {}
    segments: list[dict[str, Any]] = []
    for seg in all_segments:
        if segment_eligible_for_polish(str(seg.get('text') or '')):
            segments.append(seg)
        else:
            auto_passthrough[int(seg['id'])] = str(seg['text'])
    originals_by_id = {int(s['id']): str(s['text']) for s in all_segments}
    protection = collect_statistical_protection(
        run,
        title=original_title,
        excerpt=original_excerpt,
        html=original_html,
    )

    state = _load_polish_state(run) if resume else {}
    plan_version = int(state.get('batch_plan_version') or BATCH_PLAN_VERSION)
    if state.get('completed_batches') and not state.get('batch_plan_version'):
        plan_version = 1
    state = migrate_polish_state(state, segments, plan_version=plan_version) if state else state
    batches = batch_text_segments(segments, plan_version=plan_version)

    polished_map: dict[int, str] = {
        int(k): v for k, v in (state.get('polished_by_id') or {}).items()
    }
    polished_map.update(auto_passthrough)
    completed_batches = {int(x) for x in (state.get('completed_batches') or [])}
    completed_segment_ids = {int(x) for x in (state.get('completed_segment_ids') or [])}
    segment_outcomes: dict[str, str] = dict(state.get('segment_outcomes') or {})
    for seg_id, text in auto_passthrough.items():
        segment_outcomes.setdefault(str(seg_id), 'unchanged')
    new_title = str(state.get('title') or original_title)
    new_excerpt = str(state.get('excerpt') or original_excerpt)
    seo_done = bool(state.get('seo_done'))

    batch_logs: list[dict[str, Any]] = list(state.get('batch_logs') or [])
    provider = str(state.get('provider') or '')
    model = str(state.get('model') or '')
    total_latency = int(state.get('latency_ms') or 0)

    def _persist_state() -> None:
        _save_polish_state(
            run,
            build_polish_state_payload(
                seo_done=seo_done,
                title=new_title,
                excerpt=new_excerpt,
                polished_map=polished_map,
                completed_batches=completed_batches,
                completed_segment_ids=completed_segment_ids,
                batch_logs=batch_logs,
                provider=provider,
                model=model,
                latency_ms=total_latency,
                batch_plan_version=plan_version,
                segment_outcomes=segment_outcomes,
            ),
        )

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
        _persist_state()

    for batch_index, batch in enumerate(batches):
        if batch_segments_done(batch, completed_segment_ids):
            completed_batches.add(batch_index)
            continue
        pending_batch = [
            s for s in batch if int(s['id']) not in completed_segment_ids
        ]
        if not pending_batch:
            completed_batches.add(batch_index)
            continue
        polished_batch, provider, model, latency, logs = _polish_text_batch(
            batch_index,
            pending_batch,
            protection=protection,
            segment_outcomes=segment_outcomes,
        )
        polished_map.update(polished_batch)
        for seg in pending_batch:
            completed_segment_ids.add(int(seg['id']))
        completed_batches.add(batch_index)
        batch_logs.extend(logs)
        total_latency += latency
        _persist_state()

    repaired = repair_polished_map_numeric_safety(
        segments,
        originals_by_id,
        polished_map,
        protection=protection,
        attempts_log=batch_logs,
    )
    if repaired != polished_map:
        polished_map = repaired
        _persist_state()

    coverage = compute_polish_coverage_metrics(
        segments=segments,
        polished_map=polished_map,
        originals_by_id=originals_by_id,
        batch_logs=batch_logs,
        segment_outcomes=segment_outcomes,
    )
    assert_polish_coverage_acceptable(coverage)

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
        **coverage,
    }
    return PolishResult(
        applied=True,
        provider=provider,
        model=model,
        latency_ms=total_latency,
        report=report,
    )
