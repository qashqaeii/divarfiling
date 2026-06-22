"""ابزارهای بازار مبتنی بر فایل — فاز ۱."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.services.formatting import format_area, format_toman, full_deposit_equiv
from workspace.services.tools import build_market_snapshot, pricing_suggest


def _metric_dist(row: Dict[str, Any], key: str) -> Dict[str, Any]:
    dist = row.get(key) or {}
    return {
        'p25': dist.get('p25'),
        'p50': dist.get('median'),
        'p75': dist.get('p75'),
        'p10': dist.get('p10'),
        'p90': dist.get('p90'),
        'min': dist.get('min'),
        'max': dist.get('max'),
        'count': dist.get('count'),
        'p25_fmt': dist.get('p25_fmt') or (format_toman(dist['p25']) if dist.get('p25') else ''),
        'p50_fmt': dist.get('median_fmt') or (format_toman(dist['median']) if dist.get('median') else ''),
        'p75_fmt': dist.get('p75_fmt') or (format_toman(dist['p75']) if dist.get('p75') else ''),
        'range_50_fmt': dist.get('range_50_fmt', ''),
    }


def _resolve_market_mode(tx: Dict[str, Any], enriched, listing=None) -> str:
    """تعیین حالت ارزش‌گذاری: فروش یا اجاره."""
    if tx.get('is_mixed'):
        if listing is not None:
            has_rent = bool(listing.rent or listing.deposit)
            has_price = bool(listing.price)
            if has_rent and not has_price:
                return 'rent'
            if has_price and not has_rent:
                return 'sale'
        rent_n = 0
        sale_n = 0
        if hasattr(enriched, 'columns'):
            if 'rent_equiv' in enriched.columns:
                rent_n = int(enriched['rent_equiv'].notna().sum())
            if 'price_per_sqm' in enriched.columns:
                sale_n = int(enriched['price_per_sqm'].notna().sum())
        if sale_n and not rent_n:
            return 'sale'
        if rent_n and not sale_n:
            return 'rent'
        return 'rent' if rent_n >= sale_n else 'sale'
    if tx.get('is_rent') and not tx.get('show_price_per_sqm'):
        return 'rent'
    return 'sale'


def _mode_labels(mode: str) -> Dict[str, str]:
    if mode == 'rent':
        return {
            'actual_label': 'رهن کامل معادل',
            'expected_label': 'میانه هم‌رده (رهن کامل)',
            'pps_label': 'رهن کامل/متر',
            'price_field': 'full_deposit',
        }
    return {
        'actual_label': 'قیمت آگهی',
        'expected_label': 'میانه هم‌رده',
        'pps_label': 'قیمت هر متر',
        'price_field': 'price',
    }


def serialize_neighborhoods(rows: List[Dict[str, Any]], *, mode: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if mode == 'rent':
            metric_key = 'full_deposit' if row.get('full_deposit') else (
                'rent' if row.get('rent') else 'deposit'
            )
        else:
            metric_key = 'price_per_sqm' if row.get('price_per_sqm') else 'price'
        metric = _metric_dist(row, metric_key)
        if not metric.get('p50'):
            continue
        item: Dict[str, Any] = {
            'neighborhood': row['neighborhood'],
            'count': row.get('count', 0),
            'metric': metric_key,
            'metric_label': _metric_label(metric_key),
            **metric,
        }
        if row.get('full_deposit'):
            item['full_deposit'] = _metric_dist(row, 'full_deposit')
        if row.get('rent'):
            item['rent'] = _metric_dist(row, 'rent')
        if row.get('deposit'):
            item['deposit'] = _metric_dist(row, 'deposit')
        out.append(item)
    return out


def _metric_label(key: str) -> str:
    return {
        'price_per_sqm': 'قیمت هر متر',
        'price': 'قیمت کل',
        'full_deposit': 'رهن کامل معادل',
        'rent': 'اجاره ماهانه',
        'deposit': 'ودیعه',
    }.get(key, key)


def build_market_toolkit(dataset) -> Dict[str, Any]:
    """بسته داده ابزارهای بازار برای یک فایل."""
    from workspace.services.analyzer import filter_outliers, listings_to_dataframe
    from workspace.services.display import transaction_profile
    from workspace.services.market_analytics import neighborhood_price_analysis
    from workspace.services.valuation import compute_expected_values, enrich_dataframe, find_value_picks

    listings = list(dataset.listings.all())
    df = listings_to_dataframe(listings)
    tx = transaction_profile(dataset.transaction_type or '')
    df_clean = filter_outliers(df, dataset.transaction_type or '') if len(df) >= 10 else df
    enriched = enrich_dataframe(df_clean, dataset.transaction_type or '')

    mode = _resolve_market_mode(tx, enriched)
    scored = compute_expected_values(enriched, mode=mode)
    opportunities = find_value_picks(scored, direction='below', limit=15)
    nb_rows = neighborhood_price_analysis(df_clean, dataset.transaction_type or '', min_count=2)
    neighborhoods = serialize_neighborhoods(nb_rows, mode=mode)

    snapshot = build_market_snapshot(dataset)
    snapshot['mode'] = mode
    labels = _mode_labels(mode)

    return {
        'snapshot': snapshot,
        'opportunities': opportunities,
        'opportunities_count': len(opportunities),
        'neighborhoods': neighborhoods,
        'neighborhood_names': [n['neighborhood'] for n in neighborhoods],
        'is_rent': mode == 'rent',
        'show_price_per_sqm': bool(tx.get('show_price_per_sqm', True)),
        'mode': mode,
        'transaction_mode': tx.get('mode') or dataset.transaction_type or '',
        'labels': labels,
    }


def search_listings(dataset, query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
    from django.db.models import Q

    q = (query or '').strip()
    if not q:
        return []
    qs = dataset.listings.filter(
        Q(title__icontains=q) | Q(neighborhood__icontains=q) | Q(token__icontains=q),
    )
    items = []
    for lst in qs[:limit]:
        items.append({
            'id': lst.pk,
            'token': lst.token,
            'title': (lst.title or '')[:80],
            'neighborhood': lst.neighborhood or '',
            'area': lst.area,
            'area_fmt': format_area(lst.area) if lst.area else '',
            'price': lst.price,
            'price_fmt': format_toman(lst.price) if lst.price else '',
            'deposit_fmt': format_toman(lst.deposit) if lst.deposit else '',
            'rent_fmt': format_toman(lst.rent) if lst.rent else '',
        })
    return items


def evaluate_listing_market(
    dataset,
    *,
    listing_id: Optional[int] = None,
    area: Optional[float] = None,
    price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    neighborhood: Optional[str] = None,
) -> Dict[str, Any]:
    """ارزیابی آگهی نسبت به بازار فایل."""
    from workspace.services.analyzer import benchmark_listing, filter_outliers, listings_to_dataframe
    from workspace.services.display import transaction_profile
    from workspace.services.features import area_bucket
    from workspace.services.valuation import compute_expected_values, enrich_dataframe

    listings = list(dataset.listings.all())
    df = listings_to_dataframe(listings)
    tx = transaction_profile(dataset.transaction_type or '')
    df_clean = filter_outliers(df, dataset.transaction_type or '') if len(df) >= 10 else df
    enriched = enrich_dataframe(df_clean, dataset.transaction_type or '')

    listing = None
    if listing_id:
        listing = dataset.listings.filter(pk=listing_id).first()
        if not listing:
            return {'error': 'آگهی یافت نشد.'}

    if not listing_id and tx.get('is_mixed'):
        if price and not (deposit or rent):
            mode = 'sale'
        elif (deposit or rent) and not price:
            mode = 'rent'
        else:
            mode = _resolve_market_mode(tx, enriched)
    else:
        mode = _resolve_market_mode(tx, enriched, listing=listing)

    scored = compute_expected_values(enriched, mode=mode)
    labels = _mode_labels(mode)

    if listing_id and listing:
        bench = benchmark_listing(listing, enriched, dataset.transaction_type or '')
        area = listing.area
        neighborhood = listing.neighborhood or neighborhood
        if mode == 'rent':
            actual = full_deposit_equiv(listing.deposit, listing.rent, 30)
        else:
            actual = listing.price
        title = listing.title
        token = listing.token
        link = listing.link
    else:
        if not area or area <= 0:
            return {'error': 'متراژ را وارد کنید.'}
        if mode == 'rent':
            actual = full_deposit_equiv(deposit, rent, 30)
            if not actual:
                return {'error': 'ودیعه یا اجاره را وارد کنید.'}
        elif not price:
            return {'error': 'قیمت را وارد کنید.'}
        else:
            actual = price
        title = ''
        token = ''
        link = ''
        bench = {}

    peers = scored
    scope = 'کل فایل'
    if neighborhood:
        nb = neighborhood.strip()
        nb_peers = scored[scored['neighborhood'].astype(str).str.strip() == nb]
        if len(nb_peers) >= 5:
            peers = nb_peers
            scope = f'محله {nb}'

    bucket = area_bucket(area) if area else 'نامشخص'
    seg = peers[peers['area_bucket'] == bucket] if bucket else peers
    if len(seg) < 5:
        seg = peers
    else:
        scope = f'{scope} · متراژ {bucket}'

    if mode == 'rent':
        metric_col = 'full_deposit'
        actual_metric = actual
        pps_actual = int(actual / area) if area and actual else None
    else:
        metric_col = 'price'
        actual_metric = actual
        pps_actual = int(actual / area) if area and actual else None

    expected = None
    if 'expected_total' in seg.columns and seg['expected_total'].notna().any():
        expected = int(seg['expected_total'].median())
    elif mode == 'sale' and pps_actual and 'price_per_sqm' in seg.columns:
        med_pps = seg['price_per_sqm'].median()
        if med_pps == med_pps:
            expected = int(float(med_pps) * area)

    score = bench.get('diff_pct')
    if score is None and expected and actual_metric:
        score = round((actual_metric - expected) / expected * 100, 1)

    p25 = p75 = p50 = None
    if metric_col in seg.columns and seg[metric_col].notna().any():
        series = seg[metric_col].dropna()
        p25 = int(series.quantile(0.25))
        p75 = int(series.quantile(0.75))
        p50 = int(series.median())

    verdict = bench.get('verdict') or _verdict_from_score(score)
    tone = _tone_from_score(score)

    negotiate = None
    if score is not None and score > 5 and expected:
        negotiate = int(expected * 0.98)
    elif score is not None and score < -5 and expected:
        negotiate = int(expected * 1.02)

    return {
        'mode': mode,
        'title': title,
        'token': token,
        'link': link,
        'area': area,
        'area_fmt': format_area(area) if area else '',
        'neighborhood': neighborhood or '',
        'scope': scope,
        'actual': actual_metric,
        'actual_fmt': format_toman(actual_metric) if actual_metric else '—',
        'expected': expected,
        'expected_fmt': format_toman(expected) if expected else '—',
        'pps_actual': pps_actual,
        'pps_actual_fmt': format_toman(pps_actual, per_sqm=True) if pps_actual else '—',
        'market_median': p50,
        'market_median_fmt': format_toman(p50) if p50 else bench.get('market_median_fmt', '—'),
        'p25': p25,
        'p25_fmt': format_toman(p25) if p25 else '—',
        'p75': p75,
        'p75_fmt': format_toman(p75) if p75 else '—',
        'score': score,
        'score_fmt': f'{score:+.1f}٪' if score is not None else '—',
        'verdict': verdict,
        'tone': tone,
        'negotiate_hint': negotiate,
        'negotiate_hint_fmt': format_toman(negotiate) if negotiate else '',
        'peer_count': len(seg),
        'labels': labels,
        'copy': _build_eval_copy(verdict, actual_metric, expected, score, area, neighborhood),
    }


def pricing_suggest_banded(
    area: float,
    snapshot: Dict[str, Any],
    adjustment_pct: float = 0.0,
) -> Dict[str, Any]:
    """قیمت‌گذاری با باند P25–P75 بازار."""
    median_pps = snapshot.get('median_pps')
    if not median_pps or not area or area <= 0:
        return {}
    p25 = snapshot.get('pps_p25') or int(median_pps * 0.92)
    p75 = snapshot.get('pps_p75') or int(median_pps * 1.08)
    core = pricing_suggest(area, median_pps, adjustment_pct)
    if not core:
        return {}
    adj = 1 + adjustment_pct / 100
    band_low = int(p25 * adj * area)
    band_high = int(p75 * adj * area)
    is_rent = snapshot.get('is_rent') and snapshot.get('pps_metric') == 'full_deposit_per_sqm'
    return {
        **core,
        'band_low': band_low,
        'band_high': band_high,
        'band_low_fmt': format_toman(band_low),
        'band_high_fmt': format_toman(band_high),
        'pps_p25': p25,
        'pps_p75': p75,
        'pps_p25_fmt': format_toman(p25, per_sqm=True),
        'pps_p75_fmt': format_toman(p75, per_sqm=True),
        'total_label': 'رهن کامل پیشنهادی' if is_rent else 'قیمت پیشنهادی',
        'pps_label': 'رهن کامل/متر' if is_rent else 'قیمت هر متر',
    }


def _verdict_from_score(score: Optional[float]) -> str:
    if score is None:
        return 'داده کافی نیست'
    if score <= -12:
        return 'زیر بازار — فرصت مناسب'
    if score >= 12:
        return 'بالای بازار — مذاکره پیشنهاد می‌شود'
    if score <= -5:
        return 'کمی زیر بازار'
    if score >= 5:
        return 'کمی بالای بازار'
    return 'در محدوده متعارف بازار'


def _tone_from_score(score: Optional[float]) -> str:
    if score is None:
        return 'neutral'
    if score <= -12:
        return 'great'
    if score <= -5:
        return 'good'
    if score >= 12:
        return 'bad'
    if score >= 5:
        return 'warn'
    return 'neutral'


def _build_eval_copy(verdict, actual, expected, score, area, neighborhood) -> str:
    parts = [verdict]
    if neighborhood:
        parts.append(neighborhood)
    if area:
        parts.append(format_area(area))
    if actual:
        parts.append(format_toman(actual))
    if score is not None:
        parts.append(f'({score:+.1f}٪ نسبت به بازار)')
    if expected:
        parts.append(f'میانه هم‌رده: {format_toman(expected)}')
    return ' — '.join(parts)
