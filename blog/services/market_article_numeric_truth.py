"""منبع معتبر (Source of Truth) اعداد محاسبات بازار برای QA."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from blog.models import MarketArticleRun
from blog.services.market_article_number_utils import extract_report_numbers, normalize_number_text

_PERCENT_KEY_RE = re.compile(
    r'(pct|percent|share|ratio|rate|yoy|mom|coverage|depth|valuation)',
    re.I,
)
_PARSE_PERCENT_RE = re.compile(
    r'^([\d]+(?:[.,][\d]+)?)\s*%?$',
)


@dataclass
class MarketTruthRegistry:
    formatted_tokens: set[str] = field(default_factory=set)
    percent_values: set[float] = field(default_factory=set)
    count_values: set[int] = field(default_factory=set)

    def add_percent(self, value: float | int | str) -> None:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return
        if num < 0 or num > 1000:
            return
        rounded = round(num, 2)
        self.percent_values.add(rounded)
        for decimals in (0, 1, 2):
            label = f'{num:.{decimals}f}'.rstrip('0').rstrip('.')
            self.formatted_tokens.add(normalize_number_text(f'{label}%'))
            self.formatted_tokens.add(normalize_number_text(label))

    def add_formatted(self, text: str) -> None:
        norm = normalize_number_text(text.strip())
        if len(norm) >= 2:
            self.formatted_tokens.add(norm)

    def add_count(self, value: int | float | str) -> None:
        try:
            num = int(float(value))
        except (TypeError, ValueError):
            return
        if num <= 0:
            return
        self.count_values.add(num)
        self.formatted_tokens.add(normalize_number_text(str(num)))


def _walk_truth(value: Any, key: str, registry: MarketTruthRegistry) -> None:
    if isinstance(value, dict):
        for child_key, child_val in value.items():
            _walk_truth(child_val, child_key, registry)
        return
    if isinstance(value, list):
        for item in value:
            _walk_truth(item, key, registry)
        return
    if isinstance(value, str):
        if key.endswith('_fmt') and value.strip() and value.strip() != '—':
            registry.add_formatted(value)
        return
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if _PERCENT_KEY_RE.search(key or ''):
            registry.add_percent(value)
            return
        if isinstance(value, float) and 0 < value <= 100:
            registry.add_percent(value)
            return
        if isinstance(value, int) and value > 0:
            registry.add_count(value)


def build_market_truth_registry(run: MarketArticleRun) -> MarketTruthRegistry:
    registry = MarketTruthRegistry()
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    inner = blob.get('report') if isinstance(blob.get('report'), dict) else {}
    metrics = blob.get('metrics') if isinstance(blob.get('metrics'), dict) else {}

    _walk_truth(inner, 'report', registry)
    _walk_truth(metrics, 'metrics', registry)
    _walk_truth(blob, 'root', registry)

    for fmt in extract_report_numbers(inner):
        registry.add_formatted(fmt)

    for metric_key in ('valid_count', 'raw_count', 'median_price', 'median_area', 'quality_pct'):
        if metrics.get(metric_key) is not None:
            val = metrics[metric_key]
            if 'pct' in metric_key or metric_key == 'quality_pct':
                registry.add_percent(val)
            else:
                registry.add_count(val)

    if run.valid_count:
        registry.add_count(run.valid_count)
    if run.raw_count:
        registry.add_count(run.raw_count)
    if run.quality_pct:
        registry.add_percent(run.quality_pct)

    amenities = inner.get('amenities_coverage') if isinstance(inner, dict) else {}
    if isinstance(amenities, dict):
        for _name, payload in amenities.items():
            if isinstance(payload, dict):
                for pk in ('pct', 'percent', 'coverage_pct', 'share_pct'):
                    if payload.get(pk) is not None:
                        registry.add_percent(payload[pk])

    depth = inner.get('market_depth') if isinstance(inner, dict) else {}
    if isinstance(depth, dict):
        for pk in ('under_pct', 'fair_pct', 'over_pct'):
            if depth.get(pk) is not None:
                registry.add_percent(depth[pk])

    segments = inner.get('area_segments') if isinstance(inner, dict) else []
    if isinstance(segments, list):
        for seg in segments:
            if isinstance(seg, dict):
                for pk in ('share_pct', 'pct', 'percent'):
                    if seg.get(pk) is not None:
                        registry.add_percent(seg[pk])

    if isinstance(inner, dict):
        _register_distribution_bands(inner, registry)

    return registry


_DISTRIBUTION_BLOCKS = (
    'price_per_sqm',
    'price',
    'deposit',
    'rent',
    'full_deposit',
)


def _register_distribution_bands(inner: dict, registry: MarketTruthRegistry) -> None:
    """برچسب‌های ۵۰٪ / ۸۰٪ بازه صدکی وقتی range_*_fmt در گزارش وجود دارد."""
    for block_key in _DISTRIBUTION_BLOCKS:
        block = inner.get(block_key)
        if isinstance(block, dict):
            _register_band_block(block, registry)


def _register_band_block(block: dict, registry: MarketTruthRegistry) -> None:
    for band_key, pct in (('range_50_fmt', 50), ('range_80_fmt', 80)):
        val = block.get(band_key)
        if isinstance(val, str) and val.strip() and val.strip() != '—':
            registry.add_percent(pct)
            registry.add_formatted(val)
    for fmt_key in (
        'p10_fmt', 'p25_fmt', 'p75_fmt', 'p90_fmt',
        'median_fmt', 'iqr_fmt', 'low_fmt', 'high_fmt',
    ):
        val = block.get(fmt_key)
        if isinstance(val, str) and val.strip() and val.strip() != '—':
            registry.add_formatted(val)


def parse_percent_claim(raw: str, normalized: str) -> float | None:
    if '%' not in normalized and '٪' not in (raw or '') and 'درصد' not in (raw or ''):
        return None
    cleaned = normalized.replace('%', '').strip()
    m = _PARSE_PERCENT_RE.match(cleaned)
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', '.'))
    except ValueError:
        return None


def percent_matches_truth(value: float, registry: MarketTruthRegistry) -> bool:
    for truth in registry.percent_values:
        if abs(value - truth) <= max(0.2, truth * 0.02):
            return True
    return False


def formatted_matches_truth(normalized: str, registry: MarketTruthRegistry) -> bool:
    if normalized in registry.formatted_tokens:
        return True
    for token in registry.formatted_tokens:
        if len(normalized) >= 4 and (normalized in token or token in normalized):
            return True
    return False


def claim_verified_against_truth(
    raw: str,
    normalized: str,
    registry: MarketTruthRegistry,
) -> bool:
    pct = parse_percent_claim(raw, normalized)
    if pct is not None:
        return percent_matches_truth(pct, registry)
    if formatted_matches_truth(normalized, registry):
        return True
    digits = re.sub(r'[^\d]', '', normalized)
    if digits.isdigit():
        num = int(digits)
        if num in registry.count_values:
            return True
    return False


def find_unverified_public_claims(
    public_text: str,
    registry: MarketTruthRegistry,
    *,
    is_significant,
    stat_claim_re,
) -> list[str]:
    invented: list[str] = []
    for raw in stat_claim_re.findall(public_text or ''):
        norm = normalize_number_text(raw.strip())
        if not norm or not is_significant(raw, norm):
            continue
        if not claim_verified_against_truth(raw, norm, registry):
            invented.append(raw.strip())
    return list(dict.fromkeys(invented))


def assess_data_consistency(run: MarketArticleRun) -> list[str]:
    """ناسازگاری داده — توقف انتشار."""
    errors: list[str] = []
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    metrics = blob.get('metrics') if isinstance(blob.get('metrics'), dict) else {}
    inner = blob.get('report') if isinstance(blob.get('report'), dict) else {}

    if not inner and not metrics:
        errors.append('report_json خالی یا ناقص است.')

    metric_valid = metrics.get('valid_count')
    if metric_valid is not None and run.valid_count and int(metric_valid) != int(run.valid_count):
        errors.append('valid_count در metrics با فیلد run هم‌خوان نیست.')

    if not (run.content_html or '').strip():
        errors.append('content_html خالی است.')

    return errors
