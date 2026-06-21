"""ابزارهای محاسباتی."""
from __future__ import annotations

from typing import Dict, Optional


def deposit_rent_convert(
    full_deposit: Optional[int] = None,
    full_rent: Optional[int] = None,
    rate: int = 30,
) -> Dict:
    """تبدیل ودیعه کامل ↔ اجاره با نرخ rate:1."""
    result = {'rate': rate}
    if full_deposit and rate:
        result['monthly_rent'] = int(full_deposit / rate)
        result['from'] = 'deposit'
    elif full_rent and rate:
        result['full_deposit'] = int(full_rent * rate)
        result['from'] = 'rent'
    return result


def area_price_calc(
    price_per_sqm: Optional[float] = None,
    area: Optional[float] = None,
    total_price: Optional[int] = None,
) -> Dict:
    result = {}
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
