"""متن تحلیل بازار — زبان ساده و محاوره‌ای برای مشاور املاک."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def bucket_plain(bucket: str) -> str:
    mapping = {
        'زیر ۵۰': 'کمتر از ۵۰ متر',
        '۵۰–۷۰': '۵۰ تا ۷۰ متر',
        '۷۰–۹۰': '۷۰ تا ۹۰ متر',
        '۹۰–۱۲۰': '۹۰ تا ۱۲۰ متر',
        '۱۲۰+': 'بالای ۱۲۰ متر',
        'نامشخص': 'متراژ نامشخص',
    }
    return mapping.get(bucket, bucket)


def ui_labels(tx: Dict[str, Any]) -> Dict[str, str]:
    if tx.get('is_rent'):
        return {
            'price': 'قیمت فروش (در صورت وجود)',
            'price_per_sqm': 'قیمت هر متر',
            'area': 'متراژ رایج',
            'deposit': 'ودیعه معمول',
            'rent': 'اجاره ماهانه معمول',
            'brief_title': 'خلاصه بازار اجاره این فایل',
            'segment_title': 'اجاره و قیمت به تفکیک متراژ',
            'factor_title': 'امکانات چقدر روی قیمت اثر دارن؟',
        }
    return {
        'price': 'قیمت فروش معمول',
        'price_per_sqm': 'قیمت هر متر',
        'area': 'متراژ رایج',
        'deposit': 'ودیعه معمول',
        'rent': 'اجاره ماهانه',
        'brief_title': 'خلاصه بازار این فایل',
        'segment_title': 'قیمت به تفکیک متراژ',
        'factor_title': 'امکانات چقدر روی قیمت اثر دارن؟',
    }


def enrich_stats_plain(stats: Dict[str, Any], tx: Dict[str, Any]) -> Dict[str, Any]:
    """برچسب‌ها و توضیح ساده روی شاخص‌ها."""
    labels = ui_labels(tx)

    if stats.get('price') and stats.get('price_per_sqm') and stats.get('area'):
        p = stats['price']
        area_fmt = stats['area']['median_fmt']
        pps_fmt = stats['price_per_sqm']['median_fmt']
        p['label'] = labels['price']
        p['subtitle'] = f'معمولاً برای واحد حدود {area_fmt}'
        p['hint'] = (
            f'۵۰٪ فایل‌ها: {p.get("range_50_fmt", "—")} · '
            f'۸۰٪ فایل‌ها: {p.get("range_80_fmt", "—")}'
        )
        if p.get('implied_fmt'):
            diff = p.get('implied_diff_pct')
            if diff is not None and abs(diff) >= 3:
                if diff < 0:
                    p['compare_note'] = (
                        f'واحد {area_fmt} با متری {pps_fmt} معمولاً حدود {p["implied_fmt"]} می‌شه؛ '
                        f'ولی قیمت کل فایل‌ها کمی پایین‌تره چون متراژها یکدست نیست.'
                    )
                else:
                    p['compare_note'] = (
                        f'برای واحد {area_fmt} با متری {pps_fmt} انتظار حدود {p["implied_fmt"]} داریم؛ '
                        f'قیمت کل فایل‌ها کمی بالاتر از این برآورده.'
                    )
            else:
                p['compare_note'] = (
                    f'واحد {area_fmt} با متری {pps_fmt} حدود {p["implied_fmt"]} تمام می‌شه — '
                    f'با قیمت معمول فایل ({p["median_fmt"]}) هم‌خوانه.'
                )

        p['context_lines'] = [
            f'این عدد «قیمت وسط بازار» است: از {p.get("count", "—")} آگهی، نیمی ارزان‌تر و نیمی گران‌تر از این قیمت دارن.',
            f'متراژ رایج این فایل {area_fmt} است و قیمت هر متر معمولاً {pps_fmt}.',
            p.get('compare_note') or '',
            f'بیشتر معاملات در بازه {p.get("range_fmt", "—")} انجام می‌شه.',
        ]
        p['context_lines'] = [ln for ln in p['context_lines'] if ln]

    if stats.get('price_per_sqm'):
        stats['price_per_sqm']['label'] = labels['price_per_sqm']
        stats['price_per_sqm']['subtitle'] = (
            f'همین معیار اصلیه برای مقایسه آگهی‌ها'
            + (f' · متراژ رایج {stats["area"]["median_fmt"]}' if stats.get('area') else '')
        )
        if stats['price_per_sqm'].get('range_50_fmt'):
            stats['price_per_sqm']['hint'] = (
                f'میانه بازار: {stats["price_per_sqm"]["median_fmt"]} · '
                f'۵۰٪ فایل‌ها: {stats["price_per_sqm"]["range_50_fmt"]} · '
                f'۸۰٪ فایل‌ها: {stats["price_per_sqm"].get("range_80_fmt", "—")}'
            )

    if stats.get('area'):
        stats['area']['label'] = labels['area']
        stats['area']['subtitle'] = (
            f'از {stats["area"].get("min", "—")} تا {stats["area"].get("max", "—")} متر در این فایل دیده شده'
            if stats['area'].get('min') is not None else ''
        )
        if stats['area'].get('min') is not None:
            stats['area']['subtitle'] = (
                f'بیشتر فایل‌ها حدود {stats["area"]["median_fmt"]} · '
                f'از {int(stats["area"]["min"])} تا {int(stats["area"]["max"])} متر'
            )

    if stats.get('deposit'):
        stats['deposit']['label'] = labels['deposit']
    if stats.get('rent'):
        stats['rent']['label'] = labels['rent']

    return stats


def build_market_brief(
    stats: Dict[str, Any],
    area_segments: List[Dict[str, Any]],
    market_stats: Dict[str, Any],
    tx: Dict[str, Any],
    row_count: int = 0,
) -> str:
    """یک پاراگراف خلاصه — اولین چیزی که مشاور می‌خواند."""
    parts: List[str] = []

    if row_count:
        parts.append(f'روی {row_count} آگهی سالم این فایل کار کردیم (آگهی‌های خیلی غیرعادی حذف شدن).')

    if tx.get('is_rent') and stats.get('deposit') and stats.get('rent'):
        parts.append(
            f'ودیعه معمول {stats["deposit"]["median_fmt"]} و اجاره ماهانه معمول '
            f'{stats["rent"]["median_fmt"]} است.'
        )
    elif stats.get('price_per_sqm') and stats.get('area'):
        area_fmt = stats['area']['median_fmt']
        pps = stats['price_per_sqm']['median_fmt']
        parts.append(
            f'متراژ رایج حدود {area_fmt} است و قیمت هر متر معمولاً {pps}.'
        )
        if stats.get('price'):
            parts.append(
                f'قیمت فروش معمول کل فایل {stats["price"]["median_fmt"]} است'
                f' — بیشتر فایل‌ها بین {stats["price"].get("range_fmt", "—")} قیمت‌گذاری شدن.'
            )
            if stats['price'].get('compare_note'):
                parts.append(stats['price']['compare_note'])

    if area_segments:
        top = max(area_segments, key=lambda s: s['count'])
        parts.append(
            f'بیشترین فایل‌ها توی محدوده {top.get("bucket_plain", top["bucket"])} هستن '
            f'({top["count"]} آگهی).'
        )

    vd = market_stats.get('value_distribution')
    if vd:
        parts.append(
            f'از نظر قیمت: {vd["below_market"]} فایل زیر بازار، '
            f'{vd["fair"]} فایل سر به سر، و {vd["above_market"]} فایل بالای بازار دیده می‌شه.'
        )

    if stats.get('consultant_pct') is not None:
        cp = stats['consultant_pct']
        if cp and cp > 60:
            parts.append(f'بازار عمدتاً فایل مشاوره ({cp}٪) — رقابت روی کیفیت فایل و سرعت مهمه.')
        else:
            parts.append(f'سهم آگهی شخصی هم بالاست — فرصت تماس مستقیم با مالک بیشتره.')

    return ' '.join(parts)


def enrich_segments_plain(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for seg in segments:
        seg['bucket_plain'] = bucket_plain(seg['bucket'])
        seg['summary'] = _segment_summary(seg)
    return segments


def _segment_summary(seg: Dict[str, Any]) -> str:
    bits = [f'{seg["count"]} فایل در محدوده {seg["bucket_plain"]}']
    if seg.get('median_area_fmt'):
        bits.append(f'متراژ معمول {seg["median_area_fmt"]}')
    if seg.get('median_pps_fmt'):
        bits.append(f'متری {seg["median_pps_fmt"]}')
    if seg.get('median_price_fmt'):
        bits.append(f'قیمت کل معمول {seg["median_price_fmt"]}')
    return ' · '.join(bits)


def enrich_factors_plain(factors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for f in factors:
        label = f['label']
        premium = f.get('premium_pct')
        if label == 'سال ساخت':
            if premium is not None:
                if premium > 3:
                    f['plain'] = (
                        f'واحد نوسازتر معمولاً متری حدود {abs(premium):g}٪ گرون‌تر از بناهای قدیمی‌تره.'
                    )
                elif premium < -3:
                    f['plain'] = (
                        f'بناهای قدیمی‌تر در این فایل متری حدود {abs(premium):g}٪ ارزون‌ترن.'
                    )
                else:
                    f['plain'] = 'سال ساخت توی این فایل اختلاف قیمت چشمگیری ایجاد نکرده.'
            continue

        if premium is None:
            f['plain'] = f'درباره {label} داده کافی برای مقایسه نیست.'
        elif premium > 3:
            f['plain'] = (
                f'واحد با {label} معمولاً متری حدود {abs(premium):g}٪ گرون‌تر از بدون {label} است '
                f'({f["with_median_fmt"]} در برابر {f["without_median_fmt"]}).'
            )
        elif premium < -3:
            f['plain'] = (
                f'عجیبانه اما در این فایل، بدون {label} گرون‌تر دیده شده — '
                f'احتمالاً به‌خاطر متراژ یا محله متفاوته.'
            )
        else:
            f['plain'] = f'{label} توی این فایل اختلاف قیمت زیادی ایجاد نکرده.'
    return factors


def build_insights_plain(
    stats: Dict[str, Any],
    area_segments: List[Dict[str, Any]],
    factors: List[Dict[str, Any]],
    market_stats: Dict[str, Any],
    tx: Dict[str, Any],
) -> List[str]:
    """نکات کاربردی برای مشاور — بدون اصطلاح آماری."""
    tips: List[str] = []

    if stats.get('price_per_sqm'):
        pps = stats['price_per_sqm']
        tips.append(
            f'برای مذاکره، قیمت هر متر رو مبنا بگیر: معمولاً {pps["median_fmt"]} '
            f'و بازه رایج {pps.get("range_fmt", "—")}.'
        )

    if area_segments:
        for seg in area_segments[:3]:
            if seg.get('summary'):
                tips.append(seg['summary'] + '.')

    for f in factors:
        if f.get('plain'):
            tips.append(f['plain'])

    vd = market_stats.get('value_distribution')
    if vd and vd.get('below_market', 0) > 0:
        tips.append(
            f'{vd["below_market"]} فایل زیر بازار هست — برای پیشنهاد به خریدار اولویت بده.'
        )

    if tx.get('show_price') and stats.get('price'):
        tips.append(
            f'قبل از بازدید به مشتری بگو: فایل‌های این محله معمولاً حدود '
            f'{stats["price"]["median_fmt"]} (متراژ رایج {stats.get("area", {}).get("median_fmt", "—")}) قیمت‌گذاری می‌شن.'
        )

    return tips[:6]


def enrich_scenarios_plain(scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for s in scenarios:
        s['title'] = s.get('title', '').replace('باکت ', '')
        s['plain_title'] = bucket_plain(s['title']) if 'متر' not in s['title'] else s['title']
        s['note'] = (
            f'{s.get("count", "—")} فایل · متری {s.get("pps_fmt", "—")} · '
            f'برآورد کل {s.get("expected_price_fmt", "—")}'
        )
    return scenarios


def enrich_report_for_agents(
    report: Dict[str, Any],
    *,
    dataset_name: str = '',
    subcategory: str = '',
    transaction_type: str = '',
    factors=None,
    stats=None,
    df=None,
) -> Dict[str, Any]:
    from workspace.services.market_agent import enrich_report_for_agents as _enrich
    return _enrich(
        report,
        dataset_name=dataset_name,
        subcategory=subcategory,
        transaction_type=transaction_type,
        factors=factors,
        stats=stats,
        df=df,
    )
