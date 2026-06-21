"""تاریخچه قیمت — ثبت و نمایش بدون تکرار."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

PriceSnapshot = Tuple[Optional[int], Optional[int], Optional[int]]


def price_snapshot(price, deposit, rent) -> PriceSnapshot:
    return (price, deposit, rent)


def has_price_values(snapshot: PriceSnapshot) -> bool:
    return any(v for v in snapshot)


def load_latest_snapshots(user, tokens: Iterable[str]) -> Dict[str, Optional[PriceSnapshot]]:
    """آخرین قیمت ثبت‌شده برای هر شناسه."""
    from workspace.models import PriceHistory

    token_list = list({str(t).strip() for t in tokens if t})
    if not token_list:
        return {}

    result: Dict[str, Optional[PriceSnapshot]] = {}
    rows = (
        PriceHistory.objects.filter(user=user, token__in=token_list)
        .order_by('-recorded_at')
        .values_list('token', 'price', 'deposit', 'rent')
    )
    for token, price, deposit, rent in rows:
        if token not in result:
            result[token] = price_snapshot(price, deposit, rent)
    return result


def should_record_price(
    cache: Dict[str, Optional[PriceSnapshot]],
    token: str,
    price,
    deposit,
    rent,
) -> bool:
    """فقط وقتی قیمت نسبت به آخرین رکورد تغییر کرده باشد."""
    snap = price_snapshot(price, deposit, rent)
    if not has_price_values(snap):
        return False
    prev = cache.get(token)
    if prev == snap:
        return False
    cache[token] = snap
    return True


def dedupe_price_history(records) -> list:
    """نمایش: فقط آخرین رخداد هر ترکیب قیمت/ودیعه/اجاره."""
    seen: set[PriceSnapshot] = set()
    out = []
    for ph in records:
        key = price_snapshot(ph.price, ph.deposit, ph.rent)
        if key in seen:
            continue
        seen.add(key)
        out.append(ph)
    return out
