"""موج D — مقاله ۳: استخراج آگهی دیوار (نسخه غنی)"""

ARTICLE = {
    'keyword': 'استخراج آگهی دیوار',
    'slug_base': 'estekhraj-agahi-divar-rahnama-kamel',
    'title': 'استخراج آگهی دیوار: راهنمای کامل جمع‌آوری، فیلتر و ورود به فایلینگ',
    'excerpt': (
        'استخراج آگهی دیوار پایه فایلینگ، تحلیل بازار و CRM است. راهنمای جامع: '
        'فیلتر محله، ربات vs دستی، Export اکسل، import میزکار، پاکسازی، '
        'Compare هفتگی و زنجیره کار حرفه‌ای مشاور املاک.'
    ),
    'category': {
        'slug': 'robot-divar',
        'name': 'ربات دیوار',
        'description': 'استخراج، دانلود و مدیریت آگهی‌های دیوار برای مشاوران املاک',
        'order': 6,
    },
    'tags': [
        'استخراج آگهی دیوار',
        'ربات دیوار',
        'ربات استخراج دیوار',
        'فایلینگ دیوار',
        'دانلود آگهی دیوار',
        'فایلینگ املاک',
        'جمع‌آوری آگهی',
    ],
    'content': """
<p>قبل از CRM، قبل از گزارش قیمت، قبل از تطبیق مشتری — یک چیز لازم است: <strong>داده تمیز از دیوار</strong>. <strong>استخراج آگهی دیوار</strong> یعنی آگهی‌های یک محله (یا چند محله) را با فیلتر درست جمع کنید، در میزکار import کنید و هر هفته تازه کنید. بدون این، <a href="/real-estate-filing/">فایلینگ</a>، <a href="/real-estate-market-analysis/">تحلیل بازار</a> و <a href="/property-pricing/">قیمت‌گذاری</a> فقط روی هوا کار می‌کنند.</p>

<p><a href="https://divar.ir" rel="noopener noreferrer" target="_blank">دیوار</a> بزرگ‌ترین منبع آگهی املاک در ایران است — میلیون‌ها کاربر هر روز جستجو می‌کنند. مشاور حرفه‌ای نباید «هر بار از اول دیوار را بگردد»؛ باید <strong>استخراج تکرارپذیر</strong> داشته باشد: همان فیلتر، همان ستون‌ها، همان مسیر import.</p>

<p>این راهنمای جامع مکمل این مطالب است:</p>
<ul>
    <li><a href="/blog/chetor-agahi-divar-download/">چطور آگهی دیوار را دانلود کنیم</a></li>
    <li><a href="/blog/moghayese-dasti-vs-robot-divar/">استخراج دستی یا ربات؟</a></li>
    <li><a href="/blog/sazmandehi-agahi-haye-divar/">سازماندهی آگهی‌ها</a></li>
</ul>
<p>ابزار: <a href="/robot-divar/">ربات استخراج دیوار</a> + <a href="/">میزکار فایلینگ دیوار</a>.</p>

<div class="mk-blog-tip-box">
    <strong>خلاصه برای عجله‌ای‌ها</strong>
    <p>۱–۲ محله کاری → فیلتر فروش/اجاره جدا + متراژ ±۲۰٪ → Export (ربات یا دستی) → import با نام «[محله] — [نوع] — [تاریخ]» → حذف duplicate → Analyze sanity check → Compare هفتگی. زمان راه‌اندازی اول: ۶۰–۹۰ دقیقه؛ هفتگی: ۱۵–۳۰ دقیقه.</p>
</div>

<h2>استخراج یعنی چه — و چه نیست</h2>

<table>
    <thead>
        <tr><th>استخراج حرفه‌ای</th><th>شبه‌فایلینگ (اشتباه)</th></tr>
    </thead>
    <tbody>
        <tr><td>جدول با ستون: قیمت، متر، محله، لینک، token</td><td>اسکرین‌شات پراکنده در واتساپ</td></tr>
        <tr><td>فیلتر ثابت هر هفته</td><td>هر بار جستجوی تصادفی در دیوار</td></tr>
        <tr><td>Dataset نام‌دار در میزکار</td><td>۱۰ فایل Excel با نام export(1)</td></tr>
        <tr><td>ورودی Analyze / Compare / CRM</td><td>لینک برای خودت بدون ساختار</td></tr>
    </tbody>
</table>

<h2>چرا استخراج برای مشاور حیاتی است؟</h2>
<ol>
    <li><strong>سرعت پاسخ:</strong> — <a href="/blog/filing-hooshmand-amlak/">فایلینگ هوشمند</a> روی داده استخراج‌شده</li>
    <li><strong>گزارش قیمت:</strong> — <a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش مالک</a> بدون استخراج ممکن نیست</li>
    <li><strong>تحلیل بازار:</strong> — <a href="/blog/tahlil-bazar-amlak-divar-gheymat-gozari/">داده واقعی</a></li>
    <li><strong>تطبیق مشتری:</strong> — <a href="/blog/tatbiq-hooshmand-melk-moshtari/">پیشنهاد خودکار فایل</a></li>
    <li><strong>اعتبار:</strong> مشتری می‌فهمد «این مشاور بازار را رصد می‌کند»</li>
</ol>

<h2>۷ مرحله استخراج حرفه‌ای</h2>

<h3>۱. تعریف محدوده جغرافیایی</h3>
<p>یک یا دو محله کاری — نه «کل تهران». — <a href="/blog/bank-file-mantaghe-amlak/">بانک فایل منطقه‌ای</a>. مشاور تازه‌کار: یک محله ۵۰–۱۵۰ فایل. آژانس: چند Dataset با مسئول مشخص.</p>

<h3>۲. تعریف فیلتر</h3>
<table>
    <thead>
        <tr><th>فیلتر</th><th>اشتباه رایج</th><th>پیشنهاد</th></tr>
    </thead>
    <tbody>
        <tr><td>نوع معامله</td><td>فروش+اجاره قاطی</td><td>Dataset جدا</td></tr>
        <tr><td>متراژ</td><td>۵۰–۳۰۰ متر</td><td>±۲۰٪ میانه محله</td></tr>
        <tr><td>محله</td><td>کل منطقه</td><td>یک محله یا دو هم‌جوار</td></tr>
        <tr><td>قیمت</td><td>فیلتر خیلی تنگ</td><td>فقط اگر Dataset &gt;۵۰۰</td></tr>
        <tr><td>تاریخ Export</td><td>۳ ماه پیش</td><td>۷–۱۴ روز برای تحلیل</td></tr>
    </tbody>
</table>

<h3>۳. روش استخراج — ربات یا دستی</h3>

<table>
    <thead>
        <tr><th>معیار</th><th>دستی</th><th>ربات دیوار</th></tr>
    </thead>
    <tbody>
        <tr><td>حجم</td><td>۲۰–۵۰ آگهی</td><td>صدها تا هزار</td></tr>
        <tr><td>زمان</td><td>۲–۴ ساعت</td><td>۱۵–۴۵ دقیقه</td></tr>
        <tr><td>تکرارپذیری</td><td>پایین</td><td>بالا — <a href="/blog/filing-khodkar-amlak/">فایلینگ خودکار</a></td></tr>
        <tr><td>خطا</td><td>کپی اشتباه</td><td>ستون یکسان</td></tr>
        <tr><td>ROI</td><td>OK برای تست</td><td>آژانس / مشاور پرحجم</td></tr>
    </tbody>
</table>

<p>جزئیات: <a href="/blog/moghayese-dasti-vs-robot-divar/">مقایسه کامل دستی vs ربات</a>.</p>

<h3>۴. Export و فرمت</h3>
<p>خروجی اکسل/CSV با ستون‌های استاندارد. قبل import یک بار باز کنید: قیمت عددی، متراژ عددی، لینک/token موجود. — <a href="/blog/import-excel-agahi-amlak/">آموزش import</a>.</p>

<h3>۵. Import به Dataset</h3>
<p>نام استاندارد: «سعادت‌آباد — فروش — ۹۰–۱۱۰m — ۱۴۰۵/۰۶/۱۲». توضیح: منبع دیوار، هفته XX.</p>

<h3>۶. پاکسازی</h3>
<ul>
    <li>Duplicate token — <a href="/blog/hazf-agahi-tekrari-filing/">حذف تکراری</a></li>
    <li>پرت قیمت — <a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت</a></li>
    <li>آگهی نامعتبر (متر صفر، قیمت غیرمنطقی)</li>
</ul>

<h3>۷. Sanity check و استفاده</h3>
<p>Analyze: تعداد و میانه با «حس بازار» جور درمی‌آید؟ Compare هفته بعد. اتصال به CRM.</p>

<div class="mk-blog-inline-cta">
    <strong>اولین Dataset را امروز بسازید</strong>
    <p>ربات دیوار → Export → Import — کمتر از ۹۰ دقیقه.</p>
    <p><a href="/accounts/register/" class="mk-blog-cta-btn mk-blog-cta-btn--primary">شروع رایگان</a>
    <a href="/robot-divar/" class="mk-blog-cta-btn mk-blog-cta-btn--ghost">ربات دیوار</a>
    <a href="/real-estate-filing/" class="mk-blog-cta-btn mk-blog-cta-btn--ghost">فایلینگ املاک</a></p>
</div>

<h2>زنجیره کامل بعد از استخراج</h2>

<ol>
    <li><strong>استخراج</strong> (همین مطلب)</li>
    <li><strong>سازماندهی</strong> — <a href="/blog/sazmandehi-agahi-haye-divar/">بانک فایل</a></li>
    <li><strong>تحلیل</strong> — <a href="/blog/tahlil-bazar-amlak-divar/">تحلیل بازار</a></li>
    <li><strong>Compare</strong> — <a href="/blog/compare-dataset-rasad-bazar-mahalle/">رصد هفتگی</a></li>
    <li><strong>گزارش</strong> — <a href="/blog/gozaresh-gheymat-malek-dade-divar/">قیمت مالک</a></li>
    <li><strong>CRM</strong> — <a href="/blog/gardesh-kar-roozane-moshaver-amlak/">گردش کار روزانه</a></li>
</ol>

<p>استخراج ضعیف = کل زنجیره ضعیف. وقت زیاد در Analyze با Dataset کثیف تلف نکنید — اول پاکسازی.</p>

<h2>برنامه به‌روزرسانی</h2>

<table>
    <thead>
        <tr><th>نقش</th><th>فرکانس</th><th>کار</th><th>زمان</th></tr>
    </thead>
    <tbody>
        <tr><td>مشاور solo</td><td>هفتگی</td><td>Export ۱–۲ محله + Compare</td><td>۲۰–۳۰ دقیق</td></tr>
        <tr><td>آژانس</td><td>هفتگی</td><td>مسئول Export همه محله‌ها</td><td>۱–۲ ساعت</td></tr>
        <tr><td>مالک فعال</td><td>هر ۳–۵ روز</td><td>Export comparable محدود</td><td>۱۰ دقیق</td></tr>
        <tr><td>تحلیل فصلی</td><td>ماهانه</td><td>آرشیو ۴ Compare</td><td>۳۰ دقیق</td></tr>
    </tbody>
</table>

<h2>استخراج + CRM + ارسال فایل</h2>
<p>بعد از import، ۳ آگهی برتر را برای مشتری CRM فیلتر و ارسال کنید — <a href="/blog/eshterak-file-moshtari-link-omomi/">اشتراک فایل با لینک</a>. تاریخچه ارسال در CRM ثبت می‌شود؛ duplicate ارسال کم می‌شود.</p>

<h2>انتخاب نرم‌افزار و ربات</h2>
<p>قبل خرید: — <a href="/blog/narm-afzar-filing-amlak/">۱۲ نکته نرم‌افزار فایلینگ</a> و <a href="/real-estate-software/">نرم‌افزار مشاور املاک</a>. معیار: import آسان، duplicate، Analyze، CRM یکپارچه.</p>

<h2>قانونی و اخلاقی</h2>
<ul>
    <li>داده برای مشاوره داخلی، گزارش به مالک/خریدار — نه republish لیست کامل آگهی</li>
    <li>رعایت <a href="https://divar.ir/terms" rel="noopener noreferrer" target="_blank">شرایط استفاده دیوار</a></li>
    <li>شفافیت: «بر اساس آگهی‌های عمومی منتشرشده»</li>
    <li>احترام به مالک — تماس spam با استخراج شماره غیرمجاز خط قرمز است</li>
</ul>

<h2>۱۰ اشتباه پرتکرار استخراج</h2>
<ul>
    <li>یک بار Extract و فراموش — بازار زنده است</li>
    <li>Dataset ۵۰۰۰ تایی قدیمی — کیفیت &gt; کمیت</li>
    <li>Import بدون نام — Compare غیرممکن</li>
    <li>Skip duplicate — Analyze خراب</li>
    <li>فروش و اجاره در یک Dataset</li>
    <li>کل شهر در یک Export</li>
    <li>بدون sanity check Analyze</li>
    <li>Export بدون backup هفته قبل</li>
    <li>فقط ذخیره Excel روی دسکتاپ بدون میزکار</li>
    <li>استخراج بدون استفاده CRM — آرشیو بلااستفاده</li>
</ul>

<h2>چک‌لیست ۹۰ دقیقه — راه‌اندازی اول</h2>
<ol>
    <li>محله اصلی را انتخاب کنید (<a href="/blog/filing-amlak-yani-chi/">فایلینگ یعنی چی</a>)</li>
    <li>فیلتر فروش + متراژ متداول</li>
    <li>Export با ربات یا دستی — <a href="/blog/chetor-agahi-divar-download/">دانلود</a></li>
    <li>Import + نام Dataset</li>
    <li>حذف duplicate</li>
    <li>Analyze — یادداشت تعداد و میانه</li>
    <li>۳ آگهی → CRM برای یک مشتری</li>
    <li>یادآور Export هفتگی</li>
    <li>مطالعه <a href="/blog/compare-dataset-rasad-bazar-mahalle/">Compare</a> برای هفته بعد</li>
</ol>

<h2>مثال واقعی: مشاور نارمک — هفته اول</h2>
<p>فیلتر: فروش، ۷۵–۱۰۵m، نارمک. ربات: ۱۴۲ ردیف خام → ۱۱۸ بعد duplicate و پرت. Analyze: median 46M/m. سه فایل برای خریدار CRM — زمان کل ۷۵ دقیقه. هفته دوم Export: ۱۵ دقیقه + Compare.</p>

<h2>مدیر آژانس</h2>
<p>یک مسئول Export، نام‌گذاری واحد، آموزش import به تیم — <a href="/blog/modiriyat-ajans-amlak-crm/">مدیریت آژانس</a>. KPI: Dataset هر محله &lt; ۷ روز قدمت.</p>

<h2>مطالب مرتبط</h2>
<ul>
    <li><a href="/blog/filing-amlak-yani-chi/">فایلینگ املاک یعنی چی</a></li>
    <li><a href="/blog/import-excel-agahi-amlak/">Import اکسل</a></li>
    <li><a href="/blog/hazf-agahi-tekrari-filing/">حذف تکراری</a></li>
    <li><a href="/blog/gheymat-gozari-melk-agahi-divar/">قیمت‌گذاری ۵ قدم</a></li>
    <li><a href="/blog/crm-amlak-online-vs-excel/">CRM vs Excel</a></li>
</ul>

<h2>جمع‌بندی</h2>
<p><strong>استخراج آگهی دیوار</strong> ستون فقرات فایلینگ دیجیتال است. فیلتر درست، Export منظم، import تمیز — بقیه CRM و تحلیل روی آن سوار می‌شود. امروز یک محله، فردا Compare، پس‌فردا گزارش مالک.</p>
<p><em>نویسنده: <a href="/author/hossein-qashqaeii/">حسین قشقایی</a> — <a href="/">فایلینگ دیوار</a>.</em></p>

<h2>سوالات متداول</h2>

<h3>چند آگهی برای شروع کافی است؟</h3>
<p>۵۰–۱۵۰ معتبر برای یک محله.</p>

<h3>CRM رایگان؛ ربات چطور؟</h3>
<p>CRM میزکار رایگان — <a href="/blog/crm-amlak-raygan-rahnama/">جزئیات</a>. استخراج حجیم <a href="/robot-divar/">لایسنس ربات</a>.</p>

<h3>بدون ربات شروع کنم؟</h3>
<p>بله — ۵۰ آگهی دستی + import؛ بعداً ربات برای مقیاس.</p>

<h3>Excel مستقیم import؟</h3>
<p>بله — <a href="/blog/import-excel-agahi-amlak/">راهنما</a>.</p>

<h3>فرق این مطلب با «دانلود دیوار»؟</h3>
<p><a href="/blog/chetor-agahi-divar-download/">آن</a> روش دانلود؛ اینجا کل pipeline تا Dataset.</p>

<h3>استخراج قانونی است؟</h3>
<p>استفاده مشاوره‌ای از داده عمومی با رعایت terms دیوار رایج است؛ spam و republish ممنوع.</p>

<h3>چند محله همزمان؟</h3>
<p>مشاور solo: ۱–۲؛ آژانس: هر محله Dataset جدا.</p>

<h3>نویسنده؟</h3>
<p><a href="/author/hossein-qashqaeii/">حسین قشقایی</a>.</p>
""",
}
