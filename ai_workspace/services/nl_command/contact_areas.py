"""نرمال‌سازی و map محله‌های NL به مقادیر فایلینگ — بدون fuzzy خطرناک."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence


def _normalize_area_key(name: str) -> str:
    s = (name or '').strip()
    s = s.replace('\u200c', '').replace(' ', '').replace('‌', '')
    s = s.replace('ي', 'ی').replace('ك', 'ک')
    for i, d in enumerate('۰۱۲۳۴۵۶۷۸۹'):
        s = s.replace(d, str(i))
    return s.lower()


def map_area_names(
    raw_names: Sequence[str],
    dataset_neighborhoods: Optional[Iterable[str]] = None,
) -> List[str]:
    """
    هر نام ورودی را به مقدار canonical در فایلینگ map می‌کند اگر تطابق normalized دقیق باشد؛
    در غیر این صورت همان متن پاک‌سازی‌شده (تگ دلخواه) برمی‌گردد.
    """
    canonical: List[tuple[str, str]] = []
    for nb in dataset_neighborhoods or []:
        nb = (nb or '').strip()
        if not nb:
            continue
        canonical.append((_normalize_area_key(nb), nb))

    out: List[str] = []
    seen = set()
    for raw in raw_names:
        token = ' '.join((raw or '').split())
        if not token:
            continue
        key = _normalize_area_key(token)
        matched = None
        for ck, orig in canonical:
            if ck == key:
                matched = orig
                break
        final = matched or token
        norm_final = _normalize_area_key(final)
        if norm_final in seen:
            continue
        seen.add(norm_final)
        out.append(final)
    return out


def parse_areas_input(areas_raw) -> List[str]:
    """لیست یا رشتهٔ جدا شده با ویرگول/«و» را به لیست نام تبدیل می‌کند."""
    if areas_raw is None:
        return []
    if isinstance(areas_raw, list):
        parts = [str(x).strip() for x in areas_raw if str(x).strip()]
        return parts
    text = str(areas_raw).strip()
    if not text:
        return []
    text = text.replace('،', ',')
    chunks = re.split(r'\s+و\s+|,', text)
    return [' '.join(c.split()) for c in chunks if c.strip()]
