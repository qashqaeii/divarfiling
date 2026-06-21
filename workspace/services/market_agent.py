"""متن تحلیل — زبان ساده و کاربردی برای مشاور املاک."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from workspace.services.formatting import (
    format_area,
    format_toman,
    format_amount_range,
    full_deposit_equiv,
    phrase_commercial_comparison_basis,
    phrase_customer_ready_sale_range,
    phrase_full_deposit_equiv_market,
    phrase_per_sqm_median,
    phrase_per_sqm_range,
    phrase_rent_range,
    phrase_total_price_median,
    phrase_total_price_range,
    phrase_typical_area,
    phrase_typical_unit_rent,
    strip_toman_suffix,
)
from workspace.services.market_analytics import CURRENT_JALALI_YEAR
from workspace.services.market_context import build_action_cards, build_analysis_header, detect_market_context

MIN_SUBSET = 3
MIN_SUBSET_SHOW = 30
MIN_SUBSET_WARN = 50
FULL_AMENITY_FIELDS = ('elevator', 'parking', 'storage')


def enrich_report_for_agents(
    report: Dict[str, Any],
    *,
    dataset_name: str = '',
    subcategory: str = '',
    transaction_type: str = '',
    factors: Optional[List[Dict[str, Any]]] = None,
    stats: Optional[Dict[str, Any]] = None,
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    report = dict(report)
    ctx = detect_market_context(
        dataset_name,
        subcategory,
        transaction_type or report.get('tx', {}).get('mode', ''),
    )
    report['context'] = ctx
    report['labels'] = ctx['labels']
    report['practical_scenarios'] = _build_practical_scenarios(report, ctx, stats or {}, df)
    primary, extra = _split_scenario_cards(report['practical_scenarios'])
    report['practical_scenarios_primary'] = primary
    report['practical_scenarios_extra'] = extra
    is_rent = ctx.get('deal') == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv'
    if is_rent:
        report['professional_summary'] = _build_rent_professional_summary(report, ctx, stats or {})
        report['summary_lines'] = []
        report['summary'] = report['professional_summary'].get('intro', '')
    else:
        report['professional_summary'] = None
        report['summary_lines'] = _build_summary_lines(report, ctx, stats or {})
        report['summary'] = '\n'.join(report['summary_lines'])
    report['segment_notes'] = _build_segment_notes(report, ctx)
    report['factor_insights'] = _build_factor_insights(factors or [], ctx)
    report['insight_sections'] = _build_insight_sections(report, ctx, factors or [], stats or {})
    report['insights'] = _flatten_sections(report['insight_sections'])
    report['negotiation'] = _build_negotiation(report, ctx)
    report['confidence'] = _plain_confidence(report.get('confidence', {}))
    report['actions'] = build_action_cards(report, ctx)
    report['quick_snapshot'] = _build_quick_snapshot(report, ctx, stats or {})
    dq = report.get('data_quality') or {}
    scope = report.get('publication_scope') or {}
    report['header'] = build_analysis_header(
        dataset_name=dataset_name,
        ctx=ctx,
        valid_count=int(dq.get('valid_count') or scope.get('analyzed_count') or 0),
        scope_line=scope.get('line', ''),
    )
    report['expert_details'] = _build_expert_details(report, ctx)
    warn = _data_quality_warning(report, ctx)
    if warn:
        report['data_quality_warning'] = warn
        if is_rent and report.get('professional_summary'):
            report['professional_summary']['quality_note'] = (
                f'{report["professional_summary"].get("quality_note", "")} {warn}'.strip()
            )
        else:
            report['summary_lines'] = [warn] + report.get('summary_lines', [])
            report['summary'] = '\n'.join(report['summary_lines'])
    return report


def _data_quality_warning(report: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """هشدار وقتی قیمت‌ها برای نوع ملک غیرواقعی به نظر می‌رسند."""
    if ctx.get('prop') != 'commercial' or ctx.get('deal') != 'sale':
        return ''
    pa = report.get('price_analysis', {})
    pps = (pa.get('price_per_sqm') or {}).get('median')
    price = (pa.get('price') or {}).get('median')
    if pps is not None and pps < 1_000_000:
        return (
            '🟠 هشدار کیفیت داده: بخشی از فایل‌های این بازار قیمت غیرواقعی یا ناقص دارند — '
            'اعداد متری را با احتیاط تفسیر کن و قبل از مذاکره فایل را دستی بررسی کن.'
        )
    if price is not None and price < 100_000_000 and pps is not None and pps < 5_000_000:
        return (
            '🟠 هشدار کیفیت داده: قیمت کل یا متری با عرف بازار اداری/تجاری هم‌خوان نیست — '
            'احتمال آلودگی داده یا واحد قیمت اشتباه وجود دارد.'
        )
    return ''


def _plain_confidence(conf: Any) -> Dict[str, Any]:
    """
    Normalize `report["confidence"]` into a stable dict shape.

    The template expects `score`, `display_score`, `level_plain`.
    Some pipelines occasionally pass `confidence` as an empty string or with
    a non-numeric `score` value; we defensively coerce to safe defaults.
    """
    if conf is None or isinstance(conf, str):
        conf = {}
    elif isinstance(conf, dict):
        conf = dict(conf)
    else:
        try:
            conf = dict(conf)
        except Exception:
            conf = {}

    raw = conf.get('display_score', conf.get('score', 0))
    try:
        raw_int = int(raw)
    except (TypeError, ValueError):
        raw_int = 0

    display = min(100, raw_int)
    conf['score'] = display
    conf['display_score'] = display

    level = conf.get('level', '') or ''
    mapping = {
        'بسیار بالا': 'بسیار بالا',
        'بالا': 'بالا',
        'متوسط': 'متوسط',
        'پایین': 'پایین',
        'ضعیف': 'ضعیف',
    }
    conf['level_plain'] = mapping.get(level, level or '—')
    conf['level_hint'] = {
        'بسیار بالا': 'داده کافی — با اطمینان به مشتری بگو',
        'بالا': 'قابل اعتماد — برای مذاکره مناسب',
        'متوسط': 'متوسط — با بازدید تأیید کن',
        'پایین': 'کم‌اطمینان — فقط راهنمای اولیه',
        'ضعیف': 'فقط راهنما — حتماً بررسی میدانی',
    }.get(level, '')
    return conf


def resolve_report_confidence(
    report: Dict[str, Any],
    *,
    valid_count: int = 0,
    raw_count: int = 0,
) -> Dict[str, Any]:
    """Ensure confidence dict has a numeric score (recompute if corrupted)."""
    from workspace.services.market_analytics import compute_confidence_score

    conf = _plain_confidence(report.get('confidence', {}))
    if conf.get('display_score'):
        return conf

    dq = report.get('data_quality') or {}
    pa = report.get('price_analysis') or {}
    n_valid = int(dq.get('valid_count') or valid_count or 0)
    n_raw = int(dq.get('raw_count') or raw_count or n_valid or 0)
    removed = int(dq.get('removed_count') or max(n_raw - n_valid, 0))
    outlier_pct = round(removed / max(n_raw, 1) * 100) if n_raw else 0
    pps_cv = (
        (pa.get('price_per_sqm') or {}).get('cv')
        or (pa.get('full_deposit') or {}).get('cv')
        or (pa.get('rent') or {}).get('cv')
        or 20
    )
    return _plain_confidence(
        compute_confidence_score(n_valid, n_raw, outlier_pct, pps_cv or 20),
    )


def _district_label(report: Dict[str, Any]) -> str:
    nb = report.get('neighborhoods') or []
    if len(nb) == 1:
        return str(nb[0].get('neighborhood', ''))
    if report.get('dataset_name'):
        return str(report['dataset_name'])
    return 'این منطقه'


_L2_DUP_ACTION_TITLES = frozenset({
    'عدد آماده برای مشتری',
    'رهن کامل معادل',
    'صحبت با مشتری',
})


def _build_property_basis(
    report: Dict[str, Any],
    ctx: Dict[str, Any],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    """سطح ۱ — توضیح می‌دهد اعداد میانه برای چه ملکی است."""
    segs = report.get('area_segments') or []
    amen = report.get('amenities_coverage') or []
    build = report.get('build_year') or {}
    area = stats.get('area') or {}
    deal = ctx.get('deal')
    unit_word = _seg(ctx).get('unit_word', 'واحد')
    pa = report.get('price_analysis', {})

    basis: Dict[str, Any] = {
        'title': 'مبنای اعداد — ملک مرجع',
        'headline': '',
        'facts': [],
        'amenities': [],
        'segment_hint': '',
        'amenity_note': '',
        'note': 'برای متراژ یا امکانات متفاوت، جدول بخش «متراژ» در سطح ۲ را ببینید.',
    }

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        basis['headline'] = (
            'رهن و اجاره معمول = میانه کل فایل‌های این بازار (همه متراژها)، '
            'نه یک واحد مشخص با امکانات خاص.'
        )
    elif ctx.get('prop') in ('land', 'project'):
        basis['headline'] = (
            'قیمت معمول = میانه کل فایل‌ها — در زمین و پروژه روی قیمت کل تمرکز کن، نه فقط متری.'
        )
    else:
        basis['headline'] = (
            'قیمت معمول = میانه کل فایل‌های بازار؛ '
            f'{unit_word} ۵۰ متری فول امکانات با ۱۰۰ متری بدون پارکینگ قیمت متفاوت دارد.'
        )

    if area.get('median_fmt'):
        basis['facts'].append({
            'label': 'متراژ میانه کل فایل‌ها',
            'value': area['median_fmt'],
            'icon': 'fa-ruler-combined',
        })
    if area.get('range_fmt'):
        basis['facts'].append({
            'label': 'بازه متراژ رایج',
            'value': area['range_fmt'],
            'icon': 'fa-arrows-left-right',
        })
    elif area.get('min') and area.get('max'):
        basis['facts'].append({
            'label': 'دامنه متراژ فایل‌ها',
            'value': f'{format_area(area["min"])} تا {format_area(area["max"])}',
            'icon': 'fa-arrows-left-right',
        })

    if segs:
        top = max(segs, key=lambda s: s.get('count', 0))
        bucket = top.get('bucket_plain') or top.get('bucket', '')
        share = top.get('share_pct', 0)
        basis['facts'].append({
            'label': 'پرتقاضاترین بازه متراژ',
            'value': f'{bucket} — {top["count"]} فایل ({share}٪)',
            'icon': 'fa-chart-pie',
        })
        if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
            dep_fmt = top.get('median_deposit_fmt')
            rent_fmt = top.get('median_rent_fmt')
            full_fmt = top.get('median_full_deposit_fmt')
            if dep_fmt and rent_fmt:
                hint = f'در بازه {bucket}: {dep_fmt} رهن + {rent_fmt} اجاره'
                if full_fmt:
                    hint += f' (رهن کامل {full_fmt})'
                basis['segment_hint'] = hint
        elif top.get('median_pps_fmt'):
            hint = f'در بازه {bucket}: متری {top["median_pps_fmt"]}'
            if top.get('median_price_fmt'):
                hint += f' · قیمت کل {top["median_price_fmt"]}'
            basis['segment_hint'] = hint
        elif top.get('median_price_fmt'):
            basis['segment_hint'] = f'در بازه {bucket}: قیمت کل {top["median_price_fmt"]}'

    if build.get('median_year') and ctx.get('show_build_year'):
        age = build.get('median_age')
        val = str(build['median_year'])
        if age:
            val += f' (حدود {age} سال)'
        basis['facts'].append({
            'label': 'سال ساخت میانه',
            'value': val,
            'icon': 'fa-calendar',
        })

    for item in sorted(amen, key=lambda x: -(x.get('coverage_pct') or 0))[:4]:
        pct = item.get('coverage_pct') or 0
        if pct > 0:
            basis['amenities'].append({'label': item['label'], 'pct': pct})

    if basis['amenities']:
        common = [a for a in basis['amenities'] if a['pct'] >= 50]
        if common:
            names = '، '.join(a['label'] for a in common[:3])
            basis['amenity_note'] = f'امکانات رایج در بیشتر فایل‌ها: {names}'
        else:
            basis['amenity_note'] = 'امکانات در فایل‌ها پراکنده است — هر آگهی را جدا بررسی کن.'

    av = report.get('amenity_valuation') or {}
    if av.get('headline'):
        basis['amenity_valuation'] = av
    elif av.get('full_vs_bare', {}).get('gap_pct'):
        gap = av['full_vs_bare']['gap_pct']
        basis['amenity_valuation'] = {
            **av,
            'headline': (
                f'فول امکانات حدود {gap}٪ بالاتر از بدون امکانات '
                f'({av.get("metric_label", "قیمت")}).'
            ),
        }

    pps = pa.get('price_per_sqm', {})
    if pps.get('median_fmt') and ctx.get('show_pps') and deal != 'rent':
        basis['facts'].append({
            'label': 'قیمت هر متر (میانه کل بازار)',
            'value': pps['median_fmt'],
            'icon': 'fa-coins',
        })

    if not basis['facts'] and not basis['segment_hint']:
        return {}
    return basis


def _build_l1_ready_numbers(
    report: Dict[str, Any],
    ctx: Dict[str, Any],
    stats: Dict[str, Any],
) -> List[Dict[str, str]]:
    """اعداد آماده بر اساس متراژ — فقط سناریوهای مشخص (نه تکرار میانه کل)."""
    scenarios = report.get('practical_scenarios') or []
    area_fmt = (stats.get('area') or {}).get('median_fmt', '')
    picked: List[Dict[str, str]] = []
    skip_titles = {'رهن کامل معادل بازار', 'عدد آماده برای مشتری'}

    for sc in scenarios:
        title = sc.get('title', '')
        if title in skip_titles:
            continue
        if any(k in title for k in ('متری', 'متر', 'معمولی')) or (area_fmt and area_fmt in title):
            picked.append({
                'title': title,
                'price': sc.get('price', ''),
                'hint': sc.get('hint', ''),
            })
        if len(picked) >= 3:
            break

    if not picked:
        for sc in scenarios:
            if sc.get('title') not in skip_titles:
                picked.append({
                    'title': sc.get('title', ''),
                    'price': sc.get('price', ''),
                    'hint': sc.get('hint', ''),
                })
            if len(picked) >= 2:
                break
    return picked


def filter_l2_actions(actions: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """اقدامات سطح ۲ — بدون تکرار اعداد سطح ۱."""
    out: List[Dict[str, str]] = []
    for act in actions or []:
        if act.get('title') in _L2_DUP_ACTION_TITLES:
            continue
        out.append(act)
        if len(out) >= 3:
            break
    return out


def _snapshot_signals(
    depth: Dict[str, Any],
    liq: Dict[str, Any],
    *,
    under_label: str,
) -> List[Dict[str, str]]:
    """شاخص‌های تکمیلی سطح ۱ — بدون تکرار ارزش بازار، وضعیت و اعتماد."""
    signals: List[Dict[str, str]] = []
    under = depth.get('under_market', 0)
    if under:
        signals.append({
            'label': under_label,
            'value': f'{under} فایل',
            'icon': 'fa-arrow-trend-down',
        })
    liq_stars = (liq.get('stars') or '').strip()
    liq_label = (liq.get('label') or '').replace('نقدشوندگی ', '').strip()
    liq_value = f'{liq_stars} {liq_label}'.strip()
    if liq_value:
        signals.append({
            'label': 'نقدشوندگی',
            'value': liq_value,
            'icon': 'fa-gauge-high',
        })
    return signals


def _build_quick_snapshot(
    report: Dict[str, Any],
    ctx: Dict[str, Any],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    """سطح ۱ — شش عدد برای نگاه اول مشاور."""
    pa = report.get('price_analysis', {})
    depth = report.get('market_depth', {})
    liq = report.get('liquidity', {})
    deal = ctx.get('deal')
    district = _district_label(report)

    snap: Dict[str, Any] = {'district': district, 'signals': [], 'market_value': {}}

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        rent = pa.get('rent', {})
        dep = pa.get('deposit', {})
        fd = pa.get('full_deposit', {})
        depth = report.get('market_depth', {})
        ratio_fmt = 'هر ۳۰ میلیون تومان رهن = ۱ میلیون اجاره ماهانه'

        full_dep = fd.get('median') or full_deposit_equiv(dep.get('median'), rent.get('median'))
        full_dep_fmt = fd.get('median_fmt') or (format_toman(full_dep) if full_dep else '—')

        snap['market_value'] = {
            'title': 'ارزش بازار امروز',
            'rows': [
                {'label': 'رهن معمول', 'value': dep.get('median_fmt', '—'), 'icon': 'fa-key'},
                {'label': 'اجاره معمول', 'value': rent.get('median_fmt', '—'), 'icon': 'fa-house'},
                {'label': 'رهن کامل معادل', 'value': full_dep_fmt, 'icon': 'fa-gem'},
                {'label': 'عرف تبدیل', 'value': ratio_fmt, 'icon': 'fa-right-left'},
            ],
        }
        snap['signals'] = _snapshot_signals(
            depth, liq, under_label='فایل‌های زیر عرف بازار',
        )
        sentiment = report.get('market_sentiment') or {}
        if sentiment.get('label'):
            snap['market_sentiment'] = sentiment
        snap['property_basis'] = _build_property_basis(report, ctx, stats)
        snap['ready_numbers'] = _build_l1_ready_numbers(report, ctx, stats)
        return snap

    profile = _seg(ctx)
    mvm = profile.get('market_value_mode', 'pps')
    pps = pa.get('price_per_sqm', {})
    price = pa.get('price', {})

    if mvm == 'total' and price.get('median_fmt'):
        rows = [
            {'label': 'قیمت کل معمول', 'value': price.get('median_fmt', '—'), 'icon': 'fa-sack-dollar'},
        ]
        if price.get('p25_fmt'):
            rows.append({'label': 'هدف خرید', 'value': f'زیر {price["p25_fmt"]}', 'icon': 'fa-bullseye'})
        if price.get('p75_fmt'):
            rows.append({'label': 'سقف منطقی', 'value': f'زیر {price["p75_fmt"]}', 'icon': 'fa-arrow-up'})
        if pps.get('median_fmt'):
            rows.append({
                'label': 'متری مرجع (مقایسه)',
                'value': pps['median_fmt'],
                'icon': 'fa-ruler-combined',
            })
        snap['market_value'] = {'title': 'ارزش بازار امروز', 'rows': rows}
        snap['signals'] = _snapshot_signals(
            depth, liq, under_label='فایل‌های زیر بازار',
        )
        sentiment = report.get('market_sentiment') or {}
        if sentiment.get('label'):
            snap['market_sentiment'] = sentiment
        snap['property_basis'] = _build_property_basis(report, ctx, stats)
        snap['ready_numbers'] = _build_l1_ready_numbers(report, ctx, stats)
        return snap

    pps = pa.get('price_per_sqm', {})
    buy_fmt = depth.get('p40_fmt', '')
    sell_fmt = depth.get('p60_fmt', '')
    golden_fmt = pps.get('median_fmt', '')
    buy_lo = strip_toman_suffix(buy_fmt) if buy_fmt else ''
    sell_hi = strip_toman_suffix(sell_fmt) if sell_fmt else ''
    if buy_fmt or sell_fmt or golden_fmt:
        snap['market_value'] = {
            'title': 'ارزش بازار امروز',
            'rows': [
                {'label': 'قیمت معمول هر متر', 'value': golden_fmt or '—', 'icon': 'fa-gem'},
                {
                    'label': 'قیمت هدف خرید',
                    'value': f'زیر {buy_lo} تومان' if buy_lo else '—',
                    'icon': 'fa-bullseye',
                },
                {
                    'label': 'قیمت هدف فروش',
                    'value': f'بالای {sell_hi} تومان' if sell_hi else '—',
                    'icon': 'fa-arrow-trend-up',
                },
            ],
        }
    snap['signals'] = _snapshot_signals(
        depth, liq, under_label='فایل‌های زیر قیمت بازار',
    )
    sentiment = report.get('market_sentiment') or {}
    if sentiment.get('label'):
        snap['market_sentiment'] = sentiment
    snap['property_basis'] = _build_property_basis(report, ctx, stats)
    snap['ready_numbers'] = _build_l1_ready_numbers(report, ctx, stats)
    return snap


def _build_price_bands(dist: Dict[str, Any], *, unit: str = ' تومان/متر') -> List[Dict[str, str]]:
    """بازه‌های قیمت به زبان ساده — بر اساس صدک‌های بازار."""
    if not dist.get('p10_fmt'):
        return []
    p10 = strip_toman_suffix(dist['p10_fmt'])
    p25 = strip_toman_suffix(dist.get('p25_fmt', ''))
    p75 = strip_toman_suffix(dist.get('p75_fmt', ''))
    p90 = strip_toman_suffix(dist.get('p90_fmt', ''))
    bands = [
        {'label': 'خیلی ارزان', 'range': f'زیر {p10}{unit}'},
        {'label': 'ارزان', 'range': f'{p10} تا {p25}{unit}'},
        {'label': 'محدوده معمول بازار', 'range': f'{p25} تا {p75}{unit}'},
        {'label': 'گران', 'range': f'{p75} تا {p90}{unit}'},
        {'label': 'خیلی گران', 'range': f'بیش از {p90}{unit}'},
    ]
    return [b for b in bands if b['range']]


def _build_expert_details(report: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """سطح ۳ — آمار تخصصی برای کاربر حرفه‌ای."""
    pa = report.get('price_analysis', {})
    deal = ctx.get('deal')
    conf = report.get('confidence', {})
    trends = report.get('price_trends') or {}

    bands_on = _seg(ctx).get('bands_on', 'pps')
    if bands_on in ('full_deposit', 'rent_equiv') or deal == 'rent':
        dist = pa.get('full_deposit', {}) or pa.get('rent', {})
        unit = ' تومان'
        bands_title = 'بازه رهن کامل معادل'
    elif bands_on == 'price' or ctx.get('prop') in ('land', 'project'):
        dist = pa.get('price', {})
        unit = ' تومان'
        bands_title = 'بازه قیمت کل'
    else:
        dist = pa.get('price_per_sqm', {})
        unit = ' تومان/متر'
        bands_title = 'بازه‌های قیمت هر متر'

    expert: Dict[str, Any] = {
        'price_bands': _build_price_bands(dist, unit=unit),
        'bands_note': '(بر اساس صدک‌های بازار)',
        'bands_title': bands_title,
    }
    if dist.get('cv') is not None:
        expert['cv_pct'] = dist['cv']
        expert['cv_label'] = f'ضریب پراکندگی: {dist["cv"]}٪'
    if conf.get('display_score') is not None or conf.get('score') is not None:
        score = conf.get('display_score', conf.get('score'))
        expert['confidence'] = {
            'score': score,
            'level': conf.get('level_plain') or conf.get('level', ''),
        }
    if trends.get('pps_monthly_fmt'):
        expert['trend_monthly'] = trends['pps_monthly_fmt']
    vd = report.get('market_depth', {})
    if vd.get('under_market') is not None:
        expert['value_distribution'] = {
            'under': vd.get('under_market', 0),
            'fair': vd.get('fair_market', 0),
            'over': vd.get('overpriced', 0),
        }
    return expert


def _pct_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or not b:
        return None
    pct = round((a - b) / b * 100, 1)
    if abs(pct) > 500:
        return None
    return pct


def _metric_sane_vs_market(value: Optional[float], market: Optional[float], *, low: float = 0.05, high: float = 10.0) -> bool:
    if value is None or market is None or not market:
        return True
    return market * low <= value <= market * high


def _compare_phrase(diff_pct: Optional[float], *, higher_word: str = 'گرون‌تر', lower_word: str = 'ارزون‌تر') -> str:
    if diff_pct is None:
        return ''
    if abs(diff_pct) < 3:
        return 'هم‌تراز با میانه کل بازار'
    if diff_pct > 0:
        return f'حدود {abs(diff_pct):g}٪ {higher_word} از میانه کل بازار'
    return f'حدود {abs(diff_pct):g}٪ {lower_word} از میانه کل بازار'


def _round_area(val: float) -> int:
    if val <= 0:
        return 100
    step = 5 if val < 120 else 10
    return int(round(val / step) * step)


def _seg(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx.get('segment_profile') or {}


def _profile_sample_areas(ctx: Dict[str, Any], stats: Dict[str, Any]) -> List[int]:
    """متراژهای نمونه بر اساس زیردسته."""
    preset = _seg(ctx).get('sample_areas') or []
    if preset:
        lo = int((stats.get('area') or {}).get('min') or 30)
        hi = int((stats.get('area') or {}).get('max') or 2000)
        filtered = [a for a in preset if lo <= a <= hi]
        if filtered:
            return filtered
    return _pick_primary_areas(stats)


def _pick_primary_areas(stats: Dict[str, Any]) -> List[int]:
    """سه متراژ استاندارد برای سناریوی سطح ۱."""
    lo = int((stats.get('area') or {}).get('min') or 45)
    hi = int((stats.get('area') or {}).get('max') or 200)
    return [a for a in (80, 100, 120) if lo <= a <= hi]


def _split_scenario_cards(cards: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """جداسازی سه سناریوی اصلی از بقیه."""
    primary: List[Dict[str, str]] = []
    extra: List[Dict[str, str]] = []
    for card in cards:
        title = card.get('title', '')
        is_basic = 'معمولی' in title and any(f'{a} متری' in title for a in (80, 100, 120))
        if is_basic and len(primary) < 3:
            primary.append(card)
        else:
            extra.append(card)
    if len(primary) < 3:
        for card in cards:
            if card in primary or card in extra:
                continue
            if 'معمولی' in card.get('title', '') and len(primary) < 3:
                primary.append(card)
                if card in extra:
                    extra.remove(card)
    if not primary:
        primary = cards[:3]
        extra = cards[3:]
    return primary, extra


def _pick_sample_areas(
    stats: Dict[str, Any],
    segs: List[Dict[str, Any]],
    ctx: Optional[Dict[str, Any]] = None,
) -> List[int]:
    """متراژهای رُند برای سناریو — نزدیک متراژ رایج بازار."""
    if ctx:
        preset = _profile_sample_areas(ctx, stats)
        if preset:
            return preset[:4]
    primary = _pick_primary_areas(stats)
    if primary:
        return primary
    areas: List[int] = []
    med = (stats.get('area') or {}).get('median')
    if med:
        areas.append(_round_area(float(med)))
    for seg in segs:
        ma = seg.get('median_area')
        if ma:
            areas.append(_round_area(float(ma)))
    for fallback in (80, 90, 100, 110, 120, 130):
        areas.append(fallback)
    lo = int((stats.get('area') or {}).get('min') or 45)
    hi = int((stats.get('area') or {}).get('max') or 200)
    unique = sorted({a for a in areas if lo <= a <= hi})
    if not unique:
        unique = [100]
    if len(unique) > 4:
        mid = unique[len(unique) // 2]
        idx = unique.index(mid) if mid in unique else len(unique) // 2
        start = max(0, idx - 1)
        unique = unique[start:start + 4]
    return unique[:4]


def _subset_count(df: pd.DataFrame, mask: pd.Series, metric: str) -> int:
    if df is None or df.empty or metric not in df.columns:
        return 0
    return int((mask.fillna(False) & df[metric].notna()).sum())


def _subset_confidence(count: int) -> str:
    if count < MIN_SUBSET_SHOW:
        return 'hidden'
    if count < MIN_SUBSET_WARN:
        return 'low'
    return 'ok'


def _subset_metric(
    df: pd.DataFrame,
    mask: pd.Series,
    metric: str,
    *,
    per_sqm: bool = False,
    min_count: int = MIN_SUBSET_SHOW,
) -> Optional[float]:
    if df is None or df.empty or metric not in df.columns:
        return None
    sub = df[mask.fillna(False) & df[metric].notna()]
    if len(sub) < min_count:
        return None
    return float(sub[metric].median())


def _full_amenity_mask(df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for field in FULL_AMENITY_FIELDS:
        if field in df.columns:
            mask &= df[field] == True
        else:
            return pd.Series(False, index=df.index)
    return mask


def _new_build_mask(df: pd.DataFrame, years_new: int = 5) -> pd.Series:
    if 'build_year' not in df.columns:
        return pd.Series(False, index=df.index)
    cutoff = CURRENT_JALALI_YEAR - years_new
    return df['build_year'].notna() & (df['build_year'] >= cutoff)


def _scenario(
    title: str,
    price_fmt: str,
    body: str,
    *,
    hint: str = '',
    icon: str = 'home',
) -> Dict[str, str]:
    return {'title': title, 'price': price_fmt, 'body': body, 'hint': hint, 'icon': icon}


def _build_practical_scenarios(
    report: Dict[str, Any],
    ctx: Dict[str, Any],
    stats: Dict[str, Any],
    df: Optional[pd.DataFrame],
) -> List[Dict[str, str]]:
    """سناریوهای ساده — عدد آماده برای گفتن به مشتری."""
    pa = report.get('price_analysis', {})
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    segs = report.get('area_segments', [])
    build = report.get('build_year', {})
    cards: List[Dict[str, str]] = []

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        rent = pa.get('rent', {})
        dep = pa.get('deposit', {})
        fd = pa.get('full_deposit', {})
        region = _district_label(report)
        area_fmt = (stats.get('area') or {}).get('median_fmt', '')

        full_dep = fd.get('median') or full_deposit_equiv(dep.get('median'), rent.get('median'))
        full_fmt = fd.get('median_fmt') or (format_toman(full_dep) if full_dep else '')
        fd_stub = {'median_fmt': full_fmt} if full_fmt else {}

        if full_dep:
            cards.append(_scenario(
                'رهن کامل معادل بازار',
                format_toman(full_dep),
                phrase_full_deposit_equiv_market(dep, rent, region=region) or (
                    f'محاسبه: {dep.get("median_fmt", "—")} + '
                    f'({rent.get("median_fmt", "—")} × ۳۰).'
                ),
                hint='عدد اصلی مذاکره در بازار اجاره ایران',
                icon='key',
            ))

        if dep.get('median_fmt') and rent.get('median_fmt'):
            cards.append(_scenario(
                'عدد آماده برای مشتری',
                f'{dep["median_fmt"]} رهن + {rent["median_fmt"]} اجاره',
                (
                    f'واحد معمولی در {region} معمولاً با این بسته فایل می‌شود'
                    + (f' (رهن کامل معادل حدود {full_fmt}).' if full_fmt else '.')
                ),
                hint='همین را به مشتری بگو',
                icon='key',
            ))
        if area_fmt and dep.get('median_fmt') and rent.get('median_fmt'):
            cards.append(_scenario(
                f'واحد {area_fmt} معمولی',
                f'{dep["median_fmt"]} رهن + {rent["median_fmt"]} اجاره',
                phrase_typical_unit_rent(area_fmt, dep, rent, fd_stub, region=region) or '',
                hint='برای مشتری با متراژ رایج بازار',
                icon='home',
            ))
        return cards[:3]

    if prop in ('land', 'project') or _seg(ctx).get('metric_mode') == 'total_price':
        price = pa.get('price', {})
        med_price = price.get('median')
        pps = pa.get('price_per_sqm', {})
        unit = _seg(ctx).get('unit_word', 'ملک')
        for seg in segs[:3]:
            if seg.get('median_price_fmt'):
                cards.append(_scenario(
                    f'{unit} {seg.get("bucket_plain", "")}',
                    seg['median_price_fmt'],
                    f'{seg["count"]} فایل در این بازه — قیمت کل مهم‌تر از متری.',
                    icon='map',
                ))
        if med_price:
            cards.append(_scenario(
                f'قیمت کل معمول {unit}',
                price.get('median_fmt', '—'),
                f'بازه رایج: {price.get("range_50_fmt", "—")} — همین عدد را به مشتری بگو.',
                hint='عدد اصلی مذاکره',
                icon='key',
            ))
        if med_price and pps.get('median'):
            for area in _pick_sample_areas(stats, segs, ctx)[:2]:
                est = int(pps['median'] * area)
                cards.append(_scenario(
                    f'برآورد {area} متری',
                    format_toman(est),
                    f'متری {pps["median_fmt"]} × {area} متر (فقط برای مقایسه).',
                    icon='ruler',
                ))
        return cards[:5]

    pps = pa.get('price_per_sqm', {})
    price = pa.get('price', {})
    med_pps = pps.get('median')
    if not med_pps:
        return cards

    pps_fmt = pps['median_fmt']
    med_year = build.get('median_year')
    sample_areas = _pick_sample_areas(stats, segs, ctx)
    pps_plain = strip_toman_suffix(pps_fmt)
    unit_label = _seg(ctx).get('scenario_unit_word') or _seg(ctx).get('unit_word', 'واحد')
    region = _district_label(report)
    is_commercial = prop == 'commercial' or ctx.get('subcategory_key') in ('shop', 'office', 'industrial')
    show_amenities = ctx.get('show_residential_amenities', prop == 'residential')
    range_first = ctx.get('scenario_range_first', is_commercial)

    if range_first and pps.get('p25') and pps.get('p75'):
        area = sample_areas[0] if sample_areas else 100
        cheap = int(pps['p25'] * area)
        fair_hi = int(pps['p75'] * area)
        ref = int(med_pps * area)
        cards.append(_scenario(
            'عدد آماده برای مشتری',
            f'{format_toman(cheap)} تا {format_toman(fair_hi)}',
            phrase_customer_ready_sale_range(unit_label, area, pps, price, region=region),
            hint='مشتری بازه می‌خواهد — عدد مرجع را هم بگو',
            icon='key',
        ))
        cards.append(_scenario(
            f'عدد مرجع — {unit_label} {area} متری',
            format_toman(ref),
            f'متری مرجع بازار {pps_fmt} — برای مقایسه سریع آگهی‌ها.',
            hint='معیار اولیه، نه تنها معیار مغازه/اداری',
            icon='star',
        ))
    else:
        for area in sample_areas:
            total = int(med_pps * area)
            total_fmt = format_toman(total)
            cards.append(_scenario(
                f'{unit_label} {area} متری معمولی',
                total_fmt,
                f'با متری {pps_plain} تومان، {unit_label} {area} متری در این منطقه حدود {total_fmt} می‌شود.',
                hint='واحد معمول بدون امتیاز خاص — فقط بر اساس قیمت هر متر بازار',
                icon='building',
            ))

    if med_year and ctx.get('show_build_year'):
        for area in sample_areas[:2]:
            total = int(med_pps * area)
            cards.append(_scenario(
                f'{area} متری — سال ساخت حدود {med_year}',
                format_toman(total),
                f'واحد معمول این فایل با سن بنا میانه بازار (حدود {build.get("median_age", "—")} سال).',
                hint='برای مشتری: «واحد هم‌اندازه و هم‌سن»',
                icon='calendar',
            ))

    if show_amenities and df is not None and not df.empty and 'price_per_sqm' in df.columns:
        area_med = _round_area(float((stats.get('area') or {}).get('median') or 100))
        full = _full_amenity_mask(df)
        new = _new_build_mask(df)
        combo = full & new
        basic = pd.Series(True, index=df.index)
        if 'parking' in df.columns:
            basic &= ~df['parking'].fillna(False).astype(bool)

        profiles = [
            ('فول امکانات (آسانسور + پارکینگ + انباری)', full, 'star', area_med),
            ('نوساز (زیر ۵ سال)', new, 'sparkles', area_med),
            ('فول امکانات + نوساز', combo, 'gem', area_med),
            ('بدون پارکینگ', basic, 'car', area_med),
        ]
        if is_commercial:
            profiles = [
                ('با پارکینگ اختصاصی', df['parking'].fillna(False).astype(bool) if 'parking' in df.columns else pd.Series(False, index=df.index), 'car', area_med),
            ]
        for label, mask, icon, area in profiles:
            count = _subset_count(df, mask, 'price_per_sqm')
            if count < MIN_SUBSET_SHOW:
                continue
            pps_val = _subset_metric(df, mask, 'price_per_sqm', per_sqm=True)
            if pps_val is None:
                continue
            total = int(pps_val * area)
            total_fmt = format_toman(total)
            pps_plain = strip_toman_suffix(format_toman(pps_val, per_sqm=True))
            extra = ''
            if 'نوساز' in label:
                extra = f' — ساخت از سال {CURRENT_JALALI_YEAR - 5} به بعد'
            conf = _subset_confidence(count)
            hint = 'همین عدد رو برای مقایسه آگهی مشابه به مشتری بگو'
            if conf == 'low':
                hint = f'فقط {count} نمونه — با احتیاط استفاده کن'
            cards.append(_scenario(
                f'{area} متری {label}',
                total_fmt,
                f'در {count} فایل مشابه، هر متر حدود {pps_plain} تومان است{extra}؛ '
                f'واحد {area} متری حدود {total_fmt} می‌شود.'
                + (' (اعتماد کم)' if conf == 'low' else ''),
                hint=hint,
                icon=icon,
            ))

    if pps.get('p25') and pps.get('p75'):
        area = sample_areas[0] if sample_areas else 100
        cheap = int(pps['p25'] * area)
        fair_hi = int(pps['p75'] * area)
        lo_p = strip_toman_suffix(format_toman(pps['p25'], per_sqm=True))
        hi_p = strip_toman_suffix(format_toman(pps['p75'], per_sqm=True))
        cards.append(_scenario(
            f'بازه قیمت واحد {area} متری',
            f'{format_toman(cheap)} تا {format_toman(fair_hi)}',
            f'بیشتر واحدهای {area} متری بین {lo_p} تا {hi_p} تومان برای هر متر قیمت دارند.',
            hint=f'زیر {format_toman(cheap)} عالی، بالای {format_toman(fair_hi)} مذاکره کن',
            icon='scale-balanced',
        ))

    return cards[:8]


def _build_rent_professional_summary(
    report: Dict[str, Any],
    ctx: Dict[str, Any],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    """سطح ۲ — تحلیل حرفه‌ای اجاره: فقط رهن، اجاره، رهن کامل (یک عدد)."""
    pa = report.get('price_analysis', {})
    rent = pa.get('rent', {})
    dep = pa.get('deposit', {})
    fd = pa.get('full_deposit', {})
    depth = report.get('market_depth', {})
    dq = report.get('data_quality', {})
    liq = report.get('liquidity', {})
    scope = report.get('publication_scope') or {}
    region = _district_label(report)
    ratio_fmt = 'هر ۳۰ میلیون تومان رهن ≈ ۱ میلیون اجاره ماهانه'

    valid_n = dq.get('valid_count') or scope.get('analyzed_count') or depth.get('total') or 0
    if scope.get('date_from_fmt') and scope.get('date_to_fmt'):
        intro = (
            f'بر اساس داده‌های موجود از تاریخ {scope["date_from_fmt"]} تا {scope["date_to_fmt"]} '
            f'و تحلیل {valid_n:,} فایل معتبر، این جمع‌بندی ارائه می‌شود.'
        ).replace(',', '،')
    else:
        intro = f'بر اساس تحلیل {valid_n:,} فایل معتبر، این جمع‌بندی ارائه می‌شود.'.replace(',', '،')

    quality_note = f'{dq["removed_count"]} آگهی غیرعادی از محاسبه حذف شد.' if dq.get('removed_count') else ''

    dep_fmt = dep.get('median_fmt', '—')
    if dep_fmt != '—' and not str(dep_fmt).startswith('حدود'):
        dep_fmt = f'حدود {dep_fmt}'

    rent_fmt = rent.get('median_fmt', '—')
    if rent_fmt != '—' and not str(rent_fmt).startswith('حدود'):
        rent_fmt = f'حدود {rent_fmt}'

    full_val = fd.get('median') or full_deposit_equiv(dep.get('median'), rent.get('median'))
    full_fmt = fd.get('median_fmt') or (format_toman(full_val) if full_val else '—')
    if full_fmt != '—' and not str(full_fmt).startswith('حدود'):
        full_fmt = f'حدود {full_fmt}'

    dep_med = dep.get('median_fmt') or format_toman(dep.get('median', 0))
    rent_med = rent.get('median_fmt') or format_toman(rent.get('median', 0))
    combo_line = f'{dep_med} رهن + {rent_med} اجاره' if dep_med and rent_med else ''
    full_line = f'➡️ معادل {full_fmt} رهن کامل' if full_fmt != '—' else ''

    area_fmt = (stats.get('area') or {}).get('median_fmt', '')
    unit_word = _seg(ctx).get('unit_word', 'واحد')

    negotiate_fmt = fd.get('p75_fmt') or (
        format_toman(int(fd['p75'])) if fd.get('p75') else ''
    )

    under_pct = depth.get('under_pct', 0)
    liq_label = (liq.get('label') or '').replace('نقدشوندگی ', '').strip() or 'متوسط'
    if (liq.get('score') or 0) >= 55 and 'بالا' not in liq_label:
        liq_label = f'{liq_label} رو به بالا'

    sections: List[Dict[str, Any]] = [
        {
            'title': f'عرف بازار اجاره ({region})',
            'lead': 'در این منطقه عرف بازار به این صورت است:',
            'rows': [
                {'label': 'رهن معمول', 'value': dep_fmt},
                {'label': 'اجاره معمول', 'value': rent_fmt},
            ],
            'highlight': {
                'icon': '📌',
                'label': 'نسبت تبدیل رایج بازار',
                'value': ratio_fmt,
            },
        },
        {
            'title': 'جمع‌بندی واقعی بازار (برای تصمیم‌گیری)',
            'lead': 'مبنای اصلی تحلیل — رهن کامل معادل (رهن + اجاره × ۳۰):',
            'lines': [ln for ln in (combo_line, full_line) if ln],
        },
    ]

    if area_fmt:
        sections.append({
            'title': f'جمع‌بندی برای {unit_word} {area_fmt} معمولی',
            'lead': f'برای یک {unit_word} {area_fmt} معمولی در {region}:',
            'lines': [
                f'سناریوی رایج بازار:\n{combo_line}' if combo_line else '',
                f'رهن کامل معادل:\n{full_fmt}',
            ],
        })

    market_lines = []
    if under_pct:
        market_lines.append(f'حدود {under_pct:g}٪ فایل‌ها زیر عرف بازار هستند')
    if depth.get('under_market'):
        market_lines.append('این فایل‌ها اولویت معرفی به مشتری دارند')
    if negotiate_fmt:
        market_lines.append(f'فایل‌های بالاتر از {negotiate_fmt} رهن کامل نیاز به مذاکره دارند')
    if market_lines:
        sections.append({'title': 'وضعیت فایل‌های بازار', 'lines': market_lines})

    sections.append({
        'title': 'سرعت بازار',
        'lines': [
            f'سرعت معامله در این بازار {liq_label} است',
            '(فایل‌های قیمت‌مناسب سریع‌تر جابه‌جا می‌شوند)',
        ],
    })

    return {'intro': intro, 'quality_note': quality_note, 'sections': sections}


def _build_summary_lines(report: Dict[str, Any], ctx: Dict[str, Any], stats: Dict[str, Any]) -> List[str]:
    """خلاصه بازار — هر نکته یک خط جدا."""
    dq = report.get('data_quality', {})
    pa = report.get('price_analysis', {})
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    depth = report.get('market_depth', {})
    lines: List[str] = []

    scope = report.get('publication_scope') or {}
    if scope.get('line'):
        lines.append(scope['line'])

    if dq.get('valid_count'):
        removed = dq.get('removed_count', 0)
        if scope.get('line'):
            if removed:
                lines.append(f'{removed} آگهی غیرعادی از محاسبه حذف شد')
        elif removed:
            lines.append(f'{dq["valid_count"]} فایل معتبر بررسی شد')
            lines.append(f'{removed} آگهی غیرعادی از محاسبه حذف شد')
        else:
            lines.append(f'{dq["valid_count"]} فایل بررسی شد')

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        rent = pa.get('rent', {})
        dep = pa.get('deposit', {})
        fd = pa.get('full_deposit', {})
        region = _district_label(report)
        fm = report.get('full_mortgage') or {}
        sent = report.get('market_sentiment', {})

        quick = _build_rent_quick_summary(pa, depth, fm, sent)
        if quick:
            lines.append(quick)

        area_fmt = (stats.get('area') or {}).get('median_fmt', '')
        full_fmt = fd.get('median_fmt') or ''
        fd_stub = {'median_fmt': full_fmt} if full_fmt else {}
        unit_line = phrase_typical_unit_rent(area_fmt, dep, rent, fd_stub, region=region)
        if unit_line:
            lines.append(unit_line)
    elif prop == 'land':
        price = pa.get('price', {})
        line = phrase_total_price_median(price)
        if line:
            lines.append(line)
        line = phrase_total_price_range(price)
        if line:
            lines.append(line)
        pps = pa.get('price_per_sqm', {})
        if pps.get('median_fmt'):
            amt = strip_toman_suffix(pps['median_fmt'])
            lines.append(f'قیمت هر متر (فقط برای مقایسه): حدود {amt} تومان')
    else:
        price = pa.get('price', {})
        line = phrase_total_price_median(price)
        if line:
            lines.append(line)
        area = stats.get('area') or {}
        line = phrase_typical_area(area)
        if line:
            lines.append(line)

    if depth.get('total') and not (deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv'):
        lines.append(
            f'{depth.get("under_pct", 0)}٪ فایل‌ها ارزان‌تر از بازار، '
            f'{depth.get("fair_pct", 0)}٪ سر به سر، '
            f'و {depth.get("over_pct", 0)}٪ گران‌تر از بازار هستند'
        )

    build = report.get('build_year', {})
    if ctx.get('show_build_year') and build.get('median_year'):
        lines.append(f'سال ساخت میانه: {build["median_year"]}')

    liq = report.get('liquidity', {})
    if liq.get('label'):
        label = liq['label'].replace('نقدشوندگی ', '')
        lines.append(f'سرعت معامله در این بازار {label} است')

    return lines


def _build_summary(report: Dict[str, Any], ctx: Dict[str, Any], stats: Dict[str, Any]) -> str:
    return '\n'.join(_build_summary_lines(report, ctx, stats))


def _build_segment_notes(report: Dict[str, Any], ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """تحلیل اختصاصی هر بازه متراژ — برای مشاور."""
    segs = report.get('area_segments', [])
    if not segs:
        return []

    pa = report.get('price_analysis', {})
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    client = ctx.get('client_word', 'مشتری')
    notes: List[Dict[str, Any]] = []

    market_pps = (pa.get('price_per_sqm') or {}).get('median')
    market_price = (pa.get('price') or {}).get('median')
    market_rent = (pa.get('rent') or {}).get('median')
    market_dep = (pa.get('deposit') or {}).get('median')
    top_count = max(s['count'] for s in segs)

    for seg in segs:
        bucket = seg.get('bucket_plain') or seg.get('bucket', '')
        lines: List[str] = []
        share = seg.get('share_pct', 0)
        count = seg['count']

        supply = f'{count} فایل ({share}٪ از کل فایل)'
        if count == top_count:
            supply += ' — بیشترین عرضه در این بازه'
        lines.append(supply)

        if seg.get('median_area_fmt'):
            lines.append(f'متراژ معمول این بازه: {seg["median_area_fmt"]}')

        if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
            if seg.get('median_rent_fmt'):
                rent_line = f'اجاره معمول: {seg["median_rent_fmt"]}'
                lines.append(rent_line)
            if seg.get('median_deposit_fmt'):
                lines.append(f'رهن معمول: {seg["median_deposit_fmt"]}')
            if seg.get('median_full_deposit_fmt'):
                lines.append(f'رهن کامل معمول: {seg["median_full_deposit_fmt"]}')
        elif prop == 'land':
            if seg.get('median_price_fmt'):
                diff = _pct_diff(
                    (seg.get('price_dist') or {}).get('median'),
                    market_price,
                )
                line = f'قیمت کل معمول: {seg["median_price_fmt"]}'
                cmp = _compare_phrase(diff)
                if cmp:
                    line += f' — {cmp}'
                lines.append(line)
        else:
            pps_dist = seg.get('pps_dist') or {}
            seg_med = pps_dist.get('median')
            if seg_med and market_pps and not _metric_sane_vs_market(seg_med, market_pps):
                lines.append(
                    'داده این بازه ناسازگار با میانه کل بازار است — '
                    'قبل از استفاده، قیمت فایل‌ها را دستی بررسی کن.'
                )
            elif pps_dist.get('median_fmt'):
                diff = _pct_diff(seg_med, market_pps)
                line = f'متری معمول: {pps_dist["median_fmt"]}'
                cmp = _compare_phrase(diff)
                if cmp:
                    line += f' ({cmp})'
                if pps_dist.get('range_50_fmt'):
                    line += f' · بازه رایج: {pps_dist["range_50_fmt"]}'
                lines.append(line)

            if seg.get('median_price_fmt') and ctx.get('show_total_price'):
                diff = _pct_diff(
                    (seg.get('price_dist') or {}).get('median'),
                    market_price,
                )
                line = f'قیمت کل معمول: {seg["median_price_fmt"]}'
                cmp = _compare_phrase(diff, higher_word='بالاتر', lower_word='پایین‌تر')
                if cmp:
                    line += f' ({cmp})'
                lines.append(line)

        if seg.get('median_build_year') and ctx.get('show_build_year'):
            lines.append(f'سال ساخت میانه: {seg["median_build_year"]}')

        # توصیه عملی
        if deal == 'rent' and seg.get('median_rent_fmt'):
            lines.append(f'برای {client} با متراژ {bucket}، از همین بازه اجاره شروع کن.')
        elif prop != 'land' and seg.get('median_pps_fmt') or (seg.get('pps_dist') or {}).get('median_fmt'):
            med = pps_dist.get('median') if (pps_dist := seg.get('pps_dist') or {}) else None
            if med and market_pps:
                if med < market_pps * 0.92:
                    lines.append(f'این بازه برای {client} فرصت خوبه — متری زیر میانه کل بازار.')
                elif med > market_pps * 1.08:
                    lines.append('قیمت این بازه بالاتر از میانه — قبل از بازدید مذاکره رو در نظر بگیر.')
                else:
                    lines.append(f'قیمت این بازه نزدیک میانه بازار — مبنای مذاکره {client}.')
        elif prop == 'land' and seg.get('median_price_fmt'):
            lines.append(f'برای {client} با {bucket}، قیمت کل مهم‌تر از متریه.')

        notes.append({
            'bucket': bucket,
            'count': count,
            'share_pct': share,
            'lines': lines,
        })

    return notes


def _build_factor_insights(factors: List[Dict[str, Any]], ctx: Dict[str, Any]) -> List[str]:
    tips: List[str] = []
    for f in factors:
        plain = f.get('plain') or f.get('insight')
        if plain:
            tips.append(plain)
            premium = f.get('premium_pct')
            label = f.get('label', '')
            if premium is not None and abs(premium) >= 5 and label != 'سال ساخت':
                if premium > 0:
                    client = ctx.get('client_word', 'مشتری')
                    tips.append(
                        f'واحد بدون {label} معمولاً ارزون‌تره — اگر {client} '
                        f'بودجه محدود داره، گزینه بدون {label} رو هم نشون بده.'
                    )
                elif premium < -5:
                    tips.append(
                        f'در این فایل {label} اثر قیمتی معکوس داره — احتمالاً متراژ یا محله فرق می‌کنه.'
                    )
            elif premium is not None and abs(premium) >= 5 and label == 'سال ساخت':
                if not ctx.get('show_build_year', True):
                    continue
                if premium > 0:
                    tips.append('نوسازترها گرون‌ترن — برای مشتری حساس به بودجه، واحد قدیمی‌تر با مذاکره بررسی کن.')
                else:
                    tips.append('واحدهای قدیمی‌تر ارزون‌ترن — اگر نوساز می‌خواد، بودجه رو بالاتر ببر.')
    return tips


def _build_rent_quick_summary(
    pa: Dict[str, Any],
    depth: Dict[str, Any],
    fm: Dict[str, Any],
    sent: Dict[str, Any],
) -> str:
    """جمع‌بندی فشرده اجاره — هر نکته فقط یک‌بار."""
    rent = pa.get('rent', {})
    dep = pa.get('deposit', {})
    fd = pa.get('full_deposit', {})
    bits: List[str] = []
    dep_fmt = dep.get('median_fmt')
    rent_fmt = rent.get('median_fmt')
    equiv = full_deposit_equiv(dep.get('median'), rent.get('median'))
    equiv_fmt = format_toman(equiv) if equiv else ''

    if fd.get('median_fmt'):
        bits.append(f'رهن کامل معمول: {fd["median_fmt"]}')
    if dep_fmt and rent_fmt:
        if equiv_fmt:
            bits.append(
                f'بسته غالب: {dep_fmt} رهن + {rent_fmt} اجاره '
                f'(معادل {equiv_fmt} با ضریب ۳۰)'
            )
        else:
            bits.append(f'بسته غالب: {dep_fmt} رهن + {rent_fmt} اجاره')
    fm_count = int(fm.get('count') or 0)
    fm_dep = fm.get('median_deposit_fmt')
    if fm_count and fm_dep:
        if fm_count == 1:
            bits.append(f'۱ فایل رهن خالص: {fm_dep}')
        else:
            bits.append(f'{fm_count} فایل رهن خالص · میانه {fm_dep}')
    under = int(depth.get('under_market') or 0)
    if under:
        bits.append(f'{under} فایل زیر عرف رهن کامل')
    if sent.get('label'):
        bits.append(f'وضعیت: {sent["label"]}')
    if not bits:
        return ''
    return 'جمع‌بندی سریع: ' + ' · '.join(bits) + '.'


def _build_insight_sections(
    report: Dict[str, Any],
    ctx: Dict[str, Any],
    factors: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """بخش‌های تحلیل — هر دسته و زیردسته."""
    sections: List[Dict[str, Any]] = []
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    client = ctx.get('client_word', 'مشتری')
    pa = report.get('price_analysis', {})
    depth = report.get('market_depth', {})
    segs = report.get('area_segments', [])
    build = report.get('build_year', {})
    nb_list = report.get('neighborhoods', [])
    amen = report.get('amenities_coverage', [])
    liq = report.get('liquidity', {})
    conf = report.get('confidence', {})
    dq = report.get('data_quality', {})
    trends = report.get('price_trends')
    opps = report.get('opportunities', [])

    # ─── ۱. تحلیل کلی قیمت ───
    overview: List[str] = []
    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        fm = report.get('full_mortgage') or {}
        sent = report.get('market_sentiment', {})
        quick = _build_rent_quick_summary(pa, depth, fm, sent)
        if quick:
            overview.append(quick)
        elif report.get('full_mortgage_count'):
            overview.append(
                f'{report["full_mortgage_count"]} فایل رهن کامل — '
                f'ارزش واقعی را با رهن + (اجاره × ۳۰) محاسبه کن.'
            )
    elif prop == 'land':
        price = pa.get('price', {})
        if price.get('median_fmt'):
            overview.append(
                f'قیمت کل میانه {price["median_fmt"]} — در کلنگی/زمین روی قیمت کل تمرکز کن.'
            )
        if price.get('range_50_fmt'):
            overview.append(f'۵۰٪ فایل‌ها بین {price["range_50_fmt"]} قیمت‌گذاری شدن.')
        pps = pa.get('price_per_sqm', {})
        if pps.get('median_fmt'):
            overview.append(f'متری مرجع {pps["median_fmt"]} — فقط برای مقایسه نسبی.')
    else:
        pps = pa.get('price_per_sqm', {})
        price = pa.get('price', {})
        if pps.get('median_fmt'):
            overview.append(
                f'متری مرجع بازار: {pps["median_fmt"]} — '
                f'بازه رایج {pps.get("range_50_fmt", "—")}.'
            )
        if pps.get('range_80_fmt'):
            overview.append(f'۸۰٪ فایل‌ها بین {pps["range_80_fmt"]} قیمت دارند.')
        spread = pps.get('spread_50_pct')
        if spread is not None:
            if spread > 25:
                overview.append(
                    f'اختلاف قیمت بین فایل‌ها زیاد است — '
                    f'حتماً قبل از بازدید قیمت هر متر را با بازار چک کن.'
                )
            elif spread < 15:
                overview.append('بازار نسبتاً یکدست است — قیمت‌ها قابل پیش‌بینی‌ترند.')
        line = phrase_total_price_median(price)
        if line:
            area = stats.get('area') or {}
            if area.get('median_fmt'):
                overview.append(line.replace('است', f'است (برای واحد حدود {area["median_fmt"]})'))
            else:
                overview.append(line + '.')

    if depth.get('total'):
        if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
            overview.append(
                f'از {depth["total"]} فایل: {depth["under_market"]} رهن کامل پایین‌تر، '
                f'{depth["fair_market"]} سر به سر، {depth["overpriced"]} بالاتر از عرف.'
            )
            if depth.get('overpriced', 0) > 0:
                overview.append(
                    f'{depth["overpriced"]} فایل با رهن کامل بالاتر — '
                    f'فرصت مذاکره یا رد قبل از بازدید.'
                )
        else:
            overview.append(
                f'از {depth["total"]} فایل: {depth["under_market"]} زیر بازار، '
                f'{depth["fair_market"]} سر به سر، {depth["overpriced"]} بالای بازار.'
            )
            if depth.get('under_market', 0) > 0:
                overview.append(
                    f'{depth["under_market"]} فایل زیر قیمت بازار — '
                    f'اولویت اول برای پیشنهاد به {client}.'
                )
            if depth.get('overpriced', 0) > 0:
                overview.append(
                    f'{depth["overpriced"]} فایل بالای بازار — '
                    f'فرصت مذاکره یا رد فایل قبل از بازدید.'
                )

    if overview:
        title = _seg(ctx).get('overview_title') or 'تحلیل کلی بازار'
        if not _seg(ctx).get('overview_title'):
            if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
                title = 'تحلیل کلی اجاره و رهن'
            elif prop == 'commercial':
                title = 'تحلیل کلی قیمت اداری/تجاری'
            elif prop == 'land':
                title = 'تحلیل کلی قیمت زمین/کلنگی'
            elif prop == 'project':
                title = 'تحلیل کلی پروژه'
        sections.append({'title': title, 'items': overview})

    # ─── ۲. تحلیل متراژ ───
    area_items: List[str] = []
    if segs:
        total = sum(s['count'] for s in segs)
        sorted_segs = sorted(segs, key=lambda s: s['count'], reverse=True)
        top = sorted_segs[0]
        area_items.append(
            f'بیشترین عرضه: {top.get("bucket_plain", top["bucket"])} '
            f'({top["count"]} فایل، {top.get("share_pct", 0)}٪).'
        )
        if len(sorted_segs) >= 2:
            second = sorted_segs[1]
            area_items.append(
                f'دومین بازه پرتقاضا: {second.get("bucket_plain", second["bucket"])} '
                f'({second["count"]} فایل).'
            )
        area_items.append('جزئیات هر بازه در جدول متراژ و آکاردئون زیر آن.')
        thin = [s for s in segs if s['count'] < max(3, total * 0.05)]
        if thin:
            labels = '، '.join(s.get('bucket_plain', s['bucket']) for s in thin[:3])
            area_items.append(
                f'عرضه کم در {labels} — داده محدود؛ با احتیاط قیمت بده.'
            )

    area_med = stats.get('area') or {}
    if area_med.get('median_fmt'):
        area_items.insert(0, f'متراژ میانه کل فایل: {area_med["median_fmt"]}.')
        if area_med.get('min') is not None and area_med.get('max') is not None:
            area_items.append(
                f'متراژ از {int(area_med["min"])} تا {int(area_med["max"])} متر دیده شده.'
            )

    if area_items:
        sections.append({
            'title': f'تحلیل {ctx.get("area_word", "متراژ")}',
            'items': area_items,
        })

    # ─── ۳. امکانات و وضعیت بنا ───
    quality_items: List[str] = []
    section_title = ctx.get('amenities_section_title', 'امکانات و وضعیت بنا')
    commercial_tips = ctx.get('commercial_focus_tips') or _seg(ctx).get('commercial_focus_tips') or []

    if prop == 'commercial' and commercial_tips:
        quality_items.extend(commercial_tips)

    if ctx.get('show_amenities') and amen:
        amen_rows = amen
        if ctx.get('subcategory_key') == 'shop':
            amen_rows = []
        elif not ctx.get('show_residential_amenities', True):
            amen_rows = [a for a in amen if a.get('label') in ('پارکینگ',)]
        high = [a for a in amen_rows if (a.get('coverage_pct') or 0) >= 70]
        low = [a for a in amen_rows if (a.get('coverage_pct') or 0) < 30]
        for a in sorted(amen_rows, key=lambda x: x.get('coverage_pct', 0), reverse=True):
            quality_items.append(
                f'{a["label"]}: {a["coverage_pct"]}٪ فایل‌ها دارن '
                f'({a["count"]} مورد).'
            )
        if high:
            labels = '، '.join(a['label'] for a in high)
            quality_items.append(f'{labels} تقریباً استاندارد بازار — نبودنشون باید در مذاکره لحاظ بشه.')
        if low:
            labels = '، '.join(a['label'] for a in low)
            quality_items.append(f'{labels} کم‌دیده — وجودشون می‌تونه مزیت رقابتی باشه.')

    av = report.get('amenity_valuation') or {}
    if av.get('full_vs_bare', {}).get('gap_pct', 0) >= 5:
        fb = av['full_vs_bare']
        quality_items.append(
            f'فول امکانات: {fb["full_median_fmt"]} در مقابل بدون امکانات: '
            f'{fb["bare_median_fmt"]} (حدود {fb["gap_pct"]}٪ اختلاف).'
        )
    for item in (av.get('items') or [])[:3]:
        if abs(item.get('gap_pct') or 0) >= 4:
            quality_items.append(
                f'{item["label"]}: با امکانات {item["with_median_fmt"]} — '
                f'بدون آن {item["without_median_fmt"]} ({item["gap_pct"]:+g}٪).'
            )
    byg = av.get('build_year_gap') or {}
    if byg.get('gap_pct', 0) >= 4:
        quality_items.append(
            f'سال ساخت: واحدهای جدیدتر از {byg["median_year"]} حدود {byg["gap_pct"]}٪ '
            f'بالاتر از قدیمی‌ترها ({byg["newer_median_fmt"]} در برابر {byg["older_median_fmt"]}).'
        )
    for item in (av.get('secondary_items') or [])[:2]:
        if abs(item.get('gap_pct') or 0) >= 3:
            quality_items.append(
                f'{item["label"]}: {item["with_median_fmt"]} با امکانات — '
                f'{item["without_median_fmt"]} بدون آن ({item["gap_pct"]:+g}٪).'
            )
    if av.get('note'):
        quality_items.append(av['note'])

    quality_items.extend(_build_factor_insights(factors, ctx))

    if ctx.get('show_build_year') and build:
        if build.get('median_year'):
            quality_items.append(f'سال ساخت میانه: {build["median_year"]} (عمر ≈ {build.get("median_age", "—")} سال).')
        if build.get('under_5_pct') is not None:
            if build['under_5_pct'] >= 40:
                quality_items.append(
                    f'{build["under_5_pct"]}٪ فایل‌ها کمتر از ۵ سال عمر دارن — بازار نوساز.'
                )
            elif build['under_5_pct'] < 15:
                quality_items.append('بیشتر فایل‌ها قدیمی‌تر از ۵ سال — نوساز محدود و گرون‌تر.')
        if build.get('under_10_pct') is not None and build['under_10_pct'] >= 50:
            quality_items.append(f'{build["under_10_pct"]}٪ زیر ۱۰ سال — تنوع سنی خوب.')

    if quality_items:
        sections.append({'title': section_title, 'items': quality_items})

    # ─── ۴. محله‌ها ───
    if nb_list:
        loc_items: List[str] = []
        if len(nb_list) == 1:
            nb = nb_list[0]
            if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
                fd_m = nb.get('full_deposit') or {}
                rent_m = nb.get('rent') or {}
                dep_m = nb.get('deposit') or {}
                loc_items.append(
                    f'تمام {nb["count"]} فایل در محله {nb["neighborhood"]} — '
                    f'رهن کامل معمول {fd_m.get("median_fmt", "—")}'
                    + (f' ({dep_m.get("median_fmt", "—")} رهن + {rent_m.get("median_fmt", "—")} اجاره)' if dep_m.get('median_fmt') and rent_m.get('median_fmt') else '')
                    + '.'
                )
            else:
                metric = nb.get('price_per_sqm') or nb.get('rent') or nb.get('price') or {}
                metric_word = 'متری' if nb.get('price_per_sqm') else 'اجاره'
                loc_items.append(
                    f'تمام {nb["count"]} فایل در محله {nb["neighborhood"]} — '
                    f'{metric_word} معمول {metric.get("median_fmt", "—")}.'
                )
        else:
            cheapest = nb_list[-1]
            priciest = nb_list[0]
            if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
                p_m = priciest.get('full_deposit') or priciest.get('rent') or {}
                c_m = cheapest.get('full_deposit') or cheapest.get('rent') or {}
                loc_items.append(
                    f'گرون‌ترین: {priciest["neighborhood"]} (رهن کامل {p_m.get("median_fmt", "—")}, '
                    f'{priciest["count"]} فایل).'
                )
                loc_items.append(
                    f'ارزون‌ترین: {cheapest["neighborhood"]} (رهن کامل {c_m.get("median_fmt", "—")}, '
                    f'{cheapest["count"]} فایل).'
                )
                if p_m.get('median') and c_m.get('median') and c_m['median']:
                    gap = round((p_m['median'] - c_m['median']) / c_m['median'] * 100)
                    if gap >= 10:
                        loc_items.append(
                            f'اختلاف محله‌ها حدود {gap}٪ — با رهن کامل مقایسه کن.'
                        )
                for nb in nb_list[1:4]:
                    m = nb.get('full_deposit') or nb.get('rent') or {}
                    loc_items.append(
                        f'{nb["neighborhood"]}: رهن کامل {m.get("median_fmt", "—")} · {nb["count"]} فایل'
                    )
            else:
                p_m = priciest.get('price_per_sqm') or priciest.get('rent') or {}
                c_m = cheapest.get('price_per_sqm') or cheapest.get('rent') or {}
                loc_items.append(
                    f'گرون‌ترین: {priciest["neighborhood"]} ({p_m.get("median_fmt", "—")}, '
                    f'{priciest["count"]} فایل).'
                )
                loc_items.append(
                    f'ارزون‌ترین: {cheapest["neighborhood"]} ({c_m.get("median_fmt", "—")}, '
                    f'{cheapest["count"]} فایل).'
                )
                if p_m.get('median') and c_m.get('median') and c_m['median']:
                    gap = round((p_m['median'] - c_m['median']) / c_m['median'] * 100)
                    if gap >= 10:
                        loc_items.append(
                            f'اختلاف محله‌ها حدود {gap}٪ — قبل از بازدید محله رو با متری چک کن.'
                        )
                for nb in nb_list[1:4]:
                    m = nb.get('price_per_sqm') or nb.get('rent') or {}
                    loc_items.append(
                        f'{nb["neighborhood"]}: {m.get("median_fmt", "—")} · {nb["count"]} فایل'
                    )
        sections.append({'title': 'تحلیل محله‌ها', 'items': loc_items})

    landscape_lines = []
    try:
        from workspace.services.analyzer import build_consultant_landscape_lines
        landscape_lines = build_consultant_landscape_lines(stats.get('consultant_landscape') or {})
    except Exception:
        landscape_lines = []
    if landscape_lines:
        sections.append({'title': 'آمار مشاورین منطقه', 'items': landscape_lines})

    # ─── ۵. نقدشوندگی، روند و اعتماد ───
    meta_items: List[str] = []
    if liq.get('label'):
        meta_items.append(f'نقدشوندگی: {liq["label"]} ({liq.get("stars", "")}).')
        if liq.get('score', 0) >= 65:
            meta_items.append('بازار فعال — فایل‌های زیر بازار سریع پیشنهاد بده.')
        elif liq.get('score', 0) < 45:
            meta_items.append('بازار کندتر — روی کیفیت فایل و قیمت رقابتی تمرکز کن.')

    if trends and trends.get('pps_monthly_fmt'):
        meta_items.append(f'روند متری ماهانه: {trends["pps_monthly_fmt"]}.')
    if trends and trends.get('price_yearly_fmt'):
        meta_items.append(f'روند قیمت کل سالانه: {trends["price_yearly_fmt"]}.')

    if conf.get('score') is not None:
        valid = (dq.get('valid_count') or report.get('data_quality', {}).get('valid_count'))
        valid_note = f' — {valid} فایل معتبر' if valid else ''
        meta_items.append(
            f'اعتماد به تحلیل: {conf.get("level_plain", conf.get("level", "—"))} '
            f'({conf["score"]} از ۱۰۰){valid_note}'
        )
    if dq.get('quality_pct') is not None and dq.get('removed_count', 0) > 0:
        meta_items.append(
            f'از {dq["raw_count"]} آگهی، {dq["removed_count"]} غیرعادی حذف شد '
            f'(کیفیت {dq["quality_pct"]}٪).'
        )

    if stats.get('consultant_pct') is not None:
        cp = stats['consultant_pct']
        if cp > 60:
            meta_items.append(
                f'{cp}٪ فایل مشاور — رقابت روی کیفیت فایل و سرعت پاسخ.'
            )
        else:
            meta_items.append(
                f'سهم آگهی شخصی بالا — فرصت تماس مستقیم با مالک.'
            )

    if opps:
        meta_items.append(
            f'{len(opps)} فایل با امتیاز فرصت بالا شناسایی شد — در بخش پیشنهاد ویژه ببین.'
        )

    if meta_items:
        sections.append({'title': 'نقدشوندگی و کیفیت داده', 'items': meta_items})

    # ─── ۶. نکات تخصصی دسته ───
    specialty: List[str] = list(_seg(ctx).get('specialty_tips') or [])
    if prop == 'commercial' and deal == 'sale':
        pps = pa.get('price_per_sqm', {})
        if pps.get('spread_50_pct', 0) > 30:
            specialty.append('قیمت‌ها متنوع است — موقعیت، طبقه و دسترسی را با متری مقایسه کن.')
    if deal == 'rent':
        fd = pa.get('full_deposit', {})
        if fd.get('p25_fmt') and fd.get('p75_fmt') and fd.get('p90_fmt'):
            specialty.append(
                f'راهنمای سریع: رهن کامل زیر {fd["p25_fmt"]} → فرصت عالی · '
                f'حدود {fd.get("median_fmt", "—")} → محدوده معمول · '
                f'بالای {fd["p75_fmt"]} → مذاکره · بالای {fd["p90_fmt"]} → احتمالاً گران.'
            )
    if specialty:
        sections.append({'title': f'نکات {ctx.get("badge", "بازار")}', 'items': specialty})

    return sections


def _flatten_sections(sections: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []
    for sec in sections:
        items.extend(sec.get('items', []))
    return items


def _build_negotiation(report: Dict[str, Any], ctx: Dict[str, Any]) -> List[str]:
    pa = report.get('price_analysis', {})
    depth = report.get('market_depth', {})
    tips: List[str] = []
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    client = ctx.get('client_word', 'مشتری')

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        fd = pa.get('full_deposit', {})
        rent = pa.get('rent', {})
        dep = pa.get('deposit', {})
        tips.append('راهنمای سریع مشاور (بر اساس رهن کامل معادل):')
        if fd.get('p25_fmt'):
            tips.append(f'رهن کامل زیر {fd["p25_fmt"]} → فرصت عالی برای {client}.')
        if fd.get('median_fmt'):
            tips.append(f'رهن کامل حدود {fd["median_fmt"]} → محدوده معمول بازار.')
        if fd.get('p75_fmt'):
            tips.append(f'رهن کامل {fd["p75_fmt"]} تا {fd.get("p90_fmt", "—")} → نیاز به مذاکره.')
        if fd.get('p90_fmt'):
            tips.append(f'بالای {fd["p90_fmt"]} رهن کامل → احتمالاً گران — بررسی دقیق.')
        if dep.get('median_fmt') and rent.get('median_fmt'):
            tips.append(
                f'عرف بسته رهن+اجاره: {dep["median_fmt"]} رهن + {rent["median_fmt"]} اجاره.'
            )
        if dep.get('p25_fmt'):
            tips.append(f'هدف رهن برای مستأجر: زیر {dep["p25_fmt"]}.')
        tips.append('قانون تبدیل: هر ۳۰ میلیون تومان رهن ≈ ۱ میلیون اجاره ماهانه.')
        return tips

    pps = pa.get('price_per_sqm', {})
    price = pa.get('price', {})

    if prop == 'land':
        if price.get('p25_fmt'):
            tips.append(f'قیمت کل زیر {price["p25_fmt"]} → فرصت برای {client}.')
        if price.get('range_50_fmt'):
            tips.append(f'بیشتر قیمت‌ها: {price["range_50_fmt"]}.')
        if price.get('p75_fmt'):
            tips.append(f'بالای {price["p75_fmt"]} → مذاکره جدی.')
        return tips

    if depth.get('p40_fmt') and ctx.get('show_pps'):
        lo = strip_toman_suffix(depth['p40_fmt'])
        hi = strip_toman_suffix(depth.get('p60_fmt', '—'))
        tips.append(f'هدف خرید: زیر {lo} تومان/متر')
        tips.append(f'مذاکره فروش: بالای {hi} تومان/متر')

    for seg in report.get('area_segments', [])[:2]:
        bucket = seg.get('bucket_plain', seg.get('bucket', ''))
        if seg.get('median_pps_fmt'):
            tips.append(f'{bucket}: متری هدف ≈ {seg["median_pps_fmt"]}')

    return tips
