"""تولید HTML مقاله سیستماتیک — متن ساده، دقیق و چندمخاطبه."""
from __future__ import annotations

import html
from typing import Any

from blog.services.market_article_seo import (
    render_charts_section,
    render_convert_band,
    render_cta_section,
    render_maps_section,
    render_related_links_section,
)


def compose_market_article(
    *,
    report: dict[str, Any],
    dataset_meta: dict[str, Any],
    map_image_url: str = '',
    map_caption: str = '',
    map_assets: dict[str, str] | None = None,
    related_posts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    city = dataset_meta.get('city') or 'ایران'
    district = dataset_meta.get('district') or 'منطقه'
    tx_raw = dataset_meta.get('transaction_type') or ''
    subcat = dataset_meta.get('subcategory') or 'ملک'
    tx = report.get('tx') or {}
    tx_label = _tx_label(tx_raw, tx)
    is_rent = bool(tx.get('is_rent') and not tx.get('is_sale'))

    if is_rent:
        title = (
            f'رهن و اجاره {subcat} در {district} {city}؛ '
            f'تحلیل بازار {tx_label}، رهن کامل و راهنمای معامله'
        )
        if len(title) > 200:
            title = f'تحلیل بازار {tx_label} {subcat} در {district} {city}'
    else:
        title = (
            f'قیمت {subcat} در {district} {city}؛ '
            f'تحلیل بازار {tx_label}، قیمت هر متر و راهنمای خرید و فروش'
        )
        if len(title) > 200:
            title = f'تحلیل بازار {subcat} در {district} {city} — قیمت هر متر و وضعیت {tx_label}'

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
    deposit = pa.get('deposit') or {}
    rent = pa.get('rent') or {}
    full_dep = pa.get('full_deposit') or {}
    segments = report.get('area_segments') or []
    amenities = report.get('amenities_coverage') or {}
    amenity_val = report.get('amenity_valuation') or {}
    district_access = report.get('district_access') or {}
    opportunities = report.get('opportunities') or {}
    negotiation = report.get('negotiation') or {}
    insights = report.get('insights') or []
    prof = report.get('professional_summary') or {}

    valid_n = int(dq.get('valid_count') or scope.get('analyzed_count') or 0)
    raw_n = int(dq.get('raw_count') or valid_n)
    removed = int(dq.get('removed_count') or max(0, raw_n - valid_n))
    conf_score = conf.get('display_score') or conf.get('score') or '—'
    conf_level = conf.get('level_plain') or conf.get('level') or '—'
    pps_med = pps.get('median_fmt') or '—'
    price_med = price.get('median_fmt') or '—'
    deposit_med = deposit.get('median_fmt') or '—'
    rent_med = rent.get('median_fmt') or '—'
    full_med = full_dep.get('median_fmt') or '—'
    primary = _primary_metric(is_rent, pps=pps, price=price, deposit=deposit, rent=rent, full_dep=full_dep)
    date_from = scope.get('date_from_fmt') or '—'
    date_to = scope.get('date_to_fmt') or '—'
    under_pct = depth.get('under_pct')
    trend_fmt = trends.get('pps_monthly_fmt') or _fmt_trend(trends)
    sentiment_label = sentiment.get('label') or 'نامشخص'
    liq_label = liquidity.get('label') or '—'
    top_seg = _top_segment_name(segments)

    if is_rent:
        excerpt = (
            f'در {district} {city}، بر اساس {valid_n} فایل معتبر {subcat}، '
            f'رهن معمول {deposit_med}، اجاره معمول {rent_med} و معادل رهن کامل حدود {full_med} است. '
            f'وضعیت بازار: {sentiment_label}. '
            f'این گزارش برای مستأجر، موجر، مشاور، سازنده و سرمایه‌گذار نوشته شده است.'
        )[:300]
    else:
        excerpt = (
            f'در {district} {city}، بر اساس {valid_n} فایل معتبر {subcat}، '
            f'قیمت معمول هر متر حدود {pps_med} است. '
            f'وضعیت بازار: {sentiment_label}. '
            f'این گزارش برای خریدار، فروشنده، مشاور، سازنده و سرمایه‌گذار نوشته شده است.'
        )[:300]

    faq = _build_faq(
        city=city, district=district, subcat=subcat, tx_label=tx_label,
        pps_med=pps_med, price_med=price_med, valid_n=valid_n,
        date_from=date_from, date_to=date_to, segments=segments,
        negotiation=negotiation, sentiment_label=sentiment_label,
        under_pct=under_pct, is_rent=is_rent, deposit=deposit, rent=rent,
        full_dep=full_dep, top_seg=top_seg, primary=primary,
    )

    maps = map_assets or {}
    if map_image_url and 'featured' not in maps:
        maps = {**maps, 'featured': map_image_url}

    parts = [
        _section_who_this_is_for(city, district, subcat, tx_label),
        _section_intro(
            city, district, subcat, tx_label, valid_n, date_from, date_to,
            primary, trend_fmt, sentiment_label, conf_score, conf_level,
            prof, is_rent, deposit, rent, full_dep, pps_med, price_med,
        ),
        _section_kpi_cards(
            primary, valid_n, under_pct, trend_fmt, liq_label,
            conf_score, top_seg, is_rent, deposit, rent, full_dep, price_med,
        ),
        _section_plain_status(
            sentiment, liquidity, depth, insights, primary, conf_level, city, district, is_rent,
        ),
        _section_audiences(
            city, district, sentiment_label, under_pct, primary, negotiation,
            trend_fmt, liq_label, is_rent, top_seg,
        ),
        render_convert_band(
            city=city, district=district,
            audience='مشاور، سازنده یا سرمایه‌گذار',
            anchor='convert-mid',
        ),
        _section_pps(primary, depth, is_rent, deposit, rent, full_dep, pps),
        _section_segments(segments, primary, is_rent),
        _section_amenities(amenities, amenity_val),
        _section_district_access(district_access, city=city, district=district),
        render_convert_band(
            city=city, district=district,
            audience='مالک، مشاور یا کسی که می‌خواهد منطقه خودش را آنالیز کند',
            anchor='convert-access',
        ),
        _section_trends(trends, sentiment_label, under_pct, is_rent),
        _section_charts(
            maps, city, district, is_rent,
            subcat=subcat, tx_label=tx_label, primary=primary,
        ),
        _section_maps(
            maps, map_caption, city, district, is_rent,
            subcat=subcat, tx_label=tx_label, primary=primary, valid_n=valid_n,
        ),
        render_convert_band(
            city=city, district=district,
            audience='کسی که می‌خواهد همین نقشه‌ها را برای محله خودش بسازد',
            anchor='convert-maps',
        ),
        _section_opportunities(opportunities, under_pct, top_seg, is_rent),
        _section_negotiation(negotiation, primary, is_rent),
        _section_verdict(
            city, district, sentiment_label, opportunities, conf_level, insights, under_pct,
        ),
        _section_methodology(
            valid_n, removed, raw_n, date_from, date_to, conf_score, conf_level, dq, is_rent,
        ),
        _section_faq(faq),
        _section_related_links(
            city=city, district=district, subcat=subcat, tx_label=tx_label, is_rent=is_rent,
            related_posts=related_posts or [],
        ),
        _section_cta(city=city, district=district, tx_label=tx_label),
    ]

    return {
        'title': title,
        'excerpt': excerpt,
        'content_html': '\n'.join(p for p in parts if p),
        'faq': faq,
        'tags': _tags(city, district, tx_label, subcat),
    }


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else '—'))


def _primary_metric(is_rent: bool, *, pps, price, deposit, rent, full_dep) -> dict[str, Any]:
    """متریک اصلی نمایش برای فروش (قیمت هر متر) یا اجاره (رهن کامل)."""
    if is_rent:
        anchor = full_dep if full_dep.get('median_fmt') else (deposit if deposit.get('median_fmt') else rent)
        return {
            'is_rent': True,
            'label': 'معادل رهن کامل معمول',
            'short_label': 'رهن کامل',
            'fmt': full_dep.get('median_fmt') or deposit.get('median_fmt') or rent.get('median_fmt') or '—',
            'p25_fmt': anchor.get('p25_fmt') or full_dep.get('p25_fmt') or deposit.get('p25_fmt') or '—',
            'p75_fmt': anchor.get('p75_fmt') or full_dep.get('p75_fmt') or deposit.get('p75_fmt') or '—',
            'range_50_fmt': anchor.get('range_50_fmt') or full_dep.get('range_50_fmt') or '—',
            'range_80_fmt': anchor.get('range_80_fmt') or full_dep.get('range_80_fmt') or '—',
            'cv': full_dep.get('cv') or deposit.get('cv') or rent.get('cv'),
            'deposit_fmt': deposit.get('median_fmt') or '—',
            'rent_fmt': rent.get('median_fmt') or '—',
            'full_fmt': full_dep.get('median_fmt') or '—',
            'compare_hint': 'رهن کامل / رهن+اجاره',
        }
    return {
        'is_rent': False,
        'label': 'قیمت میانه هر متر',
        'short_label': 'قیمت هر متر',
        'fmt': pps.get('median_fmt') or '—',
        'p25_fmt': pps.get('p25_fmt') or pps.get('low_fmt') or '—',
        'p75_fmt': pps.get('p75_fmt') or pps.get('high_fmt') or '—',
        'range_50_fmt': pps.get('range_50_fmt') or pps.get('iqr_fmt') or '—',
        'range_80_fmt': pps.get('range_80_fmt') or '—',
        'cv': pps.get('cv'),
        'price_fmt': price.get('median_fmt') or '—',
        'compare_hint': 'قیمت هر متر',
    }


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
        monthly = (trends.get('trends') or {}).get('monthly')
    if monthly is None:
        return 'داده روند کافی نیست'
    sign = '+' if monthly > 0 else ''
    return f'{sign}{monthly}٪ ماهانه'


def _top_segment_name(segments: list) -> str:
    if not segments:
        return '—'
    best = max(
        segments,
        key=lambda s: (
            float(s.get('share_pct') or s.get('pct') or 0),
            int(s.get('count') or 0),
        ),
    )
    return best.get('bucket_plain') or best.get('bucket') or '—'


def _section_who_this_is_for(city, district, subcat, tx_label) -> str:
    return f'''
<section class="mk-market-section mk-market-audience-nav" id="who">
  <h2>این گزارش برای چه کسانی نوشته شده؟</h2>
  <p>
    تحلیل بازار {_e(subcat)} در {_e(district)} {_e(city)} ({_e(tx_label)}) طوری نوشته شده
    که بدون اصطلاحات پیچیده، برای همه قابل‌استفاده باشد. این گزارش بخشی از مجموعه
    <a href="/real-estate-market-analysis/">تحلیل بازار املاک</a> در فایلینگ دیوار است
    و با همان منطق <a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت آگهی‌های دیوار</a> ساخته شده.
    اگر می‌خواهید <strong>محله خودتان</strong> را همین‌طور آنالیز کنید،
    با <a href="/accounts/register/">ثبت‌نام میزکار</a> شروع کنید و برای استخراج خودکار
    <a href="/products/divar-extraction-bot/">لایسنس ربات</a> را فعال کنید.
  </p>
  <div class="mk-market-audience-grid">
    <div><strong>خریدار / مستأجر</strong><span>بفهمید قیمت عادلانه چیست و کجا مذاکره کنید.</span></div>
    <div><strong>فروشنده / موجر</strong><span>قیمت‌گذاری واقع‌بینانه و زمان مناسب عرضه.</span></div>
    <div><strong>مشاور املاک</strong><span>عددهای آماده برای جلسه، گزارش به مالک و فیلتر فرصت.</span></div>
    <div><strong>سرمایه‌گذار</strong><span>عمق بازار، نقدشوندگی و فضای زیر‌قیمت.</span></div>
    <div><strong>سازنده / انبوه‌ساز</strong><span>متراژ پرتقاضا و سطح قیمت قابل دفاع.</span></div>
  </div>
</section>
'''


def _section_intro(
    city, district, subcat, tx_label, valid_n, date_from, date_to,
    primary, trend_fmt, sentiment_label, conf_score, conf_level,
    prof, is_rent, deposit, rent, full_dep, pps_med, price_med,
) -> str:
    if isinstance(prof, dict) and (prof.get('intro') or '').strip():
        intro_html = f'<p>{_e(prof["intro"].strip())}</p>'
    else:
        intro_html = (
            f'<p>در این گزارش، بازار {_e(tx_label)} {_e(subcat)} در محله {_e(district)} شهر {_e(city)} '
            f'با زبان ساده و اعداد واقعی بررسی شده است. هدف این است که قبل از معامله یا قیمت‌گذاری، '
            f'تصویر روشنی از «عرف بازار» داشته باشید.</p>'
        )

    quality_note = ''
    if isinstance(prof, dict) and prof.get('quality_note'):
        quality_note = f'<p class="mk-market-note">{_e(prof["quality_note"])}</p>'

    if is_rent:
        metric_lis = f'''
    <li>{_e(primary["label"])}: <strong>{_e(primary["fmt"])}</strong></li>
    <li>رهن معمول: <strong>{_e(deposit.get("median_fmt") or "—")}</strong></li>
    <li>اجاره معمول: <strong>{_e(rent.get("median_fmt") or "—")}</strong></li>
'''
    else:
        metric_lis = f'''
    <li>قیمت معمول هر متر: <strong>{_e(pps_med)}</strong></li>
    <li>قیمت معمول کل واحد: <strong>{_e(price_med)}</strong></li>
'''

    return f'''
<section class="mk-market-section" id="executive-summary">
  <h2>خلاصه اجرایی؛ بازار {_e(district)} در یک نگاه</h2>
  {intro_html}
  <ul class="mk-market-bullets">
    <li>تعداد فایل‌های معتبر بررسی‌شده: <strong>{_e(valid_n)}</strong></li>
    <li>بازه زمانی داده‌ها: از <strong>{_e(date_from)}</strong> تا <strong>{_e(date_to)}</strong></li>
    {metric_lis}
    <li>روند قیمت: <strong>{_e(trend_fmt)}</strong></li>
    <li>وضعیت کلی بازار: <strong>{_e(sentiment_label)}</strong></li>
    <li>میزان اعتماد به این تحلیل: <strong>{_e(conf_score)}</strong> ({_e(conf_level)})</li>
  </ul>
  {quality_note}
  <p class="mk-market-tip">
    <strong>به زبان خیلی ساده:</strong>
    میانه یعنی «وسط بازار»؛ نصف فایل‌ها ارزان‌تر و نصف دیگر گران‌تر از این عدد هستند.
    این معیار از میانگین در برابر آگهی‌های غیرعادی مقاوم‌تر است.
  </p>
</section>
'''


def _section_kpi_cards(
    primary, valid_n, under_pct, trend_fmt, liq_label,
    conf_score, top_seg, is_rent, deposit, rent, full_dep, price_med,
) -> str:
    under = f'{under_pct}٪' if under_pct is not None else '—'
    if is_rent:
        cards = [
            (primary['label'], primary['fmt']),
            ('رهن معمول', deposit.get('median_fmt') or '—'),
            ('اجاره معمول', rent.get('median_fmt') or '—'),
            ('فایل معتبر', valid_n),
            ('زیر بازار', under),
            ('روند قیمت', trend_fmt),
            ('نقدشوندگی', liq_label),
            ('اعتماد تحلیل', conf_score),
        ]
    else:
        cards = [
            (primary['label'], primary['fmt']),
            ('قیمت معمول کل', price_med),
            ('فایل معتبر', valid_n),
            ('زیر بازار', under),
            ('روند قیمت', trend_fmt),
            ('نقدشوندگی', liq_label),
            ('اعتماد تحلیل', conf_score),
            ('متراژ پرتقاضا', top_seg),
        ]

    items = ''.join(
        f'<div class="mk-market-kpi"><span class="mk-market-kpi__lbl">{_e(lbl)}</span>'
        f'<strong class="mk-market-kpi__val">{_e(val)}</strong></div>'
        for lbl, val in cards[:8]
    )
    return f'''
<section class="mk-market-section" id="market-kpis">
  <h2>شاخص‌های اصلی بازار</h2>
  <p>این کارت‌ها مهم‌ترین عددهایی هستند که قبل از تصمیم‌گیری باید ببینید.</p>
  <div class="mk-market-kpi-grid">{items}</div>
</section>
'''


def _section_plain_status(sentiment, liquidity, depth, insights, primary, conf_level, city, district, is_rent) -> str:
    lines = []
    if sentiment.get('label'):
        lines.append(
            f'الان بازار {_e(district)} در {_e(city)} در وضعیت «{_e(sentiment.get("label"))}» قرار دارد.'
        )
    for f in (sentiment.get('factors') or [])[:4]:
        lines.append(str(f))
    if liquidity.get('label'):
        lines.append(
            f'نقدشوندگی (سرعت جذب فایل مناسب): {_e(liquidity.get("label"))}'
            f' با امتیاز {_e(liquidity.get("score", "—"))}.'
        )
    if depth.get('under_pct') is not None:
        lines.append(
            f'از نظر قیمت‌گذاری، حدود {_e(depth.get("under_pct"))}٪ فایل‌ها زیر عرف بازار، '
            f'{_e(depth.get("fair_pct", "—"))}٪ در بازه معمول و '
            f'{_e(depth.get("over_pct", "—"))}٪ بالاتر از عرف هستند.'
        )
    if primary.get('cv') is not None:
        metric_name = 'رهن کامل' if is_rent else 'قیمت هر متر'
        lines.append(
            f'پراکندگی {_e(metric_name)} (شاخص CV برابر {_e(primary.get("cv"))}) نشان می‌دهد '
            f'چقدر فضای مذاکره و اختلاف قیمت در بازار وجود دارد.'
        )
    lines.append(f'سطح اعتماد به این تحلیل: {_e(conf_level)}.')
    for tip in (insights or [])[:4]:
        if isinstance(tip, str) and tip.strip():
            lines.append(tip.strip())
    lis = ''.join(f'<li>{_e(x)}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="market-status">
  <h2>وضعیت بازار به زبان ساده</h2>
  <ul class="mk-market-bullets">{lis}</ul>
</section>
'''


def _section_audiences(
    city, district, sentiment_label, under_pct, primary, negotiation,
    trend_fmt, liq_label, is_rent, top_seg,
) -> str:
    target = '—'
    if isinstance(negotiation, dict):
        target = negotiation.get('target_fmt') or negotiation.get('offer_range_fmt') or target
    if target == '—':
        target = primary.get('p25_fmt') or primary.get('fmt') or '—'
    med = primary.get('fmt') or '—'
    p75 = primary.get('p75_fmt') or '—'
    under = f'{under_pct}٪' if under_pct is not None else 'بخشی'
    hint = primary.get('compare_hint') or 'عرف بازار'

    buyer_title = 'اگر خریدار یا مستأجر هستید'
    seller_title = 'اگر فروشنده یا موجر هستید'
    if is_rent:
        buyer_body = (
            f'اول رهن و اجاره را با عرف محله مقایسه کنید: رهن معمول {_e(primary.get("deposit_fmt"))}، '
            f'اجاره معمول {_e(primary.get("rent_fmt"))} و {_e(hint)} حدود {_e(med)}. '
            f'حدود {_e(under)} فایل‌ها زیر عرف‌اند؛ این‌ها نقطه شروع مذاکره خوب‌اند، نه لزوماً بهترین انتخاب. '
            f'بازه پیشنهادی مذاکره حدود {_e(target)} است.'
        )
        seller_body = (
            f'اگر فایل‌تان خیلی بالاتر از {_e(p75)} (بر اساس {_e(hint)}) باشد، احتمال ماندگاری بیشتر و بازدید کمتر است. '
            f'قیمت نزدیک میانه ({_e(med)}) معمولاً جذب بهتری دارد. وضعیت بازار: {_e(sentiment_label)}.'
        )
        builder_metric = med
    else:
        buyer_body = (
            f'قیمت هر متر را با میانه {_e(med)} بسنجید. فایل‌های خیلی بالاتر از {_e(p75)} را '
            f'بااحتیاط بررسی کنید. حدود {_e(under)} بازار زیر عرف است؛ فرصت‌ها را با کیفیت ساخت و امکانات فیلتر کنید. '
            f'محدوده هدف مذاکره: حدود {_e(target)}.'
        )
        seller_body = (
            f'قیمت‌گذاری نزدیک میانه ({_e(med)}) معمولاً واقعی‌تر و قابل‌دفاع‌تر است. '
            f'بالاتر از {_e(p75)} نیاز به مزیت واضح (نوساز، امکانات، موقعیت) دارد. '
            f'روند فعلی: {_e(trend_fmt)}.'
        )
        builder_metric = med

    return f'''
<section class="mk-market-section" id="audiences">
  <h2>راهنمای کاربردی برای نقش‌های مختلف</h2>
  <div class="mk-market-role">
    <h3>{buyer_title}</h3>
    <p>{buyer_body}</p>
  </div>
  <div class="mk-market-role">
    <h3>{seller_title}</h3>
    <p>{seller_body}</p>
  </div>
  <div class="mk-market-role">
    <h3>اگر مشاور املاک هستید</h3>
    <p>
      از میانه {_e(med)} به‌عنوان لنگر جلسه با مالک استفاده کنید، فرصت‌های زیر بازار را جداگانه پیگیری کنید،
      و متراژ پرتراکم ({_e(top_seg)}) را در پیشنهاد به مشتری پررنگ کنید. نقدشوندگی فعلی: {_e(liq_label)}.
      برای تکرار همین گزارش روی محله‌های خودتان:
      <a href="/products/divar-extraction-bot/">لایسنس ربات</a> +
      <a href="/accounts/register/">میزکار</a>.
    </p>
  </div>
  <div class="mk-market-role">
    <h3>اگر سرمایه‌گذار هستید</h3>
    <p>
      به ترکیب «زیر بازار + نقدشوندگی + روند» نگاه کنید. وضعیت کلی {_e(sentiment_label)} است و روند {_e(trend_fmt)}.
      فایل ارزان بدون قابلیت فروش مجدد سریع، فرصت نیست.
      رصد مداوم محله‌ها را با <a href="/real-estate-market-analysis/">تحلیل بازار فایلینگ</a> روی Dataset خودتان انجام دهید.
    </p>
  </div>
  <div class="mk-market-role">
    <h3>اگر سازنده یا انبوه‌ساز هستید</h3>
    <p>
      پرتقاضاترین بازه متراژ در این داده «{_e(top_seg)}» است. سطح قیمت قابل دفاع نزدیک {_e(primary.get("short_label"))}
      ({_e(builder_metric)}) است؛ برای پروژه‌های لوکس باید فاصله قیمت با عرف محله را شفاف توضیح دهید.
      قبل از تصمیم پروژه، محله هدف را در
      <a href="/accounts/register/">میزکار</a> با داده زنده دیوار بسازید.
    </p>
  </div>
</section>
'''


def _section_pps(primary, depth, is_rent, deposit, rent, full_dep, pps) -> str:
    if is_rent:
        rows = [
            ('رهن میانه', deposit.get('median_fmt')),
            ('اجاره میانه', rent.get('median_fmt')),
            ('معادل رهن کامل', full_dep.get('median_fmt')),
            ('بازه معمول نیمی از فایل‌ها (رهن کامل)', primary.get('range_50_fmt')),
            ('بازه وسیع‌تر (اغلب بازار)', primary.get('range_80_fmt')),
            ('محدوده ارزان‌تر (حدود چارک پایین)', primary.get('p25_fmt')),
            ('محدوده گران‌تر (حدود چارک بالا)', primary.get('p75_fmt')),
        ]
        heading = 'تحلیل رهن، اجاره و معادل رهن کامل'
        lead = (
            'عدد اصلی مقایسه در بازار اجاره «معادل رهن کامل» است (رهن + ۳۰ برابر اجاره ماهانه)، '
            'چون ترکیب رهن/اجاره واحدها یکسان نیست. بازه‌ها از صدک‌های واقعی داده محاسبه شده‌اند.'
        )
    else:
        rows = [
            ('قیمت میانه هر متر', pps.get('median_fmt')),
            ('بازه معمول نیمی از فایل‌ها', pps.get('range_50_fmt') or pps.get('iqr_fmt')),
            ('بازه وسیع‌تر (اغلب بازار)', pps.get('range_80_fmt')),
            ('محدوده ارزان‌تر (حدود چارک پایین)', pps.get('p25_fmt') or pps.get('low_fmt')),
            ('محدوده گران‌تر (حدود چارک بالا)', pps.get('p75_fmt') or pps.get('high_fmt')),
        ]
        heading = 'تحلیل قیمت هر متر (و عرف معامله)'
        lead = (
            'عدد اصلی مقایسه آگهی‌ها «قیمت هر متر» است؛ چون متراژ واحدها یکسان نیست. '
            'بازه‌ها از صدک‌های واقعی داده محاسبه شده‌اند، نه حدس کارشناسی.'
        )
    body = ''.join(
        f'<tr><th>{_e(a)}</th><td>{_e(b or "—")}</td></tr>'
        for a, b in rows if a and b and b != '—'
    )
    if not body:
        body = ''.join(
            f'<tr><th>{_e(a)}</th><td>{_e(b or "—")}</td></tr>' for a, b in rows if a
        )
    mix = ''
    if depth.get('under_pct') is not None:
        mix = (
            f'<p>ترکیب قیمت‌گذاری بازار: '
            f'<strong>{_e(depth.get("under_pct"))}٪</strong> زیر بازار، '
            f'<strong>{_e(depth.get("fair_pct", "—"))}٪</strong> معمول، '
            f'<strong>{_e(depth.get("over_pct", "—"))}٪</strong> بالای بازار.</p>'
        )
    return f'''
<section class="mk-market-section" id="price-per-sqm">
  <h2>{_e(heading)}</h2>
  <p>{_e(lead)}</p>
  <table class="mk-market-table"><tbody>{body}</tbody></table>
  {mix}
</section>
'''


def _section_segments(segments: list, primary: dict, is_rent: bool) -> str:
    if not segments:
        return ''
    rows = []
    for seg in segments[:8]:
        name = seg.get('bucket_plain') or seg.get('bucket') or '—'
        if is_rent:
            col_a = seg.get('median_deposit_fmt') or seg.get('median_rent_fmt') or '—'
            col_b = seg.get('median_full_deposit_fmt') or seg.get('median_deposit_fmt') or '—'
        else:
            col_a = (
                seg.get('median_pps_fmt')
                or seg.get('pps_median_fmt')
                or seg.get('price_per_sqm_fmt')
                or '—'
            )
            col_b = (
                seg.get('median_price_fmt')
                or seg.get('price_median_fmt')
                or seg.get('price_fmt')
                or '—'
            )
        rows.append(
            '<tr>'
            f'<td>{_e(name)}</td>'
            f'<td>{_e(seg.get("count", "—"))}</td>'
            f'<td>{_e(seg.get("share_pct", seg.get("pct", "—")))}</td>'
            f'<td>{_e(seg.get("median_area_fmt", seg.get("area_median_fmt", "—")))}</td>'
            f'<td>{_e(col_a)}</td>'
            f'<td>{_e(col_b)}</td>'
            '</tr>'
        )
    tip = (
        'اگر خریدارید، از بازه پرتقاضا شروع کنید چون انتخاب و مقایسه آسان‌تر است. '
        'اگر سازنده‌اید، همین بازه معمولاً نقدشوندگی بهتری دارد.'
    )
    head_a = 'رهن/اجاره معمول' if is_rent else 'قیمت هر متر'
    head_b = 'رهن کامل معمول' if is_rent else 'قیمت کل معمول'
    return f'''
<section class="mk-market-section" id="area-segments">
  <h2>تحلیل متراژ؛ کدام سایز بیشتر عرضه شده؟</h2>
  <p>مقایسه بازه‌های متراژ نسبت به {_e(primary.get("short_label"))} بازار ({_e(primary.get("fmt"))}).</p>
  <table class="mk-market-table">
    <thead><tr>
      <th>بازه متراژ</th><th>تعداد</th><th>سهم</th><th>متراژ معمول</th><th>{_e(head_a)}</th><th>{_e(head_b)}</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="mk-market-tip">{_e(tip)}</p>
</section>
'''


def _section_amenities(amenities: Any, amenity_val: Any) -> str:
    items: list[str] = []
    if isinstance(amenities, dict):
        for key, val in list(amenities.items())[:12]:
            if isinstance(val, dict):
                pct = val.get('pct') or val.get('coverage_pct') or val.get('share')
                items.append(f'{key}: {_e(pct)}٪ پوشش در فایل‌ها')
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
    lis = ''.join(f'<li>{x}</li>' for x in items)
    prem = ''.join(f'<li>{x}</li>' for x in premium_lines)
    prem_block = (
        f'<h3>اثر تقریبی امکانات روی قیمت</h3><ul class="mk-market-bullets">{prem}</ul>'
        if prem else ''
    )
    return f'''
<section class="mk-market-section" id="amenities">
  <h2>امکانات؛ چه چیزی در این بازار رایج است؟</h2>
  <p>پوشش امکانات نشان می‌دهد نبود یک ویژگی چقدر غیرعادی است و در مذاکره باید لحاظ شود.</p>
  <ul class="mk-market-bullets">{lis}</ul>
  {prem_block}
</section>
'''


def _section_district_access(access: Any, *, city: str, district: str) -> str:
    from blog.services.market_article_access_html import render_district_access_section
    return render_district_access_section(access, city=city, district=district)



def _section_trends(trends: dict, sentiment_label: str, under_pct, is_rent: bool) -> str:
    if not trends or not trends.get('has_data'):
        return '''
<section class="mk-market-section" id="trends">
  <h2>روند بازار</h2>
  <p>در این دیتاست، داده زمانی کافی برای محاسبه روند قابل اتکا وجود نداشت. عددهای قیمت لحظه‌ای همچنان معتبرند.</p>
</section>
'''
    tmap = trends.get('trends') or {}
    lines = [f'خوانش کلی مرتبط با روند: {_e(sentiment_label)}.']
    metric_word = 'رهن کامل' if is_rent else 'قیمت هر متر'
    if trends.get('pps_monthly_fmt'):
        lines.append(f'تغییر ماهانه {_e(metric_word)}: {_e(trends["pps_monthly_fmt"])}.')
    for key, label in (('weekly', 'هفتگی'), ('monthly', 'ماهانه'), ('quarterly', 'فصلی'), ('yearly', 'سالانه')):
        if key in tmap:
            lines.append(f'تغییر {_e(label)}: {_e(tmap[key])}٪.')
    if under_pct is not None:
        lines.append(f'هم‌زمان حدود {_e(under_pct)}٪ فایل‌ها زیر عرف قیمت هستند.')
    lis = ''.join(f'<li>{x}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="trends">
  <h2>روند بازار؛ قیمت به کدام سمت می‌رود؟</h2>
  <ul class="mk-market-bullets">{lis}</ul>
  <p class="mk-market-tip">
    روند مثبت معمولاً قدرت فروشنده/موجر را بیشتر می‌کند؛ روند منفی فضای چانه‌زنی مستأجر/خریدار را بازتر می‌کند.
    روند، پیش‌بینی قطعی آینده نیست — تصویر حرکت اخیر قیمت است.
  </p>
</section>
'''


def _section_charts(
    assets: dict[str, str],
    city: str,
    district: str,
    is_rent: bool = False,
    *,
    subcat: str = 'ملک',
    tx_label: str = 'معامله',
    primary: dict | None = None,
) -> str:
    charts = {
        k: v for k, v in (assets or {}).items()
        if isinstance(k, str) and k.startswith('chart_') and isinstance(v, str) and v
    }
    return render_charts_section(
        charts,
        city=city, district=district, is_rent=is_rent,
        subcat=subcat, tx_label=tx_label, primary=primary,
    )


def _section_maps(
    maps: dict[str, str],
    caption: str,
    city: str,
    district: str,
    is_rent: bool = False,
    *,
    subcat: str = 'ملک',
    tx_label: str = 'معامله',
    primary: dict | None = None,
    valid_n: int = 0,
) -> str:
    return render_maps_section(
        maps, caption, city, district, is_rent,
        subcat=subcat, tx_label=tx_label, primary=primary, valid_n=valid_n,
    )


def _section_opportunities(opportunities: Any, under_pct, top_seg, is_rent: bool = False) -> str:
    lines = []
    if under_pct is not None:
        lines.append(f'حدود {_e(under_pct)}٪ فایل‌ها زیر قیمت عرف بازار شناسایی شده‌اند.')
    data = opportunities
    if isinstance(opportunities, dict):
        if opportunities.get('count') is not None:
            lines.append(f'تعداد فرصت‌های رتبه‌بندی‌شده در مدل: {_e(opportunities.get("count"))}.')
        if opportunities.get('summary'):
            lines.append(str(opportunities['summary']))
        data = opportunities.get('items') or opportunities.get('deals') or []
    if isinstance(data, list):
        for item in data[:6]:
            if not isinstance(item, dict):
                continue
            area = item.get('area_fmt') or item.get('area_bucket') or item.get('bucket')
            if is_rent:
                value = (
                    item.get('full_deposit_fmt')
                    or item.get('rent_equiv_fmt')
                    or item.get('deposit_fmt')
                    or item.get('price_fmt')
                )
            else:
                value = item.get('pps_fmt') or item.get('price_per_sqm_fmt') or item.get('price_fmt')
            gap = item.get('gap_pct') or item.get('discount_pct')
            bits = [x for x in (area, value, f'شکاف {_e(gap)}٪' if gap is not None else '') if x]
            if bits:
                lines.append(' · '.join(str(b) for b in bits))
    if top_seg and top_seg != '—':
        lines.append(f'بازه متراژ پرتکرار فرصت‌ها معمولاً نزدیک «{_e(top_seg)}» دیده می‌شود.')
    if not lines:
        return ''
    lis = ''.join(f'<li>{_e(x)}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="opportunities">
  <h2>فرصت‌های بازار (بدون افشای فایل مشخص)</h2>
  <ul class="mk-market-bullets">{lis}</ul>
  <p class="mk-market-tip">
    قیمت پایین به‌تنهایی فرصت نیست. کیفیت ساخت، امکانات، زمان ماندگاری روی بازار و قابلیت فروش مجدد را همراه عدد ببینید.
  </p>
</section>
'''


def _section_negotiation(negotiation: Any, primary: dict, is_rent: bool) -> str:
    lines = []
    if isinstance(negotiation, dict):
        mapping = (
            ('target_fmt', 'قیمت/رهن هدف'),
            ('line_fmt', 'خط مذاکره'),
            ('offer_range_fmt', 'محدوده پیشنهاد منطقی'),
            ('reject_above_fmt', 'بالای این سطح را بااحتیاط بررسی کنید'),
            ('note', 'توضیح'),
            ('summary', 'جمع‌بندی مذاکره'),
        )
        for key, label in mapping:
            if negotiation.get(key):
                lines.append(f'{label}: {_e(negotiation[key])}')
        if isinstance(negotiation.get('items'), list):
            for item in negotiation['items'][:6]:
                if isinstance(item, str):
                    lines.append(_e(item))
                elif isinstance(item, dict) and item.get('text'):
                    lines.append(_e(item['text']))
    if not lines and primary:
        label = primary.get('short_label') or 'عرف'
        if primary.get('p25_fmt') and primary['p25_fmt'] != '—':
            lines.append(f'محدوده مناسب پیشنهاد (نزدیک چارک پایین {_e(label)}): {_e(primary["p25_fmt"])}')
        if primary.get('fmt') and primary['fmt'] != '—':
            lines.append(f'خط میانه بازار ({_e(label)}): {_e(primary["fmt"])}')
        if primary.get('p75_fmt') and primary['p75_fmt'] != '—':
            lines.append(f'بالای این سطح معمولاً نیاز به دلیل قوی دارد: {_e(primary["p75_fmt"])}')
    if not lines:
        return ''
    lis = ''.join(f'<li>{x}</li>' for x in lines)
    return f'''
<section class="mk-market-section" id="negotiation">
  <h2>راهبرد مذاکره با عدد واقعی</h2>
  <ul class="mk-market-bullets">{lis}</ul>
  <p>این آستانه‌ها از توزیع واقعی قیمت در همین دیتاست استخراج شده‌اند و جایگزین بازدید حضوری نیستند.</p>
</section>
'''


def _section_verdict(city, district, sentiment_label, opportunities, conf_level, insights, under_pct) -> str:
    opp_note = (
        f'وجود فایل‌های زیر عرف (حدود {under_pct}٪) فرصت جستجو ایجاد می‌کند.'
        if under_pct else 'فرصت برجسته تجمیعی ثبت نشده است.'
    )
    if opportunities:
        opp_note = 'مدل فرصت، تعدادی فایل زیر بازار را رتبه‌بندی کرده است؛ جزئیات شناسایی‌پذیر منتشر نمی‌شود.'
    tip = next((i for i in (insights or []) if isinstance(i, str) and i.strip()), '')
    tip_html = f' {_e(tip)}' if tip else ''
    return f'''
<section class="mk-market-section" id="verdict">
  <h2>جمع‌بندی کارشناسی</h2>
  <p>بازار {_e(district)} در {_e(city)} هم‌اکنون «{_e(sentiment_label)}» ارزیابی می‌شود.</p>
  <ul class="mk-market-bullets">
    <li><strong>مهم‌ترین فرصت:</strong> {_e(opp_note)}</li>
    <li><strong>مهم‌ترین ریسک:</strong> اعتماد تحلیل در سطح «{_e(conf_level)}» است؛ تصمیم نهایی با بازدید و صحت‌سنجی فایل انجام شود.</li>
    <li><strong>کاربرد:</strong> این گزارش مبنای قیمت‌گذاری، فیلتر فرصت و مذاکره برای خریدار، فروشنده، مشاور، سازنده و سرمایه‌گذار است.{tip_html}</li>
  </ul>
</section>
'''


def _section_methodology(valid_n, removed, raw_n, date_from, date_to, conf_score, conf_level, dq, is_rent=False) -> str:
    center = 'میانه رهن کامل / رهن+اجاره' if is_rent else 'میانه قیمت هر متر'
    under_rule = 'نسبت رهن کامل به میانه و عمق قیمت' if is_rent else 'نسبت قیمت هر متر به میانه و عمق قیمت'
    return f'''
<section class="mk-market-section" id="methodology">
  <h2>روش‌شناسی و کیفیت داده</h2>
  <ul class="mk-market-bullets">
    <li>تعداد فایل خام: {_e(raw_n)}</li>
    <li>تعداد فایل معتبر پس از پالایش پرت‌ها: {_e(valid_n)}</li>
    <li>فایل‌های حذف‌شده/غیرعادی: {_e(removed)}</li>
    <li>بازه زمانی پوشش داده: از {_e(date_from)} تا {_e(date_to)}</li>
    <li>شاخص مرکزی: {_e(center)} (مقاوم‌تر از میانگین در برابر آگهی غیرعادی)</li>
    <li>تشخیص زیر بازار: {_e(under_rule)}</li>
    <li>امتیاز اعتماد: {_e(conf_score)} ({_e(conf_level)})</li>
    <li>کیفیت داده: {_e(dq.get("quality_pct", "—"))}٪</li>
  </ul>
  <p>
    محدودیت مهم: این تحلیل بر اساس آگهی‌های موجود است، نه معاملات قطعی ثبت‌شده.
    ممکن است بخشی از بازار در داده نباشد. گزارش جایگزین کارشناسی میدانی نیست.
    برای اجرای همین روش روی فایل‌های خود،
    <a href="/real-estate-market-analysis/">تحلیل بازار املاک</a> و
    <a href="/blog/tahlil-gheymat-amlak-divar/">راهنمای تحلیل قیمت دیوار</a> را ببینید.
  </p>
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
    sentiment_label = kwargs['sentiment_label']
    under_pct = kwargs['under_pct']
    top_seg = kwargs['top_seg']
    negotiation = kwargs['negotiation']
    is_rent = kwargs['is_rent']
    primary = kwargs.get('primary') or {}
    deposit = kwargs.get('deposit') or {}
    rent = kwargs.get('rent') or {}
    full_dep = kwargs.get('full_dep') or {}

    anchor = primary.get('fmt') or pps_med
    target = '—'
    if isinstance(negotiation, dict):
        target = negotiation.get('target_fmt') or negotiation.get('offer_range_fmt') or '—'
    if target == '—':
        target = primary.get('p25_fmt') or anchor

    if is_rent:
        price_q = f'رهن و اجاره معمول {subcat} در {district} {city} چقدر است؟'
        price_a = (
            f'بر اساس این تحلیل، رهن معمول حدود {deposit.get("median_fmt") or "—"}، '
            f'اجاره معمول حدود {rent.get("median_fmt") or "—"} و معادل رهن کامل حدود '
            f'{full_dep.get("median_fmt") or anchor} است.'
        )
        defend = primary.get('fmt') or full_dep.get('median_fmt') or '—'
    else:
        price_q = f'قیمت هر متر {subcat} در {district} {city} چقدر است؟'
        price_a = (
            f'بر اساس این تحلیل، قیمت معمول هر متر حدود {pps_med} است'
            f' و قیمت معمول کل نزدیک {kwargs.get("price_med") or "—"} گزارش شده.'
        )
        defend = pps_med

    return [
        {'q': price_q, 'a': price_a},
        {'q': 'کدام متراژ بیشتر در بازار دیده می‌شود؟', 'a': f'پرتراکم‌ترین بازه در داده فعلی «{top_seg}» است.'},
        {
            'q': 'برای خرید یا اجاره چه عددی منطقی است؟',
            'a': f'با توجه به میانه و آستانه‌های مذاکره، محدوده هدف حدود {target} است؛ بازدید و مقایسه ضروری است.',
        },
        {
            'q': 'آیا الان بازار به نفع خریدار است یا فروشنده؟',
            'a': f'وضعیت فعلی: {sentiment_label}'
                 + (f' و حدود {under_pct}٪ فایل‌ها زیر عرف‌اند.' if under_pct is not None else '.'),
        },
        {'q': 'این تحلیل چند فایل را بررسی کرده؟', 'a': f'{valid_n} فایل معتبر پس از پالایش داده.'},
        {'q': 'داده‌ها مربوط به چه بازه‌ای هستند؟', 'a': f'از {date_from} تا {date_to}.'},
        {
            'q': 'سازنده یا سرمایه‌گذار از این گزارش چه استفاده‌ای می‌کند؟',
            'a': f'متراژ پرتقاضا ({top_seg})، سطح قیمت قابل دفاع ({defend}) و وضعیت نقدشوندگی برای تصمیم ساخت یا ورود سرمایه.',
        },
    ]


def _section_faq(faq: list[dict[str, str]]) -> str:
    blocks = [f'<h3>{_e(item["q"])}</h3><p>{_e(item["a"])}</p>' for item in faq]
    return f'''
<section class="blog-faq mk-market-section" id="faq">
  <h2>سوالات متداول</h2>
  {''.join(blocks)}
</section>
'''


def _section_related_links(
    *,
    city: str,
    district: str,
    subcat: str,
    tx_label: str,
    is_rent: bool,
    related_posts: list[dict[str, str]],
) -> str:
    return render_related_links_section(
        city=city, district=district, subcat=subcat, tx_label=tx_label,
        is_rent=is_rent, related_posts=related_posts,
    )


def _section_cta(*, city: str = '', district: str = '', tx_label: str = '') -> str:
    return render_cta_section(city=city, district=district, tx_label=tx_label)


def _tags(city: str, district: str, tx_label: str, subcat: str) -> list[str]:
    tags = [
        f'تحلیل بازار {city}',
        f'قیمت {subcat} {district}',
        district,
        city,
        tx_label,
        subcat,
        'قیمت مسکن',
        'نقشه بازار املاک',
    ]
    return [t.strip()[:100] for t in tags if t and str(t).strip()]
