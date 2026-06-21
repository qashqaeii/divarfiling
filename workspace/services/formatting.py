"""فرمت اعداد برای مشاور املاک — تومان، درصد، نمودار."""
from __future__ import annotations

from typing import Optional, Union

Number = Union[int, float, None]

# عرف بازار اجاره ایران: هر ۳۰ میلیون رهن ≈ ۱ میلیون اجاره ماهانه
STANDARD_DEPOSIT_RENT_RATIO = 30.0


def round_pct(value: Number, decimals: int = 1) -> Optional[float]:
    if value is None:
        return None
    if value == '' or value == '—':
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return round(f, decimals)


def format_toman(value: Number, *, per_sqm: bool = False) -> str:
    """
    نمایش قیمت برای مشاور:
    - میلیارد: یک رقم اعشار (۶.۵ میلیارد)
    - میلیون: رند به میلیون (۱۱۸ میلیون)
    """
    if value is None or (isinstance(value, float) and value != value):
        return '—'
    v = int(round(float(value)))
    suffix = ' تومان/متر' if per_sqm else ' تومان'

    if abs(v) >= 1_000_000_000:
        b = round(v / 1_000_000_000, 1)
        b_str = str(int(b)) if b == int(b) else f'{b:.1f}'
        return f'{b_str} میلیارد{suffix}'
    if abs(v) >= 1_000_000:
        m = round(v / 1_000_000)
        return f'{m:,} میلیون{suffix}'
    if abs(v) >= 1_000:
        k = round(v / 1_000)
        return f'{k:,} هزار{suffix}'
    return f'{v:,}{suffix}'


def format_toman_compact(value: Number) -> str:
    """فشرده فارسی برای جدول: 2.5 میلیارد، 250 میلیون، 100 هزار"""
    if value is None or (isinstance(value, float) and value != value):
        return '—'
    v = int(round(float(value)))
    if abs(v) >= 1_000_000_000:
        b = v / 1_000_000_000
        if b == int(b):
            b_str = str(int(b))
        else:
            b_str = f'{b:.1f}'.rstrip('0').rstrip('.')
        return f'{b_str} میلیارد'
    if abs(v) >= 1_000_000:
        return f'{round(v / 1_000_000)} میلیون'
    if abs(v) >= 1_000:
        return f'{round(v / 1_000)} هزار'
    return f'{v:,}'


def format_toman_short(value: Number) -> str:
    """اختصار برای نمودار: 200M ، 6.5B"""
    if value is None:
        return ''
    v = float(value)
    if abs(v) >= 1_000_000_000:
        return f'{round(v / 1_000_000_000, 1):g}B'
    if abs(v) >= 1_000_000:
        return f'{round(v / 1_000_000):g}M'
    if abs(v) >= 1_000:
        return f'{round(v / 1_000):g}K'
    return f'{int(v)}'


def format_range_short(low: Number, high: Number) -> str:
    return f'{format_toman_short(low)} – {format_toman_short(high)}'


def format_area(value: Number) -> str:
    if value is None:
        return '—'
    return f'{round(float(value), 1):g} متر'


def format_pct(value: Number) -> str:
    p = round_pct(value)
    if p is None:
        return '—'
    return f'{p:g}٪'


def strip_toman_suffix(text: str) -> str:
    """فقط مقدار پول — بدون «تومان/متر» برای استفاده در جمله."""
    for suf in (' تومان/متر', ' تومان', '/متر'):
        text = text.replace(suf, '')
    return text.strip()


def phrase_per_sqm_median(dist: dict, region: str = 'این منطقه') -> str:
    """قیمت میانگین هر متر در این منطقه 249 میلیون است"""
    if dist.get('median') is not None:
        amt = strip_toman_suffix(format_toman(dist['median'], per_sqm=True))
    elif dist.get('median_fmt'):
        amt = strip_toman_suffix(str(dist['median_fmt']))
    else:
        return ''
    return f'قیمت میانگین هر متر در {region} {amt} است'


def phrase_per_sqm_range(dist: dict) -> str:
    """بیشتر فایل‌ها بین X تومان تا Y تومان برای هر متر قیمت دارند"""
    if dist.get('p25') is not None and dist.get('p75') is not None:
        lo = strip_toman_suffix(format_toman(dist['p25'], per_sqm=True))
        hi = strip_toman_suffix(format_toman(dist['p75'], per_sqm=True))
    elif dist.get('range_50_fmt'):
        parts = str(dist['range_50_fmt']).split(' تا ')
        if len(parts) != 2:
            return f'بیشتر فایل‌ها در بازه {dist["range_50_fmt"]} قیمت دارند'
        lo = strip_toman_suffix(parts[0])
        hi = strip_toman_suffix(parts[1])
    else:
        return ''
    return f'بیشتر فایل‌ها بین {lo} تومان تا {hi} تومان برای هر متر قیمت دارند'


def phrase_total_price_median(dist: dict, region: str = 'این منطقه') -> str:
    if dist.get('median') is not None:
        amt = strip_toman_suffix(format_toman(dist['median']))
    elif dist.get('median_fmt'):
        amt = strip_toman_suffix(str(dist['median_fmt']))
    else:
        return ''
    return f'قیمت معمول یک واحد در {region} حدود {amt} تومان است'


def phrase_total_price_range(dist: dict) -> str:
    if dist.get('p25') is not None and dist.get('p75') is not None:
        lo = strip_toman_suffix(format_toman(dist['p25']))
        hi = strip_toman_suffix(format_toman(dist['p75']))
    elif dist.get('range_50_fmt'):
        parts = str(dist['range_50_fmt']).split(' تا ')
        if len(parts) != 2:
            return f'بیشتر واحدها بین {dist["range_50_fmt"]} قیمت دارند'
        lo = strip_toman_suffix(parts[0])
        hi = strip_toman_suffix(parts[1])
    else:
        return ''
    return f'بیشتر واحدها بین {lo} تومان تا {hi} تومان قیمت دارند'


def phrase_rent_median(dist: dict, region: str = 'این منطقه') -> str:
    if dist.get('median') is not None:
        amt = strip_toman_suffix(format_toman(dist['median']))
    elif dist.get('median_fmt'):
        amt = strip_toman_suffix(str(dist['median_fmt']))
    else:
        return ''
    return f'اجاره ماهانه معمول در {region} {amt} تومان است'


def phrase_rent_range(dist: dict) -> str:
    if dist.get('p25') is not None and dist.get('p75') is not None:
        lo = strip_toman_suffix(format_toman(dist['p25']))
        hi = strip_toman_suffix(format_toman(dist['p75']))
    elif dist.get('range_50_fmt'):
        parts = str(dist['range_50_fmt']).split(' تا ')
        if len(parts) != 2:
            return f'بیشتر قراردادها اجاره {dist["range_50_fmt"]} دارند'
        lo = strip_toman_suffix(parts[0])
        hi = strip_toman_suffix(parts[1])
    else:
        return ''
    return f'بیشتر فایل‌ها اجاره ماهانه بین {lo} تا {hi} تومان دارند'


def phrase_deposit_median(dist: dict, region: str = 'این منطقه') -> str:
    if dist.get('median') is not None:
        amt = strip_toman_suffix(format_toman(dist['median']))
    elif dist.get('median_fmt'):
        amt = strip_toman_suffix(str(dist['median_fmt']))
    else:
        return ''
    return f'ودیعه (رهن) معمول در {region} {amt} تومان است'


def format_rent_conversion_rule(ratio: float = STANDARD_DEPOSIT_RENT_RATIO) -> str:
    """عرف بازار: هر ۳۰ میلیون رهن = ۱ میلیون اجاره."""
    r = max(1, int(round(ratio)))
    return f'هر {r} میلیون رهن = ۱ میلیون اجاره ماهانه'


def phrase_rent_market_package(
    dep: dict,
    rent: dict,
    *,
    region: str = 'این منطقه',
) -> str:
    """عرف اجاره — زبان واقعی مشاوران."""
    dep_fmt = dep.get('median_fmt') or (
        format_toman(dep['median']) if dep.get('median') is not None else ''
    )
    rent_fmt = rent.get('median_fmt') or (
        format_toman(rent['median']) if rent.get('median') is not None else ''
    )
    if not dep_fmt or not rent_fmt:
        return ''
    return f'عرف اجاره در {region} حدود {dep_fmt} رهن و {rent_fmt} اجاره ماهانه است'


def phrase_rent_equiv_explained(
    dep: dict,
    rent: dict,
    rev: dict,
    *,
    ratio: float = STANDARD_DEPOSIT_RENT_RATIO,
    region: str = 'این منطقه',
) -> str:
    """توضیح اجاره معادل با نرخ تبدیل رایج بازار."""
    pkg = phrase_rent_market_package(dep, rent, region=region)
    rev_fmt = rev.get('median_fmt') or (
        format_toman(rev['median']) if rev.get('median') is not None else ''
    )
    if not pkg or not rev_fmt:
        return pkg
    rule = format_rent_conversion_rule(ratio)
    return (
        f'{pkg}. با نرخ تبدیل رایج بازار ({rule})، '
        f'ارزش این ترکیب حدود {rev_fmt} اجاره معادل محاسبه می‌شود.'
    )


def phrase_typical_unit_rent(
    area_fmt: str,
    dep: dict,
    rent: dict,
    rev: dict,
    *,
    region: str = 'این منطقه',
) -> str:
    """برای واحد معمول — بسته رهن+اجاره."""
    dep_fmt = dep.get('median_fmt', '—')
    rent_fmt = rent.get('median_fmt', '—')
    rev_fmt = rev.get('median_fmt', '')
    if not area_fmt:
        return ''
    base = f'برای واحد {area_fmt} معمولی در {region}: حدود {dep_fmt} رهن و {rent_fmt} اجاره ماهانه'
    if rev_fmt:
        return f'{base} (رهن کامل معادل حدود {rev_fmt}).'
    return f'{base}.'


def phrase_full_mortgage_market(fm: dict) -> str:
    """رهن کامل — ارزش‌گذاری بازاری."""
    count = fm.get('count', 0)
    if not count:
        return ''
    dep_fmt = fm.get('median_deposit_fmt', '—')
    equiv_fmt = fm.get('median_equiv_fmt', '—')
    if count == 1:
        return (
            f'۱ فایل رهن کامل — {dep_fmt} رهن کامل '
            f'معادل حدود {equiv_fmt} اجاره ماهانه ارزش‌گذاری می‌شود.'
        )
    return (
        f'{count} فایل رهن کامل — رهن کامل معمول بازار {dep_fmt} است '
        f'و معادل حدود {equiv_fmt} اجاره ماهانه محاسبه می‌شود.'
    )


def phrase_full_mortgage_example(deposit_fmt: str, equiv_fmt: str) -> str:
    return (
        f'فایل رهن کامل {deposit_fmt} معادل حدود {equiv_fmt} '
        f'اجاره ماهانه ارزش‌گذاری می‌شود.'
    )


def phrase_rent_depth(under_pct: float, under_count: int) -> str:
    if under_count and under_pct:
        return (
            f'{under_count} فایل با رهن کامل پایین‌تر از عرف بازار شناسایی شد '
            f'({under_pct:g}٪ از فایل‌ها).'
        )
    if under_pct:
        return f'{under_pct:g}٪ فایل‌ها رهن کامل پایین‌تر از ارزش بازار دارند.'
    return ''


def phrase_typical_area(area: dict, region: str = 'این منطقه') -> str:
    fmt = area.get('median_fmt') or (format_area(area['median']) if area.get('median') else '')
    if not fmt:
        return ''
    return f'متراژ معمول واحدها در {region} {fmt} است'


def _coerce_money(value: Number) -> Optional[int]:
    if value is None or value == '' or value == '—':
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return int(round(f))


def full_deposit_equiv(deposit: Number, rent: Number, ratio: float = STANDARD_DEPOSIT_RENT_RATIO) -> Optional[int]:
    """رهن کامل معادل: ودیعه + (اجاره × نسبت تبدیل)."""
    d_val = _coerce_money(deposit)
    r_val = _coerce_money(rent)
    if d_val is None and r_val is None:
        return None
    d = d_val or 0
    r = r_val or 0
    if d == 0 and r == 0:
        return None
    return int(d + r * max(ratio, 1))


def phrase_full_deposit_equiv_market(
    dep: dict,
    rent: dict,
    *,
    ratio: float = STANDARD_DEPOSIT_RENT_RATIO,
    region: str = 'این منطقه',
) -> str:
    """رهن کامل معادل — زبان بازار اجاره ایران."""
    dep_val = dep.get('median')
    rent_val = rent.get('median')
    total = full_deposit_equiv(dep_val, rent_val, ratio)
    if total is None:
        return ''
    dep_fmt = dep.get('median_fmt') or format_toman(dep_val)
    rent_fmt = rent.get('median_fmt') or format_toman(rent_val)
    total_fmt = format_toman(total)
    rule = format_rent_conversion_rule(ratio)
    return (
        f'رهن کامل معادل {region}: حدود {total_fmt}. '
        f'محاسبه: {dep_fmt} + ({rent_fmt} × {int(ratio)}) — عرف بازار: {rule}.'
    )


def format_amount_range(low: Number, high: Number) -> str:
    """بازه پول — حدود X تا Y."""
    if low is None or high is None:
        return ''
    lo, hi = int(round(float(low))), int(round(float(high)))
    if lo > hi:
        lo, hi = hi, lo
    if lo == hi:
        return f'حدود {format_toman(lo)}'
    return f'حدود {format_toman(lo)} تا {format_toman(hi)}'


def format_dist_range(dist: dict) -> str:
    """بازه از p25/p75 یا range_50_fmt."""
    p25, p75 = dist.get('p25'), dist.get('p75')
    if p25 is not None and p75 is not None:
        return format_amount_range(p25, p75)
    raw = dist.get('range_50_fmt', '')
    if raw:
        return f'حدود {raw}' if not str(raw).startswith('حدود') else str(raw)
    med = dist.get('median_fmt') or (format_toman(dist['median']) if dist.get('median') else '')
    return f'حدود {med}' if med else ''


def full_deposit_range(dep: dict, rent: dict, ratio: float = STANDARD_DEPOSIT_RENT_RATIO) -> str:
    """بازه رهن کامل معادل از بازه اجاره."""
    d = dep.get('median')
    if d is None:
        return ''
    r25, r75 = rent.get('p25'), rent.get('p75')
    if r25 is not None and r75 is not None:
        lo = full_deposit_equiv(d, r25, ratio)
        hi = full_deposit_equiv(d, r75, ratio)
        return format_amount_range(lo, hi)
    rmed = rent.get('median')
    total = full_deposit_equiv(d, rmed, ratio)
    return f'حدود {format_toman(total)}' if total else ''


def phrase_customer_ready_sale_range(
    unit: str,
    area: int,
    pps: dict,
    price: dict,
    *,
    region: str = 'این محدوده',
) -> str:
    """عدد آماده فروش — بازه + مرجع (زبان مشاور)."""
    med = pps.get('median')
    ref_fmt = format_toman(int(med * area)) if med else '—'
    pps_fmt = pps.get('median_fmt', '—')
    p25, p75 = pps.get('p25'), pps.get('p75')
    if p25 and p75:
        range_fmt = f'{format_toman(int(p25 * area))} تا {format_toman(int(p75 * area))}'
    else:
        range_fmt = price.get('range_50_fmt', '')
    if range_fmt:
        return (
            f'{unit} {area} متری در {region} معمولاً بین {range_fmt} معامله می‌شود. '
            f'عدد مرجع بازار: حدود {ref_fmt} (متری {pps_fmt}).'
        )
    return (
        f'{unit} {area} متری در {region} حدود {ref_fmt} می‌شود '
        f'(متری مرجع {pps_fmt}).'
    )


def phrase_commercial_comparison_basis(pps: dict, depth: dict) -> str:
    """مبنای مقایسه تجاری — فرصت خرید و مذاکره."""
    med = pps.get('median_fmt', '—')
    buy = depth.get('p40_fmt') or pps.get('p25_fmt', '—')
    sell = depth.get('p60_fmt') or pps.get('p75_fmt', '—')
    fair_lo = strip_toman_suffix(buy) if buy != '—' else ''
    fair_hi = strip_toman_suffix(sell) if sell != '—' else ''
    parts = [f'متری مرجع بازار: {med}.']
    if buy != '—':
        parts.append(f'فرصت خرید: زیر {buy}.')
    if fair_lo and fair_hi:
        parts.append(f'محدوده متعارف: {fair_lo} تا {fair_hi} تومان/متر.')
    if sell != '—':
        parts.append(f'نیازمند مذاکره: بالای {sell}.')
    return ' '.join(parts)
