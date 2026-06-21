"""ارزش‌گذاری و تحلیل چندبعدی — متراژ، سال ساخت، امکانات، رهن/اجاره."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from workspace.services.features import area_bucket, extract_listing_features, parse_build_year
from workspace.services.columns import extract_consultant_name
from workspace.services.formatting import (
    STANDARD_DEPOSIT_RENT_RATIO,
    format_area,
    format_pct,
    format_rent_conversion_rule,
    format_toman,
    full_deposit_equiv,
    round_pct,
)

# تأثیر نسبی امکانات روی قیمت/اجاره معادل (پیش‌فرض؛ در صورت داده کافی از بازار جایگزین می‌شود)
CORE_AMENITY_FIELDS = ('elevator', 'parking', 'storage')
SECONDARY_AMENITY_FIELDS = ('balcony', 'lobby', 'pool', 'roof_garden', 'jacuzzi', 'gym')
AMENITY_PREMIUM = {'elevator': 0.06, 'parking': 0.08, 'storage': 0.035}
SECONDARY_AMENITY_PREMIUM = {
    'balcony': 0.028,
    'lobby': 0.015,
    'pool': 0.022,
    'roof_garden': 0.018,
    'jacuzzi': 0.012,
    'gym': 0.015,
}
SECONDARY_AMENITY_LABELS = {
    'balcony': 'بالکن',
    'lobby': 'لابی',
    'pool': 'استخر',
    'roof_garden': 'روف گاردن',
    'jacuzzi': 'جکوزی',
    'gym': 'سالن ورزش',
}
SECONDARY_ADJ_MAX_BONUS = 0.08
SECONDARY_ADJ_MAX_PENALTY = 0.05
FULL_AMENITY_STACK_BONUS = 0.05
BARE_AMENITY_PENALTY = 0.05
MIN_PREMIUM_SAMPLES = 3
YEAR_PREMIUM_PER_YEAR = 0.01  # هر سال جدیدتر ≈ ۱٪
YEAR_ADJ_MIN = 0.78
YEAR_ADJ_MAX = 1.32
DEFAULT_DEPOSIT_RENT_RATIO = STANDARD_DEPOSIT_RENT_RATIO
MIN_SEGMENT_SIZE = 4


def market_deposit_rent_ratio(df: pd.DataFrame) -> float:
    """نسبت مشاهده‌شده رهن به اجاره از داده بازار (فقط برای مرجع)."""
    if 'deposit' not in df.columns or 'rent' not in df.columns:
        return DEFAULT_DEPOSIT_RENT_RATIO
    valid = df[(df['deposit'].fillna(0) > 0) & (df['rent'].fillna(0) > 0)]
    if len(valid) < MIN_SEGMENT_SIZE:
        return DEFAULT_DEPOSIT_RENT_RATIO
    med_d = valid['deposit'].median()
    med_r = valid['rent'].median()
    if med_r <= 0:
        return DEFAULT_DEPOSIT_RENT_RATIO
    ratio = med_d / med_r
    return float(max(10.0, min(ratio, 120.0)))


def standard_deposit_rent_ratio() -> float:
    """نسبت عرف بازار برای تبدیل رهن↔اجاره در گزارش."""
    return DEFAULT_DEPOSIT_RENT_RATIO


def _safe_int_money(val) -> int:
    if val is None:
        return 0
    try:
        if val != val:  # NaN
            return 0
    except TypeError:
        pass
    try:
        return max(0, int(float(val)))
    except (ValueError, TypeError):
        return 0


def rent_monthly_equivalent(
    rent: Optional[int],
    deposit: Optional[int],
    ratio: float = DEFAULT_DEPOSIT_RENT_RATIO,
) -> Optional[float]:
    """
    اجاره معادل ماهانه — رهن کامل (اجاره ۰) را با ودیعه لحاظ می‌کند.
    """
    r = _safe_int_money(rent)
    d = _safe_int_money(deposit)
    if r == 0 and d == 0:
        return None
    return r + (d / max(ratio, 1))


def _add_market_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ستون‌های بازار (باکت متراژ، اجاره معادل، ...) را به DataFrame اضافه می‌کند."""
    if df.empty:
        return df
    result = df.copy()
    if 'area_bucket' not in result.columns:
        result['area_bucket'] = result['area'].apply(area_bucket) if 'area' in result.columns else 'نامشخص'
    observed = market_deposit_rent_ratio(result)
    ratio = standard_deposit_rent_ratio()
    result['deposit_rent_ratio_observed'] = observed
    result['deposit_rent_ratio'] = ratio
    result['rent_equiv'] = [
        rent_monthly_equivalent(row.get('rent'), row.get('deposit'), ratio)
        for _, row in result.iterrows()
    ]
    result['full_deposit'] = [
        full_deposit_equiv(row.get('deposit'), row.get('rent'), ratio)
        for _, row in result.iterrows()
    ]
    if 'price' in result.columns and 'area' in result.columns:
        mask = (result['price'].notna()) & (result['area'].notna()) & (result['area'] > 0)
        if 'price_per_sqm' not in result.columns or not result['price_per_sqm'].notna().any():
            result.loc[mask, 'price_per_sqm'] = result.loc[mask, 'price'] / result.loc[mask, 'area']
    if 'rent_per_sqm' not in result.columns:
        result['rent_per_sqm'] = None
        rmask = (result['rent_equiv'].notna()) & (result['area'].notna()) & (result['area'] > 0)
        result.loc[rmask, 'rent_per_sqm'] = result.loc[rmask, 'rent_equiv'] / result.loc[rmask, 'area']
    return result


def enrich_dataframe(listings, transaction_type: str = '') -> pd.DataFrame:
    """غنی‌سازی DataFrame با ویژگی‌ها و معیارهای ارزش."""
    if isinstance(listings, pd.DataFrame):
        return _add_market_columns(listings)

    rows = []
    for lst in listings:
        feat = extract_listing_features(lst)
        rows.append({
            'listing_id': lst.pk,
            'token': lst.token,
            'title': lst.title or '',
            'price': lst.price,
            'deposit': lst.deposit,
            'rent': lst.rent,
            'area': lst.area,
            'rooms': lst.rooms or feat.get('rooms', '') or '',
            'neighborhood': lst.neighborhood or '',
            'city': lst.city or '',
            'business_type': lst.business_type or '',
            'consultant_name': extract_consultant_name(lst.data or {}),
            'link': lst.link or '',
            'build_year': feat['build_year'],
            'floor': feat['floor'],
            'elevator': feat['elevator'],
            'parking': feat['parking'],
            'storage': feat['storage'],
            'balcony': feat.get('balcony'),
            'lobby': feat.get('lobby'),
            'pool': feat.get('pool'),
            'roof_garden': feat.get('roof_garden'),
            'jacuzzi': feat.get('jacuzzi'),
            'gym': feat.get('gym'),
            'amenity_count': feat['amenity_count'],
            'price_per_sqm': lst.price_per_sqm,
            'published_at': lst.published_at,
        })

    return _add_market_columns(pd.DataFrame(rows))


def _segment_median(df: pd.DataFrame, bucket: str, col: str) -> Optional[float]:
    seg = df[(df['area_bucket'] == bucket) & df[col].notna()]
    if len(seg) < MIN_SEGMENT_SIZE:
        seg = df[df[col].notna()]
    if len(seg) < MIN_SEGMENT_SIZE:
        return None
    return float(seg[col].median())


def _bool_val(val) -> Optional[bool]:
    if val is None:
        return None
    try:
        if val != val:
            return None
    except TypeError:
        pass
    if val is True:
        return True
    if val is False:
        return False
    return None


def compute_amenity_market_premiums(df: pd.DataFrame, metric_col: str) -> Dict[str, float]:
    """پریمیوم مشاهده‌شده از داده بازار — در صورت ناکافی، مقدار پیش‌فرض."""
    premiums = dict(AMENITY_PREMIUM)
    if metric_col not in df.columns:
        return premiums
    work = df[df[metric_col].notna()]
    for field in CORE_AMENITY_FIELDS:
        if field not in work.columns:
            continue
        with_am = work[work[field] == True]
        without_am = work[work[field] == False]
        if len(with_am) < MIN_PREMIUM_SAMPLES or len(without_am) < MIN_PREMIUM_SAMPLES:
            continue
        med_with = float(with_am[metric_col].median())
        med_without = float(without_am[metric_col].median())
        if med_without > 0 and med_with > 0:
            observed = (med_with - med_without) / med_without
            premiums[field] = float(max(0.02, min(observed, 0.20)))
    return premiums


def classify_amenity_tier(row: pd.Series) -> str:
    """طبقه امکانات — full / partial / bare / unknown."""
    vals = [_bool_val(row.get(f)) for f in CORE_AMENITY_FIELDS]
    known = [v for v in vals if v is not None]
    if len(known) < 2:
        return 'unknown'
    if all(v is True for v in known) and len(known) == 3:
        return 'full'
    if all(v is False for v in known) and len(known) == 3:
        return 'bare'
    if all(v is True for v in known):
        return 'partial'
    if all(v is False for v in known):
        return 'bare'
    return 'partial'


def amenity_relative_score(row: pd.Series, seg_df: pd.DataFrame) -> int:
    """امتیاز نسبی ۰–۱۰۰ — امکانات اصلی + ثانویه + سال ساخت."""
    tier = classify_amenity_tier(row)
    if tier == 'full':
        base = 82
    elif tier == 'bare':
        base = 24
    elif tier == 'unknown':
        base = 48
    else:
        fields = [f for f in CORE_AMENITY_FIELDS if f in seg_df.columns]
        if not fields:
            base = 48
        else:
            row_amen = sum(1 for f in fields if row.get(f) is True)
            seg_counts = seg_df[fields].apply(
                lambda r: sum(1 for f in fields if r.get(f) is True), axis=1,
            )
            med_amen = float(seg_counts.median()) if len(seg_counts) else 1.5
            base = int(max(20, min(78, 48 + (row_amen - med_amen) * 12)))

    sec_bonus = 0
    for field in SECONDARY_AMENITY_FIELDS:
        if row.get(field) is True:
            sec_bonus += 3
    base = int(min(96, base + sec_bonus))

    year = row.get('build_year')
    if year is not None and not pd.isna(year) and 'build_year' in seg_df.columns:
        seg_years = seg_df['build_year'].dropna()
        if len(seg_years) >= MIN_SEGMENT_SIZE:
            diff = float(year) - float(seg_years.median())
            base = int(max(8, min(98, base + diff * 1.8)))

    return base


def _amenity_adjustment(
    row: pd.Series,
    seg_df: pd.DataFrame,
    premiums: Optional[Dict[str, float]] = None,
) -> float:
    """ضریب تعدیل بر اساس امکانات اصلی — فقط مقادیر صریح."""
    premiums = premiums or AMENITY_PREMIUM
    adj = 1.0
    explicit_true = 0
    explicit_false = 0

    for field, premium in premiums.items():
        val = _bool_val(row.get(field))
        if val is True:
            explicit_true += 1
            if field not in seg_df.columns:
                adj += premium * 0.5
                continue
            known = seg_df[field].notna()
            if not known.any():
                adj += premium * 0.5
                continue
            share = seg_df.loc[known, field].astype(bool).mean()
            if share < 0.98:
                adj += premium * (1 - share)
        elif val is False:
            explicit_false += 1
            if field not in seg_df.columns:
                adj -= premium * 0.35
                continue
            known = seg_df[field].notna()
            if not known.any():
                adj -= premium * 0.35
                continue
            share = seg_df.loc[known, field].astype(bool).mean()
            if share > 0.02:
                adj -= premium * share

    if explicit_true == 3:
        adj += FULL_AMENITY_STACK_BONUS
    elif explicit_false == 3 and len(seg_df) >= MIN_SEGMENT_SIZE:
        full_mask = pd.Series(True, index=seg_df.index)
        for field in CORE_AMENITY_FIELDS:
            if field in seg_df.columns:
                full_mask &= seg_df[field] == True
            else:
                full_mask = pd.Series(False, index=seg_df.index)
                break
        full_share = float(full_mask.mean()) if len(full_mask) else 0.0
        if full_share >= 0.2:
            adj -= BARE_AMENITY_PENALTY * min(full_share, 0.85)

    return max(0.78, min(adj, 1.38))


def _secondary_amenity_adjustment(row: pd.Series, seg_df: pd.DataFrame) -> float:
    """تعدیل امکانات ثانویه — بالکن، استخر، لابی و … با اثر کمتر."""
    bonus = 0.0
    penalty = 0.0
    for field, premium in SECONDARY_AMENITY_PREMIUM.items():
        val = _bool_val(row.get(field))
        if val is True:
            share = 0.5
            if field in seg_df.columns:
                known = seg_df[field].notna()
                if known.any():
                    share = float(seg_df.loc[known, field].astype(bool).mean())
            if share < 0.95:
                bonus += premium * (1 - share)
        elif val is False:
            share = 0.5
            if field in seg_df.columns:
                known = seg_df[field].notna()
                if known.any():
                    share = float(seg_df.loc[known, field].astype(bool).mean())
            if share > 0.08:
                penalty += premium * share * 0.65

    return max(1.0 - SECONDARY_ADJ_MAX_PENALTY, min(1.0 + SECONDARY_ADJ_MAX_BONUS, 1 + bonus - penalty))


def _year_adjustment(row: pd.Series, seg_df: pd.DataFrame) -> float:
    year = row.get('build_year')
    if year is None or pd.isna(year):
        return 1.0
    seg_years = seg_df['build_year'].dropna()
    if len(seg_years) < MIN_SEGMENT_SIZE:
        return 1.0
    med_year = float(seg_years.median())
    diff = float(year) - med_year
    return max(YEAR_ADJ_MIN, min(YEAR_ADJ_MAX, 1 + diff * YEAR_PREMIUM_PER_YEAR))


def total_feature_adjustment(
    row: pd.Series,
    seg_df: pd.DataFrame,
    premiums: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, float, float]:
    """ضریب کل = امکانات اصلی × سال ساخت × امکانات ثانویه."""
    core = _amenity_adjustment(row, seg_df, premiums)
    year = _year_adjustment(row, seg_df)
    secondary = _secondary_amenity_adjustment(row, seg_df)
    total = core * year * secondary
    total = max(0.72, min(total, 1.45))
    return total, core, year, secondary


def _segment_median_col(df: pd.DataFrame, bucket: str, col: str) -> Optional[float]:
    seg = df[(df['area_bucket'] == bucket) & df[col].notna()]
    if len(seg) < MIN_SEGMENT_SIZE:
        seg = df[df[col].notna()]
    if len(seg) < MIN_SEGMENT_SIZE:
        return None
    return float(seg[col].median())


def _segment_peer_count(df: pd.DataFrame, bucket: str) -> int:
    if 'area_bucket' not in df.columns:
        return len(df)
    seg = df[df['area_bucket'] == bucket]
    return len(seg) if len(seg) >= MIN_SEGMENT_SIZE else len(df)


def compute_expected_values(df: pd.DataFrame, mode: str = 'sale') -> pd.DataFrame:
    """محاسبه ارزش مورد انتظار — فروش: قیمت کل؛ اجاره: رهن کامل معادل."""
    result = df.copy()
    metric = 'price_per_sqm' if mode == 'sale' else 'full_deposit'
    if metric not in result.columns:
        result['expected_value'] = None
        result['expected_total'] = None
        result['expected_total_lo'] = None
        result['expected_total_hi'] = None
        result['value_score'] = None
        result['valuation_peers'] = None
        return result

    expected_list = []
    expected_total_list = []
    expected_lo_list = []
    expected_hi_list = []
    score_list = []
    peer_list = []
    amen_adj_list = []
    amen_tier_list = []
    amen_score_list = []
    year_adj_list = []
    secondary_adj_list = []
    feature_adj_list = []
    premiums = compute_amenity_market_premiums(result, metric)
    for _, row in result.iterrows():
        bucket = row.get('area_bucket', 'نامشخص')
        seg = result[result['area_bucket'] == bucket]
        if len(seg) < MIN_SEGMENT_SIZE:
            seg = result

        base_pps = _segment_median(result, bucket, metric)
        base_total = (
            _segment_median_col(result, bucket, 'price')
            if mode == 'sale' else _segment_median(result, bucket, 'full_deposit')
        )
        if base_pps is None and base_total is None:
            expected_list.append(None)
            expected_total_list.append(None)
            expected_lo_list.append(None)
            expected_hi_list.append(None)
            score_list.append(None)
            peer_list.append(None)
            amen_adj_list.append(None)
            amen_tier_list.append('unknown')
            amen_score_list.append(None)
            year_adj_list.append(None)
            secondary_adj_list.append(None)
            feature_adj_list.append(None)
            continue

        adj, core_adj, year_adj, sec_adj = total_feature_adjustment(row, seg, premiums)
        expected_pps = base_pps * adj if base_pps else None
        area = row.get('area')

        if base_total:
            expected_total = int(base_total * adj)
        elif expected_pps and area is not None and not pd.isna(area) and float(area) > 0:
            expected_total = int(expected_pps * float(area))
        else:
            expected_total = None

        seg_col = 'price' if mode == 'sale' else 'full_deposit'
        if seg_col in seg.columns:
            seg_vals = seg[seg_col].dropna()
            if len(seg_vals) >= MIN_SEGMENT_SIZE:
                lo_total = int(float(seg_vals.quantile(0.25)) * adj)
                hi_total = int(float(seg_vals.quantile(0.75)) * adj)
            elif expected_total:
                lo_total = int(expected_total * 0.92)
                hi_total = int(expected_total * 1.08)
            else:
                lo_total = hi_total = None
        elif expected_total:
            lo_total = int(expected_total * 0.92)
            hi_total = int(expected_total * 1.08)
        else:
            lo_total = hi_total = None

        actual_pps = row.get(metric)
        actual_total = row.get('price') if mode == 'sale' else row.get('full_deposit')

        if actual_total is not None and not pd.isna(actual_total) and expected_total:
            score = round_pct((float(actual_total) - expected_total) / expected_total * 100)
        elif actual_pps is not None and not pd.isna(actual_pps) and expected_pps:
            score = round_pct((float(actual_pps) - expected_pps) / expected_pps * 100)
        else:
            score = None

        expected_list.append(expected_pps)
        expected_total_list.append(expected_total)
        expected_lo_list.append(lo_total)
        expected_hi_list.append(hi_total)
        score_list.append(score)
        peer_list.append(_segment_peer_count(result, bucket))
        amen_adj_list.append(round(core_adj, 4))
        amen_tier_list.append(classify_amenity_tier(row))
        amen_score_list.append(amenity_relative_score(row, seg))
        year_adj_list.append(round(year_adj, 4))
        secondary_adj_list.append(round(sec_adj, 4))
        feature_adj_list.append(round(adj, 4))

    result['expected_value'] = expected_list
    result['expected_total'] = expected_total_list
    result['expected_total_lo'] = expected_lo_list
    result['expected_total_hi'] = expected_hi_list
    result['value_score'] = score_list
    result['valuation_peers'] = peer_list
    result['amenity_adjustment'] = amen_adj_list
    result['amenity_tier'] = amen_tier_list
    result['amenity_score'] = amen_score_list
    result['build_year_adjustment'] = year_adj_list
    result['secondary_adjustment'] = secondary_adj_list
    result['feature_adjustment'] = feature_adj_list
    return result


def value_verdict(score: Optional[float]) -> str:
    if score is None:
        return ''
    if score <= -12:
        return 'زیر بازار'
    if score >= 12:
        return 'بالای بازار'
    return 'متعارف'


def analyze_market(df: pd.DataFrame, transaction_type: str = '') -> Dict[str, Any]:
    """تحلیل جامع بازار با لحاظ متراژ، سال ساخت، امکانات و رهن/اجاره."""
    from workspace.services.display import transaction_profile

    tx = transaction_profile(transaction_type)
    if df.empty:
        return {'tx': tx, 'row_count': 0}

    ratio = standard_deposit_rent_ratio()
    observed = market_deposit_rent_ratio(df)
    if tx['is_mixed']:
        rent_n = df['rent_equiv'].notna().sum() if 'rent_equiv' in df.columns else 0
        sale_n = df['price_per_sqm'].notna().sum() if 'price_per_sqm' in df.columns else 0
        val_mode = 'rent' if rent_n >= sale_n else 'sale'
    elif tx['is_rent']:
        val_mode = 'rent'
    else:
        val_mode = 'sale'
    enriched = compute_expected_values(df, mode=val_mode)

    stats: Dict[str, Any] = {
        'tx': tx,
        'row_count': len(df),
        'deposit_rent_ratio': ratio,
        'deposit_rent_ratio_observed': round(observed, 1),
        'deposit_rent_ratio_fmt': format_rent_conversion_rule(ratio),
    }

    # متراژ
    if df['area'].notna().any():
        areas = df['area'].dropna()
        stats['area'] = {
            'median': round(areas.median(), 1),
            'median_fmt': format_area(areas.median()),
        }
        seg_counts = df['area_bucket'].value_counts().head(5)
        stats['area_segments'] = [
            {'bucket': str(k), 'count': int(v)} for k, v in seg_counts.items()
        ]

    # سال ساخت
    if df['build_year'].notna().any():
        years = df['build_year'].dropna()
        stats['build_year'] = {
            'median': int(years.median()),
            'min': int(years.min()),
            'max': int(years.max()),
            'new_share_pct': round_pct((years >= years.median()).mean() * 100),
        }

    # امکانات
    amenity_stats = []
    for field, label in [('elevator', 'آسانسور'), ('parking', 'پارکینگ'), ('storage', 'انباری')]:
        if field in df.columns:
            has = df[field].fillna(False).astype(bool)
            if has.any() or (~has & df[field].notna()).any():
                pct = round_pct(has.mean() * 100)
                amenity_stats.append({'key': field, 'label': label, 'share_pct': pct})
    stats['amenities'] = amenity_stats

    # رهن/اجاره
    if tx['show_deposit'] or tx['show_rent']:
        full_mortgage = df[(df['rent'].fillna(0) == 0) & (df['deposit'].fillna(0) > 0)]
        stats['full_mortgage_count'] = len(full_mortgage)
        stats['full_mortgage_pct'] = round_pct(len(full_mortgage) / max(len(df), 1) * 100)
        if len(full_mortgage) >= 1:
            fm_dep = float(full_mortgage['deposit'].median())
            fm_equiv = rent_monthly_equivalent(0, int(fm_dep), ratio)
            stats['full_mortgage'] = {
                'count': len(full_mortgage),
                'median_deposit': int(fm_dep),
                'median_deposit_fmt': format_toman(fm_dep),
                'median_equiv_fmt': format_toman(fm_equiv) if fm_equiv else '—',
            }
        if df['full_deposit'].notna().any():
            fd = df['full_deposit'].dropna()
            stats['full_deposit'] = {
                'median': int(fd.median()),
                'median_fmt': format_toman(fd.median()),
                'p25_fmt': format_toman(fd.quantile(0.25)),
                'p75_fmt': format_toman(fd.quantile(0.75)),
            }
        if df['rent_equiv'].notna().any():
            rev = df['rent_equiv'].dropna()
            stats['rent_equiv'] = {
                'median': int(rev.median()),
                'median_fmt': format_toman(rev.median()),
                'p25_fmt': format_toman(rev.quantile(0.25)),
                'p75_fmt': format_toman(rev.quantile(0.75)),
            }

    # امتیاز ارزش
    scored = enriched[enriched['value_score'].notna()]
    if len(scored):
        below = int((scored['value_score'] < -12).sum())
        above = int((scored['value_score'] > 12).sum())
        stats['value_distribution'] = {
            'below_market': below,
            'fair': len(scored) - below - above,
            'above_market': above,
        }

    return {
        'stats': stats,
        'enriched_df': enriched,
        'ratio': ratio,
    }


def find_value_picks(
    enriched: pd.DataFrame,
    *,
    direction: str = 'below',
    limit: int = 8,
    min_deposit_for_zero_rent: int = 50_000_000,
) -> List[Dict]:
    """
    پیشنهادهای هوشمند — بر اساس امتیاز ارزش (نه فقط اجاره خام).
    آگهی با اجاره ۰ و رهن بالا = رهن کامل، نه الزاماً زیر بازار.
    """
    df = enriched[enriched['value_score'].notna()].copy()
    if df.empty:
        return []

    # حذف موارد گمراه‌کننده: اجاره صفر با رهن پایین (داده ناقص)
    if 'rent' in df.columns and 'deposit' in df.columns:
        bad = (df['rent'].fillna(0) == 0) & (df['deposit'].fillna(0) < min_deposit_for_zero_rent)
        df = df[~bad]

    if direction == 'below':
        picks = df[df['value_score'] < -12].sort_values('value_score')
        badge = 'زیر بازار'
    else:
        picks = df[df['value_score'] > 12].sort_values('value_score', ascending=False)
        badge = 'بالای بازار'

    items = []
    for _, r in picks.head(limit).iterrows():
        score = r['value_score']
        rent_e = r.get('rent_equiv')
        reason_parts = [f'{score:g}٪ نسبت به ارزش تعدیل‌شده']
        if r.get('rent') == 0 and (r.get('deposit') or 0) > 0:
            reason_parts.append('رهن کامل / اجاره صفر')
        build_year = r.get('build_year')
        if build_year is not None and pd.notna(build_year):
            reason_parts.append(f"ساخت {int(build_year)}")
        amen = []
        if r.get('elevator'):
            amen.append('آسانسور')
        if r.get('parking'):
            amen.append('پارکینگ')
        if r.get('storage'):
            amen.append('انباری')
        if amen:
            reason_parts.append(' · '.join(amen))

        items.append({
            'listing_id': int(r['listing_id']),
            'token': str(r['token']),
            'title': str(r['title'])[:60],
            'neighborhood': str(r.get('neighborhood', '')),
            'area_fmt': format_area(r.get('area')) if pd.notna(r.get('area')) else '',
            'price_fmt': format_toman(r.get('price')) if pd.notna(r.get('price')) else '',
            'deposit_fmt': format_toman(r.get('deposit')) if pd.notna(r.get('deposit')) else '',
            'rent_fmt': format_toman(r.get('rent')) if pd.notna(r.get('rent')) and r.get('rent') else '',
            'rent_equiv_fmt': format_toman(rent_e) if pd.notna(rent_e) else '',
            'price_per_sqm_fmt': (
                format_toman(r.get('price_per_sqm'), per_sqm=True)
                if pd.notna(r.get('price_per_sqm')) else ''
            ),
            'value_score': score,
            'badge': badge,
            'reason': ' — '.join(reason_parts),
        })
    return items


def build_consultant_insights(
    df: pd.DataFrame,
    market: Dict[str, Any],
    transaction_type: str = '',
) -> List[Dict]:
    """کارت‌های تحلیل تفکیک‌شده برای مشاور."""
    from workspace.services.display import transaction_profile

    tx = transaction_profile(transaction_type)
    stats = market.get('stats', {})
    enriched = market.get('enriched_df', df)
    cards: List[Dict] = []

    # ─── متدولوژی ───
    cards.append({
        'kind': 'bullets',
        'title': 'این گزارش چطور ساخته شده؟',
        'icon': 'compass',
        'bullets': [
            'آگهی‌ها بر اساس متراژ مشابه (۵۰ تا ۷۰، ۷۰ تا ۹۰، ۹۰ تا ۱۲۰ و …) با هم مقایسه می‌شن',
            'سال ساخت و امکانات (آسانسور، پارکینگ، انباری) روی قیمت لحاظ می‌شه',
            f'برای اجاره: رهن کامل معادل = رهن + (اجاره × ۳۰)',
            'آگهی‌های خیلی غیرعادی از محاسبه حذف می‌شن تا عدد واقعی‌تر باشه',
        ],
    })

    # ─── خلاصه ویژگی‌ها ───
    summary = []
    if stats.get('row_count'):
        summary.append(f'{stats["row_count"]} آگهی فعال.')
    if stats.get('rent_equiv'):
        re = stats['rent_equiv']
        summary.append(f'اجاره معادل معمول: {re["median_fmt"]} (بازه {re["p25_fmt"]} تا {re["p75_fmt"]}).')
    if stats.get('build_year'):
        by = stats['build_year']
        summary.append(f'سال ساخت رایج: {by["median"]} (از {by["min"]} تا {by["max"]}).')
    if stats.get('area'):
        summary.append(f'متراژ رایج: {stats["area"]["median_fmt"]}.')
    if summary:
        cards.append({
            'kind': 'text',
            'title': 'خلاصه بازار',
            'icon': 'clipboard-list',
            'content': ' '.join(summary),
        })

    # ─── امکانات ───
    if stats.get('amenities'):
        cards.append({
            'kind': 'bullets',
            'title': 'پوشش امکانات در بازار',
            'icon': 'building',
            'bullets': [
                f'{a["label"]}: {a["share_pct"]}٪ آگهی‌ها'
                for a in stats['amenities']
            ],
        })

    # ─── رهن کامل ───
    if tx['is_rent'] and stats.get('full_mortgage_count', 0) > 0:
        cards.append({
            'kind': 'text',
            'title': 'توجه: رهن کامل',
            'icon': 'info-circle',
            'content': (
                f'{stats["full_mortgage_count"]} آگهی ({stats.get("full_mortgage_pct", 0)}٪) '
                f'با اجاره صفر و ودیعه بالا هستند. این‌ها لزوماً «ارزان» نیستند — '
                f'ارزش واقعی از طریق اجاره معادل (ودیعه÷{stats.get("deposit_rent_ratio_fmt")}) محاسبه می‌شود.'
            ),
        })

    # ─── توزیع ارزش ───
    if stats.get('value_distribution'):
        vd = stats['value_distribution']
        cards.append({
            'kind': 'bullets',
            'title': 'چند فایل زیر/سر/بالای بازار هستند؟',
            'icon': 'chart-pie',
            'bullets': [
                f'زیر بازار: {vd["below_market"]} فایل — اولویت پیشنهاد به خریدار',
                f'سر به سر: {vd["fair"]} فایل',
                f'بالای بازار: {vd["above_market"]} فایل — فرصت مذاکره',
            ],
        })

    # ─── پیشنهادها ───
    below = find_value_picks(enriched, direction='below')
    if below:
        cards.append({
            'kind': 'listings',
            'title': 'پیشنهاد ویژه — زیر بازار',
            'icon': 'star',
            'subtitle': 'متراژ، سال ساخت و امکانات در نظر گرفته شده',
            'listings': below,
        })

    above = find_value_picks(enriched, direction='above', limit=5)
    if above:
        cards.append({
            'kind': 'listings',
            'title': 'بالای بازار — اولویت مذاکره',
            'icon': 'arrow-trend-up',
            'subtitle': 'احتمالاً فضای مذاکره بیشتری داره',
            'listings': above,
        })

    # ─── باکت متراژ ───
    if stats.get('area_segments'):
        cards.append({
            'kind': 'bullets',
            'title': 'پراکندگی متراژ',
            'icon': 'ruler-combined',
            'bullets': [f'{s["bucket"]}: {s["count"]} فایل' for s in stats['area_segments']],
        })

    return cards
