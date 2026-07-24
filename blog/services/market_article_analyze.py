"""اجرای موتور تحلیل برای مقاله سیستماتیک + sanitize خروجی عمومی."""
from __future__ import annotations

import copy
import re
from datetime import date, datetime
from typing import Any

from workspace.models import Dataset
from workspace.services.analyzer import (
    build_analysis_dashboard,
    compute_outliers_report,
    compute_statistics,
    filter_outliers,
    listings_to_dataframe,
)
from workspace.services.charts import build_all_charts
from workspace.services.display import transaction_profile
from workspace.services.market_agent import resolve_report_confidence
from workspace.services.valuation import analyze_market

_BLOCKED_KEYS = {
    'token', 'tokens', 'link', 'links', 'url', 'urls', 'phone', 'phones',
    'mobile', 'contact', 'contacts', 'owner', 'user', 'username', 'email',
    'advertiser', 'description', 'title', 'images', 'image', 'listings',
    'listing_id', 'listing_ids', 'dataset_id', 'consultant_cards',
}
_PHONE_RE = re.compile(r'(?:\+98|0098|0)?9\d{9}')
_TOKEN_RE = re.compile(r'\b[A-Za-z0-9_-]{10,}\b')


def run_dataset_analysis(dataset: Dataset) -> dict[str, Any]:
    """مسیر مشابه DatasetAnalyzeView بدون Template."""
    listings = list(dataset.listings.all())
    df = listings_to_dataframe(listings)
    lite = len(df) > 200
    df_clean = filter_outliers(df, dataset.transaction_type) if len(df) >= 10 else df

    tx = transaction_profile(dataset.transaction_type)
    stats = compute_statistics(df_clean, dataset.transaction_type)
    outliers = compute_outliers_report(df, dataset.transaction_type)
    market = analyze_market(df_clean, dataset.transaction_type)
    dashboard = build_analysis_dashboard(
        df_clean,
        stats,
        market,
        dataset.transaction_type,
        df_raw=df,
        outliers_report=outliers,
        listings=listings,
        dataset_name=dataset.name,
        subcategory=dataset.subcategory or '',
    )
    prof = dashboard['professional']
    confidence = resolve_report_confidence(
        prof, valid_count=len(df_clean), raw_count=len(df),
    )
    prof['confidence'] = confidence

    charts = build_all_charts(
        df_clean,
        lite=lite,
        transaction_type=dataset.transaction_type,
        market_stats=market.get('stats', {}),
        area_segments=dashboard['area_segments'],
        report=prof,
    )

    geo_points = _extract_geo_points(
        listings,
        transaction_type=dataset.transaction_type or '',
        limit=800,
    )

    return {
        'report': prof,
        'stats': stats,
        'tx': tx,
        'outliers': outliers,
        'market_stats': market.get('stats', {}),
        'area_segments': dashboard['area_segments'],
        'insights': dashboard['insights'],
        'charts': charts,
        'row_count': len(df),
        'clean_count': len(df_clean),
        'lite_mode': lite,
        'geo_points': geo_points,
        'dataset_meta': {
            'city': (dataset.city or '').strip(),
            'district': (dataset.district or '').strip(),
            'transaction_type': (dataset.transaction_type or '').strip(),
            'subcategory': (dataset.subcategory or '').strip(),
            'name': dataset.name,
            'updated_at': dataset.updated_at.isoformat() if dataset.updated_at else None,
        },
    }


def sanitize_report_for_public(payload: dict[str, Any]) -> dict[str, Any]:
    """حذف شناسه‌ها، لینک‌ها و مختصات خام از خروجی قابل انتشار."""
    cleaned = _deep_sanitize(copy.deepcopy(payload))
    # Keep aggregated geo for OG renderer only under private key that composer ignores
    if 'geo_points' in payload:
        cleaned['_geo_for_assets'] = payload['geo_points']
    return cleaned


def extract_quality_metrics(analysis: dict[str, Any]) -> dict[str, Any]:
    report = analysis.get('report') or {}
    conf = report.get('confidence') or {}
    dq = report.get('data_quality') or {}
    scope = report.get('publication_scope') or {}

    data_from = _parse_date(scope.get('date_from') or scope.get('from'))
    data_to = _parse_date(scope.get('date_to') or scope.get('to'))
    if data_from is None and scope.get('date_from_fmt'):
        data_from = None  # keep fmt only in report
    if data_to is None and scope.get('date_to_fmt'):
        data_to = None

    return {
        'confidence_score': conf.get('score') or conf.get('display_score'),
        'quality_pct': dq.get('quality_pct'),
        'quality_score': dq.get('quality_pct'),
        'valid_count': dq.get('valid_count') or analysis.get('clean_count') or 0,
        'raw_count': dq.get('raw_count') or analysis.get('row_count') or 0,
        'data_from': data_from,
        'data_to': data_to,
        'date_from_fmt': scope.get('date_from_fmt') or '',
        'date_to_fmt': scope.get('date_to_fmt') or '',
    }


def _extract_geo_points(
    listings,
    *,
    transaction_type: str = '',
    limit: int = 800,
) -> list[dict[str, float]]:
    from workspace.services.formatting import full_deposit_equiv

    tx = transaction_profile(transaction_type)
    is_rent = bool(tx.get('is_rent') and not tx.get('is_sale'))
    points: list[dict[str, float]] = []
    for lst in listings:
        lat = getattr(lst, 'latitude', None)
        lng = getattr(lst, 'longitude', None)
        if lat is None or lng is None:
            continue
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            continue

        value = 0.0
        weight = 1.0
        if is_rent:
            try:
                fd = full_deposit_equiv(
                    getattr(lst, 'deposit', None),
                    getattr(lst, 'rent', None),
                )
                if fd:
                    value = float(fd)
                    weight = max(0.4, min(3.0, value / 800_000_000))
            except (TypeError, ValueError):
                weight = 1.0
        else:
            pps = getattr(lst, 'price_per_sqm', None)
            if pps:
                try:
                    value = float(pps)
                    weight = max(0.4, min(3.0, value / 50_000_000))
                except (TypeError, ValueError):
                    weight = 1.0

        points.append({
            'lat': lat_f,
            'lng': lng_f,
            'w': round(weight, 3),
            'value': value,
            'pps': value,
        })
        if len(points) >= limit:
            break
    return points


def _deep_sanitize(value: Any, *, key: str | None = None) -> Any:
    if key and key.lower() in _BLOCKED_KEYS:
        return None
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if str(k).lower() in _BLOCKED_KEYS:
                continue
            cleaned = _deep_sanitize(v, key=str(k))
            if cleaned is not None:
                out[k] = cleaned
        return out
    if isinstance(value, list):
        return [_deep_sanitize(v) for v in value if _deep_sanitize(v) is not None]
    if isinstance(value, str):
        text = _PHONE_RE.sub('[حذف‌شده]', value)
        # Strip long token-like sequences only when key suggests identity
        if key and key.lower() in ('token', 'id', 'slug'):
            text = _TOKEN_RE.sub('[حذف‌شده]', text)
        return text
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _parse_date(value: Any) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).date()
    except ValueError:
        return None
