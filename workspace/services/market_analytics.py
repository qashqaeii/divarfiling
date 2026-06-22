"""تحلیل حرفه‌ای بازار — Percentile، عمق بازار، امتیاز فرصت و اعتماد."""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from workspace.services.display import transaction_profile
from workspace.services.features import assign_standard_area_bucket, standard_area_bucket_edges
from workspace.services.formatting import format_area, format_pct, format_rent_conversion_rule, format_toman, round_pct
from workspace.services.valuation import rent_monthly_equivalent, standard_deposit_rent_ratio

MIN_SEGMENT = 3
CURRENT_JALALI_YEAR = 1404

EXTENDED_AMENITIES = [
    ('elevator', 'آسانسور'),
    ('parking', 'پارکینگ'),
    ('storage', 'انباری'),
    ('balcony', 'بالکن'),
    ('lobby', 'لابی'),
    ('pool', 'استخر'),
    ('roof_garden', 'روف گاردن'),
    ('jacuzzi', 'جکوزی'),
    ('gym', 'سالن ورزش'),
]

CORE_OPPORTUNITY_AMENITIES = EXTENDED_AMENITIES[:3]
SECONDARY_OPPORTUNITY_AMENITIES = EXTENDED_AMENITIES[3:]

STAR_LABELS = [
    (80, '★★★★★', 'فرصت بسیار خوب'),
    (65, '★★★★', 'فرصت خوب'),
    (45, '★★★', 'معمولی'),
    (25, '★★', 'ضعیف'),
    (0, '★', 'بسیار گران'),
]

LIQUIDITY_LABELS = [
    (80, '★★★★★', 'نقدشوندگی بسیار بالا'),
    (65, '★★★★', 'بالا'),
    (45, '★★★', 'متوسط'),
    (25, '★★', 'پایین'),
    (0, '★', 'ضعیف'),
]

CONFIDENCE_LABELS = [
    (85, 'بسیار بالا'),
    (70, 'بالا'),
    (50, 'متوسط'),
    (30, 'پایین'),
    (0, 'ضعیف'),
]


def _score_label(score: float, labels: List[Tuple]) -> Tuple[str, str]:
    for threshold, stars, text in labels:
        if score >= threshold:
            return stars, text
    return labels[-1][1], labels[-1][2]


def _cv(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < 2:
        return 0.0
    mean = clean.mean()
    if not mean:
        return 0.0
    return float(clean.std() / mean)


def distribution_stats(series: pd.Series) -> Dict[str, Any]:
    """آمار توزیع کامل — میانگین، میانه، P10–P90."""
    clean = series.dropna()
    if len(clean) < 2:
        return {'count': len(clean)}
    return {
        'count': len(clean),
        'mean': float(clean.mean()),
        'median': float(clean.median()),
        'p10': float(clean.quantile(0.10)),
        'p25': float(clean.quantile(0.25)),
        'p50': float(clean.quantile(0.50)),
        'p75': float(clean.quantile(0.75)),
        'p90': float(clean.quantile(0.90)),
        'min': float(clean.min()),
        'max': float(clean.max()),
        'cv': round(_cv(clean) * 100, 1),
    }


def _fmt_dist(
    dist: Dict[str, Any],
    *,
    money: bool = False,
    per_sqm: bool = False,
    area: bool = False,
) -> Dict[str, Any]:
    if dist.get('count', 0) < 2:
        return dist
    fmt = format_area if area else (lambda v: format_toman(v, per_sqm=per_sqm))
    dist = dict(dist)
    dist['mean_fmt'] = fmt(dist['mean'])
    dist['median_fmt'] = fmt(dist['median'])
    dist['p10_fmt'] = fmt(dist['p10'])
    dist['p25_fmt'] = fmt(dist['p25'])
    dist['p50_fmt'] = fmt(dist['p50'])
    dist['p75_fmt'] = fmt(dist['p75'])
    dist['p90_fmt'] = fmt(dist['p90'])
    dist['range_50_fmt'] = f'{dist["p25_fmt"]} تا {dist["p75_fmt"]}'
    dist['range_80_fmt'] = f'{dist["p10_fmt"]} تا {dist["p90_fmt"]}'
    dist['spread_50_pct'] = round_pct((dist['p75'] - dist['p25']) / dist['p50'] * 100) if dist['p50'] else None
    return dist


def _round_edge(val: float, *, down: bool) -> int:
    step = 5 if val < 150 else (10 if val < 300 else 20)
    if down:
        return int(math.floor(val / step) * step)
    return int(math.ceil(val / step) * step)


def dynamic_area_bucket_edges(
    areas: pd.Series,
    min_size: int = MIN_SEGMENT,
    max_buckets: int = 6,
) -> List[Tuple[float, float, str]]:
    clean = areas.dropna().sort_values()
    n = len(clean)
    if n < min_size:
        return []
    if n < min_size * 2:
        lo, hi = float(clean.min()), float(clean.max())
        return [(lo, hi, f'{int(lo)}–{int(hi)} متر')]

    max_k = min(max_buckets, n // min_size)
    for k in range(max_k, 1, -1):
        quantiles = [clean.quantile(i / k) for i in range(k + 1)]
        edges: List[Tuple[float, float, str]] = []
        counts: List[int] = []
        for i in range(k):
            lo = float(clean.min()) if i == 0 else _round_edge(quantiles[i], down=True)
            hi = float(clean.max()) if i == k - 1 else _round_edge(quantiles[i + 1], down=False)
            if hi <= lo:
                continue
            label = f'{int(lo)}–{int(hi)} متر'
            edges.append((lo, hi, label))
            if i == k - 1:
                mask = (clean >= lo) & (clean <= hi)
            else:
                mask = (clean >= lo) & (clean < hi)
            counts.append(int(mask.sum()))
        if edges and all(c >= min_size for c in counts):
            return edges
    lo, hi = float(clean.min()), float(clean.max())
    return [(lo, hi, f'{int(lo)}–{int(hi)} متر')]


def assign_dynamic_bucket(area: float, edges: List[Tuple[float, float, str]]) -> str:
    if not edges or not area or area <= 0:
        return 'نامشخص'
    for i, (lo, hi, label) in enumerate(edges):
        if i == len(edges) - 1:
            if lo <= area <= hi:
                return label
        elif lo <= area < hi:
            return label
    return edges[-1][2]


def analyze_dynamic_area_segments(
    df: pd.DataFrame,
    transaction_type: str = '',
) -> List[Dict[str, Any]]:
    tx = transaction_profile(transaction_type)
    if df.empty or 'area' not in df.columns:
        return []

    work = df.copy()
    edges = standard_area_bucket_edges(work['area'].dropna())
    if not edges:
        return []

    work['dynamic_bucket'] = work['area'].apply(lambda a: assign_standard_area_bucket(a, edges))
    segments: List[Dict[str, Any]] = []
    total = len(work)

    for _lo, _hi, label in edges:
        seg = work[work['dynamic_bucket'] == label]
        if len(seg) < MIN_SEGMENT:
            continue
        row: Dict[str, Any] = {
            'bucket': label,
            'bucket_plain': label,
            'count': len(seg),
            'share_pct': round_pct(len(seg) / max(total, 1) * 100),
        }
        if seg['area'].notna().any():
            ad = distribution_stats(seg['area'])
            row['median_area'] = round(ad['median'], 1)
            row['median_area_fmt'] = format_area(ad['median'])
            row['area_dist'] = _fmt_dist(ad, area=True)

        if tx['show_price_per_sqm'] and seg['price_per_sqm'].notna().sum() >= MIN_SEGMENT:
            pdist = _fmt_dist(distribution_stats(seg['price_per_sqm']), per_sqm=True)
            row['pps_dist'] = pdist
            row['median_pps_fmt'] = pdist['median_fmt']
            row['pps_range_50_fmt'] = pdist['range_50_fmt']
            row['pps_range_80_fmt'] = pdist['range_80_fmt']

        if tx['show_price'] and seg['price'].notna().sum() >= MIN_SEGMENT:
            pr = _fmt_dist(distribution_stats(seg['price']))
            row['price_dist'] = pr
            row['median_price_fmt'] = pr['median_fmt']
            row['price_range_50_fmt'] = pr['range_50_fmt']
            row['price_range_80_fmt'] = pr['range_80_fmt']

        if tx['show_rent'] and 'rent' in seg.columns and seg['rent'].replace(0, pd.NA).notna().sum() >= MIN_SEGMENT:
            rv = _fmt_dist(distribution_stats(seg['rent'].replace(0, pd.NA).dropna()))
            row['median_rent_fmt'] = rv['median_fmt']
            row['rent_range_50_fmt'] = rv['range_50_fmt']

        if tx['show_deposit'] and 'deposit' in seg.columns and seg['deposit'].replace(0, pd.NA).notna().sum() >= MIN_SEGMENT:
            dv = _fmt_dist(distribution_stats(seg['deposit'].replace(0, pd.NA).dropna()))
            row['median_deposit_fmt'] = dv['median_fmt']

        if tx['is_rent'] and 'full_deposit' in seg.columns and seg['full_deposit'].notna().sum() >= MIN_SEGMENT:
            fd = _fmt_dist(distribution_stats(seg['full_deposit'].dropna()))
            row['full_deposit_dist'] = fd
            row['median_full_deposit_fmt'] = fd['median_fmt']
            row['full_deposit_range_50_fmt'] = fd['range_50_fmt']

        if seg['build_year'].notna().sum() >= MIN_SEGMENT:
            row['median_build_year'] = int(seg['build_year'].dropna().median())

        segments.append(row)
    return segments


def _full_mortgage_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """تحلیل رهن کامل — زبان بازار."""
    if 'rent' not in df.columns or 'deposit' not in df.columns:
        return {}
    fm = df[(df['rent'].fillna(0) == 0) & (df['deposit'].fillna(0) > 0)]
    if fm.empty:
        return {}
    ratio = standard_deposit_rent_ratio()
    med_dep = float(fm['deposit'].median())
    equiv = rent_monthly_equivalent(0, int(med_dep), ratio)
    return {
        'count': len(fm),
        'median_deposit': int(med_dep),
        'median_deposit_fmt': format_toman(med_dep),
        'median_equiv_fmt': format_toman(equiv) if equiv else '—',
        'share_pct': round_pct(len(fm) / max(len(df), 1) * 100),
    }


def market_depth_distribution(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """عمق بازار بر اساس P40 و P60."""
    clean = df[col].dropna()
    if len(clean) < 5:
        return {}
    p40 = float(clean.quantile(0.40))
    p60 = float(clean.quantile(0.60))
    under = int((clean < p40).sum())
    fair = int(((clean >= p40) & (clean <= p60)).sum())
    over = int((clean > p60).sum())
    total = len(clean)
    return {
        'p40': p40,
        'p60': p60,
        'p40_fmt': format_toman(p40, per_sqm=(col in ('price_per_sqm', 'rent_per_sqm'))),
        'p60_fmt': format_toman(p60, per_sqm=(col in ('price_per_sqm', 'rent_per_sqm'))),
        'under_market': under,
        'fair_market': fair,
        'overpriced': over,
        'under_pct': round_pct(under / total * 100),
        'fair_pct': round_pct(fair / total * 100),
        'over_pct': round_pct(over / total * 100),
        'total': total,
    }


def neighborhood_price_analysis(
    df: pd.DataFrame,
    transaction_type: str = '',
    min_count: int = 3,
) -> List[Dict[str, Any]]:
    tx = transaction_profile(transaction_type)
    if 'neighborhood' not in df.columns:
        return []

    results: List[Dict[str, Any]] = []
    grouped = df[df['neighborhood'].astype(str).str.strip() != ''].groupby('neighborhood')
    for nb, grp in grouped:
        if len(grp) < min_count:
            continue
        row: Dict[str, Any] = {'neighborhood': str(nb), 'count': len(grp)}
        if tx['show_price'] and grp['price'].notna().sum() >= min_count:
            row['price'] = _fmt_dist(distribution_stats(grp['price']))
        if tx['show_price_per_sqm'] and grp['price_per_sqm'].notna().sum() >= min_count:
            row['price_per_sqm'] = _fmt_dist(distribution_stats(grp['price_per_sqm']), per_sqm=True)
        if tx['show_rent'] and grp['rent'].notna().sum() >= min_count:
            row['rent'] = _fmt_dist(distribution_stats(grp['rent'].dropna()))
        if (tx['show_deposit'] or tx['show_rent']) and 'full_deposit' in grp.columns and grp['full_deposit'].notna().sum() >= min_count:
            row['full_deposit'] = _fmt_dist(distribution_stats(grp['full_deposit'].dropna()))
        if tx['show_deposit'] and grp['deposit'].notna().sum() >= min_count:
            row['deposit'] = _fmt_dist(distribution_stats(grp['deposit'].dropna()))
        results.append(row)

    def _sort_key(x):
        if x.get('full_deposit'):
            return x['full_deposit'].get('median', 0)
        if x.get('price_per_sqm'):
            return x['price_per_sqm'].get('median', 0)
        if x.get('rent'):
            return x['rent'].get('median', 0)
        return x.get('price', {}).get('median', 0)

    results.sort(key=_sort_key, reverse=True)
    return results[:12]


def build_year_analysis(df: pd.DataFrame, current_year: int = CURRENT_JALALI_YEAR) -> Dict[str, Any]:
    if 'build_year' not in df.columns or not df['build_year'].notna().any():
        return {}
    years = df['build_year'].dropna()
    n = len(years)
    ages = current_year - years
    under_5 = int((ages < 5).sum())
    under_10 = int((ages < 10).sum())
    return {
        'median_year': int(years.median()),
        'median_age': round(float(ages.median()), 1),
        'min_year': int(years.min()),
        'max_year': int(years.max()),
        'under_5_count': under_5,
        'under_5_pct': round_pct(under_5 / n * 100),
        'under_10_count': under_10,
        'under_10_pct': round_pct(under_10 / n * 100),
        'new_ratio_pct': round_pct(under_5 / n * 100),
    }


def amenities_coverage(df: pd.DataFrame) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    n = len(df)
    if not n:
        return items
    for field, label in EXTENDED_AMENITIES:
        if field not in df.columns:
            continue
        col = df[field]
        known = col.notna()
        if not known.any():
            continue
        has = col.fillna(False).astype(bool)
        items.append({
            'key': field,
            'label': label,
            'count': int(has.sum()),
            'coverage_pct': round_pct(has.sum() / n * 100),
            'known_pct': round_pct(known.sum() / n * 100),
        })
    return items


def analyze_amenity_valuation(df: pd.DataFrame, transaction_type: str = '') -> Dict[str, Any]:
    """اثر امکانات و سال ساخت روی قیمت."""
    tx = transaction_profile(transaction_type)
    if tx.get('is_rent'):
        metric = 'full_deposit' if 'full_deposit' in df.columns else 'rent_equiv'
        metric_label = 'رهن کامل'
    elif tx.get('show_price_per_sqm') and 'price_per_sqm' in df.columns:
        metric = 'price_per_sqm'
        metric_label = 'قیمت هر متر'
    else:
        return {}

    if metric not in df.columns or df[metric].notna().sum() < MIN_SEGMENT:
        return {}

    from workspace.services.valuation import (
        CORE_AMENITY_FIELDS,
        SECONDARY_AMENITY_FIELDS,
        SECONDARY_AMENITY_LABELS,
        compute_amenity_market_premiums,
    )

    work = df[df[metric].notna()].copy()
    premiums = compute_amenity_market_premiums(work, metric)
    labels = {'elevator': 'آسانسور', 'parking': 'پارکینگ', 'storage': 'انباری'}
    items: List[Dict[str, Any]] = []
    secondary_items: List[Dict[str, Any]] = []

    def _gap_item(field: str, label: str, *, secondary: bool = False) -> None:
        if field not in work.columns:
            return
        with_am = work[work[field] == True]
        without_am = work[work[field] == False]
        if len(with_am) < MIN_SEGMENT or len(without_am) < MIN_SEGMENT:
            return
        med_with = float(with_am[metric].median())
        med_without = float(without_am[metric].median())
        gap_pct = round_pct((med_with - med_without) / med_without * 100) if med_without else 0
        entry = {
            'key': field,
            'label': label,
            'gap_pct': gap_pct,
            'with_median_fmt': format_toman(med_with, per_sqm=(metric == 'price_per_sqm')),
            'without_median_fmt': format_toman(med_without, per_sqm=(metric == 'price_per_sqm')),
            'with_count': len(with_am),
            'without_count': len(without_am),
        }
        if secondary:
            secondary_items.append(entry)
        else:
            entry['premium_pct'] = premiums.get(field, 0)
            items.append(entry)

    for field in CORE_AMENITY_FIELDS:
        _gap_item(field, labels.get(field, field))

    for field in SECONDARY_AMENITY_FIELDS:
        _gap_item(field, SECONDARY_AMENITY_LABELS.get(field, field), secondary=True)

    full_mask = pd.Series(True, index=work.index)
    bare_mask = pd.Series(True, index=work.index)
    for field in CORE_AMENITY_FIELDS:
        if field not in work.columns:
            full_mask = pd.Series(False, index=work.index)
            bare_mask = pd.Series(False, index=work.index)
            break
        full_mask &= work[field] == True
        bare_mask &= work[field] == False

    full_vs_bare: Dict[str, Any] = {}
    full_sub = work[full_mask]
    bare_sub = work[bare_mask]
    if len(full_sub) >= MIN_SEGMENT and len(bare_sub) >= MIN_SEGMENT:
        med_full = float(full_sub[metric].median())
        med_bare = float(bare_sub[metric].median())
        gap = round_pct((med_full - med_bare) / med_bare * 100) if med_bare else 0
        full_vs_bare = {
            'gap_pct': gap,
            'full_median_fmt': format_toman(med_full, per_sqm=(metric == 'price_per_sqm')),
            'bare_median_fmt': format_toman(med_bare, per_sqm=(metric == 'price_per_sqm')),
            'full_count': len(full_sub),
            'bare_count': len(bare_sub),
        }

    build_year_gap: Dict[str, Any] = {}
    if 'build_year' in work.columns:
        years = work['build_year'].dropna()
        if len(years) >= MIN_SEGMENT * 2:
            med_year = float(years.median())
            newer = work[work['build_year'] >= med_year]
            older = work[work['build_year'] < med_year]
            if len(newer) >= MIN_SEGMENT and len(older) >= MIN_SEGMENT:
                med_new = float(newer[metric].median())
                med_old = float(older[metric].median())
                ygap = round_pct((med_new - med_old) / med_old * 100) if med_old else 0
                build_year_gap = {
                    'median_year': int(med_year),
                    'gap_pct': ygap,
                    'newer_median_fmt': format_toman(med_new, per_sqm=(metric == 'price_per_sqm')),
                    'older_median_fmt': format_toman(med_old, per_sqm=(metric == 'price_per_sqm')),
                    'newer_count': len(newer),
                    'older_count': len(older),
                }

    headline = ''
    if full_vs_bare.get('gap_pct', 0) >= 5:
        headline = (
            f'فول امکانات (آسانسور+پارکینگ+انباری) در این بازار حدود {full_vs_bare["gap_pct"]}٪ '
            f'بالاتر از واحد بدون امکانات است ({metric_label}).'
        )
    elif build_year_gap.get('gap_pct', 0) >= 5:
        headline = (
            f'واحدهای نوسازتر (از {build_year_gap["median_year"]}) حدود '
            f'{build_year_gap["gap_pct"]}٪ بالاتر از قدیمی‌ترها ({metric_label}).'
        )
    elif items:
        top = max(items, key=lambda x: abs(x.get('gap_pct') or 0))
        if abs(top.get('gap_pct') or 0) >= 3:
            headline = f'{top["label"]} حدود {abs(top["gap_pct"])}٪ روی {metric_label} اثر دارد.'
    elif secondary_items:
        top = max(secondary_items, key=lambda x: abs(x.get('gap_pct') or 0))
        if abs(top.get('gap_pct') or 0) >= 2:
            headline = f'{top["label"]} حدود {abs(top["gap_pct"])}٪ روی {metric_label} اثر دارد.'

    if not items and not full_vs_bare and not secondary_items and not build_year_gap:
        return {}

    return {
        'metric_label': metric_label,
        'items': items,
        'secondary_items': secondary_items,
        'full_vs_bare': full_vs_bare,
        'build_year_gap': build_year_gap,
        'headline': headline,
        'note': 'در ارزش‌گذاری هر آگهی، سال ساخت، امکانات اصلی و ثانویه (بالکن، استخر و …) لحاظ می‌شود.',
    }


def _clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def compute_opportunity_score(row: pd.Series, df: pd.DataFrame, metric: str) -> Dict[str, Any]:
    """امتیاز فرصت — قیمت + سال ساخت + امکانات + متراژ."""
    price_score = 22.0
    age_score = 28.0
    amen_score = 28.0
    area_score = 22.0

    vs = row.get('value_score')
    if vs is not None and not pd.isna(vs):
        price_score = _clamp(22 - float(vs) * 0.55)

    year = row.get('build_year')
    if year is not None and not pd.isna(year) and 'build_year' in df.columns and df['build_year'].notna().any():
        med_year = float(df['build_year'].dropna().median())
        diff = float(year) - med_year
        age_score = _clamp(28 + diff * 2.2)
        year_adj = row.get('build_year_adjustment')
        if year_adj is not None and not pd.isna(year_adj) and float(year_adj) > 1.04:
            age_score = _clamp(age_score + 4)

    tier = row.get('amenity_tier')
    rel_amen = row.get('amenity_score')
    if rel_amen is not None and not pd.isna(rel_amen):
        amen_score = _clamp(float(rel_amen) * 0.30)
    else:
        amen_fields = [f for f, _ in CORE_OPPORTUNITY_AMENITIES if f in df.columns]
        if amen_fields:
            row_amen = sum(1 for f in amen_fields if row.get(f) is True)
            seg_amen = df[amen_fields].apply(
                lambda r: sum(1 for f in amen_fields if r.get(f) is True), axis=1,
            )
            med_amen = float(seg_amen.median()) if len(seg_amen) else 1.5
            amen_score = _clamp(28 + (row_amen - med_amen) * 10)

    if tier == 'full':
        amen_score = _clamp(amen_score + 8)
    elif tier == 'bare':
        amen_score = _clamp(amen_score - 6)

    if row.get('balcony') is True:
        amen_score = _clamp(amen_score + 4)
    elif row.get('balcony') is False and 'balcony' in df.columns:
        known = df['balcony'].notna()
        if known.any() and df.loc[known, 'balcony'].astype(bool).mean() >= 0.5:
            amen_score = _clamp(amen_score - 3)

    sec_bonus = sum(2 for f, _ in SECONDARY_OPPORTUNITY_AMENITIES[1:] if row.get(f) is True)
    amen_score = _clamp(amen_score + sec_bonus)

    bucket = row.get('dynamic_bucket') or row.get('area_bucket', '')
    if bucket and 'dynamic_bucket' in df.columns:
        share = (df['dynamic_bucket'] == bucket).mean()
        area_score = _clamp(14 + share * 36)

    total = round(price_score + age_score + amen_score + area_score)
    stars, label = _score_label(total, STAR_LABELS)
    return {
        'score': total,
        'stars': stars,
        'label': label,
        'price_score': round(price_score),
        'age_score': round(age_score),
        'amenities_score': round(amen_score),
        'area_score': round(area_score),
        'amenity_tier': tier or 'unknown',
    }


OUT_OF_AREA_KEYWORDS = (
    'هشتگرد', 'شهریار', 'گرمدره', 'شهرری', 'ورامین', 'پردیس', 'اندیشه',
    'پرند', 'ملارد', 'رباطکریم', 'اسلامشهر', 'بومهن', 'دماوند', 'فشم',
    'لواسان', 'شمیرانات', 'کرج', 'نظرآباد',
)
VILLA_TITLE_KEYWORDS = ('ویلا', 'باغ', 'باغچه', 'باغ ویلا', 'باغ‌ویلا')


def _primary_neighborhood(neighborhoods: List[Dict[str, Any]]) -> Optional[str]:
    if not neighborhoods:
        return None
    top = max(neighborhoods, key=lambda x: x.get('count', 0))
    total = sum(n.get('count', 0) for n in neighborhoods)
    if total and top.get('count', 0) / total >= 0.65:
        return str(top.get('neighborhood', '')).strip()
    return None


def _listing_matches_market(row: pd.Series, primary_nb: Optional[str]) -> bool:
    if not primary_nb:
        return True
    title = str(row.get('title', ''))
    nb = str(row.get('neighborhood', '')).strip()

    for kw in OUT_OF_AREA_KEYWORDS:
        if kw in title and kw not in primary_nb:
            return False

    if any(kw in title for kw in VILLA_TITLE_KEYWORDS):
        if 'ویلا' not in primary_nb and 'باغ' not in primary_nb:
            return False

    if nb and nb != primary_nb:
        return False
    return True


def _is_plausible_opportunity(
    row: pd.Series,
    *,
    market_median_pps: Optional[float] = None,
    market_median_equiv: Optional[float] = None,
    is_rent: bool = False,
    min_price: int = 1_000_000_000,
    min_full_deposit: int = 100_000_000,
) -> bool:
    vs = row.get('value_score')
    if vs is None or pd.isna(vs):
        return False
    vs_f = float(vs)
    if vs_f > -8 or vs_f < -30:
        return False

    if is_rent:
        fd = row.get('full_deposit')
        if fd is None or pd.isna(fd) or float(fd) < min_full_deposit:
            return False
        if market_median_equiv and float(fd) < market_median_equiv * 0.55:
            return False
        return True

    price = row.get('price')
    if pd.isna(price) or float(price) < min_price:
        return False

    pps = row.get('price_per_sqm')
    if market_median_pps and pd.notna(pps):
        if float(pps) < market_median_pps * 0.55:
            return False
    return True


def _valuation_basis(row: pd.Series, work: pd.DataFrame, *, is_rent: bool = False) -> Dict[str, Any]:
    """توضیح شفاف مبنای ارزش‌گذاری برای مشاور."""
    lines: List[str] = []
    if pd.notna(row.get('area')):
        lines.append(format_area(row.get('area')))
    year = row.get('build_year')
    if year is not None and not pd.isna(year):
        lines.append(f'ساخت {int(year)}')
    if is_rent:
        dep = row.get('deposit')
        rent = row.get('rent')
        if pd.notna(dep) and float(dep) > 0:
            lines.append(f'رهن {format_toman(dep)}')
        if pd.notna(rent) and float(rent) > 0:
            lines.append(f'اجاره {format_toman(rent)}')
    for field, label in (('parking', 'پارکینگ'), ('elevator', 'آسانسور'), ('storage', 'انباری')):
        if row.get(field) is True:
            lines.append(label)
    peers = row.get('valuation_peers')
    if peers is not None and not pd.isna(peers) and int(peers) > 0:
        lines.append(f'{int(peers)} فایل مشابه')
    bucket = row.get('area_bucket') or row.get('dynamic_bucket')
    return {'lines': lines, 'peer_count': int(peers) if peers is not None and not pd.isna(peers) else 0, 'bucket': bucket}


def _opportunity_amenities(row: pd.Series) -> List[Dict[str, str]]:
    """وضعیت امکانات برای کارت فرصت — اصلی + بالکن + ثانویه (فقط دارد)."""
    icons = {
        'elevator': 'fa-arrows-alt-v',
        'parking': 'fa-car',
        'storage': 'fa-archive',
        'balcony': 'fa-sun',
        'lobby': 'fa-door-open',
        'pool': 'fa-water',
        'roof_garden': 'fa-seedling',
        'jacuzzi': 'fa-hot-tub',
        'gym': 'fa-dumbbell',
    }
    luxury_only = {f for f, _ in SECONDARY_OPPORTUNITY_AMENITIES[1:]}
    items: List[Dict[str, str]] = []
    for field, label in CORE_OPPORTUNITY_AMENITIES + SECONDARY_OPPORTUNITY_AMENITIES:
        val = row.get(field)
        if field in luxury_only and val is not True:
            continue
        if val is True:
            state = 'yes'
        elif val is False:
            state = 'no'
        else:
            state = 'unknown'
        items.append({
            'field': field,
            'label': label,
            'icon': icons.get(field, 'fa-circle'),
            'state': state,
            'tier': 'secondary' if field in {f for f, _ in SECONDARY_OPPORTUNITY_AMENITIES} else 'core',
        })
    return items


def _opportunity_reasons(row: pd.Series, df: pd.DataFrame, *, is_rent: bool = False) -> List[str]:
    """دلایل امتیاز فرصت — برای نمایش به مشاور."""
    reasons: List[str] = []
    vs = row.get('value_score')
    if vs is not None and not pd.isna(vs) and vs < 0:
        if is_rent:
            reasons.append(f'{abs(float(vs)):g}٪ زیر رهن کامل بازار')
        else:
            reasons.append(f'{abs(float(vs)):g}٪ ارزان‌تر از ارزش بازار')

    year = row.get('build_year')
    if year is not None and not pd.isna(year) and 'build_year' in df.columns and df['build_year'].notna().any():
        med_year = float(df['build_year'].dropna().median())
        ydiff = float(year) - med_year
        if ydiff >= 3:
            reasons.append(f'نوسازتر از میانه بازار (ساخت {int(year)})')
        elif ydiff <= -5:
            reasons.append(f'قدیمی‌تر از میانه — باید ارزان‌تر باشد (ساخت {int(year)})')

    for field, label in (
        ('parking', 'پارکینگ'), ('elevator', 'آسانسور'), ('storage', 'انباری'), ('balcony', 'بالکن'),
    ):
        val = row.get(field)
        if val is True:
            reasons.append(f'{label} دارد')
        elif val is False and field in df.columns:
            known = df[field].notna()
            if known.any():
                share = df.loc[known, field].astype(bool).mean()
                if share >= 0.55:
                    reasons.append(f'بدون {label} — در بازاری که اکثراً دارند')

    for field, label in (('pool', 'استخر'), ('lobby', 'لابی'), ('gym', 'سالن ورزش')):
        if row.get(field) is True:
            reasons.append(f'{label} دارد (امتیاز اضافه)')

    tier = row.get('amenity_tier')
    if tier == 'full':
        reasons.insert(0, 'فول امکانات — ارزش بالاتر از میانه بازار')
    elif tier == 'bare':
        reasons.append('بدون امکانات پایه — باید ارزان‌تر از بازار باشد')

    feat_adj = row.get('feature_adjustment') or row.get('amenity_adjustment')
    if feat_adj is not None and not pd.isna(feat_adj) and float(feat_adj) > 1.08:
        reasons.append('سال ساخت و امکانات در ارزش‌گذاری لحاظ شده')

    bucket = row.get('dynamic_bucket') or row.get('area_bucket', '')
    if bucket and 'dynamic_bucket' in df.columns:
        share = (df['dynamic_bucket'] == bucket).mean()
        if share >= 0.12:
            reasons.append('متراژ پرتقاضا')

    expected = row.get('expected_total')
    actual = row.get('full_deposit') if is_rent else row.get('price')
    if (
        expected is not None and not pd.isna(expected)
        and actual is not None and not pd.isna(actual)
        and float(expected) > float(actual)
    ):
        save = format_toman(float(expected) - float(actual))
        if is_rent:
            reasons.append(f'حدود {save} زیر رهن کامل تخمینی')
        else:
            reasons.append(f'حدود {save} زیر قیمت تخمینی')

    peers = row.get('valuation_peers')
    if peers is not None and not pd.isna(peers) and int(peers) >= 3:
        reasons.append(f'مقایسه با {int(peers)} فایل مشابه')

    return reasons[:5]


def rank_opportunity_deals(
    enriched: pd.DataFrame,
    transaction_type: str = '',
    limit: int = 20,
    neighborhoods: Optional[List[Dict[str, Any]]] = None,
    market_median_pps: Optional[float] = None,
    market_median_equiv: Optional[float] = None,
) -> List[Dict[str, Any]]:
    if enriched.empty:
        return []
    tx = transaction_profile(transaction_type)
    is_rent = tx['is_rent']
    work = enriched.copy()
    if 'dynamic_bucket' not in work.columns and 'area' in work.columns:
        edges = standard_area_bucket_edges(work['area'].dropna())
        work['dynamic_bucket'] = work['area'].apply(lambda a: assign_standard_area_bucket(a, edges))

    primary_nb = _primary_neighborhood(neighborhoods or [])
    deals: List[Dict[str, Any]] = []
    for _, row in work.iterrows():
        if not _listing_matches_market(row, primary_nb):
            continue
        if not _is_plausible_opportunity(
            row,
            market_median_pps=market_median_pps,
            market_median_equiv=market_median_equiv,
            is_rent=is_rent,
        ):
            continue

        vs = row.get('value_score')
        opp = compute_opportunity_score(row, work, 'full_deposit' if is_rent else 'price_per_sqm')
        if opp['score'] < 45:
            continue

        expected_total = row.get('expected_total')
        expected_lo = row.get('expected_total_lo')
        expected_hi = row.get('expected_total_hi')
        basis = _valuation_basis(row, work, is_rent=is_rent)

        deal: Dict[str, Any] = {
            'listing_id': int(row['listing_id']) if pd.notna(row.get('listing_id')) else None,
            'title': str(row.get('title', ''))[:60],
            'neighborhood': str(row.get('neighborhood', '')),
            'area_fmt': format_area(row.get('area')) if pd.notna(row.get('area')) else '',
            'expected_price_fmt': format_toman(expected_total) if pd.notna(expected_total) else '',
            'expected_range_fmt': (
                f'{format_toman(expected_lo)} تا {format_toman(expected_hi)}'
                if pd.notna(expected_lo) and pd.notna(expected_hi) else ''
            ),
            'value_score': vs,
            'value_diff_pct': abs(float(vs)) if float(vs) < 0 else None,
            'opportunity_score': opp['score'],
            'stars': opp['stars'],
            'label': opp['label'],
            'reasons': _opportunity_reasons(row, work, is_rent=is_rent),
            'amenities': _opportunity_amenities(row),
            'amenity_tier': row.get('amenity_tier') or 'unknown',
            'amenity_score': row.get('amenity_score'),
            'valuation_basis': basis.get('lines', []),
            'valuation_peers': basis.get('peer_count', 0),
        }
        if is_rent:
            rent_v = row.get('rent')
            dep_v = row.get('deposit')
            fd_v = row.get('full_deposit')
            deal['rent_fmt'] = format_toman(rent_v) if pd.notna(rent_v) and float(rent_v) > 0 else ''
            deal['deposit_fmt'] = format_toman(dep_v) if pd.notna(dep_v) and float(dep_v) > 0 else ''
            deal['full_deposit_fmt'] = format_toman(fd_v) if pd.notna(fd_v) else ''
            deal['rent_equiv_fmt'] = deal['full_deposit_fmt']
            deal['price_fmt'] = deal['full_deposit_fmt']
        else:
            actual_total = row.get('price') if pd.notna(row.get('price')) else None
            deal['price_fmt'] = format_toman(actual_total) if actual_total else ''
            deal['price_per_sqm_fmt'] = (
                format_toman(row.get('price_per_sqm'), per_sqm=True)
                if pd.notna(row.get('price_per_sqm')) else ''
            )
        deals.append(deal)
    deals.sort(key=lambda d: (d.get('value_score') or 0, d['opportunity_score']))
    for i, deal in enumerate(deals[:limit], start=1):
        deal['rank'] = i
    return deals[:limit]


def compute_liquidity_score(
    df: pd.DataFrame,
    depth: Dict[str, Any],
    price_dist: Dict[str, Any],
    area_segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    n = len(df)
    volume = _clamp(n / 60 * 25)
    under_ratio = depth.get('under_pct', 0) or 0
    under_factor = _clamp(under_ratio / 40 * 25)
    cv = price_dist.get('cv', 30) or 30
    dispersion = _clamp(25 - cv * 0.5)
    concentration = 0.0
    if area_segments:
        max_share = max(s.get('share_pct', 0) or 0 for s in area_segments)
        concentration = _clamp(max_share / 50 * 25)
    total = round(volume + under_factor + dispersion + concentration)
    stars, label = _score_label(total, LIQUIDITY_LABELS)
    return {
        'score': total,
        'stars': stars,
        'label': label,
        'volume_score': round(volume),
        'under_market_score': round(under_factor),
        'stability_score': round(dispersion),
        'concentration_score': round(concentration),
    }


def compute_confidence_score(
    n_valid: int,
    n_raw: int,
    outlier_pct: float,
    price_cv: float,
) -> Dict[str, Any]:
    quality_pct = max(0, 100 - outlier_pct)
    sample_pts = min(20, 8 + n_valid / 40)
    quality_pts = min(28, quality_pct * 0.28)
    stability_pts = min(22, max(8, 22 - price_cv * 0.2))
    total = min(100, round(30 + sample_pts + quality_pts + stability_pts))
    level = CONFIDENCE_LABELS[-1][1]
    for threshold, lbl in CONFIDENCE_LABELS:
        if total >= threshold:
            level = lbl
            break
    return {
        'score': total,
        'display_score': total,
        'level': level,
        'sample_score': round(sample_pts),
        'quality_score': round(quality_pts),
        'stability_score': round(stability_pts),
    }


def compute_market_sentiment(
    depth: Dict[str, Any],
    liquidity: Dict[str, Any],
    price_trends: Optional[Dict[str, Any]],
    price_dist: Dict[str, Any],
    *,
    audience: str = 'buyer',
) -> Dict[str, Any]:
    """وضعیت کلی بازار — خریدارانه/مستأجرانه، متعادل یا فروشنده‌محور."""
    score = 0
    factors: List[str] = []

    under_pct = depth.get('under_pct', 0) or 0
    if under_pct >= 35:
        score += 2
        factors.append(f'{under_pct}٪ فایل زیر بازار')
    elif under_pct >= 25:
        score += 1
        factors.append(f'{under_pct}٪ فایل زیر بازار')

    monthly = (price_trends or {}).get('pps_monthly_pct')
    if monthly is not None:
        if monthly <= -3:
            score += 2
            factors.append(f'روند نزولی {monthly:+g}٪')
        elif monthly >= 3:
            score -= 2
            factors.append(f'روند صعودی {monthly:+g}٪')

    if liquidity.get('score', 0) >= 65:
        score += 1
        factors.append('نقدشوندگی بالا')

    cv = price_dist.get('cv', 20) or 20
    if cv >= 28:
        score += 1
        factors.append('فضای مذاکره بالا')

    over_pct = depth.get('over_pct', 0) or 0
    if over_pct >= 40:
        score -= 1

    if audience == 'tenant':
        if score >= 3:
            label, tone, icon = 'مناسب مستأجر', 'buyer', 'fa-circle-check'
        elif score <= 0:
            label, tone, icon = 'مناسب موجر', 'seller', 'fa-circle-xmark'
        else:
            label, tone, icon = 'متعادل', 'balanced', 'fa-scale-balanced'
    elif score >= 3:
        label, tone, icon = 'مناسب خریدار', 'buyer', 'fa-circle-check'
    elif score <= 0:
        label, tone, icon = 'مناسب فروشنده', 'seller', 'fa-circle-xmark'
    else:
        label, tone, icon = 'متعادل', 'balanced', 'fa-scale-balanced'

    return {
        'label': label,
        'icon': icon,
        'tone': tone,
        'score': score,
        'factors': factors[:4],
    }


def compute_publication_scope(
    df: pd.DataFrame,
    n_analyzed: int,
    listings=None,
) -> Dict[str, Any]:
    """بازه تاریخ انتشار آگهی‌های مبنای تحلیل."""
    from workspace.services.display import to_jalali_display

    dates: List = []
    if 'published_at' in df.columns:
        for val in df['published_at'].dropna():
            dates.append(val)
    elif listings is not None:
        for lst in listings:
            pub = getattr(lst, 'published_at', None)
            if pub is not None:
                dates.append(pub)

    if not dates:
        return {}

    parsed = pd.to_datetime(pd.Series(dates), errors='coerce').dropna()
    if parsed.empty:
        return {}

    min_d = parsed.min()
    max_d = parsed.max()
    # در متن تحلیل فقط تاریخ نمایش داده شود (بدون ساعت/دقیقه).
    # چرا؟ چون `published_at` ممکن است timestamp باشد و `to_jalali_display` در صورت وجود ساعت/دقیقه،
    # زمان را هم برمی‌گرداند.
    min_fmt = to_jalali_display(min_d.date() if hasattr(min_d, 'date') else min_d)
    max_fmt = to_jalali_display(max_d.date() if hasattr(max_d, 'date') else max_d)
    n = int(n_analyzed or len(parsed))
    line = (
        f'بر اساس داده‌های موجود از تاریخ {min_fmt} تا {max_fmt} '
        f'و بر اساس تحلیل {n:,} فایل متفاوت، این تحلیل ارائه می‌شود.'
    ).replace(',', '،')

    return {
        'date_from': min_d,
        'date_to': max_d,
        'date_from_fmt': min_fmt,
        'date_to_fmt': max_fmt,
        'count_with_date': int(len(parsed)),
        'analyzed_count': n,
        'line': line,
    }


def compute_data_quality(
    n_raw: int,
    n_valid: int,
    outliers_report: List[Dict],
) -> Dict[str, Any]:
    removed = n_raw - n_valid
    outlier_pct = round_pct(removed / max(n_raw, 1) * 100)
    quality_pct = round_pct(n_valid / max(n_raw, 1) * 100)
    by_field = [
        {'field': o['field'], 'removed': o['removed'], 'pct': o['pct']}
        for o in outliers_report if o.get('removed')
    ]
    return {
        'raw_count': n_raw,
        'valid_count': n_valid,
        'removed_count': removed,
        'outlier_pct': outlier_pct,
        'quality_pct': quality_pct,
        'by_field': by_field,
    }


def compute_price_trends(listings) -> Optional[Dict[str, Any]]:
    """روند قیمت از تاریخ انتشار — در صورت وجود داده کافی."""
    points: List[Tuple] = []
    for lst in listings:
        pub = getattr(lst, 'published_at', None)
        pps = lst.price_per_sqm
        price = lst.price
        if not pub:
            continue
        if pps:
            points.append((pub, float(pps), 'pps'))
        elif price:
            points.append((pub, float(price), 'price'))

    if len(points) < 8:
        return None

    df = pd.DataFrame(points, columns=['date', 'value', 'kind'])
    df = df.sort_values('date')
    now = df['date'].max()
    trends: Dict[str, Any] = {}

    for days, key in ((7, 'weekly'), (30, 'monthly'), (90, 'quarterly'), (365, 'yearly')):
        cutoff = now - timedelta(days=days)
        recent = df[df['date'] >= cutoff]['value']
        older = df[df['date'] < cutoff]['value']
        if len(recent) >= 3 and len(older) >= 3:
            change = (recent.median() - older.median()) / older.median() * 100
            trends[key] = round_pct(change)

    if not trends:
        return None

    pps_rows = df[df['kind'] == 'pps']
    price_rows = df[df['kind'] == 'price']
    result: Dict[str, Any] = {'has_data': True, 'points': len(df)}
    if len(pps_rows) >= 8 and 'monthly' in trends:
        result['pps_monthly_pct'] = trends.get('monthly')
        result['pps_monthly_fmt'] = f'{trends["monthly"]:+g}٪' if trends.get('monthly') is not None else None
    if len(price_rows) >= 8 and 'yearly' in trends:
        result['price_yearly_pct'] = trends.get('yearly')
        result['price_yearly_fmt'] = f'{trends["yearly"]:+g}٪' if trends.get('yearly') is not None else None
    result['trends'] = trends
    return result


def generate_professional_insights(report: Dict[str, Any]) -> List[str]:
    """بینش‌های داده‌محور — نه کلیشه."""
    tips: List[str] = []
    tx = report.get('tx', {})
    pps = report.get('price_analysis', {}).get('price_per_sqm', {})
    depth = report.get('market_depth', {})
    segments = report.get('area_segments', [])
    build = report.get('build_year', {})
    liquidity = report.get('liquidity', {})
    confidence = report.get('confidence', {})
    nb_list = report.get('neighborhoods', [])
    dataset_name = report.get('dataset_name', 'این فایل')

    if pps.get('median_fmt'):
        spread = pps.get('spread_50_pct')
        tips.append(
            f'قیمت هر متر بازار {pps["median_fmt"]} است — '
            f'۵۰٪ فایل‌ها بین {pps.get("range_50_fmt", "—")} و '
            f'۸۰٪ فایل‌ها بین {pps.get("range_80_fmt", "—")}.'
        )
        if spread is not None:
            if spread < 15:
                tips.append(f'شکاف P25 تا P75 حدود {spread:g}٪ است — بازار نسبتاً پایدار.')
            elif spread > 25:
                tips.append(f'شکاف P25 تا P75 حدود {spread:g}٪ است — پراکندگی قیمت بالاست؛ مذاکره مهم‌تر.')

    if depth.get('under_pct') is not None:
        tips.append(
            f'{depth["under_pct"]}٪ فایل‌ها زیر ارزش بازار (P40)، '
            f'{depth["fair_pct"]}٪ سر به سر، و {depth["over_pct"]}٪ بالای بازار.'
        )

    if segments:
        top = max(segments, key=lambda s: s['count'])
        tips.append(
            f'بیشترین عرضه در محدوده {top["bucket_plain"]} است '
            f'({top["count"]} فایل، {top.get("share_pct", 0)}٪).'
        )
        if top.get('pps_dist', {}).get('median_fmt'):
            tips.append(
                f'در محدوده {top["bucket_plain"]} متری معمول {top["pps_dist"]["median_fmt"]}.'
            )

    if build.get('under_5_pct') is not None and build['under_5_pct'] >= 40:
        tips.append(f'{build["under_5_pct"]}٪ فایل‌ها کمتر از ۵ سال عمر دارند — بازار نوساز است.')

    if build.get('median_year'):
        med = build['median_year']
        pps_med = pps.get('median')
        pps_mean = pps.get('mean')
        if pps_med and pps_mean and pps_mean > pps_med * 1.05:
            diff = round_pct((pps_mean - pps_med) / pps_med * 100)
            tips.append(f'فایل‌های نوسازتر حدود {diff}٪ بالاتر از میانه بازار قیمت‌گذاری شده‌اند.')

    if liquidity.get('label'):
        tips.append(f'نقدشوندگی بازار: {liquidity["label"]} ({liquidity.get("stars", "")}).')

    if confidence.get('score') is not None:
        tips.append(
            f'اعتماد به تحلیل: {confidence.get("level", "—")} '
            f'({min(100, confidence["score"])} از ۱۰۰).'
        )

    if nb_list and len(nb_list) >= 2:
        tips.append(
            f'گران‌ترین محله در فایل: {nb_list[0]["neighborhood"]} '
            f'({nb_list[0].get("price_per_sqm", {}).get("median_fmt", "—")}).'
        )

    trends = report.get('price_trends')
    if trends and trends.get('pps_monthly_fmt'):
        tips.append(f'روند متری: {trends["pps_monthly_fmt"]} نسبت به ماه قبل.')

    return tips[:8]


def negotiation_recommendations(
    price_analysis: Dict[str, Any],
    market_depth: Dict[str, Any],
) -> List[str]:
    tips: List[str] = []
    pps = price_analysis.get('price_per_sqm', {})
    if market_depth.get('p40_fmt'):
        tips.append(f'هدف خرید: زیر {market_depth["p40_fmt"]} (زیر P40 بازار)')
        tips.append(
            f'قیمت سر به سر: {market_depth["p40_fmt"]} تا {market_depth.get("p60_fmt", "—")}'
        )
        tips.append(f'بالای {market_depth.get("p60_fmt", "—")}: مذاکره جدی یا رد فایل')
    if pps.get('range_50_fmt'):
        tips.append(f'۵۰٪ بازار (P25–P75): {pps["range_50_fmt"]}')
    if pps.get('range_80_fmt'):
        tips.append(f'۸۰٪ بازار (P10–P90): {pps["range_80_fmt"]}')
    return tips


def build_professional_report(
    df_raw: pd.DataFrame,
    df_clean: pd.DataFrame,
    stats: Dict[str, Any],
    market: Dict[str, Any],
    transaction_type: str = '',
    outliers_report: Optional[List[Dict]] = None,
    listings=None,
    dataset_name: str = '',
    subcategory: str = '',
    factors: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """بسته کامل گزارش حرفه‌ای."""
    tx = transaction_profile(transaction_type)
    outliers_report = outliers_report or []
    enriched = market.get('enriched_df', df_clean)

    if 'area' in df_clean.columns:
        edges = standard_area_bucket_edges(df_clean['area'].dropna())
        df_clean = df_clean.copy()
        df_clean['dynamic_bucket'] = df_clean['area'].apply(lambda a: assign_standard_area_bucket(a, edges))
        if not enriched.empty:
            enriched = enriched.copy()
            enriched['dynamic_bucket'] = enriched['area'].apply(lambda a: assign_standard_area_bucket(a, edges))

    price_analysis: Dict[str, Any] = {}
    metric_col = 'price_per_sqm' if tx['show_price_per_sqm'] else ('full_deposit' if tx['is_rent'] else 'price')

    if tx['show_price'] and df_clean['price'].notna().any():
        price_analysis['price'] = _fmt_dist(distribution_stats(df_clean['price'].dropna()))
    if tx['show_price_per_sqm'] and df_clean['price_per_sqm'].notna().any():
        price_analysis['price_per_sqm'] = _fmt_dist(
            distribution_stats(df_clean['price_per_sqm'].dropna()), per_sqm=True,
        )
    if tx['is_rent'] and 'full_deposit' in df_clean.columns and df_clean['full_deposit'].notna().any():
        price_analysis['full_deposit'] = _fmt_dist(distribution_stats(df_clean['full_deposit'].dropna()))

    if tx['show_deposit'] and 'deposit' in df_clean.columns and df_clean['deposit'].notna().any():
        dep = df_clean['deposit'].dropna()
        dep = dep[dep > 0]
        if len(dep) >= 3:
            price_analysis['deposit'] = _fmt_dist(distribution_stats(dep))

    if tx['show_rent'] and 'rent' in df_clean.columns:
        rev = df_clean['rent'].dropna()
        rev = rev[rev > 0]
        if len(rev) >= 3:
            price_analysis['rent'] = _fmt_dist(distribution_stats(rev))

    depth_col = metric_col if metric_col in df_clean.columns else 'price_per_sqm'
    if tx['is_rent'] and 'full_deposit' in df_clean.columns and df_clean['full_deposit'].notna().sum() >= 5:
        depth_col = 'full_deposit'
    market_depth = market_depth_distribution(df_clean, depth_col) if depth_col in df_clean.columns else {}

    area_segments = analyze_dynamic_area_segments(df_clean, transaction_type)
    neighborhoods = neighborhood_price_analysis(df_clean, transaction_type)
    build = build_year_analysis(df_clean)
    amenity_cov = amenities_coverage(df_clean)
    amenity_valuation = analyze_amenity_valuation(df_clean, transaction_type)

    total_removed = sum(o.get('removed', 0) for o in outliers_report)
    outlier_pct = round_pct(total_removed / max(len(df_raw), 1) * 100) or 0
    pps_cv = (
        price_analysis.get('price_per_sqm', {}).get('cv')
        or price_analysis.get('full_deposit', {}).get('cv')
        or price_analysis.get('rent', {}).get('cv')
        or 20
    )

    full_deposit_dist = price_analysis.get('full_deposit', {})
    confidence = compute_confidence_score(len(df_clean), len(df_raw), outlier_pct, pps_cv)
    data_quality = compute_data_quality(len(df_raw), len(df_clean), outliers_report)
    publication_scope = compute_publication_scope(df_clean, len(df_clean), listings=listings)
    liquidity = compute_liquidity_score(
        df_clean, market_depth,
        price_analysis.get('price_per_sqm') or full_deposit_dist or price_analysis.get('rent', {}),
        area_segments,
    )
    opportunities = rank_opportunity_deals(
        enriched,
        transaction_type,
        neighborhoods=neighborhoods,
        market_median_pps=(price_analysis.get('price_per_sqm') or {}).get('median'),
        market_median_equiv=full_deposit_dist.get('median'),
    )
    price_trends = compute_price_trends(listings) if listings is not None else None
    market_sentiment = compute_market_sentiment(
        market_depth,
        liquidity,
        price_trends,
        price_analysis.get('price_per_sqm') or full_deposit_dist or price_analysis.get('rent', {}),
        audience='tenant' if tx['is_rent'] else 'buyer',
    )

    mstats = market.get('stats', {})
    full_mortgage = mstats.get('full_mortgage_count', 0)
    full_mortgage_analysis = mstats.get('full_mortgage') or _full_mortgage_analysis(df_clean)
    ratio_std = standard_deposit_rent_ratio()

    report: Dict[str, Any] = {
        'tx': tx,
        'dataset_name': dataset_name,
        'subcategory': subcategory,
        'price_analysis': price_analysis,
        'market_depth': market_depth,
        'area_segments': area_segments,
        'neighborhoods': neighborhoods,
        'build_year': build,
        'amenities_coverage': amenity_cov,
        'amenity_valuation': amenity_valuation,
        'confidence': confidence,
        'data_quality': data_quality,
        'publication_scope': publication_scope,
        'liquidity': liquidity,
        'opportunities': opportunities,
        'price_trends': price_trends,
        'market_sentiment': market_sentiment,
        'metric_col': depth_col,
        'full_mortgage_count': full_mortgage,
        'full_mortgage': full_mortgage_analysis,
        'deposit_rent_ratio': ratio_std,
        'deposit_rent_ratio_observed': mstats.get('deposit_rent_ratio_observed'),
        'deposit_rent_ratio_fmt': format_rent_conversion_rule(ratio_std),
    }
    report['insights'] = generate_professional_insights(report)
    report['negotiation'] = negotiation_recommendations(price_analysis, market_depth)
    from workspace.services.market_copy import enrich_report_for_agents
    return enrich_report_for_agents(
        report,
        dataset_name=dataset_name,
        subcategory=subcategory,
        transaction_type=transaction_type,
        factors=factors,
        stats=stats,
        df=df_clean,
    )
