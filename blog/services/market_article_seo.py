"""توضیحات SEO نقشه‌ها و لینک‌سازی داخلی مقالات سیستماتیک."""
from __future__ import annotations

import html
from typing import Any


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else '—'))


def map_specs(
    *,
    city: str,
    district: str,
    subcat: str,
    tx_label: str,
    is_rent: bool,
    primary: dict | None,
    valid_n: int,
) -> list[dict[str, str]]:
    place = f'{district} {city}'
    metric = (primary or {}).get('short_label') or ('رهن کامل' if is_rent else 'قیمت هر متر')
    metric_fmt = (primary or {}).get('fmt') or '—'
    value_label = 'سطح رهن کامل' if is_rent else 'سطح قیمت هر متر'
    deal_word = 'اجاره' if is_rent else 'خرید و فروش'
    n_txt = str(valid_n) if valid_n else 'چند صد'

    def _heat(key: str, basemap: str, basemap_fa: str) -> dict[str, str]:
        return {
            'key': key,
            'h3': f'هیت‌مپ تراکم روی نقشه {basemap_fa}؛ {district}',
            'alt': (
                f'هیت‌مپ تراکم فایل‌های {tx_label} {subcat} در {district} {city} '
                f'روی نقشه {basemap_fa}'
            ),
            'lead': (
                f'زرد = عرضه کمتر، قرمز = کانون پرتراکم؛ بستر {basemap_fa} برای خوانش سریع تراکم.'
            ),
            'body': (
                f'در بازار {deal_word} {place}، تراکم یعنی کجا سریع‌تر چند گزینه هم‌سطح می‌بینید. '
                f'نقشه {basemap_fa} کمک می‌کند کانون‌ها را روی بافت واقعی محله ببینید. '
                f'نمایش تجمیعی است و موقعیت تک‌آگهی افشا نمی‌شود.'
            ),
            'uses': (
                f'کاربرد: محدود کردن محدوده جستجو و اولویت‌بندی محله‌گردی با '
                f'<a href="/robot-divar/">ربات استخراج دیوار</a>.'
            ),
        }

    def _value(key: str, basemap_fa: str) -> dict[str, str]:
        return {
            'key': key,
            'h3': f'{value_label} روی نقشه {basemap_fa}؛ {place}',
            'alt': (
                f'نقشه {value_label} {subcat} در {district} {city} روی بستر {basemap_fa}؛ '
                f'میانه {metric_fmt}'
            ),
            'lead': (
                f'آبی‌تر = {metric} پایین‌تر، قرمزتر = بالاتر. میانه بازار: {metric_fmt}.'
            ),
            'body': (
                f'این لایه می‌گوید کجای {district} نسبت به عرف گران‌تر/ارزان‌تر است. '
                f'مرجع: {_e(metric)} ({_e(metric_fmt)}). با بخش فرصت‌ها و '
                f'<a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">Value Score</a> '
                f'کنار هم بخوانید.'
            ),
            'uses': (
                f'کاربرد: قیمت‌گذاری نزدیک عرف و توضیح تفاوت خیابان‌به‌خیابان — '
                f'<a href="/blog/gheymat-gozari-melk-agahi-divar/">قیمت‌گذاری با داده دیوار</a>.'
            ),
        }

    def _grid(key: str, basemap_fa: str) -> dict[str, str]:
        return {
            'key': key,
            'h3': f'شبکه کمی تراکم روی نقشه {basemap_fa}؛ {district}',
            'alt': f'شبکه کمی تعداد فایل {subcat} در {district} {city} روی نقشه {basemap_fa}',
            'lead': 'عدد روی خانه‌های گرم = تعداد فایل تجمیعی در همان سلول.',
            'body': (
                f'برای کسانی که «چند فایل» می‌خواهند نه فقط رنگ. خانه‌های پررنگ با عدد بالاتر '
                f'نمونه آماری قوی‌تری دارند (از حدود {_e(n_txt)} فایل معتبر).'
            ),
            'uses': 'کاربرد: سنجش عمق محلی عرضه قبل از تعریف محدوده پروژه یا سرمایه.',
        }

    def _hotspots(key: str, basemap_fa: str) -> dict[str, str]:
        return {
            'key': key,
            'h3': f'کانون‌های پرتراکم روی نقشه {basemap_fa}؛ {place}',
            'alt': f'رتبه کانون‌های پرتراکم {subcat} در {district} {city} روی نقشه {basemap_fa}',
            'lead': '۳ تا ۵ کانون با رتبه تراکم؛ عدد کنار رتبه ≈ حجم فایل همان سلول.',
            'body': (
                f'رتبه ۱ پرتراکم‌ترین سلول در داده فعلی {place} است — لزوماً بهترین معامله نیست، '
                f'ولی جایی است که مقایسه گزینه‌ها سریع‌تر پیش می‌رود.'
            ),
            'uses': (
                f'کاربرد تیم فروش: تقسیم محله و فیلینگ هدفمند با '
                f'<a href="/real-estate-filing/">فایلینگ دیوار</a>.'
            ),
        }

    def _dots(key: str, basemap_fa: str) -> dict[str, str]:
        return {
            'key': key,
            'h3': f'پراکنش تجمیعی روی نقشه {basemap_fa}؛ {district}',
            'alt': f'نقاط تجمیعی عرضه {subcat} در {district} {city} روی نقشه {basemap_fa}',
            'lead': 'نقطه درشت‌تر = سلول پرتراکم‌تر؛ بدون پین تک‌آگهی.',
            'body': (
                f'نمای نقطه‌ای برای کسانی که پراکنش را بدون هیت‌مپ نرم ترجیح می‌دهند؛ '
                f'روی بستر {basemap_fa} پوشش جغرافیایی بانک فایل را سریع می‌بینید.'
            ),
            'uses': 'کاربرد: کنترل پوشش جغرافیایی و معرفی محدوده به مشتری غیربومی.',
        }

    specs = [
        {
            'key': 'featured',
            'h3': f'نقشه شاخص بازار {subcat} در {place}',
            'alt': (
                f'نقشه شاخص بازار {tx_label} {subcat} در محله {district} شهر {city}؛ '
                f'تحلیل مکانی فایلینگ دیوار'
            ),
            'lead': (
                f'نقطه شروع خوانش مکانی بازار {tx_label} در {place}؛ '
                f'سبک basemap در هر ساخت مقاله تصادفی انتخاب می‌شود.'
            ),
            'body': (
                f'این نقشه نمای کلی پراکنش تجمیعی آگهی‌های {subcat} در {place} است. '
                f'برای تکرار همین تحلیل روی فایل خودتان از '
                f'<a href="/real-estate-market-analysis/">تحلیل بازار املاک</a> استفاده کنید.'
            ),
            'uses': (
                f'کاربرد: جلسه با مالک و نقطه شروع '
                f'<a href="/blog/gozaresh-gheymat-malek-divar-dade-rahnama/">گزارش قیمت داده‌محور</a>.'
            ),
        },
        # کلیدهای جدید (تنوع basemap)
        _heat('map_sat_heat', 'satellite', 'ماهواره‌ای'),
        _value('map_sat_value', 'ماهواره‌ای'),
        _hotspots('map_sat_hotspots', 'ماهواره‌ای'),
        _grid('map_sat_grid', 'ماهواره‌ای'),
        _dots('map_sat_dots', 'ماهواره‌ای'),
        _heat('map_dark_heat', 'dark', 'تیره'),
        _value('map_dark_value', 'تیره'),
        _hotspots('map_dark_hotspots', 'تیره'),
        _dots('map_dark_dots', 'تیره'),
        _heat('map_light_heat', 'light', 'روشن'),
        _value('map_light_value', 'روشن'),
        _grid('map_light_grid', 'روشن'),
        _hotspots('map_light_hotspots', 'روشن'),
        _heat('map_street_heat', 'street', 'شهری'),
        _value('map_street_value', 'شهری'),
        _hotspots('map_street_hotspots', 'شهری'),
        _grid('map_street_grid', 'شهری'),
        _dots('map_street_dots', 'شهری'),
        # سازگاری با مقالات قدیمی
        _heat('street_heat', 'street', 'شهری'),
        _value('street_value', 'شهری'),
        _grid('street_grid', 'شهری'),
        _hotspots('street_hotspots', 'شهری'),
        _dots('street_dots', 'شهری'),
        _heat('satellite_heat', 'satellite', 'ماهواره‌ای'),
        _value('satellite_value', 'ماهواره‌ای'),
        {
            'key': 'satellite',
            'h3': f'نمای ماهواره‌ای منطقه {place}',
            'alt': f'تصویر ماهواره‌ای محله {district} {city} با لایه تراکم فایل‌های مسکن',
            'lead': 'بستر ماهواره‌ای با لایه تراکم تجمیعی برای جهت‌یابی سریع در محله.',
            'body': (
                f'این نما برای کسانی است که محله {district} را کمتر می‌شناسند و می‌خواهند '
                f'قبل از بازدید میدانی، بافت کلی و پراکنش عرضه را یک‌جا ببینند.'
            ),
            'uses': 'کاربرد عمومی: جهت‌یابی و معرفی محله به مشتری غیربومی.',
        },
        {
            'key': 'price',
            'h3': f'نقشه {value_label} در {place}',
            'alt': f'نقشه {value_label} بازار {tx_label} {subcat} در {district} {city}',
            'lead': f'رنگ گرم‌تر یعنی {value_label} بالاتر در شبکه تجمیعی.',
            'body': (
                f'لایه ارزش قیمتی/رهنی برای مقایسه مکانی عرف بازار {tx_label} در {place}. '
                f'میانه مرجع: {_e(metric_fmt)}.'
            ),
            'uses': 'کاربرد: کنترل سریع فایل‌های بالاتر از عرف قبل از بازدید.',
        },
    ]
    return specs


def chart_specs(
    *,
    city: str,
    district: str,
    subcat: str,
    tx_label: str,
    is_rent: bool,
    primary: dict | None,
) -> list[dict[str, str]]:
    place = f'{district} {city}'
    metric = (primary or {}).get('short_label') or ('رهن کامل' if is_rent else 'قیمت هر متر')
    ladder = 'رهن کامل' if is_rent else 'قیمت هر متر'
    return [
        {
            'key': 'chart_price_ladder',
            'h3': f'نردبان {ladder}؛ توزیع چارک و دهک در {place}',
            'alt': f'نمودار نردبان {ladder} بازار {tx_label} {subcat} در {district} {city}',
            'lead': f'از دهک پایین تا دهک بالا — تصویر فشرده از پهنه {metric}.',
            'body': (
                f'این نمودار نشان می‌دهد بازار {tx_label} در {place} چقدر فشرده یا کشیده است. '
                f'فاصله زیاد بین چارک‌ها یعنی ناهمگنی قیمتی؛ فاصله کم یعنی بازار یکدست‌تر.'
            ),
            'uses': 'کاربرد: توضیح بازه مذاکره به مالک/مشتری بدون جدول خام.',
        },
        {
            'key': 'chart_area_share',
            'h3': f'سهم بازه‌های متراژ در عرضه {district}',
            'alt': f'نمودار سهم متراژ فایل‌های {subcat} در {district} {city}',
            'lead': 'کدام باند متراژ بیشترین عمق عرضه را دارد؟',
            'body': (
                f'عمق عرضه در هر باند متراژ مشخص می‌کند کجا بانک فایل برای {tx_label} قوی‌تر است '
                f'و کجا کمبود گزینه دارید.'
            ),
            'uses': 'کاربرد سازنده/سرمایه‌گذار: انتخاب متراژ قابل‌فروش قبل از تعریف محصول.',
        },
        {
            'key': 'chart_market_depth',
            'h3': f'عمق بازار نسبت به عرف؛ {place}',
            'alt': f'نمودار دونات سهم فایل‌های زیر/نزدیک/بالای عرف در {district} {city}',
            'lead': 'سهم فایل‌های زیر عرف، نزدیک عرف و بالای عرف در یک نگاه.',
            'body': (
                'این دونات پاسخ می‌دهد بازار چقدر فرصت زیر‌عرف دارد و چقدر فایل بالاتر از بدنه بازار است.'
            ),
            'uses': (
                'کاربرد: فیلتر فرصت با '
                '<a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">Value Score</a>.'
            ),
        },
        {
            'key': 'chart_access',
            'h3': f'امکانات شهری اطراف {district} به‌تفکیک گروه',
            'alt': f'نمودار تعداد امکانات دسترسی محله {district} {city}',
            'lead': 'تعداد نقاط دسترسی (حمل‌ونقل، خدمات، آموزش و …) در شعاع تحلیل.',
            'body': (
                f'مقایسه گروهی امکانات اطراف {place} برای جلسه با مشتری و ارزیابی زیست‌پذیری محله.'
            ),
            'uses': 'کاربرد مشاور: روایت دسترسی در گزارش مالک بدون اعداد فاصله پیچیده.',
        },
        {
            'key': 'chart_amenities',
            'h3': f'پوشش امکانات داخل فایل‌های {subcat}',
            'alt': f'نمودار درصد پوشش امکانات آگهی‌های {subcat} در {district} {city}',
            'lead': 'درصد فایل‌هایی که هر امکان را دارند — نبود چه چیزی غیرعادی است؟',
            'body': (
                'پوشش امکانات نشان می‌دهد نبود یک ویژگی چقدر غیرمعمول است و در مذاکره باید لحاظ شود.'
            ),
            'uses': 'کاربرد: اولویت‌بندی فیلتر امکانات هنگام ساخت بانک فایل.',
        },
    ]


def render_maps_section(
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
    if not maps:
        return f'''
<section class="mk-market-section" id="spatial">
  <h2>نقشه و تحلیل مکانی بازار {_e(district)} {_e(city)}</h2>
  <p>مختصات کافی برای ساخت نقشه شهری/ماهواره‌ای در {_e(district)} {_e(city)} موجود نبود.</p>
</section>
'''
    blocks = []
    seen = set()
    for spec in map_specs(
        city=city, district=district, subcat=subcat, tx_label=tx_label,
        is_rent=is_rent, primary=primary, valid_n=valid_n,
    ):
        url = maps.get(spec['key'])
        if not url or url in seen:
            continue
        seen.add(url)
        blocks.append(f'''
  <figure class="mk-market-map" id="map-{_e(spec["key"])}">
    <div class="mk-market-map__head">
      <h3>{_e(spec["h3"])}</h3>
      <span class="mk-market-map__tag">{_e(district)} · {_e(city)}</span>
    </div>
    <img src="{_e(url)}" alt="{_e(spec["alt"])}" width="1600" height="960" loading="lazy"
         title="{_e(spec["h3"])}">
    <figcaption>
      <strong>{_e(spec["lead"])}</strong>
      <span class="mk-market-map__privacy">نمایش تجمیعی شبکه‌ای — موقعیت تک‌آگهی نشان داده نمی‌شود.</span>
    </figcaption>
    <div class="mk-market-map__body">
      <p>{spec["body"]}</p>
      <p class="mk-market-map__use">{spec["uses"]}</p>
    </div>
  </figure>
''')

    guide = f'''
  <div class="mk-market-map-guide">
    <strong>چطور نقشه‌های {_e(district)} را بخوانید:</strong>
    اول ماهواره/بافت فیزیکی، بعد تراکم (کجا فایل زیاد است)، سپس سطح ارزش،
    و در پایان کانون‌ها یا شبکه کمی برای اولویت بازدید. برای هر مقاله ترکیب basemap
    (ماهواره، تیره، روشن، شهری) و نوع لایه عوض می‌شود تا دید تکراری نباشد.
    همه لایه‌ها تجمیعی‌اند و موقعیت تک‌آگهی را نشان نمی‌دهند.
  </div>
'''
    intro = f'''
  <p>
    نقشه‌های زیر تحلیل مکانی بازار {_e(tx_label)} {_e(subcat)} در محله {_e(district)} شهر {_e(city)} هستند.
    هدف این بخش پاسخ به سه سؤال است: <em>عرضه کجاست؟</em>، <em>ارزش نسبی کجاست؟</em> و
    <em>بازدید را از کجا شروع کنیم؟</em>
    اگر به روش کار با نقشه حرفه‌ای علاقه دارید،
    <a href="/blog/?cat=tahlil-bazar">آرشیو تحلیل بازار</a> و صفحه
    <a href="/real-estate-market-analysis/">تحلیل بازار املاک</a> را هم ببینید.
  </p>
'''
    return f'''
<section class="mk-market-section" id="spatial">
  <h2>نقشه و تحلیل مکانی؛ بازار {_e(district)} {_e(city)}</h2>
  {intro}
  {guide}
  {''.join(blocks)}
</section>
'''


def render_charts_section(
    charts: dict[str, str],
    *,
    city: str,
    district: str,
    is_rent: bool = False,
    subcat: str = 'ملک',
    tx_label: str = 'معامله',
    primary: dict | None = None,
) -> str:
    if not charts:
        return ''
    blocks = []
    seen = set()
    for spec in chart_specs(
        city=city, district=district, subcat=subcat, tx_label=tx_label,
        is_rent=is_rent, primary=primary,
    ):
        url = charts.get(spec['key'])
        if not url or url in seen:
            continue
        seen.add(url)
        blocks.append(f'''
  <figure class="mk-market-chart" id="chart-{_e(spec["key"])}">
    <div class="mk-market-chart__head">
      <h3>{_e(spec["h3"])}</h3>
      <span class="mk-market-chart__tag">نمودار تحلیلی</span>
    </div>
    <img src="{_e(url)}" alt="{_e(spec["alt"])}" width="1400" height="780" loading="lazy"
         title="{_e(spec["h3"])}">
    <figcaption>
      <strong>{_e(spec["lead"])}</strong>
    </figcaption>
    <div class="mk-market-chart__body">
      <p>{spec["body"]}</p>
      <p class="mk-market-chart__use">{spec["uses"]}</p>
    </div>
  </figure>
''')
    if not blocks:
        return ''
    return f'''
<section class="mk-market-section" id="charts">
  <h2>نمودارهای تحلیلی بازار {_e(district)} {_e(city)}</h2>
  <p>
    نمودارهای زیر همان عددهای گزارش را به تصویر تبدیل می‌کنند تا توزیع قیمت، سهم متراژ،
    عمق نسبت به عرف و امکانات در یک نگاه خوانا باشد — مکمل نقشه‌های مکانی بخش بعد.
  </p>
  {''.join(blocks)}
</section>
'''


def render_related_links_section(
    *,
    city: str,
    district: str,
    subcat: str,
    tx_label: str,
    is_rent: bool,
    related_posts: list[dict[str, str]],
) -> str:
    related_items = []
    for item in related_posts[:6]:
        title = (item.get('title') or '').strip()
        url = (item.get('url') or '').strip()
        if title and url:
            related_items.append(f'<li><a href="{_e(url)}">{_e(title)}</a></li>')
    related_block = ''
    if related_items:
        related_block = f'''
  <h3>سایر تحلیل‌های بازار منتشرشده</h3>
  <ul class="mk-market-related-list">{''.join(related_items)}</ul>
'''

    deal_guides = (
        '''
    <li><a href="/blog/gozaresh-gheymat-malek-divar-dade-rahnama/">گزارش قیمت برای مالک با داده دیوار</a></li>
    <li><a href="/blog/gheymat-gozari-melk-agahi-divar/">قیمت‌گذاری ملک بر اساس آگهی دیوار</a></li>
    <li><a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">تشخیص ملک زیر بازار و Value Score</a></li>
    <li><a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت املاک از روی دیوار</a></li>
'''
        if not is_rent else
        '''
    <li><a href="/blog/gozaresh-gheymat-malek-divar-dade-rahnama/">گزارش قیمت/رهن داده‌محور برای مالک و موجر</a></li>
    <li><a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت و رهن از روی آگهی دیوار</a></li>
    <li><a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">فایل زیر عرف بازار و امتیاز ارزش</a></li>
    <li><a href="/blog/gheymat-gozari-melk-agahi-divar/">چارچوب قیمت‌گذاری با داده آگهی</a></li>
'''
    )

    return f'''
<section class="mk-market-section mk-market-links" id="related-guides">
  <h2>ادامه مطالعه و لینک‌های کاربردی</h2>
  <p>
    اگر این تحلیل {_e(tx_label)} {_e(subcat)} در {_e(district)} {_e(city)} برایتان مفید بود،
    مسیرهای زیر برای عمیق‌تر شدن و اجرای عملی روی فایل‌های خودتان پیشنهاد می‌شود.
  </p>
  {related_block}
  <h3>راهنماهای مکمل قیمت و بازار</h3>
  <ul class="mk-market-related-list">{deal_guides}
  </ul>
  <h3>ابزارها و صفحات محصول</h3>
  <ul class="mk-market-related-list">
    <li><a href="/products/divar-extraction-bot/">خرید لایسنس ربات استخراج دیوار</a></li>
    <li><a href="/accounts/register/">ثبت‌نام رایگان میزکار</a></li>
    <li><a href="/real-estate-market-analysis/">تحلیل بازار املاک در فایلینگ دیوار</a></li>
    <li><a href="/real-estate-filing/">فایلینگ دیوار؛ بانک فایل و دیتاست محله</a></li>
    <li><a href="/robot-divar/">ربات استخراج آگهی دیوار</a></li>
    <li><a href="/real-estate-crm/">CRM املاک برای پیگیری مشتری و مالک</a></li>
    <li><a href="/blog/?cat=tahlil-bazar">آرشیو مقالات تحلیل بازار</a></li>
    <li><a href="/author/hossein-qashqaeii/">نویسنده: حسین قشقایی</a></li>
  </ul>
</section>
'''


def render_cta_section(*, city: str = '', district: str = '', tx_label: str = '') -> str:
    place = f'{district} {city}'.strip() or 'محله خودتان'
    bot_url = '/products/divar-extraction-bot/'
    return f'''
<section class="mk-market-section mk-market-cta mk-market-cta--final" id="cta">
  <h2>محله خودتان را مثل {_e(place)} تحلیل کنید</h2>
  <p>
    این گزارش یک نمونه عمومی از تحلیل داده‌محور بازار {_e(tx_label)} است.
    اگر مشاور، سازنده، سرمایه‌گذار یا مالکید و می‌خواهید <strong>همین منطق را روی فایل‌های واقعی محله خودتان</strong>
    اجرا کنید، مسیر فایلینگ دیوار این است: استخراج آگهی با لایسنس ربات → ساخت Dataset در میزکار →
    نقشه، امتیاز دسترسی، Value Score و گزارش جلسه.
  </p>
  <div class="mk-market-cta-personas">
    <article>
      <strong>مشاور املاک</strong>
      <span>بانک فایل به‌روز، گزارش برای مالک، و فیلتر فرصت زیر بازار — بدون اسکرول دستی دیوار.</span>
    </article>
    <article>
      <strong>سازنده / انبوه‌ساز</strong>
      <span>متراژ پرتقاضا، سطح قیمت قابل دفاع و نقشه عرضه را قبل از تصمیم پروژه ببینید.</span>
    </article>
    <article>
      <strong>سرمایه‌گذار</strong>
      <span>عمق بازار، نقدشوندگی و فایل‌های زیر عرف را با داده محله خودتان رصد کنید.</span>
    </article>
    <article>
      <strong>مالک / موجر</strong>
      <span>قیمت‌گذاری واقع‌بینانه با میانه محله؛ آماده‌سازی برای مذاکره یا سپردن به مشاور.</span>
    </article>
  </div>
  <div class="mk-market-cta-links">
    <a class="mk-market-cta-btn mk-market-cta-btn--primary" href="{_e(bot_url)}">خرید لایسنس ربات استخراج</a>
    <a class="mk-market-cta-btn mk-market-cta-btn--primary" href="/accounts/register/">شروع رایگان میزکار</a>
    <a class="mk-market-cta-btn" href="/real-estate-market-analysis/">تحلیل بازار در پلتفرم</a>
    <a class="mk-market-cta-btn" href="/real-estate-filing/">فایلینگ دیوار</a>
    <a class="mk-market-cta-btn" href="/robot-divar/">ربات دیوار</a>
  </div>
  <p class="mk-market-cta-note">
    ثبت‌نام میزکار رایگان است؛ برای استخراج خودکار و مقیاس حرفه‌ای،
    <a href="{_e(bot_url)}">لایسنس ربات</a> را فعال کنید تا داده محله‌تان همیشه تازه بماند.
  </p>
</section>
'''


def render_convert_band(
    *,
    city: str = '',
    district: str = '',
    audience: str = '',
    anchor: str = 'convert',
) -> str:
    """نوار تبدیل میانی — سوق به لایسنس و میزکار."""
    place = f'{district} {city}'.strip() or 'محله خودتان'
    who = audience or 'مشاور، سازنده یا سرمایه‌گذار'
    bot_url = '/products/divar-extraction-bot/'
    return f'''
<aside class="mk-market-convert" id="{_e(anchor)}" aria-label="دعوت به استفاده از پلتفرم">
  <div class="mk-market-convert__copy">
    <strong>می‌خواهید {_e(place)} یا محله خودتان را همین‌طور آنالیز کنید؟</strong>
    <p>
      اگر {_e(who)} هستید، در فایلینگ دیوار Dataset بسازید، نقشه و امتیاز دسترسی بگیرید
      و با لایسنس ربات، آگهی‌های تازه دیوار را خودکار وارد میزکار کنید.
    </p>
  </div>
  <div class="mk-market-convert__actions">
    <a href="{_e(bot_url)}">خرید لایسنس</a>
    <a href="/accounts/register/">ثبت‌نام میزکار</a>
    <a href="/real-estate-market-analysis/">شروع تحلیل بازار</a>
  </div>
</aside>
'''