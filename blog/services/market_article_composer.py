"""تولید HTML مقاله سیستماتیک ۱۵بخشی از گزارش تحلیل."""
from __future__ import annotations

import html
from typing import Any


def compose_market_article(
    *,
    report: dict[str, Any],
    dataset_meta: dict[str, Any],
    map_image_url: str = '',
    map_caption: str = '',
) -> dict[str, Any]:
    city = dataset_meta.get('city') or 'ایران'
    district = dataset_meta.get('district') or 'منطقه'
    tx_raw = dataset_meta.get('transaction_type') or ''
    subcat = dataset_meta.get('subcategory') or 'ملک'
    tx_label = _tx_label(tx_raw, report.get('tx') or {})

    title = f'قیمت {subcat} در {district} {city}؛ تحلیل بازار {tx_label} و قیمت هر متر'
    if len(title) > 200:
        title = f'تحلیل بازار {subcat} در {district} {city}'

    conf = report.get('confidence') or {}
    dq = report.get('data_quality') or {}
    scope = report.get('publication_scope') or {}
    sentiment = report.get('market_sentiment') or {}
    liquidity = report.get('liquidity') or {}
    trends = report.get('price_trends') or {}
    depth = report.get('market_depth') or {}
    pa = report.get('price_analysis') or {}
    pps = pa.get('price_per_sqm') or {}
    price = pa.get('price') or {}
    segments = report.get('area_segments') or []
    amenities = report.get('amenities_coverage') or {}
    amenity_val = report.get('amenity_valuation') or {}
    opportunities = report.get('opportunities') or {}
    negotiation = report.get('negotiation') or {}
    insights = report.get('insights') or []
    prof = report.get('professional_summary') or {}

    valid_n = dq.get('valid_count') or scope.get('analyzed_count') or 0
    raw_n = dq.get('raw_count') or valid_n
    removed = dq.get('removed_count') or max(0, int(raw_n) - int(valid_n))
    conf_score = conf.get('display_score') or conf.get('score') or '—'
    conf_level = conf.get('level_plain') or conf.get('level') or '—'
    pps_med = pps.get('median_fmt') or '—'
    date_from = scope.get('date_from_fmt') or '—'
    date_to = scope.get('date_to_fmt') or '—'
    under_pct = depth.get('under_pct')
    trend_fmt = trends.get('pps_monthly_fmt') or _fmt_trend(trends)
    sentiment_label = sentiment.get('label') or 'نامشخص'
    liq_label = liquidity.get('label') or '—'

    excerpt = (
        f'تحلیل بازار {subcat} در {district} {city} بر اساس {valid_n} فایل معتبر؛ '
        f'قیمت معمول هر متر {pps_med}؛ وضعیت بازار: {sentiment_label}؛ '
        f'اعتماد تحلیل {conf_score}.'
    )[:300]

    faq = _build_faq(
        city=city,
        district=district,
        subcat=subcat,
        pps_med=pps_med,
        valid_n=valid_n,
        date_from=date_from,
        date_to=date_to,
        segments=segments,
        negotiation=negotiation,
        sentiment_label=sentiment_label,
        under_pct=under_pct,
    )

    parts: list[str] = []
    parts.append(_section_intro(
        city, district, subcat, tx_label, valid_n, date_from, date_to,
        pps_med, trend_fmt, sentiment_label, conf_score, conf_level, prof,
    ))
    parts.append(_section_kpi_cards(
        pps_med, price, valid_n, under_pct, trend_fmt, liq_label, conf_score, segments,
    ))
    parts.append(_section_market_status(
        sentiment, liquidity, depth, insights, pps, conf_level,
    ))
    parts.append(_section_pps(pps, depth, pa))
    parts.append(_section_segments(segments, pps_med))
    parts.append(_section_amenities(amenities, amenity_val))
    parts.append(_section_trends(trends, sentiment_label))
    parts.append(_section_map(map_image_url, map_caption, city, district))
    parts.append(_section_opportunities(opportunities, under_pct))
    parts.append(_section_negotiation(negotiation, pps))
    parts.append(_section_verdict(
        city, district, sentiment_label, opportunities, conf_level, insights,
    ))
    parts.append(_section_methodology(
        valid_n, removed, raw_n, date_from, date_to, conf_score, conf_level, dq,
    ))
    parts.append(_section_faq(faq))
    parts.append(_section_cta())

    content = '\n'.join(p for p in parts if p)
    return {
        'title': title,
        'excerpt': excerpt,
        'content_html': content,
        'faq': faq,
        'tags': _tags(city, district, tx_label, subcat),
    }


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else '—'))


def _tx_label(raw: str, tx: dict) -> str:
    if tx.get('is_rent') and not tx.get('is_sale'):
        return 'اجاره'
    if tx.get('is_sale') and not tx.get('is_rent'):
        return 'فروش'
    text = (raw or '').strip()
    if 'اجاره' in text:
        return 'اجاره'
    if 'فروش' in text or 'خرید' in text:
        return 'فروش'
    return text or 'معامله'


def _fmt_trend(trends: dict) -> str:
    if not trends:
        return 'داده روند کافی نیست'
    monthly = trends.get('pps_monthly_pct')
    if monthly is None:
        t = (trends.get('trends') or {}).get('monthly')
        if t is None:
            return 'داده روند کافی نیست'
        monthly = t
    sign = '+' if monthly > 0 else ''
    return f'{sign}{monthly}٪ ماهانه'


def _section_intro(
    city, district, subcat, tx_label, valid_n, date_from, date_to,
    pps_med, trend_fmt, sentiment_label, conf_score, conf_level, prof,
) -> str:
    intro = ''
    if isinstance(prof, dict):
        intro = (prof.get('intro') or '').strip()
    if not intro:
        intro = (
            f'در این گزارش، بازار {tx_label} {subcat} در محله {district} شهر {city} '
            f'بر اساس {valid_n} فایل معتبر بررسی شده است.'
        )
    quality_note = ''
    if isinstance(prof, dict) and prof.get('quality_note'):
        quality_note = f'<p class="mk-market-note">{_e(prof["quality_note"])}</p>'
    return f'''
<section class="mk-market-section" id="executive-summary">
  <h2>خلاصه اجرایی بازار { _e(district) }</h2>
  <p>{_e(intro)}</p>
  <ul class="mk-market-bullets">
    <li>تعداد فایل‌های بررسی‌شده: <strong>{_e(valid_n)}</strong></li>
    <li>بازه زمانی داده‌ها: از <strong>{_e(date_from)}</strong> تا <strong>{_e(date_to)}</strong></li>
    <li>قیمت معمول هر متر: <strong>{_e(pps_med)}</strong></li>
    <li>روند بازار: <strong>{_e(trend_fmt)}</strong></li>
    <li>وضعیت بازار: <strong>{_e(sentiment_label)}</strong></li>
    <li>اعتماد تحلیل: <strong>{_e(conf_score)}</strong> ({_e(conf_level)})</li>
  </ul>
  {quality_note}
</section>
'''


def _section_kpi_cards(pps_med, price, valid_n, under_pct, trend_fmt, liq_label, conf_score, segments) -> str:
    top_seg = segments[0] if segments else {}
    dense = top_seg.get('bucket_plain') or top_seg.get('bucket') or '—'
    price_med = (price or {}).get('median_fmt') or '—'
    under = f'{under_pct}٪' if under_pct is not None else '—'
    cards = [
        ('قیمت میانه هر متر', pps_med),
        ('قیمت معمول کل', price_med),
        ('فایل معتبر', valid_n),
        ('فایل‌های زیر بازار', under),
        ('روند قیمت', trend_fmt),
        ('نقدشوندگی', liq_label),
        ('امتیاز اعتماد', conf_score),
        ('پرتراکم‌ترین متراژ', dense),
    ]
    items = ''.join(
        f'<div class="mk-market-kpi"><span class="mk-market-kpi__lbl">{_e(lbl)}</span>'
        f'<strong class="mk-market-kpi__val">{_e(val)}</strong></div>'
        for lbl, val in cards
    )
    return f'''
<section class="mk-market-section" id="market-kpis">
  <h2>شاخص‌های اصلی بازار</h2>
  <div class="mk-market-kpi-grid">{items}</div>
</section>
'''


def _section_market_status(sentiment, liquidity, depth, insights, pps, conf_level) -> str:
    lines = []
    if sentiment.get('label'):
        lines.append(f'وضعیت کلی بازار: {_e(sentiment.get("label"))}.')
    if sentiment.get('factors'):
        for f in sentiment['factors'][:4]:
            lines.append(str(f))
    if liquidity.get('label'):
        lines.append(f'نقدشوندگی: {_e(liquidity.get("label"))} (امتیاز {_e(liquidity.get("score", "—"))}).')
    if depth.get('under_pct') is not None:
        lines.append(
            f'حدود {_e(depth.get("under_pct"))}٪ فایل‌ها زیر بازار، '
            f'{_e(depth.get("fair_pct", "—"))}٪ در بازه معمول و '
            f'{_e(depth.get("over_pct", "—"))}٪ بالای بازار هستند.'
        )
    if pps.get('cv') is not None:
        lines.append(f'پراکندگی قیمت هر متر (CV): {_e(pps.get("cv"))} — شاخص فضای مذاکره.')
    lines.append(f'سطح اعتماد به این تحلیل: {_e(conf_level)}.')
    for tip in (insights or [])[:5]:
        if isinstance(tip, str) and tip.strip():
            lines.append(tip.strip())
    lis = ''.join(f'<li>{_e(x)}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="market-status">
  <h2>تحلیل کامل وضعیت بازار</h2>
  <ul class="mk-market-bullets">{lis}</ul>
</section>
'''


def _section_pps(pps: dict, depth: dict, pa: dict) -> str:
    if not pps:
        return ''
    rows = [
        ('قیمت میانه هر متر', pps.get('median_fmt')),
        ('بازه معمول (۵۰٪)', pps.get('range_50_fmt') or pps.get('iqr_fmt')),
        ('بازه وسیع‌تر (۸۰٪)', pps.get('range_80_fmt')),
        ('محدوده ارزان‌تر', pps.get('p25_fmt') or pps.get('low_fmt')),
        ('محدوده گران‌تر', pps.get('p75_fmt') or pps.get('high_fmt')),
    ]
    body = ''.join(
        f'<tr><th>{_e(a)}</th><td>{_e(b or "—")}</td></tr>' for a, b in rows if a
    )
    mix = ''
    if depth.get('under_pct') is not None:
        mix = (
            f'<p>ترکیب بازار: {_e(depth.get("under_pct"))}٪ زیر بازار، '
            f'{_e(depth.get("fair_pct", "—"))}٪ معمول، '
            f'{_e(depth.get("over_pct", "—"))}٪ بالای بازار.</p>'
        )
    return f'''
<section class="mk-market-section" id="price-per-sqm">
  <h2>تحلیل قیمت هر متر</h2>
  <table class="mk-market-table"><tbody>{body}</tbody></table>
  {mix}
</section>
'''


def _section_segments(segments: list, market_pps: str) -> str:
    if not segments:
        return ''
    rows = []
    for seg in segments[:8]:
        name = seg.get('bucket_plain') or seg.get('bucket') or '—'
        rows.append(
            '<tr>'
            f'<td>{_e(name)}</td>'
            f'<td>{_e(seg.get("count", "—"))}</td>'
            f'<td>{_e(seg.get("share_pct", seg.get("pct", "—")))}</td>'
            f'<td>{_e(seg.get("area_median_fmt", seg.get("median_area_fmt", "—")))}</td>'
            f'<td>{_e(seg.get("pps_median_fmt", seg.get("price_per_sqm_fmt", "—")))}</td>'
            f'<td>{_e(seg.get("price_median_fmt", seg.get("price_fmt", "—")))}</td>'
            '</tr>'
        )
    return f'''
<section class="mk-market-section" id="area-segments">
  <h2>تحلیل متراژ</h2>
  <p>مقایسه بازه‌های متراژ نسبت به میانه کل بازار ({_e(market_pps)}).</p>
  <table class="mk-market-table">
    <thead><tr>
      <th>بازه</th><th>تعداد</th><th>سهم</th><th>متراژ معمول</th><th>قیمت هر متر</th><th>قیمت کل</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
'''


def _section_amenities(amenities: Any, amenity_val: Any) -> str:
    items: list[str] = []
    if isinstance(amenities, dict):
        for key, val in list(amenities.items())[:12]:
            if isinstance(val, dict):
                pct = val.get('pct') or val.get('coverage_pct') or val.get('share')
                items.append(f'{key}: {_e(pct)}٪ پوشش')
            elif val is not None:
                items.append(f'{key}: {_e(val)}')
    elif isinstance(amenities, list):
        for row in amenities[:12]:
            if isinstance(row, dict):
                items.append(
                    f'{row.get("label") or row.get("name") or "امکانات"}: '
                    f'{_e(row.get("pct", row.get("coverage_pct", "—")))}٪'
                )
    premium_lines = []
    if isinstance(amenity_val, dict):
        for key, val in list(amenity_val.items())[:8]:
            if isinstance(val, dict) and val.get('premium_fmt'):
                premium_lines.append(f'{key}: اثر تقریبی {_e(val["premium_fmt"])}')
            elif isinstance(val, dict) and val.get('note'):
                premium_lines.append(f'{key}: {_e(val["note"])}')
    if not items and not premium_lines:
        return ''
    lis = ''.join(f'<li>{_e(x) if not x.startswith("<") else x}</li>' for x in items)
    # fix double escape - items already have escaped pct
    lis = ''.join(f'<li>{x}</li>' for x in items)
    prem = ''.join(f'<li>{x}</li>' for x in premium_lines)
    prem_block = f'<h3>اثر تقریبی روی قیمت</h3><ul class="mk-market-bullets">{prem}</ul>' if prem else ''
    return f'''
<section class="mk-market-section" id="amenities">
  <h2>تحلیل امکانات</h2>
  <ul class="mk-market-bullets">{lis}</ul>
  {prem_block}
</section>
'''


def _section_trends(trends: dict, sentiment_label: str) -> str:
    if not trends or not trends.get('has_data'):
        return '''
<section class="mk-market-section" id="trends">
  <h2>روند بازار</h2>
  <p>برای محاسبه روند قابل اتکا، داده زمانی کافی در این دیتاست موجود نبود.</p>
</section>
'''
    tmap = trends.get('trends') or {}
    lines = [f'وضعیت کلی مرتبط با روند: {_e(sentiment_label)}.']
    if trends.get('pps_monthly_fmt'):
        lines.append(f'تغییر ماهانه قیمت هر متر: {_e(trends["pps_monthly_fmt"])}.')
    for key, label in (('weekly', 'هفتگی'), ('monthly', 'ماهانه'), ('quarterly', 'فصلی'), ('yearly', 'سالانه')):
        if key in tmap:
            lines.append(f'تغییر {_e(label)}: {_e(tmap[key])}٪.')
    if trends.get('points'):
        lines.append(f'تعداد نقاط زمانی استفاده‌شده: {_e(trends["points"])}.')
    lis = ''.join(f'<li>{x}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="trends">
  <h2>روند بازار</h2>
  <ul class="mk-market-bullets">{lis}</ul>
  <p>تفسیر: روند مثبت معمولاً فضای فروشنده‌محورتر و روند منفی فضای مذاکره خریدار را تقویت می‌کند؛ اعداد بالا مبنای تصمیم‌اند نه پیش‌بینی قطعی.</p>
</section>
'''


def _section_map(url: str, caption: str, city: str, district: str) -> str:
    if not url:
        return f'''
<section class="mk-market-section" id="spatial">
  <h2>نقشه و تحلیل مکانی</h2>
  <p>مختصات کافی برای تولید نقشه تراکم در {_e(district)} {_e(city)} در دسترس نبود. تحلیل مکانی در نسخه بعدی با داده جغرافیایی کامل‌تر تکمیل می‌شود.</p>
</section>
'''
    cap = caption or f'نقشه تراکم بازار در {district} {city}'
    return f'''
<section class="mk-market-section" id="spatial">
  <h2>نقشه و تحلیل مکانی</h2>
  <figure class="mk-market-map">
    <img src="{_e(url)}" alt="{_e(cap)}" width="1200" height="630" loading="lazy">
    <figcaption>{_e(cap)} — نمایش تجمیعی؛ موقعیت دقیق آگهی‌ها نمایش داده نمی‌شود.</figcaption>
  </figure>
</section>
'''


def _section_opportunities(opportunities: Any, under_pct) -> str:
    lines = []
    if under_pct is not None:
        lines.append(f'حدود {_e(under_pct)}٪ فایل‌ها زیر قیمت بازار شناسایی شده‌اند.')
    data = opportunities
    if isinstance(opportunities, dict):
        if opportunities.get('count') is not None:
            lines.append(f'تعداد فرصت‌های رتبه‌بندی‌شده: {_e(opportunities.get("count"))}.')
        if opportunities.get('summary'):
            lines.append(str(opportunities['summary']))
        data = opportunities.get('items') or opportunities.get('deals') or []
    if isinstance(data, list):
        areas = []
        for item in data[:8]:
            if not isinstance(item, dict):
                continue
            # Only aggregate fields — never token/link
            area = item.get('area_fmt') or item.get('area_bucket') or item.get('bucket')
            pps = item.get('pps_fmt') or item.get('price_per_sqm_fmt')
            gap = item.get('gap_pct') or item.get('discount_pct')
            bits = [x for x in (area, pps, f'شکاف {_e(gap)}٪' if gap is not None else '') if x]
            if bits:
                areas.append(' · '.join(str(b) for b in bits))
        if areas:
            lines.append('نمونه‌های تجمیعی فرصت (بدون شناسه):')
            lines.extend(areas[:5])
    if not lines:
        return ''
    lis = ''.join(f'<li>{_e(x) if "·" not in str(x) else _e(x)}</li>' for x in lines)
    lis = ''.join(f'<li>{_e(x)}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="opportunities">
  <h2>فرصت‌های بازار</h2>
  <ul class="mk-market-bullets">{lis}</ul>
  <p>پیشنهاد عملی: فایل‌های زیر بازار را با کیفیت ساخت، امکانات و زمان ماندگاری روی بازار تطبیق دهید؛ قیمت پایین به‌تنهایی معیار خرید نیست.</p>
</section>
'''


def _section_negotiation(negotiation: Any, pps: dict) -> str:
    lines = []
    if isinstance(negotiation, dict):
        for key, label in (
            ('target_fmt', 'قیمت هدف خرید'),
            ('target', 'قیمت هدف خرید'),
            ('line_fmt', 'خط مذاکره'),
            ('offer_range_fmt', 'محدوده پیشنهاد'),
            ('reject_above_fmt', 'آستانه نیاز به بررسی/رد'),
            ('note', 'توضیح'),
            ('summary', 'جمع‌بندی مذاکره'),
        ):
            if negotiation.get(key):
                lines.append(f'{label}: {_e(negotiation[key])}')
        if isinstance(negotiation.get('items'), list):
            for item in negotiation['items'][:6]:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, dict) and item.get('text'):
                    lines.append(str(item['text']))
    if not lines and pps:
        if pps.get('p25_fmt'):
            lines.append(f'محدوده مناسب پیشنهاد (نزدیک چارک پایین): {_e(pps["p25_fmt"])}')
        if pps.get('median_fmt'):
            lines.append(f'خط میانه بازار: {_e(pps["median_fmt"])}')
        if pps.get('p75_fmt'):
            lines.append(f'بالای این سطح معمولاً نیاز به بررسی دقیق دارد: {_e(pps["p75_fmt"])}')
    if not lines:
        return ''
    lis = ''.join(f'<li>{x if x.startswith("محدوده") or ":" in x else _e(x)}</li>' for x in lines)
    # lines already escaped where needed
    lis = ''.join(f'<li>{x}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="negotiation">
  <h2>راهبرد مذاکره</h2>
  <ul class="mk-market-bullets">{lis}</ul>
</section>
'''


def _section_verdict(city, district, sentiment_label, opportunities, conf_level, insights) -> str:
    opp_note = 'فرصت زیر بازار در داده‌ها دیده می‌شود.' if opportunities else 'فرصت برجسته تجمیعی ثبت نشده است.'
    risk = f'اعتماد تحلیل در سطح «{_e(conf_level)}» است؛ تصمیم نهایی باید با بازدید و صحت‌سنجی فایل انجام شود.'
    tip = ''
    for item in (insights or [])[:1]:
        if isinstance(item, str):
            tip = item
    tip_html = f' — {_e(tip)}' if tip else ''
    return f'''
<section class="mk-market-section" id="verdict">
  <h2>جمع‌بندی کارشناسی</h2>
  <p>بازار {_e(district)} در {_e(city)} هم‌اکنون {_e(sentiment_label)} ارزیابی می‌شود.</p>
  <ul class="mk-market-bullets">
    <li>مهم‌ترین فرصت: {_e(opp_note)}</li>
    <li>مهم‌ترین ریسک: {risk}</li>
    <li>کاربرد: این تحلیل مبنای قیمت‌گذاری، فیلتر فرصت و مذاکره برای مشاور و خریدار است{tip_html}.</li>
  </ul>
</section>
'''


def _section_methodology(valid_n, removed, raw_n, date_from, date_to, conf_score, conf_level, dq) -> str:
    return f'''
<section class="mk-market-section" id="methodology">
  <h2>روش‌شناسی و کیفیت داده</h2>
  <ul class="mk-market-bullets">
    <li>تعداد فایل بررسی‌شده (خام): {_e(raw_n)}</li>
    <li>تعداد فایل معتبر پس از پالایش: {_e(valid_n)}</li>
    <li>فایل‌های حذف‌شده/غیرعادی: {_e(removed)}</li>
    <li>بازه زمانی تحلیل: از {_e(date_from)} تا {_e(date_to)}</li>
    <li>شاخص مرکزی قیمت: میانه (مقاوم‌تر از میانگین در برابر پرت‌ها)</li>
    <li>تشخیص زیر بازار: نسبت قیمت هر متر به میانه بازار و عمق قیمت</li>
    <li>امتیاز اعتماد: {_e(conf_score)} ({_e(conf_level)})</li>
    <li>کیفیت داده: {_e(dq.get("quality_pct", "—"))}٪</li>
  </ul>
  <p>محدودیت‌ها: تحلیل بر اساس آگهی‌های موجود است، نه معاملات قطعی ثبت‌شده؛ ممکن است بخشی از بازار در داده نباشد. این گزارش جایگزین کارشناسی میدانی نیست.</p>
</section>
'''


def _build_faq(**kwargs) -> list[dict[str, str]]:
    city = kwargs['city']
    district = kwargs['district']
    subcat = kwargs['subcat']
    pps_med = kwargs['pps_med']
    valid_n = kwargs['valid_n']
    date_from = kwargs['date_from']
    date_to = kwargs['date_to']
    segments = kwargs['segments']
    negotiation = kwargs['negotiation']
    sentiment_label = kwargs['sentiment_label']
    under_pct = kwargs['under_pct']

    top_seg = '—'
    if segments:
        top_seg = segments[0].get('bucket_plain') or segments[0].get('bucket') or '—'

    target = '—'
    if isinstance(negotiation, dict):
        target = negotiation.get('target_fmt') or negotiation.get('offer_range_fmt') or '—'
    if target == '—' and kwargs.get('pps_med'):
        target = pps_med

    faq = [
        {
            'q': f'قیمت هر متر {subcat} در {district} {city} چقدر است؟',
            'a': f'بر اساس این تحلیل، قیمت معمول هر متر حدود {pps_med} است.',
        },
        {
            'q': 'کدام متراژ عرضه بیشتری دارد؟',
            'a': f'پرتراکم‌ترین بازه متراژ در داده فعلی «{top_seg}» است.',
        },
        {
            'q': 'چه قیمتی برای خرید مناسب است؟',
            'a': f'با توجه به میانه و آستانه‌های مذاکره، محدوده هدف حدود {target} ارزیابی می‌شود؛ بازدید و مقایسه فایل ضروری است.',
        },
        {
            'q': 'آیا بازار برای خریداران مناسب است؟',
            'a': f'وضعیت فعلی بازار: {sentiment_label}'
                 + (f' و حدود {under_pct}٪ فایل‌ها زیر بازار هستند.' if under_pct is not None else '.'),
        },
        {
            'q': 'این تحلیل بر اساس چند فایل ساخته شده؟',
            'a': f'{valid_n} فایل معتبر پس از پالایش داده در محاسبه لحاظ شده است.',
        },
        {
            'q': 'داده‌ها مربوط به چه بازه‌ای هستند؟',
            'a': f'از {date_from} تا {date_to}.',
        },
    ]
    return faq


def _section_faq(faq: list[dict[str, str]]) -> str:
    blocks = []
    for item in faq:
        blocks.append(
            f'<h3>{_e(item["q"])}</h3><p>{_e(item["a"])}</p>'
        )
    return f'''
<section class="blog-faq mk-market-section" id="faq">
  <h2>سوالات متداول</h2>
  {''.join(blocks)}
</section>
'''


def _section_cta() -> str:
    return '''
<section class="mk-market-section mk-market-cta" id="cta">
  <h2>ادامه مسیر با فایلینگ دیوار</h2>
  <p>همین تحلیل را می‌توانید روی فایل‌های خود در میزکار اجرا کنید، فرصت‌های زیر بازار را فیلتر کنید و با ربات فایلینگ دیوار بانک فایل به‌روز بسازید.</p>
  <ul class="mk-market-bullets">
    <li><a href="/features/market-intelligence/">امکانات تحلیل بازار</a></li>
    <li><a href="/products/">ربات فایلینگ دیوار</a></li>
    <li><a href="/workspace/">ورود به میزکار</a></li>
    <li><a href="/blog/">سایر تحلیل‌ها و مقالات</a></li>
  </ul>
</section>
'''


def _tags(city: str, district: str, tx_label: str, subcat: str) -> list[str]:
    tags = [city, district, tx_label, subcat, 'تحلیل بازار', 'قیمت هر متر']
    return [t for t in tags if t and t != '—'][:8]
