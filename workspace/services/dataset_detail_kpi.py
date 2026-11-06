"""KPIهای تحلیلی صفحه جزئیات پوشه استخراج — فقط از داده معتبر."""
from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any, Dict, Optional, Sequence

from django.utils import timezone

from workspace.services.formatting import format_area, format_toman_compact

_MIN_PRICE_SAMPLES = 3
_MIN_AREA_SAMPLES = 3
_MIN_PUBLISHED_COVERAGE = 0.25


def _positive_values(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values if v is not None and float(v) > 0]


def _positive_median(values: Sequence[float]) -> Optional[float]:
    clean = _positive_values(values)
    if len(clean) < _MIN_PRICE_SAMPLES:
        return None
    return float(median(clean))


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return '—'
    return format_toman_compact(value)


def _fmt_area_short(value: Optional[float]) -> str:
    if value is None:
        return '—'
    return f'{round(float(value), 1):g}'


def build_dataset_detail_insight_kpis(
    *,
    listings_qs,
    tx: Dict[str, Any],
    total_count: int,
    genuine_count: int,
    genuine_pct: int,
) -> Dict[str, Any]:
    """چهار KPI تصمیم‌یار برای جزئیات پوشه + پرچم‌های نمایش."""
    total = int(total_count or 0)
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # ── ۱) آگهی‌های جدید (۷ روز) ──
    published_known = listings_qs.exclude(published_at__isnull=True).count()
    coverage = (published_known / total) if total else 0
    new_kpi: Dict[str, Any]
    if total and coverage >= _MIN_PUBLISHED_COVERAGE:
        new_n = listings_qs.filter(published_at__gte=week_ago).count()
        new_kpi = {
            'has_value': True,
            'value': new_n,
            'value_display': str(new_n),
            'share': round(new_n * 100 / total) if total else 0,
            'meta': 'منتشرشده در ۷ روز اخیر',
            'hint': f'بر اساس تاریخ انتشار · پوشش {round(coverage * 100)}٪',
        }
    else:
        new_kpi = {
            'has_value': False,
            'value': None,
            'value_display': '—',
            'share': 0,
            'meta': 'منتشرشده در ۷ روز اخیر',
            'hint': 'تاریخ انتشار معتبر کافی نیست',
        }

    # ── ۲) مالک‌های مستقیم ──
    genuine = int(genuine_count or 0)
    owners_kpi = {
        'has_value': bool(total),
        'value': genuine if total else None,
        'value_display': str(genuine) if total else '—',
        'share': int(genuine_pct or 0) if total else 0,
        'meta': f'{int(genuine_pct or 0)}٪ از پوشه' if total else 'بر اساس تشخیص معتبر',
        'hint': 'تشخیص از متن/نوع آگهی‌دهنده (مالک واقعی)',
    }

    # ── ۳) شاخص قیمت ──
    price_kpi = _build_price_kpi(listings_qs, tx, total)

    # ── ۴) میانه متراژ ──
    area_kpi = _build_area_kpi(listings_qs, total)

    return {
        'insight_new': new_kpi,
        'insight_owners': owners_kpi,
        'insight_price': price_kpi,
        'insight_area': area_kpi,
    }


def _build_price_kpi(listings_qs, tx: Dict[str, Any], total: int) -> Dict[str, Any]:
    empty = {
        'has_value': False,
        'value': None,
        'value_display': '—',
        'secondary_display': '',
        'share': 0,
        'meta': 'بر اساس قیمت‌های معتبر',
        'hint': 'داده قیمت کافی نیست',
        'mode': 'none',
    }
    if not total:
        return empty

    if tx.get('is_rent') and not tx.get('is_mixed'):
        deposits = list(
            listings_qs.exclude(deposit__isnull=True)
            .exclude(deposit__lte=0)
            .values_list('deposit', flat=True)[:5000]
        )
        rents = list(
            listings_qs.exclude(rent__isnull=True)
            .exclude(rent__lte=0)
            .values_list('rent', flat=True)[:5000]
        )
        med_dep = _positive_median(deposits)
        med_rent = _positive_median(rents)
        if med_dep is None and med_rent is None:
            return empty
        sample_n = max(len(deposits), len(rents))
        if med_dep is not None:
            primary = _fmt_money(med_dep)
            secondary = f'اجاره {_fmt_money(med_rent)}' if med_rent is not None else ''
            label_meta = 'میانه رهن'
        else:
            primary = _fmt_money(med_rent)
            secondary = ''
            label_meta = 'میانه اجاره'
        return {
            'has_value': True,
            'value': med_dep if med_dep is not None else med_rent,
            'value_display': primary,
            'secondary_display': secondary,
            'share': round(sample_n * 100 / total) if total else 0,
            'meta': f'{label_meta} · {sample_n} نمونه معتبر',
            'hint': 'فقط مقادیر عددی مثبت',
            'mode': 'rent',
            'title': 'میانه رهن و اجاره',
        }

    # فروش / ترکیبی: میانه قیمت و قیمت هر متر
    rows = list(
        listings_qs.exclude(price__isnull=True)
        .exclude(price__lte=0)
        .values_list('price', 'area')[:5000]
    )
    prices = [p for p, _a in rows if p and p > 0]
    med_price = _positive_median(prices)
    pps = [
        p / a for p, a in rows
        if p and p > 0 and a is not None and float(a) > 0
    ]
    med_pps = _positive_median(pps)
    if med_price is None and med_pps is None:
        return {
            **empty,
            'title': 'میانه قیمت',
            'meta': 'بر اساس قیمت‌های معتبر',
        }
    return {
        'has_value': True,
        'value': med_price if med_price is not None else med_pps,
        'value_display': _fmt_money(med_price) if med_price is not None else _fmt_money(med_pps),
        'secondary_display': (
            f'هر متر {_fmt_money(med_pps)}' if med_pps is not None and med_price is not None
            else ('' if med_price is not None else '')
        ),
        'share': round(len(prices) * 100 / total) if total and prices else 0,
        'meta': f'میانه قیمت · {len(prices)} نمونه معتبر' if prices else 'میانه قیمت هر متر',
        'hint': 'فقط قیمت‌های عددی مثبت',
        'mode': 'sale',
        'title': 'میانه قیمت',
    }


def _build_area_kpi(listings_qs, total: int) -> Dict[str, Any]:
    empty = {
        'has_value': False,
        'value': None,
        'value_display': '—',
        'secondary_display': '',
        'share': 0,
        'meta': 'بر اساس متراژهای معتبر',
        'hint': 'متراژ عددی کافی نیست',
        'sample_count': 0,
        'min_area': None,
        'max_area': None,
    }
    if not total:
        return empty

    areas = _positive_values(
        listings_qs.exclude(area__isnull=True)
        .exclude(area__lte=0)
        .values_list('area', flat=True)[:5000]
    )
    if len(areas) < _MIN_AREA_SAMPLES:
        return empty

    med = float(median(areas))
    lo, hi = min(areas), max(areas)
    sample_n = len(areas)
    return {
        'has_value': True,
        'value': med,
        'value_display': format_area(med),
        'secondary_display': f'بازه {_fmt_area_short(lo)}–{_fmt_area_short(hi)} متر',
        'share': round(sample_n * 100 / total) if total else 0,
        'meta': f'{sample_n} نمونه معتبر',
        'hint': 'فقط متراژهای عددی مثبت',
        'sample_count': sample_n,
        'min_area': lo,
        'max_area': hi,
    }

