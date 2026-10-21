"""Quality Gateهای انتشار خودکار مقالات سیستماتیک."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from blog.models import MarketArticleRun, Post
from blog.services.market_article_analyze import _PHONE_RE, _TOKEN_RE
from blog.services.market_article_autopublish_config import AutoPublishSettings
from blog.services.market_article_number_utils import extract_report_numbers, normalize_number_text
from blog.services.market_article_numeric_truth import (
    assess_data_consistency,
    build_market_truth_registry,
    find_unverified_public_claims,
)
from blog.services.market_article_pipeline import get_existing_link

_H1_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.I | re.S)
_IMG_RE = re.compile(r'<img[^>]+>', re.I)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_NUM_FMT_RE = re.compile(r'[\d۰-۹]{1,3}(?:[,\،][\d۰-۹]{3})+(?:\s*(?:میلیون|میلیارد|تومان|متر))?', re.U)
_STAT_CLAIM_RE = re.compile(
    r'[\d۰-۹]{1,3}(?:[,\،][\d۰-۹]{3})+(?:\s*(?:میلیون|میلیارد|تومان|متر(?:\s*/\s*متر)?|%|٪))?'
    r'|[\d۰-۹]+(?:\s*(?:میلیون|میلیارد))(?:\s*(?:تومان|متر(?:\s*/\s*متر)?))?'
    r'|[\d۰-۹]+(?:[\.٫][\d۰-۹]+)?\s*٪',
    re.U,
)
_SCRIPT_STYLE_RE = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.I | re.S)
_ATTR_VALUE_RE = re.compile(
    r'\b(src|href|class|id|data-[a-z0-9_-]+)=("([^"]*)"|\'([^\']*)\')',
    re.I,
)
_PLACEHOLDER_IMG_RE = re.compile(r'placeholder|via\.placeholder|dummyimage|data:image/gif', re.I)

PRIVACY_PATTERNS = [
    _PHONE_RE,
    re.compile(r'\btoken[s]?\b', re.I),
    re.compile(r'divar\.ir/v/[A-Za-z0-9_-]+', re.I),
    re.compile(r'share[_-]?token', re.I),
]

# فاز پولیش: ادعای عددی در QA نهایی + remediation بررسی می‌شود.
QA_POLISH_PHASE_EXCLUDE = frozenset({'data_numeric_claims'})

REQUIRED_SECTION_IDS = (
    'executive-summary',
    'market-kpis',
    'market-status',
    'price-per-sqm',
    'faq',
    'verdict',
)


@dataclass
class QACheck:
    key: str
    category: str
    passed: bool
    critical: bool
    message: str
    score_delta: float = 0.0


@dataclass
class QAReport:
    checks: list[QACheck] = field(default_factory=list)
    data_score: float = 0.0
    content_score: float = 0.0
    seo_score: float = 0.0
    media_score: float = 0.0
    technical_score: float = 0.0
    total_score: float = 0.0
    critical_errors: int = 0
    failure_reasons: list[str] = field(default_factory=list)

    def add(self, check: QACheck) -> None:
        self.checks.append(check)
        if check.critical and not check.passed:
            self.critical_errors += 1
            self.failure_reasons.append(check.message)

    @property
    def passed(self) -> bool:
        return self.critical_errors == 0 and self.total_score >= 0


def public_content_surfaces(run: MarketArticleRun) -> str:
    """متن و HTML منتشرشده — بدون attributeهای URL/CSS."""
    html = run.content_html or ''
    html = _SCRIPT_STYLE_RE.sub(' ', html)
    html = _ATTR_VALUE_RE.sub(' ', html)
    html = re.sub(r'<[^>]+>', ' ', html)
    seo = run.seo_json if isinstance(run.seo_json, dict) else {}
    parts = [
        html,
        str(seo.get('title') or ''),
        str(seo.get('excerpt') or ''),
        str(seo.get('json_ld') or ''),
    ]
    return '\n'.join(parts)


def build_snapshot_allowed_values(
    inner_report: dict,
    metrics: dict,
    run: MarketArticleRun,
) -> set[str]:
    allowed: set[str] = set()
    for fmt in extract_report_numbers(inner_report):
        norm = normalize_number_text(fmt)
        if len(norm) >= 2:
            allowed.add(norm)
    for key in ('valid_count', 'raw_count', 'median_price', 'median_area'):
        val = metrics.get(key)
        if val is not None and val != '':
            allowed.add(normalize_number_text(str(val)))
    if run.valid_count:
        allowed.add(normalize_number_text(str(run.valid_count)))
    if run.raw_count:
        allowed.add(normalize_number_text(str(run.raw_count)))
    return {a for a in allowed if a}


def is_significant_stat_claim(raw: str, normalized: str) -> bool:
    if any(u in raw for u in ('میلیون', 'میلیارد', 'تومان', 'متر', '%', '٪')):
        return True
    digits = re.sub(r'[^\d]', '', normalized)
    return len(digits) >= 6


def number_allowed_in_public(normalized: str, allowed: set[str]) -> bool:
    if normalized in allowed:
        return True
    for candidate in allowed:
        if len(normalized) >= 4 and (normalized in candidate or candidate in normalized):
            return True
    return False


def find_invented_public_claims(public_text: str, allowed: set[str]) -> list[str]:
    """سازگاری با تست‌های قدیمی — ترجیحاً از find_unverified_numeric_claims استفاده کنید."""
    invented: list[str] = []
    for raw in _STAT_CLAIM_RE.findall(public_text or ''):
        norm = normalize_number_text(raw.strip())
        if not norm or not is_significant_stat_claim(raw, norm):
            continue
        if not number_allowed_in_public(norm, allowed):
            invented.append(raw.strip())
    return list(dict.fromkeys(invented))


def find_unverified_numeric_claims(run: MarketArticleRun) -> list[str]:
    registry = build_market_truth_registry(run)
    public_text = public_content_surfaces(run)
    return find_unverified_public_claims(
        public_text,
        registry,
        is_significant=is_significant_stat_claim,
        stat_claim_re=_STAT_CLAIM_RE,
    )


_extract_report_numbers = extract_report_numbers


def _check_data_quality(run: MarketArticleRun, settings: AutoPublishSettings, report: QAReport) -> None:
    valid = int(run.valid_count or 0)
    raw = int(run.raw_count or 0) or valid
    ratio = (valid / raw) if raw else 0.0
    pct = run.quality_pct or (ratio * 100)

    ok_records = valid >= settings.min_records
    report.add(QACheck(
        'data_min_records', 'data', ok_records, True,
        f'{"✓" if ok_records else "✗"} {valid} رکورد معتبر (حداقل {settings.min_records})',
        score_delta=15.0 if ok_records else 0.0,
    ))

    ok_ratio = ratio >= settings.min_valid_ratio
    report.add(QACheck(
        'data_valid_ratio', 'data', ok_ratio, True,
        f'{"✓" if ok_ratio else "✗"} کیفیت داده {pct:.1f}٪',
        score_delta=15.0 if ok_ratio else 0.0,
    ))

    insights = []
    blob = run.report_json or {}
    inner = blob.get('report') if isinstance(blob.get('report'), dict) else blob
    if isinstance(inner, dict):
        insights = inner.get('insights') or []
    ok_insights = len(insights) >= settings.min_insights
    report.add(QACheck(
        'data_insights', 'data', ok_insights, False,
        f'{"✓" if ok_insights else "✗"} {len(insights)} Insight (حداقل {settings.min_insights})',
        score_delta=10.0 if ok_insights else 3.0,
    ))


def _check_data_consistency(run: MarketArticleRun, report: QAReport) -> None:
    issues = assess_data_consistency(run)
    ok = not issues
    report.add(QACheck(
        'data_consistency', 'data', ok, True,
        '✓ داده‌های بازار سازگار است' if ok else f'✗ {issues[0]}',
        score_delta=8.0 if ok else 0.0,
    ))


def _check_numeric_claims(run: MarketArticleRun, report: QAReport) -> None:
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    inner_report = blob.get('report') if isinstance(blob.get('report'), dict) else {}
    public_text = public_content_surfaces(run)
    invented = find_unverified_numeric_claims(run)
    ok_claims = len(invented) == 0
    detail = '✓ ادعاهای عددی عمومی با محاسبات بازار تأیید شد'
    if not ok_claims:
        sample = '، '.join(invented[:3])
        detail = f'✗ {len(invented)} ادعای عددی غیرقابل‌تأیید ({sample})'
    report.add(QACheck(
        'data_numeric_claims', 'data', ok_claims, True,
        detail,
        score_delta=10.0 if ok_claims else 0.0,
    ))

    headline_fmts = [f for f in extract_report_numbers(inner_report) if len(f) >= 4][:8]
    mentioned = 0
    norm_public = normalize_number_text(public_text)
    for fmt in headline_fmts:
        if normalize_number_text(fmt) in norm_public or fmt in public_text:
            mentioned += 1
    coverage_ok = headline_fmts and mentioned >= min(2, len(headline_fmts))
    report.add(QACheck(
        'data_numeric_snapshot_coverage', 'data', coverage_ok, False,
        f'{"✓" if coverage_ok else "—"} پوشش KPIهای Snapshot در متن ({mentioned}/{len(headline_fmts) or 0})',
        score_delta=4.0 if coverage_ok else 1.0,
    ))


def _check_content_quality(run: MarketArticleRun, report: QAReport) -> None:
    content = run.content_html or ''
    text_only = re.sub(r'<[^>]+>', ' ', content)
    words = [w for w in text_only.split() if len(w) > 1]

    ok_length = len(words) >= 400
    report.add(QACheck(
        'content_length', 'content', ok_length, True,
        f'{"✓" if ok_length else "✗"} طول متن ({len(words)} کلمه)',
        score_delta=10.0 if ok_length else 0.0,
    ))

    sections_found = sum(
        1 for section_id in REQUIRED_SECTION_IDS
        if f'id="{section_id}"' in content or f"id='{section_id}'" in content
    )
    section_blocks = len(re.findall(r'\bmk-market-section\b', content))
    ok_structure = sections_found >= 4 and section_blocks >= 6
    report.add(QACheck(
        'content_structure', 'content', ok_structure, False,
        f'{"✓" if ok_structure else "✗"} ساختار مقاله ({sections_found} بخش اصلی، {section_blocks} بلاک)',
        score_delta=8.0 if ok_structure else 2.0,
    ))

    ok_intro = 'id="executive-summary"' in content or 'mk-market-section' in content
    report.add(QACheck(
        'content_intro', 'content', ok_intro, False,
        '✓ مقدمه/خلاصه اجرایی' if ok_intro else '✗ مقدمه ناقص',
        score_delta=7.0 if ok_intro else 0.0,
    ))


def _check_seo(run: MarketArticleRun, report: QAReport) -> None:
    seo = run.seo_json or {}
    title = (seo.get('title') or '').strip()
    excerpt = (seo.get('excerpt') or '').strip()
    slug = (seo.get('slug') or run.market_key or '').strip()

    ok_title = bool(title) and len(title) >= 20
    report.add(QACheck(
        'seo_title', 'seo', ok_title, True,
        '✓ عنوان معتبر' if ok_title else '✗ عنوان نامعتبر',
        score_delta=5.0 if ok_title else 0.0,
    ))

    dup_title = Post.objects.filter(title=title).exclude(pk=run.post_id).exists() if title else False
    report.add(QACheck(
        'seo_unique_title', 'seo', not dup_title, True,
        '✓ عنوان یکتا' if not dup_title else '✗ عنوان تکراری',
        score_delta=5.0 if not dup_title else 0.0,
    ))

    dup_meta = Post.objects.filter(excerpt=excerpt).exclude(pk=run.post_id).exists() if len(excerpt) > 20 else False
    report.add(QACheck(
        'seo_unique_meta', 'seo', not dup_meta, True,
        '✓ Meta Description یکتا' if not dup_meta else '✗ Meta Description تکراری',
        score_delta=4.0 if not dup_meta else 0.0,
    ))

    h1_matches = _H1_RE.findall(run.content_html or '')
    ok_h1 = len(h1_matches) <= 1
    report.add(QACheck(
        'seo_h1', 'seo', ok_h1, False,
        '✓ H1 تکی' if ok_h1 else f'✗ {len(h1_matches)} H1',
        score_delta=3.0 if ok_h1 else 0.0,
    ))

    ok_slug = bool(slug) and ' ' not in slug and len(slug) <= 220
    slug_taken = Post.objects.filter(slug=slug).exclude(pk=run.post_id).exists() if slug else True
    link = get_existing_link(run.market_key)
    if link and link.post_id:
        slug_taken = False
    report.add(QACheck(
        'seo_slug', 'seo', ok_slug and not slug_taken, True,
        '✓ Slug معتبر و یکتا' if ok_slug and not slug_taken else '✗ Slug نامعتبر یا تکراری',
        score_delta=4.0 if ok_slug and not slug_taken else 0.0,
    ))

    content = run.content_html or ''
    has_internal = '/blog/' in content or 'mk-market-related' in content
    report.add(QACheck(
        'seo_internal_links', 'seo', has_internal, False,
        '✓ لینک داخلی' if has_internal else '✗ لینک داخلی ناکافی',
        score_delta=4.0 if has_internal else 1.0,
    ))

    stuffing = title.count('تحلیل') > 3 or title.count('قیمت') > 3
    report.add(QACheck(
        'seo_no_stuffing', 'seo', not stuffing, False,
        '✓ بدون Keyword Stuffing' if not stuffing else '✗ Keyword Stuffing',
        score_delta=3.0 if not stuffing else 0.0,
    ))


def _check_media(run: MarketArticleRun, report: QAReport, dataset_meta: dict) -> None:
    ok_featured = bool(run.featured_image and run.featured_image.name)
    report.add(QACheck(
        'media_featured_exists', 'media', ok_featured, True,
        '✓ Featured Image موجود' if ok_featured else '✗ Featured Image ساخته نشد',
        score_delta=8.0 if ok_featured else 0.0,
    ))

    ratio_ok = False
    if ok_featured:
        try:
            with run.featured_image.open('rb') as fh:
                img = Image.open(fh)
                w, h = img.size
                if h > 0:
                    ratio = w / h
                    ratio_ok = 1.65 <= ratio <= 2.05
        except Exception:
            ratio_ok = False
    report.add(QACheck(
        'media_featured_ratio', 'media', ratio_ok or not ok_featured, True,
        '✓ Featured Image نسبت مناسب' if ratio_ok else ('—' if not ok_featured else '✗ Featured Image نسبت نامناسب'),
        score_delta=4.0 if ratio_ok else 0.0,
    ))

    chart = run.chart_assets or {}
    map_keys = [k for k in chart if k.startswith(('street_', 'satellite_', 'map_', 'featured')) and isinstance(chart[k], str)]
    ok_maps = len(map_keys) >= 1 or bool(run.featured_image)
    report.add(QACheck(
        'media_maps', 'media', ok_maps, False,
        '✓ نقشه‌ها' if ok_maps else '✗ نقشه ناقص',
        score_delta=3.0 if ok_maps else 0.0,
    ))

    chart_keys = [k for k in chart if k.startswith('chart_') and isinstance(chart[k], str) and chart[k]]
    ok_charts = len(chart_keys) >= 1
    report.add(QACheck(
        'media_charts', 'media', ok_charts, False,
        f'✓ {len(chart_keys)} نمودار' if ok_charts else '✗ نمودار ناقص',
        score_delta=3.0 if ok_charts else 0.0,
    ))

    city = (dataset_meta.get('city') or '').strip()
    district = (dataset_meta.get('district') or '').strip()
    content = run.content_html or ''
    location_ok = (not city or city in content) and (not district or district in content or district == 'منطقه')
    report.add(QACheck(
        'media_location', 'media', location_ok, True,
        '✓ محدوده جغرافیایی صحیح' if location_ok else '✗ نقشه/متن محدوده اشتباه',
        score_delta=2.0 if location_ok else 0.0,
    ))

    broken_placeholder = bool(_PLACEHOLDER_IMG_RE.search(content))
    report.add(QACheck(
        'media_no_placeholder', 'media', not broken_placeholder, True,
        '✓ بدون Placeholder' if not broken_placeholder else '✗ Placeholder در مقاله',
        score_delta=2.0 if not broken_placeholder else 0.0,
    ))


def _check_technical(run: MarketArticleRun, report: QAReport) -> None:
    content = run.content_html or ''
    imgs = _IMG_RE.findall(content)
    broken_alt = sum(1 for tag in imgs if 'alt=' not in tag.lower())
    ok_alt = broken_alt == 0 or len(imgs) == 0
    report.add(QACheck(
        'technical_alt', 'technical', ok_alt, False,
        '✓ Alt Text' if ok_alt else f'✗ {broken_alt} تصویر بدون Alt',
        score_delta=3.0 if ok_alt else 1.0,
    ))

    hrefs = _HREF_RE.findall(content)
    bad_links = [h for h in hrefs if h.startswith('#') is False and h.startswith('/') is False and not h.startswith('http')]
    ok_links = len(bad_links) == 0
    report.add(QACheck(
        'technical_links', 'technical', ok_links, False,
        '✓ لینک‌ها سالم' if ok_links else f'✗ {len(bad_links)} لینک مشکوک',
        score_delta=4.0 if ok_links else 0.0,
    ))

    ok_render = bool(content.strip()) and 'mk-market' in content
    report.add(QACheck(
        'technical_render', 'technical', ok_render, True,
        '✓ Rendering معتبر' if ok_render else '✗ Rendering نامعتبر',
        score_delta=3.0 if ok_render else 0.0,
    ))


def _privacy_hits(blob: str) -> list[str]:
    hits: list[str] = []
    for pat in PRIVACY_PATTERNS:
        if pat.search(blob or ''):
            hits.append(pat.pattern[:40])
    return hits


def _check_privacy(run: MarketArticleRun, report: QAReport) -> None:
    public_blob = public_content_surfaces(run)
    public_hits = _privacy_hits(public_blob)
    ok_public = len(public_hits) == 0
    report.add(QACheck(
        'privacy', 'data', ok_public, True,
        '✓ بدون داده خصوصی در خروجی عمومی' if ok_public else f'✗ داده خصوصی در محتوا ({len(public_hits)} مورد)',
        score_delta=5.0 if ok_public else 0.0,
    ))

    internal_blob = str(run.report_json or {})
    internal_hits = _privacy_hits(internal_blob)
    ok_internal = len(internal_hits) == 0
    report.add(QACheck(
        'privacy_internal_storage', 'data', ok_internal, False,
        '✓ report_json بدون الگوی حساس' if ok_internal else f'— الگوی حساس در report_json ({len(internal_hits)} مورد)',
        score_delta=2.0 if ok_internal else 0.0,
    ))


def _finalize_scores(report: QAReport) -> None:
    cats = {'data': 30.0, 'content': 25.0, 'seo': 20.0, 'media': 15.0, 'technical': 10.0}
    earned = {k: 0.0 for k in cats}
    for check in report.checks:
        if check.passed and check.score_delta:
            earned[check.category] = min(cats.get(check.category, 0), earned.get(check.category, 0) + check.score_delta)

    report.data_score = round(min(30.0, earned.get('data', 0)), 1)
    report.content_score = round(min(25.0, earned.get('content', 0)), 1)
    report.seo_score = round(min(20.0, earned.get('seo', 0)), 1)
    report.media_score = round(min(15.0, earned.get('media', 0)), 1)
    report.technical_score = round(min(10.0, earned.get('technical', 0)), 1)
    report.total_score = round(
        report.data_score + report.content_score + report.seo_score + report.media_score + report.technical_score,
        1,
    )


def run_quality_gates(
    run: MarketArticleRun,
    settings: AutoPublishSettings,
    *,
    exclude_checks: frozenset[str] | None = None,
) -> QAReport:
    report = QAReport()
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    dataset_meta = blob.get('dataset_meta') if isinstance(blob.get('dataset_meta'), dict) else {}
    skip = exclude_checks or frozenset()

    _check_data_quality(run, settings, report)
    _check_data_consistency(run, report)
    if 'data_numeric_claims' not in skip:
        _check_numeric_claims(run, report)
    _check_content_quality(run, report)
    _check_seo(run, report)
    _check_media(run, report, dataset_meta)
    _check_technical(run, report)
    _check_privacy(run, report)
    _finalize_scores(report)
    return report


def qa_passes_for_publish(qa: QAReport, settings: AutoPublishSettings) -> bool:
    return qa.critical_errors == 0 and qa.total_score >= settings.quality_threshold
