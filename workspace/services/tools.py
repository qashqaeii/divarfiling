"""ابزارهای محاسباتی."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.services.formatting import full_deposit_equiv


def deposit_rent_convert(
    full_deposit: Optional[int] = None,
    full_rent: Optional[int] = None,
    rate: int = 30,
) -> Dict:
    """تبدیل ودیعه کامل ↔ اجاره با نرخ rate:1."""
    result: Dict[str, Any] = {'rate': rate}
    if full_deposit and rate:
        result['monthly_rent'] = int(full_deposit / rate)
        result['from'] = 'deposit'
    elif full_rent and rate:
        result['full_deposit'] = int(full_rent * rate)
        result['from'] = 'rent'
    return result


def mixed_rent_calc(
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    rate: int = 30,
) -> Dict:
    """رهن ترکیبی → رهن کامل و اجاره کامل معادل."""
    if deposit is None and rent is None:
        return {}
    if not rate:
        return {}
    d = deposit or 0
    r = rent or 0
    if d == 0 and r == 0:
        return {}
    full_dep = full_deposit_equiv(d, r, rate)
    if full_dep is None:
        return {}
    return {
        'deposit': d,
        'rent': r,
        'rate': rate,
        'full_deposit': full_dep,
        'full_rent': int(full_dep / rate),
    }


def _listing_compare_row(
    *,
    price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    area: Optional[float] = None,
    label: str = '',
    is_rent: bool = False,
    rate: int = 30,
) -> Optional[Dict]:
    if not area or area <= 0:
        return None
    if is_rent:
        fd = full_deposit_equiv(deposit, rent, rate)
        if fd is None:
            return None
        return {
            'label': label,
            'area': area,
            'full_deposit': fd,
            'per_sqm': round(fd / area),
            'metric': 'full_deposit',
        }
    if not price:
        return None
    return {
        'label': label,
        'area': area,
        'price': price,
        'per_sqm': round(price / area),
        'metric': 'price',
    }


def compare_properties(
    a: Dict[str, Any],
    b: Dict[str, Any],
    *,
    is_rent: bool = False,
    rate: int = 30,
) -> Dict:
    """مقایسه دو ملک — نرمال‌سازی با قیمت هر متر یا رهن کامل هر متر."""
    keys = ('price', 'deposit', 'rent', 'area', 'label')
    row_a = _listing_compare_row(is_rent=is_rent, rate=rate, **{k: a.get(k) for k in keys})
    row_b = _listing_compare_row(is_rent=is_rent, rate=rate, **{k: b.get(k) for k in keys})
    result: Dict[str, Any] = {
        'is_rent': is_rent,
        'rate': rate,
        'a': row_a,
        'b': row_b,
    }
    if not row_a or not row_b:
        return result
    pps_a = row_a['per_sqm']
    pps_b = row_b['per_sqm']
    if not pps_a or not pps_b:
        return result
    diff_pct = round((pps_b - pps_a) / pps_a * 100, 1) if pps_a else None
    if diff_pct is None:
        return result
    if diff_pct < -1:
        winner = 'b'
        verdict = f'{b.get("label") or "آگهی ب"} ارزان‌تر است'
    elif diff_pct > 1:
        winner = 'a'
        verdict = f'{a.get("label") or "آگهی الف"} ارزان‌تر است'
    else:
        winner = 'tie'
        verdict = 'تقریباً برابر'
    result.update({
        'diff_pct': diff_pct,
        'winner': winner,
        'verdict': verdict,
        'cheaper_per_sqm': min(pps_a, pps_b),
    })
    return result


def discount_calc(list_price: int, discount_pct: float) -> Dict:
    """تخفیف از قیمت آگهی."""
    discount_pct = max(0.0, min(discount_pct, 100.0))
    savings = int(list_price * discount_pct / 100)
    final_price = list_price - savings
    return {
        'list_price': list_price,
        'discount_pct': discount_pct,
        'savings': savings,
        'final_price': final_price,
    }


def rent_commission_calc(
    monthly_rent: int,
    tenant_share: float = 50.0,
    landlord_share: float = 50.0,
) -> Dict:
    """کمیسیون اجاره — سهم مستأجر و مالک (پایه: نصف اجاره هر طرف)."""
    tenant = int(monthly_rent * tenant_share / 100)
    landlord = int(monthly_rent * landlord_share / 100)
    return {
        'monthly_rent': monthly_rent,
        'tenant_commission': tenant,
        'landlord_commission': landlord,
        'total_commission': tenant + landlord,
        'tenant_share': tenant_share,
        'landlord_share': landlord_share,
    }


def budget_calc(
    budget: int,
    price_per_sqm: Optional[float] = None,
    area: Optional[float] = None,
) -> Dict:
    """بودجه مشتری ↔ متراژ یا قیمت متر."""
    result: Dict[str, Any] = {'budget': budget}
    if budget and price_per_sqm and price_per_sqm > 0 and not area:
        max_area = round(budget / price_per_sqm, 1)
        result['mode'] = 'max_area'
        result['max_area'] = max_area
        result['price_per_sqm'] = price_per_sqm
    elif budget and area and area > 0 and not price_per_sqm:
        required_pps = int(budget / area)
        result['mode'] = 'required_pps'
        result['required_pps'] = required_pps
        result['area'] = area
    elif budget and price_per_sqm and area and price_per_sqm > 0 and area > 0:
        total = int(price_per_sqm * area)
        result['mode'] = 'affordability'
        result['total_price'] = total
        result['price_per_sqm'] = price_per_sqm
        result['area'] = area
        result['affordable'] = total <= budget
        result['shortfall'] = max(0, total - budget)
        result['surplus'] = max(0, budget - total)
    return result


def pricing_suggest(
    area: float,
    market_median_pps: float,
    adjustment_pct: float = 0.0,
) -> Dict:
    """قیمت‌گذاری بر اساس میانه بازار."""
    if not area or area <= 0 or not market_median_pps or market_median_pps <= 0:
        return {}
    adj = 1 + adjustment_pct / 100
    suggested_pps = market_median_pps * adj
    total = int(suggested_pps * area)
    return {
        'area': area,
        'market_median_pps': market_median_pps,
        'adjustment_pct': adjustment_pct,
        'suggested_pps': round(suggested_pps),
        'suggested_total': total,
    }


def area_price_calc(
    price_per_sqm: Optional[float] = None,
    area: Optional[float] = None,
    total_price: Optional[int] = None,
) -> Dict:
    result: Dict[str, Any] = {}
    if price_per_sqm and area:
        result['total_price'] = int(price_per_sqm * area)
        result['price_per_sqm'] = price_per_sqm
        result['area'] = area
    elif total_price and area and area > 0:
        result['price_per_sqm'] = int(total_price / area)
        result['total_price'] = total_price
        result['area'] = area
    elif total_price and price_per_sqm and price_per_sqm > 0:
        result['area'] = round(total_price / price_per_sqm, 1)
        result['total_price'] = total_price
        result['price_per_sqm'] = price_per_sqm
    return result


def commission_calc(price: int, buyer_pct: float = 1.0, seller_pct: float = 1.0) -> Dict:
    buyer = int(price * buyer_pct / 100)
    seller = int(price * seller_pct / 100)
    return {
        'price': price,
        'buyer_commission': buyer,
        'seller_commission': seller,
        'total_commission': buyer + seller,
        'buyer_pct': buyer_pct,
        'seller_pct': seller_pct,
    }


def build_market_snapshot(dataset) -> Dict[str, Any]:
    """آمار بازار یک فایل — برای ابزارهای هوشمند."""
    from workspace.services.analyzer import compute_statistics, listings_to_dataframe
    from workspace.services.valuation import market_deposit_rent_ratio, standard_deposit_rent_ratio

    listings = list(dataset.listings.all())
    df = listings_to_dataframe(listings)
    stats = compute_statistics(df, dataset.transaction_type or '')
    tx = stats.get('tx') or {}
    ratio = market_deposit_rent_ratio(df) if len(df) >= 5 else standard_deposit_rent_ratio()
    pps = stats.get('price_per_sqm') or {}
    price = stats.get('price') or {}
    area = stats.get('area') or {}

    snapshot: Dict[str, Any] = {
        'dataset_id': str(dataset.pk),
        'dataset_name': dataset.name,
        'transaction_type': dataset.transaction_type or '',
        'row_count': stats.get('row_count', 0),
        'is_rent': bool(tx.get('is_rent')),
        'show_price_per_sqm': bool(tx.get('show_price_per_sqm', True)),
        'ratio': round(float(ratio), 1),
        'median_pps': pps.get('median'),
        'pps_p25': pps.get('p25'),
        'pps_p75': pps.get('p75'),
        'median_price': price.get('median'),
        'median_area': area.get('median'),
        'analyze_url': f'/workspace/datasets/{dataset.pk}/analyze/',
    }

    if tx.get('is_rent'):
        dep_med = (stats.get('deposit') or {}).get('median')
        rent_med = (stats.get('rent') or {}).get('median')
        snapshot['median_deposit'] = dep_med
        snapshot['median_rent'] = rent_med
        fd = full_deposit_equiv(dep_med, rent_med, ratio)
        if fd:
            snapshot['median_full_deposit'] = fd
            med_area = area.get('median')
            if med_area and not snapshot.get('median_pps'):
                snapshot['median_pps'] = int(fd / med_area)
                snapshot['pps_metric'] = 'full_deposit_per_sqm'

    snapshot['supports_pricing'] = bool(snapshot.get('median_pps'))
    return snapshot
