"""تحلیل آماری و راهنمای مشاور املاک."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from workspace.services.columns import is_consultant
from workspace.services.display import market_tier_from_score, transaction_profile
from workspace.services.formatting import format_area, format_pct, format_toman, full_deposit_equiv, round_pct
from workspace.services.market_analytics import (
    build_professional_report,
    distribution_stats,
    _fmt_dist,
)
from workspace.services.market_copy import (
    bucket_plain,
    build_insights_plain,
    build_market_brief,
    enrich_factors_plain,
    enrich_scenarios_plain,
    enrich_segments_plain,
    enrich_stats_plain,
    ui_labels,
)
from workspace.services.valuation import (
    analyze_market, area_bucket, build_consultant_insights, compute_expected_values,
    enrich_dataframe, rent_monthly_equivalent, value_verdict,
)


def listings_to_dataframe(listings) -> pd.DataFrame:
    return enrich_dataframe(listings)


def _ensure_pps(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if 'price_per_sqm' not in result.columns or not result['price_per_sqm'].notna().any():
        if 'price' in result.columns and 'area' in result.columns:
            mask = (result['price'].notna()) & (result['area'].notna()) & (result['area'] > 0)
            result.loc[mask, 'price_per_sqm'] = result.loc[mask, 'price'] / result.loc[mask, 'area']
    return result


MEDIAN_RATIO_LOW = 0.05
MEDIAN_RATIO_HIGH = 10.0


def remove_outliers_iqr(series: pd.Series, factor: float = 1.5) -> Tuple[pd.Series, Dict]:
    clean = series.dropna()
    if len(clean) < 4:
        return pd.Series(True, index=series.index), {'removed': 0, 'pct': 0, 'samples': []}
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - factor * iqr, q3 + factor * iqr
    mask = (series >= low) & (series <= high) | series.isna()
    removed = int((~mask & series.notna()).sum())
    samples = series[~mask].dropna().head(3).tolist()
    return mask, {
        'removed': removed,
        'pct': round_pct(removed / max(len(series), 1) * 100),
        'samples': samples,
    }


def remove_outliers_median_ratio(
    series: pd.Series,
    *,
    low_ratio: float = MEDIAN_RATIO_LOW,
    high_ratio: float = MEDIAN_RATIO_HIGH,
) -> Tuple[pd.Series, Dict]:
    """حذف مقادیر کمتر از ۵٪ یا بیشتر از ۱۰ برابر میانه — برای قیمت‌های غیرواقعی."""
    clean = series.dropna()
    if len(clean) < 4:
        return pd.Series(True, index=series.index), {'removed': 0, 'pct': 0, 'samples': []}
    med = float(clean.median())
    if med <= 0:
        return pd.Series(True, index=series.index), {'removed': 0, 'pct': 0, 'samples': []}
    low, high = med * low_ratio, med * high_ratio
    mask = ((series >= low) & (series <= high)) | series.isna()
    removed = int((~mask & series.notna()).sum())
    samples = series[~mask].dropna().head(3).tolist()
    return mask, {
        'removed': removed,
        'pct': round_pct(removed / max(len(series), 1) * 100),
        'samples': samples,
    }


def _stats_from_distribution(dist: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """آمار قیمت از distribution_stats — بدون تولید mean جعلی."""
    if dist.get('count', 0) < 2 or 'mean' not in dist:
        return None
    return {
        'mean': int(dist['mean']),
        'median': int(dist['median']),
        'min': int(dist['min']),
        'max': int(dist['max']),
        'p10': int(dist['p10']),
        'p25': int(dist['p25']),
        'p50': int(dist['p50']),
        'p75': int(dist['p75']),
        'p90': int(dist['p90']),
        'count': dist['count'],
        'cv': dist.get('cv'),
        'median_fmt': dist['median_fmt'],
        'mean_fmt': dist['mean_fmt'],
        'range_50_fmt': dist['range_50_fmt'],
        'range_80_fmt': dist['range_80_fmt'],
        'range_fmt': dist['range_50_fmt'],
        'spread_50_pct': dist.get('spread_50_pct'),
    }


def compute_statistics(df: pd.DataFrame, transaction_type: str = '') -> Dict[str, Any]:
    df = _ensure_pps(df)
    tx = transaction_profile(transaction_type)
    stats: Dict[str, Any] = {'transaction_type': transaction_type, 'row_count': len(df), 'tx': tx}

    if tx['show_price'] and 'price' in df.columns and df['price'].notna().any():
        prices = df['price'].dropna()
        dist = _fmt_dist(distribution_stats(prices))
        price_stats = _stats_from_distribution(dist)
        if price_stats:
            stats['price'] = price_stats

    if tx['show_price_per_sqm'] and 'price_per_sqm' in df.columns and df['price_per_sqm'].notna().any():
        pps = df['price_per_sqm'].dropna()
        dist = _fmt_dist(distribution_stats(pps), per_sqm=True)
        pps_stats = _stats_from_distribution(dist)
        if pps_stats:
            stats['price_per_sqm'] = pps_stats

    if 'area' in df.columns and df['area'].notna().any():
        areas = df['area'].dropna()
        stats['area'] = {
            'mean': round(areas.mean(), 1),
            'median': round(areas.median(), 1),
            'min': round(areas.min(), 1),
            'max': round(areas.max(), 1),
            'median_fmt': format_area(areas.median()),
        }

    if tx['show_deposit'] or tx['show_rent']:
        for col, key in [('deposit', 'deposit'), ('rent', 'rent')]:
            if col == 'deposit' and not tx['show_deposit']:
                continue
            if col == 'rent' and not tx['show_rent']:
                continue
            if col in df.columns and df[col].notna().any():
                s = df[col].dropna()
                stats[key] = {
                    'median': int(s.median()),
                    'mean': int(s.mean()),
                    'median_fmt': format_toman(s.median()),
                }

    if 'business_type' in df.columns:
        consultant_count = sum(1 for bt in df['business_type'] if is_consultant(str(bt)))
        pct = round_pct(consultant_count / max(len(df), 1) * 100)
        stats['consultant_pct'] = pct
        stats['personal_pct'] = round_pct(100 - pct) if pct is not None else None

    if 'neighborhood' in df.columns:
        nb_counts = df['neighborhood'].replace('', pd.NA).dropna().value_counts()
        if len(nb_counts):
            stats['top_neighborhood'] = str(nb_counts.index[0])
            stats['top_neighborhood_count'] = int(nb_counts.iloc[0])

    stats['consultant_landscape'] = analyze_consultant_landscape(df)

    return enrich_stats_context(stats, df, tx)


def analyze_consultant_landscape(df: pd.DataFrame) -> Dict[str, Any]:
    """آمار مشاورین/آژانس‌های فعال در همین فایل."""
    if df.empty or 'business_type' not in df.columns:
        return {'has_data': False}

    work = df.copy()
    if 'consultant_name' not in work.columns:
        work['consultant_name'] = ''

    consultant_mask = work['business_type'].apply(lambda bt: is_consultant(str(bt)))
    consultants = work[consultant_mask]
    total = len(work)
    consultant_count = len(consultants)
    if consultant_count == 0:
        return {
            'has_data': False,
            'total': total,
            'consultant_count': 0,
        }

    named = consultants[
        consultants['consultant_name'].astype(str).str.strip().replace({'nan': '', 'None': ''}) != ''
    ]
    named_count = len(named)
    landscape: Dict[str, Any] = {
        'has_data': True,
        'total': total,
        'consultant_count': consultant_count,
        'consultant_pct': round_pct(consultant_count / max(total, 1) * 100),
        'named_count': named_count,
    }

    if named_count == 0:
        return landscape

    counts = named['consultant_name'].value_counts()
    top_name = str(counts.index[0])
    top_count = int(counts.iloc[0])
    landscape['top_agency'] = top_name
    landscape['top_agency_count'] = top_count
    landscape['top_agency_share_pct'] = round_pct(top_count / max(consultant_count, 1) * 100)
    landscape['agency_count'] = int(len(counts))
    landscape['top_agencies'] = [
        {
            'name': str(name),
            'count': int(cnt),
            'share_pct': round_pct(int(cnt) / max(consultant_count, 1) * 100),
        }
        for name, cnt in counts.head(5).items()
    ]

    top_nb = None
    if 'neighborhood' in named.columns:
        nb_series = named['neighborhood'].replace('', pd.NA).dropna()
        if len(nb_series):
            top_nb = str(nb_series.value_counts().index[0])
            nb_df = named[named['neighborhood'] == top_nb]
            if len(nb_df) >= 2:
                nb_counts = nb_df['consultant_name'].value_counts()
                landscape['top_neighborhood'] = top_nb
                landscape['top_neighborhood_leader'] = str(nb_counts.index[0])
                landscape['top_neighborhood_leader_count'] = int(nb_counts.iloc[0])

    return landscape


def build_consultant_landscape_lines(landscape: Dict[str, Any]) -> List[str]:
    """متن خلاصه آمار مشاورین برای بخش تحلیل."""
    if not landscape.get('has_data'):
        return []

    lines: List[str] = []
    total = landscape.get('total', 0)
    c_count = landscape.get('consultant_count', 0)
    c_pct = landscape.get('consultant_pct')
    if c_count and c_pct is not None:
        lines.append(
            f'از {total:,} آگهی، {c_count:,} مورد ({format_pct(c_pct)}) مربوط به مشاورین و آژانس‌هاست.'
        )

    named = landscape.get('named_count', 0)
    if named:
        lines.append(f'برای {named:,} آگهی مشاور، نام آژانس/مشاور ثبت شده است.')
    elif c_count:
        lines.append('نام آژانس در داده‌ها ثبت نشده — فقط نوع «مشاور» مشخص است.')

    top = landscape.get('top_agency')
    if top:
        share = landscape.get('top_agency_share_pct')
        cnt = landscape.get('top_agency_count', 0)
        share_txt = f' ({format_pct(share)} از فایل مشاورین)' if share is not None else ''
        lines.append(f'بیشترین تعداد آگهی: «{top}» با {cnt:,} فایل{share_txt}.')

    agencies = landscape.get('top_agencies') or []
    if len(agencies) > 1:
        others = ' · '.join(
            f'«{a["name"]}» ({a["count"]:,})' for a in agencies[1:4]
        )
        if others:
            lines.append(f'سایر آژانس‌های پرفایل: {others}.')

    nb = landscape.get('top_neighborhood')
    leader = landscape.get('top_neighborhood_leader')
    if nb and leader:
        lcnt = landscape.get('top_neighborhood_leader_count', 0)
        lines.append(f'در محله «{nb}»، «{leader}» با {lcnt:,} فایل بیشترین حضور را دارد.')

    agency_n = landscape.get('agency_count')
    if agency_n and agency_n > 1:
        lines.append(f'در مجموع {agency_n} آژانس/مشاور مختلف در این فایل فعال‌اند.')

    return lines


def enrich_stats_context(stats: Dict[str, Any], df: pd.DataFrame, tx: Dict[str, Any]) -> Dict[str, Any]:
    """زمینه‌سازی شاخص‌ها — ارتباط قیمت کل، متراژ و قیمت/متر."""
    if stats.get('price') and stats.get('price_per_sqm') and stats.get('area'):
        med_area = stats['area']['median']
        med_pps = stats['price_per_sqm']['median']
        implied = int(med_pps * med_area)
        med_price = stats['price']['median']
        stats['price']['median_area_fmt'] = stats['area']['median_fmt']
        stats['price']['median_pps_fmt'] = stats['price_per_sqm']['median_fmt']
        stats['price']['implied_fmt'] = format_toman(implied)
        diff = round_pct((med_price - implied) / implied * 100) if implied else None
        stats['price']['implied_diff_pct'] = diff

    if stats.get('deposit') and stats.get('rent'):
        dep, rent = stats['deposit']['median'], stats['rent']['median']
        ratio = round(dep / max(rent, 1))
        stats['deposit']['subtitle'] = f'به ازای هر ۱ میلیون اجاره، حدود {ratio} میلیون ودیعه'
        stats['rent']['subtitle'] = f'اجاره رایج · ودیعه {stats["deposit"]["median_fmt"]}'

    return enrich_stats_plain(stats, tx)


def analyze_area_segments(df: pd.DataFrame, transaction_type: str = '') -> List[Dict[str, Any]]:
    """تحلیل تفکیک‌شده بر اساس باکت متراژ."""
    tx = transaction_profile(transaction_type)
    if df.empty:
        return []

    work = _ensure_pps(df)
    if 'area_bucket' not in work.columns:
        work = work.copy()
        work['area_bucket'] = work['area'].apply(area_bucket) if 'area' in work.columns else 'نامشخص'

    bucket_order = ['زیر ۵۰', '۵۰–۷۰', '۷۰–۹۰', '۹۰–۱۲۰', '۱۲۰+', 'نامشخص']
    segments: List[Dict[str, Any]] = []

    for bucket in bucket_order:
        seg = work[work['area_bucket'] == bucket]
        if len(seg) < 2:
            continue
        row: Dict[str, Any] = {
            'bucket': bucket,
            'count': len(seg),
            'share_pct': round_pct(len(seg) / max(len(work), 1) * 100),
        }
        if seg['area'].notna().any():
            areas = seg['area'].dropna()
            row['median_area'] = round(areas.median(), 1)
            row['median_area_fmt'] = format_area(areas.median())
            row['area_range_fmt'] = f'{format_area(areas.quantile(0.25))} – {format_area(areas.quantile(0.75))}'

        if tx['show_price'] and seg['price'].notna().sum() >= 2:
            prices = seg['price'].dropna()
            row['median_price'] = int(prices.median())
            row['median_price_fmt'] = format_toman(prices.median())
            row['price_range_fmt'] = (
                f'{format_toman(prices.quantile(0.25))} – {format_toman(prices.quantile(0.75))}'
            )

        if tx['show_price_per_sqm'] and seg['price_per_sqm'].notna().sum() >= 2:
            pps = seg['price_per_sqm'].dropna()
            row['median_pps'] = int(pps.median())
            row['median_pps_fmt'] = format_toman(pps.median(), per_sqm=True)
            row['pps_range_fmt'] = (
                f'{format_toman(pps.quantile(0.25), per_sqm=True)} – '
                f'{format_toman(pps.quantile(0.75), per_sqm=True)}'
            )

        if tx['show_rent'] and 'rent_equiv' in seg.columns and seg['rent_equiv'].notna().sum() >= 2:
            rev = seg['rent_equiv'].dropna()
            row['median_rent_equiv_fmt'] = format_toman(rev.median())
            row['rent_equiv_range_fmt'] = (
                f'{format_toman(rev.quantile(0.25))} – {format_toman(rev.quantile(0.75))}'
            )

        if seg['build_year'].notna().sum() >= 2:
            years = seg['build_year'].dropna()
            row['median_build_year'] = int(years.median())

        segments.append(row)

    return segments


def build_price_scenarios(
    stats: Dict[str, Any],
    area_segments: List[Dict[str, Any]],
    tx: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """سناریوهای قیمت برای باکت‌های متراژ."""
    if not tx.get('show_price_per_sqm') or not stats.get('price_per_sqm'):
        return []

    scenarios: List[Dict[str, Any]] = []
    if area_segments:
        for seg in area_segments:
            if not seg.get('median_pps_fmt'):
                continue
            med_a = seg.get('median_area')
            med_pps = seg.get('median_pps')
            if not med_a or not med_pps:
                continue
            expected = int(med_pps * med_a)
            scenarios.append({
                'title': seg.get('bucket_plain', bucket_plain(seg['bucket'])),
                'area_fmt': seg.get('median_area_fmt', '—'),
                'count': seg['count'],
                'pps_fmt': seg['median_pps_fmt'],
                'expected_price_fmt': format_toman(expected),
                'actual_median_fmt': seg.get('median_price_fmt', '—'),
                'pps_range_fmt': seg.get('pps_range_fmt', ''),
                'note': (
                    f'{seg["count"]} آگهی ({seg.get("share_pct", 0)}٪ فایل) · '
                    f'قیمت/متر میانه {seg["median_pps_fmt"]}'
                ),
            })
        return scenarios

    med_pps = stats['price_per_sqm']['median']
    for area in (70, 90, 110, 130):
        scenarios.append({
            'title': f'سناریوی {area} متر',
            'area_fmt': format_area(area),
            'count': None,
            'pps_fmt': stats['price_per_sqm']['median_fmt'],
            'expected_price_fmt': format_toman(int(med_pps * area)),
            'actual_median_fmt': '—',
            'pps_range_fmt': stats['price_per_sqm'].get('range_fmt', ''),
            'note': f'بر اساس میانه قیمت/متر کل فایل ({stats["price_per_sqm"]["median_fmt"]})',
        })
    return scenarios


def build_factor_analysis(df: pd.DataFrame, transaction_type: str = '') -> List[Dict[str, Any]]:
    """تأثیر امکانات و سال ساخت بر قیمت/متر."""
    tx = transaction_profile(transaction_type)
    work = _ensure_pps(df)
    metric = 'price_per_sqm' if tx.get('show_price_per_sqm') else 'rent_per_sqm'
    per_sqm = metric == 'price_per_sqm'
    if metric not in work.columns or not work[metric].notna().any():
        if 'rent_equiv' in work.columns and work['rent_equiv'].notna().any():
            work = work.copy()
            mask = (work['area'].notna()) & (work['area'] > 0)
            work.loc[mask, 'rent_per_sqm'] = work.loc[mask, 'rent_equiv'] / work.loc[mask, 'area']
            metric = 'rent_per_sqm'
            per_sqm = False
        else:
            return []

    factors: List[Dict[str, Any]] = []

    for field, label in [('elevator', 'آسانسور'), ('parking', 'پارکینگ'), ('storage', 'انباری')]:
        if field not in work.columns:
            continue
        with_am = work[work[field] == True]
        without_am = work[work[field] == False]
        if len(with_am) < 3 or len(without_am) < 3:
            continue
        med_with = float(with_am[metric].median())
        med_without = float(without_am[metric].median())
        premium = round_pct((med_with - med_without) / med_without * 100) if med_without else None
        factors.append({
            'label': label,
            'with_count': len(with_am),
            'without_count': len(without_am),
            'with_share_pct': round_pct(len(with_am) / max(len(work), 1) * 100),
            'with_median_fmt': format_toman(med_with, per_sqm=per_sqm),
            'without_median_fmt': format_toman(med_without, per_sqm=per_sqm),
            'premium_pct': premium,
            'insight': (
                f'آگهی‌های دارای {label}: میانه {format_toman(med_with, per_sqm=per_sqm)} '
                f'({len(with_am)} مورد) · بدون {label}: '
                f'{format_toman(med_without, per_sqm=per_sqm)} ({len(without_am)} مورد)'
                + (f' · اختلاف {premium:+g}٪' if premium is not None else '')
            ),
        })

    if work['build_year'].notna().sum() >= 8:
        years = work['build_year'].dropna()
        med_year = int(years.median())
        newer = work[work['build_year'] >= med_year]
        older = work[work['build_year'] < med_year]
        if len(newer) >= 3 and len(older) >= 3:
            med_new = float(newer[metric].median())
            med_old = float(older[metric].median())
            premium = round_pct((med_new - med_old) / med_old * 100) if med_old else None
            factors.append({
                'label': 'سال ساخت',
                'with_count': len(newer),
                'without_count': len(older),
                'with_share_pct': round_pct(len(newer) / max(len(work), 1) * 100),
                'with_median_fmt': format_toman(med_new, per_sqm=per_sqm),
                'without_median_fmt': format_toman(med_old, per_sqm=per_sqm),
                'premium_pct': premium,
                'insight': (
                    f'ساخت جدیدتر (≥ {med_year}): {format_toman(med_new, per_sqm=per_sqm)} · '
                    f'قدیمی‌تر (< {med_year}): {format_toman(med_old, per_sqm=per_sqm)}'
                    + (f' · اختلاف {premium:+g}٪' if premium is not None else '')
                ),
            })

    return factors


def build_executive_insights(
    stats: Dict[str, Any],
    area_segments: List[Dict[str, Any]],
    factors: List[Dict[str, Any]],
    market_stats: Dict[str, Any],
    tx: Dict[str, Any],
) -> List[str]:
    """نکات کاربردی برای مشاور — زبان بازار."""
    return build_insights_plain(stats, area_segments, factors, market_stats, tx)


def build_analysis_dashboard(
    df: pd.DataFrame,
    stats: Dict[str, Any],
    market: Dict[str, Any],
    transaction_type: str = '',
    *,
    df_raw: Optional[pd.DataFrame] = None,
    outliers_report: Optional[List[Dict]] = None,
    listings=None,
    dataset_name: str = '',
    subcategory: str = '',
) -> Dict[str, Any]:
    """بسته کامل تحلیل حرفه‌ای برای صفحه Analyze."""
    tx = transaction_profile(transaction_type)
    market_stats = market.get('stats', {})

    factors = enrich_factors_plain(build_factor_analysis(df, transaction_type))
    professional = build_professional_report(
        df_raw if df_raw is not None else df,
        df,
        stats,
        market,
        transaction_type,
        outliers_report=outliers_report,
        listings=listings,
        dataset_name=dataset_name,
        subcategory=subcategory,
        factors=factors,
    )

    area_segments = enrich_segments_plain(professional['area_segments'])
    scenarios = enrich_scenarios_plain(
        build_price_scenarios(stats, area_segments, tx),
    )
    insights = professional['insights']
    market_brief = professional.get('summary') or ' '.join(insights[:2]) if insights else build_market_brief(
        stats, area_segments, market_stats, tx, stats.get('row_count', 0),
    )

    return {
        'area_segments': area_segments,
        'scenarios': scenarios,
        'factors': factors,
        'insights': insights,
        'market_brief': market_brief,
        'ui_labels': ui_labels(tx),
        'market_stats': market_stats,
        'professional': professional,
    }


def _outlier_columns(transaction_type: str = '') -> List[Tuple[str, str]]:
    tx = transaction_profile(transaction_type)
    cols: List[Tuple[str, str]] = []
    if tx['show_price']:
        cols.append(('price', 'قیمت کل'))
    if tx['show_price_per_sqm']:
        cols.append(('price_per_sqm', 'قیمت هر متر'))
    cols.append(('area', 'متراژ'))
    if tx['show_deposit']:
        cols.append(('deposit', 'ودیعه'))
    if tx['show_rent']:
        cols.append(('rent', 'اجاره'))
    return cols


def _ratio_outlier_columns(transaction_type: str = '') -> List[Tuple[str, str]]:
    tx = transaction_profile(transaction_type)
    cols: List[Tuple[str, str]] = []
    if tx['show_price']:
        cols.append(('price', 'قیمت کل (میانه)'))
    if tx['show_price_per_sqm']:
        cols.append(('price_per_sqm', 'قیمت هر متر (میانه)'))
    return cols


def compute_outliers_report(df: pd.DataFrame, transaction_type: str = '') -> List[Dict]:
    df = _ensure_pps(df)
    report = []
    for col, label in _outlier_columns(transaction_type):
        if col not in df.columns or not df[col].notna().any():
            continue
        _, info = remove_outliers_iqr(df[col])
        if info['removed']:
            report.append({'field': label, **info})
    for col, label in _ratio_outlier_columns(transaction_type):
        if col not in df.columns or not df[col].notna().any():
            continue
        _, info = remove_outliers_median_ratio(df[col])
        if info['removed']:
            report.append({'field': label, **info})
    return report


def filter_outliers(df: pd.DataFrame, transaction_type: str = '') -> pd.DataFrame:
    result = _ensure_pps(df)
    combined_mask = pd.Series(True, index=result.index)
    for col, _ in _outlier_columns(transaction_type):
        if col in result.columns and result[col].notna().any():
            mask, _ = remove_outliers_iqr(result[col])
            combined_mask &= mask
    subset = result[combined_mask]
    for col, _ in _ratio_outlier_columns(transaction_type):
        if col not in subset.columns or not subset[col].notna().any():
            continue
        ratio_mask, _ = remove_outliers_median_ratio(subset[col])
        drop_idx = subset.index[~ratio_mask]
        combined_mask.loc[drop_idx] = False
    return result[combined_mask]


def neighborhood_stats(df: pd.DataFrame, top_n: int = 10) -> List[Dict]:
    df = _ensure_pps(df)
    if 'neighborhood' not in df.columns or not df['neighborhood'].replace('', pd.NA).notna().any():
        return []
    grouped = df.groupby('neighborhood')['price_per_sqm'].agg(['median', 'count']).reset_index()
    grouped = grouped[grouped['count'] >= 2].sort_values('median', ascending=False).head(top_n)
    return [
        {
            'neighborhood': row['neighborhood'],
            'median_pps': int(row['median']),
            'median_fmt': format_toman(row['median'], per_sqm=True),
            'count': int(row['count']),
        }
        for _, row in grouped.iterrows()
    ]


def rooms_distribution(df: pd.DataFrame) -> List[Dict]:
    if 'rooms' not in df.columns:
        return []
    counts = df['rooms'].replace('', pd.NA).dropna().value_counts().head(8)
    return [{'rooms': str(k), 'count': int(v)} for k, v in counts.items()]


def find_duplicates(df: pd.DataFrame) -> List[str]:
    if 'token' not in df.columns:
        return []
    counts = df['token'].value_counts()
    return counts[counts > 1].index.tolist()


def _listing_item(row, badge: str = '', reason: str = '') -> Dict:
    pps = row.get('price_per_sqm')
    return {
        'listing_id': int(row['listing_id']) if pd.notna(row.get('listing_id')) else None,
        'token': str(row.get('token', '')),
        'title': str(row.get('title', ''))[:60],
        'neighborhood': str(row.get('neighborhood', '')),
        'area': row.get('area'),
        'area_fmt': format_area(row.get('area')) if pd.notna(row.get('area')) else '',
        'price': row.get('price'),
        'price_fmt': format_toman(row.get('price')) if pd.notna(row.get('price')) else '',
        'deposit_fmt': format_toman(row.get('deposit')) if pd.notna(row.get('deposit')) else '',
        'rent_fmt': format_toman(row.get('rent')) if pd.notna(row.get('rent')) else '',
        'price_per_sqm': int(pps) if pd.notna(pps) else None,
        'price_per_sqm_fmt': format_toman(pps, per_sqm=True) if pd.notna(pps) else '',
        'badge': badge,
        'reason': reason,
    }


def generate_consultant_guide(
    df: pd.DataFrame,
    stats: Dict,
    transaction_type: str,
    dataset_id: str = '',
) -> List[Dict]:
    """کارت‌های راهنمای مشاور — ساختارمند با لینک آگهی."""
    df = _ensure_pps(df)
    tx = transaction_profile(transaction_type)
    cards: List[Dict] = []

    # ─── خلاصه بازار ───
    summary_parts = []
    if stats.get('row_count'):
        summary_parts.append(f'توی این فایل {stats["row_count"]} آگهی فعال داریم.')
    if tx['is_rent'] and stats.get('deposit') and stats.get('rent'):
        summary_parts.append(
            f'ودیعه معمول {stats["deposit"]["median_fmt"]} و '
            f'اجاره ماهانه معمول {stats["rent"]["median_fmt"]}.'
        )
    if stats.get('price_per_sqm'):
        pps = stats['price_per_sqm']
        summary_parts.append(
            f'قیمت هر متر معمول {pps["median_fmt"]} است؛ '
            f'بیشتر فایل‌ها بین {pps["range_fmt"]} قیمت‌گذاری شدن.'
        )
    if stats.get('price'):
        summary_parts.append(
            f'قیمت فروش معمول {stats["price"]["median_fmt"]} و '
            f'بازه رایج: {stats["price"]["range_fmt"]}.'
        )
    if stats.get('area'):
        summary_parts.append(f'متراژ رایج حدود {stats["area"]["median_fmt"]}.')
    if summary_parts:
        cards.append({
            'kind': 'text',
            'title': 'خلاصه برای شما',
            'icon': 'clipboard-list',
            'content': ' '.join(summary_parts),
        })

    # ─── راهنمای مذاکره فروش ───
    if tx['show_price_per_sqm'] and stats.get('price_per_sqm'):
        med = stats['price_per_sqm']['median']
        cheap = int(med * 0.85)
        expensive = int(med * 1.15)
        cards.append({
            'kind': 'bullets',
            'title': 'راهنمای مذاکره و برچسب‌گذاری',
            'icon': 'handshake',
            'bullets': [
                f'زیر {format_toman(cheap, per_sqm=True)}: فرصت خرید — به مشتری پیشنهاد بده',
                f'{format_toman(cheap, per_sqm=True)} تا {format_toman(expensive, per_sqm=True)}: قیمت سر به سر بازار',
                f'بالای {format_toman(expensive, per_sqm=True)}: حتماً مذاکره کن یا امکانات رو چک کن',
                'قبل از بازدید، متری آگهی رو با بازار همین فایل مقایسه کن.',
            ],
        })

    # ─── راهنمای مذاکره اجاره ───
    if tx['is_rent'] and stats.get('rent'):
        med = stats['rent']['median']
        cheap = int(med * 0.9)
        expensive = int(med * 1.1)
        bullets = [
            f'زیر {format_toman(cheap)}: اجاره پایین‌تر از بازار — پیشنهاد سریع به مشتری',
            f'{format_toman(cheap)} تا {format_toman(expensive)}: اجاره متعارف بازار',
            f'بالای {format_toman(expensive)}: نیاز به مذاکره یا بررسی امکانات',
        ]
        if stats.get('deposit'):
            dep_med = stats['deposit']['median']
            bullets.append(f'ودیعه معمول بازار: {stats["deposit"]["median_fmt"]}')
            bullets.append(f'نسبت تقریبی رهن به اجاره: {round(dep_med / max(med, 1))}:۱')
        cards.append({
            'kind': 'bullets',
            'title': 'راهنمای مذاکره اجاره',
            'icon': 'key',
            'bullets': bullets,
        })

    # ─── محله‌ها ───
    nb_stats = neighborhood_stats(df, 8) if stats.get('price_per_sqm') else []
    if nb_stats:
        cards.append({
            'kind': 'bullets',
            'title': 'مقایسه محله‌ها (قیمت هر متر)',
            'icon': 'map-marker-alt',
            'bullets': [
                f'{n["neighborhood"]}: {n["median_fmt"]} — {n["count"]} آگهی'
                for n in nb_stats
            ],
        })

    # ─── تحلیل چندبعدی (متراژ، سال ساخت، امکانات، رهن/اجاره) ───
    market = analyze_market(df, transaction_type)
    valuation_cards = build_consultant_insights(df, market, transaction_type)
    # جایگزین پیشنهادهای ساده قبلی
    cards = [c for c in cards if c.get('kind') != 'listings' or 'پیشنهاد' not in c.get('title', '')]
    cards.extend(valuation_cards)

    # ─── ترکیب آگهی‌دهنده ───
    if stats.get('consultant_pct') is not None:
        cp = stats['consultant_pct']
        pp = stats.get('personal_pct', round_pct(100 - cp))
        cards.append({
            'kind': 'text',
            'title': 'ترکیب آگهی‌دهندگان',
            'icon': 'users',
            'content': (
                f'{format_pct(cp)} آگهی از مشاورین املاک و {format_pct(pp)} شخصی است. '
                + ('بازار عمدتاً فایل مشاور است — رقابت روی سرعت و کیفیت فایل مهم است.'
                   if cp and cp > 60 else
                   'سهم آگهی شخصی بالاست — فرصت ارتباط مستقیم با مالک بیشتر است.')
            ),
        })

    landscape_lines = build_consultant_landscape_lines(stats.get('consultant_landscape') or {})
    if landscape_lines:
        cards.append({
            'kind': 'bullets',
            'title': 'آمار مشاورین منطقه',
            'icon': 'user-tie',
            'bullets': landscape_lines,
        })

    # ─── توزیع اتاق ───
    rooms = rooms_distribution(df)
    if rooms:
        cards.append({
            'kind': 'bullets',
            'title': 'توزیع تعداد اتاق',
            'icon': 'door-open',
            'bullets': [f'{r["rooms"]} خواب: {r["count"]} آگهی' for r in rooms],
        })

    # ─── تکراری ───
    dups = find_duplicates(df)
    if dups:
        cards.append({
            'kind': 'text',
            'title': 'هشدار آگهی تکراری',
            'icon': 'exclamation-triangle',
            'content': (
                f'{len(dups)} شناسه تکراری یافت شد. '
                'احتمال نشر مجدد یک ملک توسط چند مشاور یا آگهی قدیمی/جدید وجود دارد.'
            ),
        })

    # ─── اجاره ───
    if tx['show_deposit'] and tx['show_rent'] and stats.get('deposit') and stats.get('rent'):
        dep = stats['deposit']['median']
        rent = stats['rent']['median']
        ratio = round(dep / max(rent, 1))
        cards.append({
            'kind': 'bullets',
            'title': 'تحلیل رهن و اجاره',
            'icon': 'home',
            'bullets': [
                f'ودیعه (رهن) معمول: {stats["deposit"]["median_fmt"]}',
                f'اجاره ماهانه معمول: {stats["rent"]["median_fmt"]}',
                f'نسبت رهن به اجاره در بازار: حدود {ratio}:۱',
                'برای تبدیل رهن به اجاره از ابزار «ودیعه ↔ اجاره» استفاده کن.',
            ],
        })

    # ─── نکته عملیاتی ───
    cards.append({
        'kind': 'bullets',
        'title': 'چک‌لیست کار مشاور با این فایل',
        'icon': 'check-double',
        'bullets': [
            'فایل‌های زیر بازار رو اول به مشتری نشون بده.',
            'قبل از بازدید، متری آگهی رو با بازار همین فایل مقایسه کن.',
            'برای مذاکره، بازه رایج قیمت (نه فقط یک عدد) رو مبنا بگیر.',
            'آگهی تکراری رو یکی کن تا مشتری گیج نشه.',
        ],
    })

    return cards


def benchmark_listing(listing, df: pd.DataFrame, transaction_type: str = '') -> Dict:
    tx = transaction_profile(transaction_type)
    result = {'token': listing.token, 'title': listing.title}
    if df.empty:
        return result

    # df از listings_to_dataframe قبلاً enrich شده است
    enriched = df if 'full_deposit' in df.columns else enrich_dataframe(df)
    mode = 'rent' if tx['is_rent'] and not tx['show_price_per_sqm'] else 'sale'
    if tx['is_mixed']:
        mode = 'rent' if (listing.rent or listing.deposit) and not listing.price else 'sale'
    scored = compute_expected_values(enriched, mode=mode)
    row = scored[scored['listing_id'] == listing.pk]
    if row.empty:
        return result
    r = row.iloc[0]
    score = r.get('value_score')

    if mode == 'rent':
        full_dep = r.get('full_deposit')
        if pd.isna(full_dep) or full_dep is None:
            full_dep = full_deposit_equiv(listing.deposit, listing.rent, 30)
        result['metric'] = 'full_deposit'
        result['label'] = 'رهن کامل معادل'
        listing_metric = None
        try:
            if full_dep is not None and full_dep == full_dep:
                listing_metric = float(full_dep)
        except (TypeError, ValueError):
            listing_metric = None
        result['listing_metric'] = listing_metric
        result['price_per_sqm_fmt'] = format_toman(listing_metric) if listing_metric else '—'
        med = scored['full_deposit'].median()
        market_median = float(med) if pd.notna(med) else None
        result['market_median'] = market_median
        result['market_median_fmt'] = format_toman(market_median) if market_median is not None else '—'
        if listing.rent == 0 and (listing.deposit or 0) > 0:
            result['note'] = 'رهن کامل — مقایسه بر اساس رهن کامل معادل'
    else:
        pps = listing.price_per_sqm
        if pps is None or (isinstance(pps, float) and pd.isna(pps)):
            pps = r.get('price_per_sqm')
        result['metric'] = 'price_per_sqm'
        result['label'] = 'قیمت هر متر'
        listing_metric = None
        try:
            if pps is not None and pps == pps:
                listing_metric = float(pps)
        except (TypeError, ValueError):
            listing_metric = None
        result['listing_metric'] = listing_metric
        result['price_per_sqm_fmt'] = format_toman(listing_metric, per_sqm=True) if listing_metric else '—'
        med = scored['price_per_sqm'].median()
        market_median = float(med) if pd.notna(med) else None
        result['market_median'] = market_median
        result['market_median_fmt'] = format_toman(market_median, per_sqm=True) if market_median is not None else '—'

    result['diff_pct'] = None
    try:
        if score is not None and not pd.isna(score):
            result['diff_pct'] = round(float(score), 1)
    except (TypeError, ValueError):
        result['diff_pct'] = None
    listing_metric = result.get('listing_metric')
    market_median = result.get('market_median')
    score_num = result['diff_pct']
    if (
        score_num is None
        and listing_metric is not None
        and market_median not in (None, 0)
        and market_median == market_median
    ):
        try:
            score_num = round((float(listing_metric) - float(market_median)) / float(market_median) * 100, 1)
        except (TypeError, ValueError, ZeroDivisionError):
            score_num = None
    _apply_benchmark_score(result, score_num)
    result['sample_count'] = int(len(scored))
    if listing_metric is not None and market_median is not None:
        diff_amount = listing_metric - market_median
        result['diff_amount'] = round(diff_amount, 0)
        per_sqm = mode != 'rent'
        result['diff_amount_fmt'] = format_toman(abs(diff_amount), per_sqm=per_sqm)
    else:
        result['diff_amount'] = None
        result['diff_amount_fmt'] = ''
    return result


def _apply_benchmark_score(result: Dict, score_num: Optional[float]) -> None:
    result['diff_pct'] = score_num
    result['value_score'] = score_num
    result['market_tier'] = market_tier_from_score(score_num)
    if score_num is not None and score_num <= -12:
        result['verdict'] = 'زیر بازار — فرصت مناسب برای مشتری'
    elif score_num is not None and score_num >= 12:
        result['verdict'] = 'بالای بازار — پیشنهاد مذاکره'
    elif score_num is not None:
        result['verdict'] = 'در محدوده متعادل بازار'
    else:
        result['verdict'] = value_verdict(score_num)
