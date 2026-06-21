"""Compact Level-2 analysis UI model — fuse charts, insights, and tables for consultants."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.services.market_agent import filter_l2_actions


def _bucket_charts(charts: Optional[List[Dict]]) -> Dict[str, List[Dict]]:
    buckets: Dict[str, List[Dict]] = {
        'overview': [],
        'price': [],
        'segments': [],
        'neighborhood': [],
    }
    for i, ch in enumerate(charts or []):
        title = ch.get('title', '')
        entry = {**ch, 'idx': i}
        if any(k in title for k in ('محله', 'مقایسه محله')):
            buckets['neighborhood'].append(entry)
        elif any(k in title for k in (
            'محدوده متراژ', 'متراژ در هر', 'توزیع متراژ', 'بیشتر فایل‌ها چند متری',
            'تعداد اتاق', 'پارکینگ و آسانسور', 'امکانات',
        )):
            buckets['segments'].append(entry)
        elif any(k in title for k in (
            'ارزون', 'سر به سر', 'سطح قیمت', 'پوشش امکانات', 'چند فایل زیر',
        )):
            buckets['overview'].append(entry)
        else:
            buckets['price'].append(entry)
    return buckets


def _bucket_insight_sections(sections: Optional[List[Dict]]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {
        'overview': [],
        'price': [],
        'segments': [],
        'neighborhood': [],
    }
    for sec in sections or []:
        title = sec.get('title', '')
        items = [x for x in (sec.get('items') or []) if x]
        if not items:
            continue
        if any(k in title for k in ('محله', 'منطقه')):
            key = 'neighborhood'
        elif any(k in title for k in ('متراژ', 'باکت', 'امکانات', 'سال ساخت', 'بنا')):
            key = 'segments'
        elif any(k in title for k in ('قیمت', 'رهن', 'اجاره', 'مذاکره', 'کلنگی', 'زمین', 'پروژه')):
            key = 'price'
        else:
            key = 'overview'
        buckets[key].extend(items)
    for key in buckets:
        buckets[key] = buckets[key][:3]
    return buckets


def build_l2_ui(
    report: Dict[str, Any],
    charts: Optional[List[Dict]],
    *,
    flat_insights: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Shape data for the fused Level-2 consultant dashboard."""
    chart_buckets = _bucket_charts(charts)
    insight_buckets = _bucket_insight_sections(report.get('insight_sections'))
    if not any(insight_buckets.values()) and flat_insights:
        insight_buckets['overview'] = flat_insights[:3]

    tabs: List[Dict[str, Any]] = []
    tab_defs = (
        ('overview', 'نمای کلی', 'fa-compass'),
        ('price', 'قیمت', 'fa-coins'),
        ('segments', 'متراژ', 'fa-table-cells'),
        ('neighborhood', 'محله', 'fa-map-location-dot'),
    )
    for tab_id, label, icon in tab_defs:
        tab_charts = chart_buckets.get(tab_id, [])[:2]
        tab_insights = insight_buckets.get(tab_id, [])
        has_table = False
        if tab_id == 'segments' and report.get('area_segments'):
            has_table = True
        if tab_id == 'neighborhood' and report.get('neighborhoods'):
            has_table = True
        if tab_id == 'overview' and report.get('market_depth', {}).get('total'):
            has_table = True
        if not (tab_charts or tab_insights or has_table):
            continue
        tabs.append({
            'id': tab_id,
            'label': label,
            'icon': icon,
            'charts': tab_charts,
            'insights': tab_insights,
            'has_depth': tab_id == 'overview' and bool(report.get('market_depth', {}).get('total')),
            'has_segments': tab_id == 'segments' and bool(report.get('area_segments')),
            'has_amenities': tab_id == 'segments' and bool(report.get('amenities_coverage')),
            'has_neighborhoods': tab_id == 'neighborhood' and bool(report.get('neighborhoods')),
        })

    opps = report.get('opportunities') or []
    return {
        'tabs': tabs,
        'actions': filter_l2_actions(report.get('actions')),
        'scenarios': [],
        'scenarios_extra': [],
        'opportunities': opps[:3],
        'opportunities_more': opps[3:],
        'negotiation': (report.get('negotiation') or [])[:4],
        'has_prose': bool(
            report.get('professional_summary')
            or report.get('summary_lines')
            or report.get('summary')
        ),
        'quality_note': (
            (report.get('professional_summary') or {}).get('quality_note')
            or report.get('data_quality_warning')
            or ''
        ),
    }


def _seg(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx.get('segment_profile') or {}


def _l3_verdict(report: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Executive verdict — synthesized advisory headline for L3."""
    depth = report.get('market_depth') or {}
    sentiment = report.get('market_sentiment') or {}
    conf = report.get('confidence') or {}
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    client = ctx.get('client_word', 'مشتری')
    under_pct = float(depth.get('under_pct') or 0)
    over_pct = float(depth.get('over_pct') or 0)
    under_n = int(depth.get('under_market') or 0)
    total = int(depth.get('total') or 0)

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        metric_word = 'رهن کامل'
    elif prop == 'land':
        metric_word = 'قیمت کل'
    else:
        metric_word = 'قیمت هر متر'

    if under_pct >= 35 and under_n >= 3:
        headline = f'بازار شکار فرصت — سهم قابل توجه زیر عرف در {metric_word}'
        tone = 'positive'
        icon = 'fa-bullseye'
    elif over_pct >= 40:
        headline = f'بازار سخت‌گیر — تمرکز قیمت بالای عرف در {metric_word}'
        tone = 'caution'
        icon = 'fa-triangle-exclamation'
    elif sentiment.get('tone') == 'hot':
        headline = 'بازار داغ — سرعت تصمیم‌گیری مزیت رقابتی است'
        tone = 'positive'
        icon = 'fa-fire-flame-curved'
    elif sentiment.get('tone') == 'cold':
        headline = 'بازار آرام — مذاکره عمیق‌تر از سرعت، ارزش می‌آفریند'
        tone = 'neutral'
        icon = 'fa-hourglass-half'
    else:
        headline = 'بازار متعادل — کیفیت فایل تعیین‌کننده نتیجه است'
        tone = 'neutral'
        icon = 'fa-scale-balanced'

    lead_bits: List[str] = []
    if total:
        lead_bits.append(
            f'{under_n} فایل زیر عرف از {total} مورد بررسی‌شده — '
            f'اولویت پیشنهاد به {client}.'
        )
    if sentiment.get('label'):
        lead_bits.append(f'وضعیت کلی: {sentiment["label"]}.')
    level = conf.get('level_plain') or conf.get('level')
    score = conf.get('display_score', conf.get('score'))
    if level and score is not None:
        lead_bits.append(f'اعتماد تحلیل: {level} ({score} از ۱۰۰).')

    return {
        'headline': headline,
        'lead': ' '.join(lead_bits) if lead_bits else 'جمع‌بندی بر اساس الگوی قیمت، عمق بازار و کیفیت عرضه.',
        'tone': tone,
        'icon': icon,
    }


def _l3_market_thesis(report: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Market thesis — strategic read on pricing structure."""
    pa = report.get('price_analysis') or {}
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    trends = report.get('price_trends') or {}
    liq = report.get('liquidity') or {}
    items: List[str] = []

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        fd = pa.get('full_deposit') or {}
        rent = pa.get('rent') or {}
        dep = pa.get('deposit') or {}
        if fd.get('median_fmt') and fd.get('range_50_fmt'):
            items.append(
                f'محور قیمت‌گذاری بازار روی رهن کامل معادل است — '
                f'میانه {fd["median_fmt"]} و بازه رایج {fd["range_50_fmt"]}.'
            )
        if dep.get('median_fmt') and rent.get('median_fmt'):
            items.append(
                f'بسته رهن+اجاره غالب: {dep["median_fmt"]} ودیعه با {rent["median_fmt"]} اجاره — '
                f'هر تبدیل را با ضریب ۳۰ بر ۱ بسنج.'
            )
    elif prop == 'land':
        price = pa.get('price') or {}
        if price.get('median_fmt'):
            items.append(
                f'در این بازار تصمیم خرید بر قیمت کل استوار است — '
                f'میانه {price["median_fmt"]}.'
            )
        if price.get('range_50_fmt'):
            items.append(f'نیمی از عرضه بین {price["range_50_fmt"]} قیمت‌گذاری شده.')
    else:
        pps = pa.get('price_per_sqm') or {}
        if pps.get('median_fmt'):
            items.append(
                f'محور ارزش‌گذاری: قیمت هر متر با میانه {pps["median_fmt"]} '
                f'و بازه میانی {pps.get("range_50_fmt", "—")}.'
            )
        spread = pps.get('spread_50_pct')
        if spread is not None:
            if spread > 25:
                items.append(
                    'پراکندگی قیمت بالاست — تفاوت امکانات، طبقه و موقعیت '
                    'تفسیر متری را تعیین می‌کند.'
                )
            elif spread < 15:
                items.append(
                    'بازار نسبتاً یکدست است — انحراف از میانه معمولاً نشانه ریسک یا مزیت مشخص است.'
                )

    if trends.get('pps_monthly_fmt'):
        items.append(f'روند متری اخیر: {trends["pps_monthly_fmt"]} — در برآورد هدف لحاظ کن.')
    if trends.get('price_yearly_fmt'):
        items.append(f'روند قیمت کل سالانه: {trends["price_yearly_fmt"]}.')

    if liq.get('label'):
        liq_hint = ''
        score = liq.get('score', 0)
        if score >= 65:
            liq_hint = ' فایل‌های زیر بازار سریع‌تر جذب می‌شوند.'
        elif score < 45:
            liq_hint = ' صبر در مذاکره و کیفیت ارائه فایل اهمیت بیشتری دارد.'
        items.append(f'نقدشوندگی: {liq["label"]}.{liq_hint}')

    if not items:
        return {}
    return {
        'id': 'thesis',
        'title': 'تز بازار',
        'icon': 'fa-compass-drafting',
        'lead': 'برداشت کارشناسی از ساختار قیمت و رفتار فعلی بازار.',
        'items': items[:5],
        'tone': 'default',
    }


def _l3_negotiation_playbook(report: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Negotiation playbook — actionable thresholds for advisors."""
    raw = report.get('negotiation') or []
    pa = report.get('price_analysis') or {}
    depth = report.get('market_depth') or {}
    deal = ctx.get('deal')
    prop = ctx.get('prop')
    client = ctx.get('client_word', 'مشتری')
    items: List[Dict[str, str]] = []

    if deal == 'rent' or _seg(ctx).get('metric_mode') == 'rent_equiv':
        fd = pa.get('full_deposit') or {}
        if fd.get('p25_fmt'):
            items.append({
                'label': 'هدف پیشنهاد',
                'text': f'رهن کامل زیر {fd["p25_fmt"]} — اولویت تماس با {client}.',
                'tone': 'positive',
            })
        if fd.get('median_fmt'):
            items.append({
                'label': 'محدوده عرف',
                'text': f'حدود {fd["median_fmt"]} — قیمت قابل دفاع در بازار.',
                'tone': 'neutral',
            })
        if fd.get('p75_fmt'):
            items.append({
                'label': 'شروع مذاکره',
                'text': f'بالای {fd["p75_fmt"]} — فضای چانه‌زنی جدی وجود دارد.',
                'tone': 'caution',
            })
        if fd.get('p90_fmt'):
            items.append({
                'label': 'رد یا مذاکره سنگین',
                'text': f'بیش از {fd["p90_fmt"]} — احتمال گرانی بالا؛ قبل از بازدید فیلتر کن.',
                'tone': 'caution',
            })
    elif prop == 'land':
        price = pa.get('price') or {}
        if price.get('p25_fmt'):
            items.append({
                'label': 'هدف خرید',
                'text': f'قیمت کل زیر {price["p25_fmt"]} — فرصت ارزش‌افزوده.',
                'tone': 'positive',
            })
        if price.get('p75_fmt'):
            items.append({
                'label': 'سقف مذاکره',
                'text': f'بالای {price["p75_fmt"]} — نیاز به توجیه حقوقی و موقعیت.',
                'tone': 'caution',
            })
    else:
        if depth.get('p40_fmt') and ctx.get('show_pps'):
            lo = depth['p40_fmt']
            hi = depth.get('p60_fmt', '—')
            items.append({
                'label': 'هدف خرید',
                'text': f'متری زیر {lo} — محدوده جذاب برای {client}.',
                'tone': 'positive',
            })
            items.append({
                'label': 'خط مذاکره فروش',
                'text': f'بالای {hi} — فشار قیمت یا رد فایل توجیه‌پذیر است.',
                'tone': 'caution',
            })
        for seg in (report.get('area_segments') or [])[:2]:
            bucket = seg.get('bucket_plain', seg.get('bucket', ''))
            if seg.get('median_pps_fmt'):
                items.append({
                    'label': bucket,
                    'text': f'متری مرجع این بازه: {seg["median_pps_fmt"]}.',
                    'tone': 'neutral',
                })

    if not items and raw:
        for line in raw[1:5]:
            items.append({'label': 'راهنما', 'text': line, 'tone': 'neutral'})

    if not items:
        return {}
    return {
        'id': 'playbook',
        'title': 'راهبرد مذاکره',
        'icon': 'fa-handshake',
        'lead': 'آستانه‌های عملی برای پیشنهاد، مذاکره و رد فایل.',
        'items': items[:5],
        'tone': 'default',
    }


def _l3_risk_flags(report: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Risk flags — caveats advisors should surface to clients."""
    items: List[Dict[str, str]] = []
    warn = (report.get('data_quality_warning') or '').strip()
    if warn:
        items.append({'text': warn.replace('🟠 ', ''), 'severity': 'high'})

    pa = report.get('price_analysis') or {}
    pps = pa.get('price_per_sqm') or {}
    cv = pps.get('cv')
    if cv is not None and cv > 30:
        items.append({
            'text': f'پراکندگی آماری بالا (CV={cv}٪) — هر فایل را جداگانه با امکانات و موقعیت بسنج.',
            'severity': 'medium',
        })

    conf = report.get('confidence') or {}
    score = conf.get('display_score', conf.get('score', 100))
    if score is not None and int(score) < 55:
        items.append({
            'text': 'اعتماد تحلیل پایین — قبل از تصمیم نهایی نمونه بیشتری جمع‌آوری کن.',
            'severity': 'high',
        })

    segs = report.get('area_segments') or []
    if segs:
        total = sum(s.get('count', 0) for s in segs)
        thin = [s for s in segs if s.get('count', 0) < max(3, total * 0.05)]
        if thin:
            labels = '، '.join(
                s.get('bucket_plain', s.get('bucket', '')) for s in thin[:2]
            )
            items.append({
                'text': f'داده محدود در بازه‌های {labels} — قیمت‌گذاری با احتیاط.',
                'severity': 'medium',
            })

    liq = report.get('liquidity') or {}
    if liq.get('score', 100) < 40:
        items.append({
            'text': 'نقدشوندگی پایین — زمان فروش یا اجاره ممکن است طولانی‌تر از میانگین باشد.',
            'severity': 'medium',
        })

    over_pct = float((report.get('market_depth') or {}).get('over_pct') or 0)
    if over_pct >= 45:
        items.append({
            'text': 'سهم بالای بازار بالای عرف است — ریسک قیمت‌گذاری خوش‌بینانه برای فروشنده.',
            'severity': 'medium',
        })

    if not items:
        return {}
    return {
        'id': 'risks',
        'title': 'پرچم‌های ریسک',
        'icon': 'fa-shield-halved',
        'lead': 'نکاتی که باید پیش از تعهد به مشتری شفاف شوند.',
        'items': items[:5],
        'tone': 'caution',
    }


def _l3_segment_intel(report: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Segment intelligence — supply/demand structure by size and location."""
    items: List[str] = []
    segs = report.get('area_segments') or []
    if segs:
        sorted_segs = sorted(segs, key=lambda s: s.get('count', 0), reverse=True)
        top = sorted_segs[0]
        items.append(
            f'قلب عرضه: {top.get("bucket_plain", top.get("bucket", ""))} '
            f'با {top.get("share_pct", 0)}٪ سهم — قیمت این بازه مرجع بازار است.'
        )
        if len(sorted_segs) >= 2:
            second = sorted_segs[1]
            if top.get('median_pps_fmt') and second.get('median_pps_fmt'):
                items.append(
                    f'مقایسه متری: {top.get("bucket_plain", top["bucket"])} '
                    f'({top["median_pps_fmt"]}) در برابر '
                    f'{second.get("bucket_plain", second["bucket"])} ({second["median_pps_fmt"]}).'
                )

    nb = report.get('neighborhoods') or []
    if len(nb) >= 2:
        top_nb = nb[0]
        items.append(
            f'محور موقعیت: {top_nb.get("name", "—")} پرتقاضاترین محله '
            f'({top_nb.get("count", 0)} فایل).'
        )
        if nb[1].get('name') and top_nb.get('median_pps_fmt') and nb[1].get('median_pps_fmt'):
            items.append(
                f'فاصله متری {top_nb["name"]} و {nb[1]["name"]}: '
                f'{top_nb["median_pps_fmt"]} در برابر {nb[1]["median_pps_fmt"]}.'
            )

    build = report.get('build_year') or {}
    if build.get('dominant_label'):
        items.append(f'سال ساخت غالب: {build["dominant_label"]} — در تخمین ارزش لحاظ کن.')

    av = report.get('amenity_valuation') or {}
    if av.get('headline'):
        items.append(av['headline'])
    elif av.get('full_vs_bare', {}).get('gap_pct'):
        gap = av['full_vs_bare']['gap_pct']
        items.append(f'پریمیوم امکانات کامل نسبت به بدون امکانات: حدود {gap}٪.')

    opps = report.get('opportunities') or []
    if opps:
        items.append(
            f'{len(opps)} فایل با امتیاز فرصت شناسایی شد — '
            f'در بخش فرصت‌های برتر سطح ۲ جزئیات را ببین.'
        )

    if not items:
        return {}
    return {
        'id': 'segments',
        'title': 'هوش بخش‌بندی',
        'icon': 'fa-chart-pie',
        'lead': 'ساختار عرضه بر اساس متراژ، محله و ویژگی‌های بنا.',
        'items': items[:5],
        'tone': 'default',
    }


def build_l3_ui(report: Dict[str, Any]) -> Dict[str, Any]:
    """Shape data for Level-3 expert advisory dashboard."""
    ctx = report.get('context') or {}
    expert = report.get('expert_details') or {}
    bands = expert.get('price_bands') or []
    conf = expert.get('confidence') or {}

    sections: List[Dict[str, Any]] = []
    for builder in (_l3_market_thesis, _l3_negotiation_playbook, _l3_risk_flags, _l3_segment_intel):
        sec = builder(report, ctx)
        if sec:
            sections.append(sec)

    verdict = _l3_verdict(report, ctx)
    has_content = bool(sections or bands or verdict.get('headline'))

    meta_parts = []
    if bands:
        meta_parts.append('بازه قیمت')
    if any(s.get('id') == 'playbook' for s in sections):
        meta_parts.append('مذاکره')
    if any(s.get('id') == 'risks' for s in sections):
        meta_parts.append('ریسک')
    if conf.get('level'):
        meta_parts.append('اعتماد')

    return {
        'show': has_content,
        'summary_meta': ' · '.join(meta_parts) if meta_parts else 'تحلیل کارشناسی',
        'verdict': verdict,
        'sections': sections,
        'bands': {
            'title': expert.get('bands_title', 'بازه‌های قیمت'),
            'note': expert.get('bands_note', ''),
            'items': bands,
            'cv_label': expert.get('cv_label', ''),
            'trend_monthly': expert.get('trend_monthly', ''),
        },
        'confidence': {
            'level': conf.get('level', ''),
            'score': conf.get('score'),
        } if conf.get('level') or conf.get('score') is not None else None,
    }
