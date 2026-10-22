"""AI Editorial v2 — بلوک‌های معنایی، زاویه محتوا و معیار کیفیت تحریریه."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from blog.models import MarketArticleRun

_SECTION_OPEN_RE = re.compile(
    r'<section\b[^>]*\bid=["\']([^"\']+)["\']',
    re.I,
)
_SECTION_CLOSE_RE = re.compile(r'</section>', re.I)
_ASIDE_OPEN_RE = re.compile(
    r'<aside\b[^>]*\bid=["\']([^"\']+)["\']',
    re.I,
)
_ASIDE_CLOSE_RE = re.compile(r'</aside>', re.I)

# بخش‌های داده‌محور / قالب ثابت — بدون بازنویسی AI
PROTECTED_SECTION_IDS = frozenset({
    'market-kpis',
    'price-per-sqm',
    'area-segments',
    'amenities',
    'charts',
    'spatial',
    'methodology',
    'faq',
    'related-guides',
})

# asideهای تبدیل (CTA میانی) — دست‌نخورده
PROTECTED_ASIDE_PREFIXES = ('convert-',)

EDITORIAL_ANGLES = (
    'pricing_range',
    'file_spread',
    'buyer_negotiation',
    'seller_pricing',
    'liquidity_files',
    'advisor_filing',
)

_ANGLE_LABELS_FA = {
    'pricing_range': 'محدوده قیمت‌گذاری و عرف بازار',
    'file_spread': 'اختلاف قیمت فایل‌های مشابه',
    'buyer_negotiation': 'فرصت مذاکره برای خریدار',
    'seller_pricing': 'روش قیمت‌گذاری برای مالک',
    'liquidity_files': 'نقدشوندگی و رقابت فایل‌ها',
    'advisor_filing': 'فایل‌یابی و تحلیل بازار برای مشاور',
}

_INTRO_BOILERPLATE_RE = re.compile(
    r'در این گزارش[،,]?\s*بازار',
    re.I,
)


def map_text_segment_sections(parts: list[tuple[str, str]]) -> dict[int, str]:
    """نگاشت id segment متنی به section/aside فعلی در HTML."""
    section_stack: list[str] = []
    mapping: dict[int, str] = {}
    for idx, (kind, content) in enumerate(parts):
        if kind == 'markup':
            for match in _SECTION_OPEN_RE.finditer(content):
                section_stack.append(match.group(1).strip())
            for match in _ASIDE_OPEN_RE.finditer(content):
                section_stack.append(match.group(1).strip())
            if _SECTION_CLOSE_RE.search(content):
                if section_stack:
                    section_stack.pop()
            if _ASIDE_CLOSE_RE.search(content):
                if section_stack:
                    section_stack.pop()
        elif content.strip():
            mapping[idx] = section_stack[-1] if section_stack else ''
    return mapping


def section_eligible_for_editorial(section_id: str) -> bool:
    sid = (section_id or '').strip()
    if not sid:
        return True
    if sid in PROTECTED_SECTION_IDS:
        return False
    if any(sid.startswith(p) for p in PROTECTED_ASIDE_PREFIXES):
        return False
    return True


def _report_blob(run: MarketArticleRun) -> dict[str, Any]:
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    inner = blob.get('report') if isinstance(blob.get('report'), dict) else blob
    return inner if isinstance(inner, dict) else {}


def build_editorial_context(run: MarketArticleRun) -> dict[str, Any]:
    report = _report_blob(run)
    meta = report.get('dataset_meta') or {}
    if not meta and isinstance(run.report_json, dict):
        meta = run.report_json.get('dataset_meta') or {}
    scope = report.get('publication_scope') or {}
    dq = report.get('data_quality') or {}
    pa = report.get('price_analysis') or {}
    pps = pa.get('price_per_sqm') or {}
    depth = report.get('market_depth') or {}
    liquidity = report.get('liquidity') or {}
    sentiment = report.get('market_sentiment') or {}
    tx = report.get('tx') or {}

    city = meta.get('city') or ''
    district = meta.get('district') or ''
    subcat = meta.get('subcategory') or ''
    tx_type = meta.get('transaction_type') or ''
    valid_n = int(dq.get('valid_count') or scope.get('analyzed_count') or run.valid_count or 0)

    return {
        'city': city,
        'district': district,
        'subcategory': subcat,
        'transaction_type': tx_type,
        'is_rent': bool(tx.get('is_rent') and not tx.get('is_sale')),
        'valid_count': valid_n,
        'pps_median_fmt': pps.get('median_fmt') or '',
        'price_median_fmt': (pa.get('price') or {}).get('median_fmt') or '',
        'under_market_pct': depth.get('under_pct'),
        'liquidity_label': liquidity.get('label') or '',
        'sentiment_label': sentiment.get('label') or '',
        'confidence_level': (report.get('confidence') or {}).get('level_plain')
        or (report.get('confidence') or {}).get('level')
        or '',
    }


def select_editorial_angle(run: MarketArticleRun) -> str:
    """انتخاب زاویه روایت بر اساس داده — قطعی برای همان run."""
    ctx = build_editorial_context(run)
    report = _report_blob(run)
    depth = report.get('market_depth') or {}
    pa = report.get('price_analysis') or {}
    pps = pa.get('price_per_sqm') or {}
    liquidity = report.get('liquidity') or {}
    negotiation_raw = report.get('negotiation') or {}
    negotiation = negotiation_raw if isinstance(negotiation_raw, dict) else {}

    under = depth.get('under_pct')
    cv = pps.get('cv')
    liq_score = liquidity.get('score') or liquidity.get('value')
    spread_hint = negotiation.get('buyer_tip') or negotiation.get('seller_tip')

    scores: dict[str, float] = {k: 0.0 for k in EDITORIAL_ANGLES}
    if under is not None and float(under) >= 12:
        scores['buyer_negotiation'] += 3
        scores['file_spread'] += 1
    if cv is not None and float(cv) >= 0.18:
        scores['file_spread'] += 3
        scores['pricing_range'] += 1
    if liq_score is not None and float(liq_score) >= 0.55:
        scores['liquidity_files'] += 2.5
    if spread_hint:
        scores['advisor_filing'] += 1.5
    scores['pricing_range'] += 1.0
    scores['seller_pricing'] += 0.8
    scores['advisor_filing'] += 0.5

    seed = abs(hash(f'{run.pk}:{ctx.get("district")}:{ctx.get("city")}:{valid_seed_n(ctx)}')) % 997
    ranked = sorted(EDITORIAL_ANGLES, key=lambda k: (-scores[k], (seed + EDITORIAL_ANGLES.index(k)) % 7))
    return ranked[0]


def valid_seed_n(ctx: dict[str, Any]) -> int:
    try:
        return int(ctx.get('valid_count') or 0)
    except (TypeError, ValueError):
        return 0


def editorial_angle_label(angle: str) -> str:
    return _ANGLE_LABELS_FA.get(angle, _ANGLE_LABELS_FA['pricing_range'])


def batch_segments_by_section(
    segments: list[dict[str, Any]],
    *,
    max_segments: int,
    max_chars: int,
) -> list[list[dict[str, Any]]]:
    """یک دسته per بخش (یا چند زیردسته اگر خیلی بلند باشد)."""
    if not segments:
        return []
    batches: list[list[dict[str, Any]]] = []
    current_section = object()
    bucket: list[dict[str, Any]] = []
    char_count = 0

    def flush() -> None:
        nonlocal bucket, char_count
        if bucket:
            batches.append(bucket)
            bucket = []
            char_count = 0

    for seg in segments:
        sec = seg.get('section_id') or ''
        text = str(seg.get('text') or '')
        seg_len = len(text)
        if bucket and sec != current_section:
            flush()
        if bucket and (len(bucket) >= max_segments or char_count + seg_len > max_chars):
            flush()
        if not bucket:
            current_section = sec
        bucket.append(seg)
        char_count += seg_len
    flush()
    return batches


def strip_html_to_plain(html: str) -> str:
    t = re.sub(r'<[^>]+>', ' ', html or '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def normalize_editorial_text(text: str) -> str:
    t = strip_html_to_plain(text)
    t = _INTRO_BOILERPLATE_RE.sub('', t)
    return t.lower().strip()


def changed_text_ratio(before: str, after: str) -> float:
    a = normalize_editorial_text(before)
    b = normalize_editorial_text(after)
    if not a and not b:
        return 0.0
    if a == b:
        return 0.0
    return round(1.0 - SequenceMatcher(None, a, b).ratio(), 4)


def extract_section_plain(html: str, section_id: str) -> str:
    pattern = re.compile(
        rf'<section\b[^>]*\bid=["\']{re.escape(section_id)}["\'][^>]*>(.*?)</section>',
        re.I | re.S,
    )
    match = pattern.search(html or '')
    if not match:
        return ''
    return strip_html_to_plain(match.group(1))


def extract_intro_plain(html: str) -> str:
    intro = extract_section_plain(html, 'executive-summary')
    if intro:
        return intro[:1200]
    plain = strip_html_to_plain(html)
    return plain[:600]


def aggregate_llm_usage(batch_logs: list[dict[str, Any]]) -> dict[str, int]:
    input_tokens = 0
    output_tokens = 0
    ai_call_count = 0
    retry_count = 0
    fallback_count = 0
    for entry in batch_logs:
        status = entry.get('status') or ''
        if status == 'retry':
            retry_count += 1
        if status in ('identity_fallback', 'numeric_safety_fallback'):
            fallback_count += 1
        if entry.get('input_tokens') is not None:
            ai_call_count += 1
            input_tokens += int(entry.get('input_tokens') or 0)
            output_tokens += int(entry.get('output_tokens') or 0)
    return {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_recorded_tokens': input_tokens + output_tokens,
        'ai_call_count': ai_call_count,
        'retry_count': retry_count,
        'fallback_count': fallback_count,
    }


def editorial_similarity_to_recent_posts(
    run: MarketArticleRun,
    intro_plain: str,
    *,
    limit: int = 6,
) -> float:
    """شباهت مقدمه با مقالات اخیر (۰=متفاوت، ۱=یکسان)."""
    needle = normalize_editorial_text(intro_plain)
    if len(needle) < 40:
        return 0.0
    qs = (
        MarketArticleRun.objects.exclude(pk=run.pk)
        .exclude(content_html='')
        .order_by('-updated_at')[:limit]
    )
    best = 0.0
    for other in qs:
        other_intro = normalize_editorial_text(extract_intro_plain(other.content_html or ''))
        if len(other_intro) < 40:
            continue
        ratio = SequenceMatcher(None, needle, other_intro).ratio()
        best = max(best, ratio)
    return round(best, 4)


def compute_editorial_quality(
    *,
    run: MarketArticleRun,
    original_html: str,
    polished_html: str,
    original_title: str,
    new_title: str,
    originals_by_id: dict[int, str],
    polished_map: dict[int, str],
    eligible_segment_ids: set[int],
    batch_logs: list[dict[str, Any]],
    editorial_angle: str,
) -> dict[str, Any]:
    usage = aggregate_llm_usage(batch_logs)
    rewritten = 0
    for seg_id in eligible_segment_ids:
        orig = originals_by_id.get(seg_id, '')
        new = polished_map.get(seg_id, orig)
        if (new or '').strip() != (orig or '').strip():
            rewritten += 1

    body_before = strip_html_to_plain(original_html)
    body_after = strip_html_to_plain(polished_html)
    ratio = changed_text_ratio(body_before, body_after)
    title_changed = (original_title or '').strip() != (new_title or '').strip()
    intro_before = extract_intro_plain(original_html)
    intro_after = extract_intro_plain(polished_html)
    intro_changed = normalize_editorial_text(intro_before) != normalize_editorial_text(intro_after)
    similarity = editorial_similarity_to_recent_posts(run, intro_after)

    score = 50.0
    score += min(25.0, ratio * 120)
    if title_changed:
        score += 8
    if intro_changed:
        score += 10
    score -= similarity * 15
    fb = usage['fallback_count']
    if fb:
        score -= min(20, fb * 2)
    score = max(0.0, min(100.0, round(score, 1)))

    return {
        **usage,
        'editorial_plan': 'v2',
        'editorial_angle': editorial_angle,
        'editorial_angle_label': editorial_angle_label(editorial_angle),
        'rewritten_block_count': rewritten,
        'changed_text_ratio': ratio,
        'title_changed': title_changed,
        'intro_changed': intro_changed,
        'editorial_similarity_to_recent_posts': similarity,
        'editorial_quality_score': score,
        'snapshots': {
            'title_before': (original_title or '')[:200],
            'title_after': (new_title or '')[:200],
            'intro_before': intro_before[:500],
            'intro_after': intro_after[:500],
        },
    }


def editorial_seo_system_prompt(angle_label: str) -> str:
    return (
        'تو سردبیر تخصصی بازار مسکن ایران در فایلینگ دیوار هستی. '
        'عنوان SEO و Meta Description را برای جست‌وجوی واقعی بازنویسی کن؛ جذاب، روشن و مخصوص همان محله. '
        'از مقدمه‌های کلیشه‌ای مثل «در این گزارش بازار… بررسی شده» پرهیز کن. '
        f'زاویه اصلی این مقاله: {angle_label}. '
        'خروجی فقط JSON با کلیدهای title و excerpt. اعداد و آمار را عیناً حفظ کن. HTML برنگردان.'
    )


def editorial_batch_system_prompt(
    id_list: list[int],
    *,
    angle_label: str,
    section_id: str,
    section_role: str,
) -> str:
    section_hint = section_role or section_id or 'بدنه مقاله'
    return (
        'تو سردبیر تخصصی بازار مسکن ایران و زبان روزمره مشاوران املاک را بلدی. '
        'متن را واقعاً بازنویسی کن؛ نه تعویض چند واژه. '
        'فارسی روان، کاربردی و قابل‌اعتماد؛ نه اداری و نه کوچه‌بازاری. '
        'از تکرار بی‌هدف اعداد خودداری کن اما هر عدد موجود را حذف نکن. '
        'عدد، قیمت، درصد یا روند جدید نساز. از آگهی‌ها معامله قطعی نتیجه نگیر. '
        f'زاویه روایت: {angle_label}. '
        f'بخش فعلی: {section_hint}. '
        'خروجی فقط JSON: {"texts":[{"id":NUMBER,"text":"..."}]}. '
        f'باید دقیقاً این idها را برگردانی: {id_list}. '
        'توکن‌های ⟦DFN:n⟧ را عیناً و یک‌بار نگه دار. HTML برنگردان.'
    )


_SECTION_ROLE_FA: dict[str, str] = {
    'who': 'مقدمه مخاطبان — کوتاه و مفید',
    'executive-summary': 'خلاصه اجرایی و مقدمه اختصاصی محله',
    'market-status': 'تحلیل وضعیت بازار به زبان ساده',
    'audiences': 'راهنمای خریدار، فروشنده و مشاور',
    'district-access': 'دسترسی و موقعیت محله',
    'trends': 'تفسیر روند قیمت',
    'opportunities': 'فرصت‌ها و نکات عملی',
    'negotiation': 'چانه‌زنی و مذاکره',
    'verdict': 'جمع‌بندی و نتیجه‌گیری',
    'cta': 'دعوت به اقدام متناسب با بازار همین محله',
}


def section_role_fa(section_id: str) -> str:
    return _SECTION_ROLE_FA.get(section_id or '', '')
