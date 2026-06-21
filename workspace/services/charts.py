"""داده نمودار برای Chart.js — با اختصار M/B."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from workspace.services.display import transaction_profile
from workspace.services.formatting import format_range_short, format_toman, format_toman_short


def _histogram_bins(series: pd.Series, bins: int = 20, money: bool = False) -> Dict[str, List]:
    clean = series.dropna()
    if len(clean) < 2:
        return {'labels': [], 'values': []}
    counts, edges = pd.cut(clean, bins=min(bins, len(clean)), retbins=True)
    hist = counts.value_counts().sort_index()
    labels = []
    for interval in hist.index:
        left, right = float(interval.left), float(interval.right)
        if money:
            labels.append(format_range_short(left, right))
        else:
            labels.append(f'{round(left):g}–{round(right):g}')
    return {'labels': labels, 'values': hist.values.tolist()}


def _chart_meta(axis: str = 'money', unit: str = '') -> Dict:
    return {'axis': axis, 'unit': unit}


def _safe_int(value: Any) -> Optional[int]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def chart_price_histogram(df: pd.DataFrame, lite: bool = False) -> Dict:
    if 'price' not in df.columns or not df['price'].notna().any():
        return {}
    bins = 8 if lite else 12
    data = _histogram_bins(df['price'], bins, money=True)
    return {
        'type': 'bar',
        'title': 'پراکندگی قیمت فروش',
        'labels': data['labels'],
        'datasets': [{'label': 'تعداد آگهی', 'data': data['values'], 'backgroundColor': 'rgba(59,130,246,0.75)'}],
        **_chart_meta('money', 'تومان'),
    }


def chart_price_per_sqm_histogram(df: pd.DataFrame, lite: bool = False) -> Dict:
    if 'price_per_sqm' not in df.columns:
        if 'price' in df.columns and 'area' in df.columns:
            valid = df[(df['price'].notna()) & (df['area'].notna()) & (df['area'] > 0)].copy()
            valid['price_per_sqm'] = valid['price'] / valid['area']
            df = valid
        else:
            return {}
    if not df['price_per_sqm'].notna().any():
        return {}
    bins = 8 if lite else 12
    data = _histogram_bins(df['price_per_sqm'], bins, money=True)
    return {
        'type': 'bar',
        'title': 'پراکندگی قیمت هر متر',
        'labels': data['labels'],
        'datasets': [{'label': 'تعداد آگهی', 'data': data['values'], 'backgroundColor': 'rgba(16,185,129,0.75)'}],
        **_chart_meta('money', 'تومان/متر'),
    }


def chart_area_histogram(df: pd.DataFrame, lite: bool = False) -> Dict:
    if 'area' not in df.columns or not df['area'].notna().any():
        return {}
    bins = 8 if lite else 12
    data = _histogram_bins(df['area'], bins, money=False)
    return {
        'type': 'bar',
        'title': 'پراکندگی متراژ',
        'labels': data['labels'],
        'datasets': [{'label': 'تعداد آگهی', 'data': data['values'], 'backgroundColor': 'rgba(139,92,246,0.75)'}],
        **_chart_meta('area', 'متر'),
    }


def chart_scatter_price_area(df: pd.DataFrame, max_points: int = 200) -> Dict:
    if 'price' not in df.columns or 'area' not in df.columns:
        return {}
    valid = df[(df['price'].notna()) & (df['area'].notna())].head(max_points)
    points = [
        {'x': float(r['area']), 'y': val}
        for _, r in valid.iterrows()
        if (val := _safe_int(r['price'])) is not None
    ]
    if len(points) < 2:
        return {}
    return {
        'type': 'scatter',
        'title': 'رابطه متراژ و قیمت فروش',
        'datasets': [{
            'label': 'آگهی',
            'data': points,
            'backgroundColor': 'rgba(59,130,246,0.45)',
        }],
        'xAxis': 'area',
        'yAxis': 'money',
    }


def chart_neighborhood_bar(df: pd.DataFrame, top_n: int = 10) -> Dict:
    if 'neighborhood' not in df.columns:
        return {}
    work = df.copy()
    if 'price_per_sqm' not in work.columns:
        if 'price' in work.columns and 'area' in work.columns:
            work = work[
                work['price'].notna() & work['area'].notna() & (work['area'] > 0)
            ].copy()
            work['price_per_sqm'] = work['price'] / work['area']
        else:
            return {}
    work = work[work['price_per_sqm'].notna()]
    work = work[
        work['neighborhood'].notna()
        & (work['neighborhood'].astype(str).str.strip() != '')
    ]
    if len(work) < 2:
        return {}
    grouped = (
        work.groupby('neighborhood')['price_per_sqm']
        .median()
        .dropna()
        .sort_values(ascending=True)
        .tail(top_n)
    )
    if len(grouped) < 2:
        return {}
    values = [_safe_int(v) for v in grouped.values]
    pairs = [(label, val) for label, val in zip(grouped.index, values) if val is not None]
    if len(pairs) < 2:
        return {}
    return {
        'type': 'bar',
        'title': 'قیمت هر متر — مقایسه محله‌ها',
        'labels': [str(label)[:20] for label, _ in pairs],
        'datasets': [{
            'label': 'تومان/متر',
            'data': [val for _, val in pairs],
            'backgroundColor': 'rgba(245,158,11,0.75)',
        }],
        'horizontal': True,
        **_chart_meta('money', 'تومان/متر'),
    }


def chart_rooms_bar(df: pd.DataFrame) -> Dict:
    if 'rooms' not in df.columns:
        return {}
    counts = df['rooms'].replace('', pd.NA).dropna().value_counts().head(8)
    if len(counts) < 1:
        return {}
    return {
        'type': 'bar',
        'title': 'توزیع تعداد اتاق',
        'labels': [str(k) for k in counts.index],
        'datasets': [{
            'label': 'تعداد آگهی',
            'data': [int(v) for v in counts.values],
            'backgroundColor': 'rgba(99,102,241,0.75)',
        }],
        **_chart_meta('count', 'آگهی'),
    }


def chart_deposit_histogram(df: pd.DataFrame) -> Dict:
    if 'deposit' not in df.columns or not df['deposit'].notna().any():
        return {}
    data = _histogram_bins(df['deposit'], 10, money=True)
    return {
        'type': 'bar',
        'title': 'توزیع ودیعه (رهن)',
        'labels': data['labels'],
        'datasets': [{'label': 'تعداد', 'data': data['values'], 'backgroundColor': 'rgba(236,72,153,0.75)'}],
        **_chart_meta('money', 'تومان'),
    }


def chart_rent_histogram(df: pd.DataFrame) -> Dict:
    if 'rent' not in df.columns or not df['rent'].notna().any():
        return {}
    data = _histogram_bins(df['rent'], 10, money=True)
    return {
        'type': 'bar',
        'title': 'توزیع اجاره ماهانه',
        'labels': data['labels'],
        'datasets': [{'label': 'تعداد', 'data': data['values'], 'backgroundColor': 'rgba(14,165,233,0.75)'}],
        **_chart_meta('money', 'تومان'),
    }


def chart_area_bucket_comparison(
    df: pd.DataFrame,
    transaction_type: str = '',
    area_segments: Optional[List[Dict]] = None,
) -> Dict:
    """میانه قیمت/متر و قیمت کل به تفکیک محدوده متراژ (داینامیک)."""
    tx = transaction_profile(transaction_type)
    labels, pps_vals, price_vals = [], [], []

    if area_segments and len(area_segments) >= 2:
        for seg in area_segments:
            labels.append(seg.get('bucket_plain', seg['bucket']))
            pdist = seg.get('pps_dist') or {}
            pr = seg.get('price_dist') or {}
            pps_vals.append(_safe_int(pdist.get('median')))
            price_vals.append(_safe_int(pr.get('median')))
    else:
        work = df.copy()
        if 'dynamic_bucket' in work.columns:
            bucket_col = 'dynamic_bucket'
        elif 'area_bucket' in work.columns:
            bucket_col = 'area_bucket'
        else:
            from workspace.services.features import area_bucket
            work['area_bucket'] = work['area'].apply(area_bucket) if 'area' in work.columns else 'نامشخص'
            bucket_col = 'area_bucket'

        for bucket in work[bucket_col].value_counts().index:
            seg = work[work[bucket_col] == bucket]
            if len(seg) < 2:
                continue
            labels.append(str(bucket))
            if tx['show_price_per_sqm'] and seg['price_per_sqm'].notna().sum() >= 2:
                pps_vals.append(_safe_int(seg['price_per_sqm'].median()))
            else:
                pps_vals.append(None)
            if tx['show_price'] and seg['price'].notna().sum() >= 2:
                price_vals.append(_safe_int(seg['price'].median()))
            else:
                price_vals.append(None)

    if len(labels) < 2:
        return {}

    datasets = []
    if any(v is not None for v in pps_vals):
        datasets.append({
            'label': 'میانه قیمت/متر',
            'data': [v or 0 for v in pps_vals],
            'backgroundColor': 'rgba(16,185,129,0.75)',
            'yAxisID': 'y',
        })
    if any(v is not None for v in price_vals):
        datasets.append({
            'label': 'میانه قیمت کل',
            'data': [v or 0 for v in price_vals],
            'backgroundColor': 'rgba(59,130,246,0.65)',
            'yAxisID': 'y1',
        })

    if not datasets:
        return {}

    return {
        'type': 'bar',
        'title': 'قیمت هر متر در هر محدوده متراژ',
        'labels': labels,
        'datasets': datasets,
        'dual_axis': True,
        'axis': 'money',
        'unit': 'تومان',
    }


def chart_amenity_premium(df: pd.DataFrame, transaction_type: str = '') -> Dict:
    """مقایسه میانه قیمت/متر با و بدون امکانات."""
    tx = transaction_profile(transaction_type)
    if 'price_per_sqm' not in df.columns:
        return {}
    work = df[df['price_per_sqm'].notna()].copy()
    if work.empty:
        return {}

    labels, with_data, without_data = [], [], []
    for field, label in [('elevator', 'آسانسور'), ('parking', 'پارکینگ'), ('storage', 'انباری')]:
        if field not in work.columns:
            continue
        with_am = work[work[field] == True]
        without_am = work[work[field] == False]
        if len(with_am) < 3 or len(without_am) < 3:
            continue
        with_med = _safe_int(with_am['price_per_sqm'].median())
        without_med = _safe_int(without_am['price_per_sqm'].median())
        if with_med is None or without_med is None:
            continue
        labels.append(label)
        with_data.append(with_med)
        without_data.append(without_med)

    if len(labels) < 1:
        return {}

    return {
        'type': 'bar',
        'title': 'پارکینگ و آسانسور چقدر روی متری اثر دارند؟',
        'labels': labels,
        'datasets': [
            {'label': 'دارد', 'data': with_data, 'backgroundColor': 'rgba(124,58,237,0.8)'},
            {'label': 'ندارد', 'data': without_data, 'backgroundColor': 'rgba(148,163,184,0.65)'},
        ],
        'axis': 'money',
        'unit': 'تومان/متر',
    }


def chart_market_depth(report: Optional[Dict]) -> Dict:
    depth = (report or {}).get('market_depth', {})
    if not depth or not depth.get('total'):
        return {}
    return {
        'type': 'doughnut',
        'title': 'چند فایل ارزون، سر به سر و گرونه؟',
        'labels': [
            f'ارزون‌تر از بازار ({depth.get("under_pct", 0)}٪)',
            f'سر به سر ({depth.get("fair_pct", 0)}٪)',
            f'گرون‌تر از بازار ({depth.get("over_pct", 0)}٪)',
        ],
        'datasets': [{
            'data': [depth['under_market'], depth['fair_market'], depth['overpriced']],
            'backgroundColor': [
                'rgba(16,185,129,0.85)',
                'rgba(59,130,246,0.75)',
                'rgba(239,68,68,0.75)',
            ],
        }],
        'axis': 'count',
        'unit': 'فایل',
    }


def chart_percentile_price(report: Optional[Dict]) -> Dict:
    pps = (report or {}).get('price_analysis', {}).get('price_per_sqm', {})
    if not pps or pps.get('count', 0) < 3:
        return {}
    keys = ['p10', 'p25', 'p50', 'p75', 'p90']
    labels = ['ارزون‌ترین‌ها', 'پایین بازار', 'وسط بازار', 'بالای بازار', 'گرون‌ترین‌ها']
    values = [v for k in keys if (v := _safe_int(pps.get(k))) is not None]
    labels = [lbl for lbl, k in zip(labels, keys) if _safe_int(pps.get(k)) is not None]
    if len(values) < 3:
        return {}
    return {
        'type': 'bar',
        'title': 'سطح قیمت هر متر در این فایل',
        'labels': labels,
        'datasets': [{
            'label': 'قیمت هر متر',
            'data': values,
            'backgroundColor': [
                'rgba(148,163,184,0.7)', 'rgba(99,102,241,0.75)',
                'rgba(59,130,246,0.85)', 'rgba(99,102,241,0.75)',
                'rgba(148,163,184,0.7)',
            ],
        }],
        'axis': 'money',
        'unit': 'تومان/متر',
    }


def chart_amenities_coverage(report: Optional[Dict]) -> Dict:
    items = (report or {}).get('amenities_coverage', [])
    items = [i for i in items if i.get('coverage_pct') is not None]
    if len(items) < 2:
        return {}
    items = sorted(items, key=lambda x: x['coverage_pct'], reverse=True)[:8]
    return {
        'type': 'bar',
        'title': 'پوشش امکانات در فایل',
        'labels': [i['label'] for i in items],
        'datasets': [{
            'label': 'درصد فایل‌ها',
            'data': [i['coverage_pct'] for i in items],
            'backgroundColor': 'rgba(124,58,237,0.75)',
        }],
        'axis': 'percent',
        'unit': '٪',
    }


def chart_value_distribution(market_stats: Dict, report: Optional[Dict] = None) -> Dict:
    c = chart_market_depth(report)
    if c:
        return c
    vd = (market_stats or {}).get('value_distribution')
    if not vd:
        return {}
    return {
        'type': 'doughnut',
        'title': 'چند فایل زیر/سر/بالای بازار هستند؟',
        'labels': ['زیر بازار', 'متعارف', 'بالای بازار'],
        'datasets': [{
            'data': [vd['below_market'], vd['fair'], vd['above_market']],
            'backgroundColor': [
                'rgba(16,185,129,0.85)',
                'rgba(59,130,246,0.75)',
                'rgba(239,68,68,0.75)',
            ],
        }],
        'axis': 'count',
        'unit': 'آگهی',
    }


def chart_area_segment_share(area_segments: List[Dict]) -> Dict:
    if not area_segments or len(area_segments) < 2:
        return {}
    return {
        'type': 'doughnut',
        'title': 'بیشتر فایل‌ها چند متری هستند؟',
        'labels': [s['bucket'] for s in area_segments],
        'datasets': [{
            'data': [s['count'] for s in area_segments],
            'backgroundColor': [
                'rgba(99,102,241,0.8)', 'rgba(59,130,246,0.75)', 'rgba(16,185,129,0.75)',
                'rgba(245,158,11,0.75)', 'rgba(239,68,68,0.7)', 'rgba(148,163,184,0.6)',
            ][:len(area_segments)],
        }],
        'axis': 'count',
        'unit': 'آگهی',
    }


def build_all_charts(
    df: pd.DataFrame,
    lite: bool = False,
    transaction_type: str = '',
    market_stats: Optional[Dict] = None,
    area_segments: Optional[List[Dict]] = None,
    report: Optional[Dict] = None,
) -> List[Dict]:
    tx = transaction_profile(transaction_type)
    charts = []

    c = chart_percentile_price(report)
    if c:
        charts.append(c)

    c = chart_area_segment_share(area_segments or [])
    if c:
        charts.append(c)

    c = chart_amenities_coverage(report)
    if c:
        charts.append(c)

    c = chart_area_bucket_comparison(df, transaction_type, area_segments)
    if c:
        charts.append(c)

    if not lite:
        if tx['show_price_per_sqm'] or tx['show_price']:
            for fn in (chart_price_per_sqm_histogram, chart_price_histogram):
                c = fn(df, lite=lite)
                if c:
                    charts.append(c)
        c = chart_scatter_price_area(df)
        if c:
            charts.append(c)

    c = chart_area_histogram(df, lite=lite)
    if c:
        charts.append(c)

    if tx['show_price_per_sqm'] or tx['show_price']:
        c = chart_neighborhood_bar(df)
        if c:
            charts.append(c)

    if not lite:
        c = chart_rooms_bar(df)
        if c:
            charts.append(c)
        if tx['show_deposit']:
            c = chart_deposit_histogram(df)
            if c:
                charts.append(c)
        if tx['show_rent']:
            c = chart_rent_histogram(df)
            if c:
                charts.append(c)
        c = chart_amenity_premium(df, transaction_type)
        if c:
            charts.append(c)

    c = chart_value_distribution(market_stats or {}, report)
    if c and c not in charts:
        charts.append(c)

    return charts


def map_markers(
    listings,
    settings=None,
    transaction_type: str = '',
    dataset_id=None,
) -> List[Dict]:
    import math

    import pandas as pd
    from django.urls import reverse

    from workspace.services.analyzer import listings_to_dataframe
    from workspace.services.display import (
        listing_map_deposit_label,
        listing_map_price_label,
        listing_map_rent_label,
        location_accuracy_for_map,
        market_tier_from_score,
        to_jalali_display,
        transaction_profile,
    )
    from workspace.services.formatting import format_area, format_toman
    from workspace.services.valuation import compute_expected_values, value_verdict

    tx = transaction_profile(transaction_type)
    listings_list = [lst for lst in listings if lst.latitude and lst.longitude]
    val_mode = 'rent' if tx['is_rent'] and not tx['is_sale'] else 'sale'

    score_map: Dict[int, Dict[str, Any]] = {}
    full_dep_map: Dict[int, int] = {}
    if listings_list:
        df = listings_to_dataframe(listings_list)
        if not df.empty:
            scored = compute_expected_values(df, mode=val_mode)
            for _, row in scored.iterrows():
                lid = row.get('listing_id')
                if lid is None or (isinstance(lid, float) and math.isnan(lid)):
                    continue
                lid = int(lid)
                vs = row.get('value_score')
                vs_num = None if vs is None or (isinstance(vs, float) and math.isnan(vs)) else float(vs)
                score_map[lid] = {
                    'value_score': vs_num,
                    'market_tier': market_tier_from_score(vs_num),
                    'verdict': value_verdict(vs_num),
                }
                fd = row.get('full_deposit')
                if fd is not None and not (isinstance(fd, float) and math.isnan(fd)):
                    full_dep_map[lid] = int(fd)

    markers = []
    for lst in listings_list:
        price_label = listing_map_price_label(lst, tx)
        deposit_label = listing_map_deposit_label(lst)
        rent_label = listing_map_rent_label(lst)

        is_consultant = 'مشاور' in (lst.business_type or '')
        platform_url = ''
        if dataset_id and lst.pk:
            platform_url = reverse(
                'workspace:listing_detail',
                kwargs={'dataset_id': dataset_id, 'listing_id': lst.pk},
            )

        loc_acc = location_accuracy_for_map(lst.data or {})
        sm = score_map.get(lst.pk, {})
        full_dep = full_dep_map.get(lst.pk) or 0
        if not full_dep and val_mode == 'rent':
            dep = lst.deposit or 0
            rent = lst.rent or 0
            if dep or rent:
                full_dep = int(dep + rent * 30)

        if val_mode == 'rent':
            filter_value = full_dep or lst.deposit or lst.rent or 0
        else:
            filter_value = lst.price or 0

        published_ts = None
        if lst.published_at:
            published_ts = int(lst.published_at.timestamp() * 1000)

        markers.append({
            'id': lst.pk,
            'lat': lst.latitude,
            'lng': lst.longitude,
            'title': lst.title,
            'price': lst.price,
            'price_label': price_label,
            'deposit_label': deposit_label,
            'rent_label': rent_label,
            'area': lst.area,
            'area_label': format_area(lst.area) if lst.area else '',
            'rooms': lst.rooms or '',
            'pps_label': format_toman(lst.price_per_sqm, per_sqm=True) if lst.price_per_sqm else '',
            'full_deposit': full_dep,
            'full_deposit_label': format_toman(full_dep) if full_dep else '',
            'neighborhood': lst.neighborhood or '',
            'city': lst.city or '',
            'business_type': lst.business_type or '',
            'seller_type': 'مشاور' if is_consultant else 'شخصی',
            'published': to_jalali_display(lst.published_at) if lst.published_at else '',
            'published_ts': published_ts,
            'token': lst.token,
            'link': lst.link,
            'platform_url': platform_url,
            'thumb': (lst.images[0] if lst.images else '') or '',
            'phone': lst.data.get('شماره تماس', lst.data.get('phone', '')),
            'is_consultant': is_consultant,
            'location_label': loc_acc.get('label', ''),
            'location_kind': loc_acc.get('kind', ''),
            'location_radius_m': int(loc_acc.get('radius_m') or 0),
            'value_score': sm.get('value_score'),
            'market_tier': sm.get('market_tier', 'unknown'),
            'verdict': sm.get('verdict', ''),
            'filter_value': filter_value,
            'value': lst.price or full_dep or lst.rent or lst.deposit or 0,
            'pps': lst.price_per_sqm or 0,
        })
    return markers
