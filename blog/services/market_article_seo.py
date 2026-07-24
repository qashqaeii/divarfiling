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

    return [
        {
            'key': 'featured',
            'h3': f'نقشه شاخص بازار {subcat} در {place}',
            'alt': (
                f'نقشه شاخص تراکم فایل‌های {tx_label} {subcat} در محله {district} شهر {city}؛ '
                f'تحلیل مکانی بازار مسکن فایلینگ دیوار'
            ),
            'lead': (
                f'نقطه شروع خوانش مکانی بازار {tx_label} در {place}؛ '
                f'لایه تراکم روی نقشه شهری نزدیک محله.'
            ),
            'body': (
                f'این نقشه نمای کلی از پراکنش تجمیعی آگهی‌های {subcat} در {place} را نشان می‌دهد. '
                f'قبل از ورود به جزئیات رنگ و ارزش، با این تصویر بفهمید «قلب عرضه» کجای محله است. '
                f'برای مقایسه با عددهای میانه بازار، بخش شاخص‌های اصلی همین گزارش را ببینید '
                f'و اگر می‌خواهید همین تحلیل را روی فایل‌های خود تکرار کنید، از '
                f'<a href="/real-estate-market-analysis/">تحلیل بازار املاک</a> در میزکار استفاده کنید.'
            ),
            'uses': (
                f'کاربرد: جلسه با مالک، معرفی محدوده کاری به مشتری، و نقطه شروع '
                f'<a href="/blog/gozaresh-gheymat-malek-divar-dade-rahnama/">گزارش قیمت داده‌محور</a>.'
            ),
        },
        {
            'key': 'street_heat',
            'h3': f'هیت‌مپ تراکم عرضه؛ کجا در {district} فایل بیشتر است؟',
            'alt': (
                f'هیت‌مپ تراکم فایل‌های {tx_label} {subcat} در {district} {city}؛ '
                f'زرد کم‌فایل و قرمز پرتراکم روی نقشه شهری'
            ),
            'lead': (
                'رنگ زرد یعنی عرضه کمتر و قرمز یعنی کانون پرتراکم فایل. '
                'برای پیدا کردن جایی که انتخاب و مقایسه آسان‌تر است.'
            ),
            'body': (
                f'در بازار {deal_word} {place}، تراکم فایل یعنی «کجا می‌توانید سریع‌تر چند گزینه هم‌سطح ببینید». '
                f'مناطق قرمز معمولاً برای فیلتر اولیه و زمان‌بندی بازدید مناسب‌ترند؛ مناطق زرد ممکن است '
                f'کمبود عرضه یا پراکندگی جغرافیایی را نشان دهند. این لایه موقعیت تک‌آگهی را نشان نمی‌دهد '
                f'و فقط شبکه تجمیعی است تا حریم خصوصی حفظ شود.'
            ),
            'uses': (
                f'کاربرد خریدار/مستأجر: محدود کردن محدوده جستجو. کاربرد مشاور: اولویت‌بندی محله‌گردی و '
                f'بانک فایل با <a href="/robot-divar/">ربات استخراج دیوار</a>.'
            ),
        },
        {
            'key': 'street_value',
            'h3': f'نقشه {value_label} در {place}',
            'alt': (
                f'نقشه سطح {metric} {subcat} در محله {district} {city}؛ '
                f'آبی ارزان‌تر و قرمز گران‌تر نسبت به عرف بازار {tx_label}'
            ),
            'lead': (
                f'آبی‌تر یعنی {metric} پایین‌تر و قرمزتر یعنی بالاتر. '
                f'میانه بازار در این گزارش: {metric_fmt}.'
            ),
            'body': (
                f'این لایه به سؤال «کجای {district} گران‌تر یا ارزان‌تر از عرف است؟» جواب می‌دهد. '
                f'عدد مرجع مقایسه، {_e(metric)} بازار ({_e(metric_fmt)}) است. رنگ‌ها نسبی‌اند؛ '
                f'یعنی یک نقطه قرمز لزوماً «غیرمنطقی» نیست، بلکه نسبت به بدنه بازار همین دیتاست بالاتر است. '
                f'برای تشخیص فرصت زیر‌بازار، این نقشه را با بخش فرصت‌ها و '
                f'<a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">راهنمای Value Score</a> کنار هم ببینید.'
            ),
            'uses': (
                f'کاربرد فروشنده/موجر: قیمت‌گذاری نزدیک عرف محله. کاربرد مشاور: توضیح تفاوت قیمت خیابان به خیابان '
                f'بدون افشای فایل رقیب — مکمل <a href="/blog/gheymat-gozari-melk-agahi-divar/">قیمت‌گذاری با داده دیوار</a>.'
            ),
        },
        {
            'key': 'street_grid',
            'h3': f'شبکه کمی تراکم فایل در {district}',
            'alt': (
                f'شبکه کمی تراکم آگهی‌های {subcat} در {district} {city}؛ '
                f'عدد روی خانه‌های گرم نشان‌دهنده تعداد فایل تجمیعی'
            ),
            'lead': (
                'هر خانه شبکه چند فایل نزدیک را تجمیع می‌کند؛ '
                'عدد روی خانه‌های گرم = تعداد فایل در آن سلول.'
            ),
            'body': (
                f'شبکه کمی برای کسانی است که می‌خواهند «چند فایل» را ببینند نه فقط رنگ. '
                f'خانه‌های پررنگ‌تر با عدد بالاتر، کانون‌هایی هستند که نمونه آماری قوی‌تری دارند '
                f'(از حدود {_e(n_txt)} فایل معتبر کل گزارش). وقتی عدد خانه کم باشد، قضاوت قیمتی را بااحتیاط‌تر انجام دهید.'
            ),
            'uses': (
                'کاربرد تحلیل‌گر/سرمایه‌گذار: سنجش عمق محلی عرضه قبل از ورود سرمایه یا تعریف محدوده پروژه.'
            ),
        },
        {
            'key': 'street_hotspots',
            'h3': f'کانون‌های پرتراکم بازار {place}',
            'alt': (
                f'رتبه‌بندی کانون‌های پرتراکم عرضه {subcat} در {district} {city} '
                f'برای اولویت بازدید و فیلتر فایل'
            ),
            'lead': (
                '۳ تا ۵ کانون عرضه با رتبه تراکم مشخص شده‌اند؛ '
                'عدد کنار هر رتبه تقریبی از حجم فایل همان سلول است.'
            ),
            'body': (
                f'کانون‌های پرتراکم به شما می‌گویند زمان بازدید و بازاریابی را کجا متمرکز کنید. '
                f'رتبه ۱ پرتراکم‌ترین سلول در داده فعلی {place} است؛ لزوماً «بهترین معامله» نیست، '
                f'ولی جایی است که مقایسه گزینه‌ها سریع‌تر پیش می‌رود. بعد از شناسایی کانون، عددهای '
                f'{_e(metric)} و بازه مذاکره همین مقاله را برای فیلتر قیمت به کار ببرید.'
            ),
            'uses': (
                f'کاربرد تیم فروش: تقسیم محله بین مشاوران و برنامه‌ریزی فیلینگ هدفمند با '
                f'<a href="/real-estate-filing/">فایلینگ دیوار</a>.'
            ),
        },
        {
            'key': 'satellite_heat',
            'h3': f'تراکم فایل روی تصویر ماهواره‌ای {district}',
            'alt': (
                f'هیت‌مپ تراکم {tx_label} {subcat} روی تصویر ماهواره‌ای محله {district} {city}'
            ),
            'lead': (
                'همان لایه تراکم روی بستر ماهواره‌ای؛ برای درک بافت ساخته‌شده، معابر و بلوک‌های ساختمانی.'
            ),
            'body': (
                f'نقشه ماهواره‌ای کمک می‌کند بفهمید تراکم فایل با چه بافت فیزیکی هم‌خوان است '
                f'(بلوک نوساز، معابر اصلی، یا بافت ریزدانه). این دید برای سازنده و سرمایه‌گذار مهم است، '
                f'چون عرضه روی نقشه خیابان گاهی از بافت واقعی جدا به نظر می‌رسد.'
            ),
            'uses': (
                'کاربرد سازنده: تطبیق محدوده پرتقاضا با دسترسی و بافت قابل‌ساخت.'
            ),
        },
        {
            'key': 'satellite_value',
            'h3': f'{value_label} روی ماهواره؛ {place}',
            'alt': (
                f'نقشه {value_label} {subcat} روی تصویر ماهواره‌ای {district} {city}؛ '
                f'میانه بازار {metric_fmt}'
            ),
            'lead': (
                f'ترکیب بافت فیزیکی محله با {value_label}. '
                f'رنگ گرم‌تر یعنی سطح بالاتر نسبت به بدنه بازار.'
            ),
            'body': (
                f'وقتی رنگ ارزش را روی ماهواره می‌بینید، تفاوت قیمت را به خیابان، میدان و نوع ساخت وصل می‌کنید. '
                f'این نقشه برای جلسه با مالک یا سازنده قوی‌تر از جدول خام است؛ چون «چرا این محدوده گران‌تر است» '
                f'را روی تصویر واقعی محله توضیح می‌دهد.'
            ),
            'uses': (
                f'کاربرد مشاور: روایت قیمت در جلسه مالک با ارجاع به '
                f'<a href="/blog/gozaresh-gheymat-malek-divar-dade-rahnama/">گزارش قیمت برای مالک</a>.'
            ),
        },
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
        {
            'key': 'street_dots',
            'h3': f'پراکنش تجمیعی فایل‌ها در {district}',
            'alt': f'نقشه نقاط تجمیعی عرضه {subcat} در {district} {city}',
            'lead': 'نقاط درشت‌تر = سلول‌های پرتراکم‌تر در نمایش تجمیعی.',
            'body': (
                'نمای نقطه‌ای برای کسانی که ترجیح می‌دهند پراکنش را بدون هیت‌مپ نرم ببینند؛ '
                'هنوز تجمیعی است و پین تک‌آگهی نیست.'
            ),
            'uses': 'کاربرد: کنترل پوشش جغرافیایی بانک فایل محله.',
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
    اول تراکم (کجا فایل زیاد است)، بعد سطح ارزش (کجا گران‌تر/ارزان‌تر است)،
    سپس کانون‌های پرتراکم را برای اولویت بازدید ببینید. ماهواره بافت فیزیکی را شفاف می‌کند.
    همه لایه‌ها با مقیاس، جهت شمال و راهنمای رنگ ساخته شده‌اند و برای تصمیم میدانی طراحی شده‌اند.
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
    place = f'{district} {city}'.strip() or 'محله خود'
    return f'''
<section class="mk-market-section mk-market-cta" id="cta">
  <h2>همین تحلیل را برای فایل‌های خود در {_e(place)} بسازید</h2>
  <p>
    گزارش بالا نمونه‌ای از تحلیل داده‌محور بازار {_e(tx_label)} است. می‌توانید Dataset محله خود را در میزکار بسازید،
    فرصت‌های زیر بازار را فیلتر کنید، نقشه مکانی ببینید و با
    <a href="/robot-divar/">ربات فایلینگ دیوار</a> بانک فایل را به‌روز نگه دارید.
  </p>
  <div class="mk-market-cta-links">
    <a href="/real-estate-market-analysis/">شروع تحلیل بازار</a>
    <a href="/real-estate-filing/">فایلینگ دیوار</a>
    <a href="/accounts/register/">ثبت‌نام و ورود به میزکار</a>
    <a href="/blog/?cat=tahlil-bazar">سایر تحلیل‌های بازار</a>
  </div>
</section>
'''
