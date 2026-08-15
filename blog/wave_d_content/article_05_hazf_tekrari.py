"""موج D — مقاله ۵: حذف آگهی تکراری (نسخه غنی)"""

ARTICLE = {
    'keyword': 'حذف آگهی تکراری فایلینگ',
    'slug_base': 'hazf-agahi-tekrari-filing',
    'title': 'حذف آگهی تکراری در فایلینگ: راهنمای پاکسازی بانک فایل برای تحلیل درست',
    'excerpt': (
        'آگهی تکراری میانه قیمت، Compare و گزارش مالک را خراب می‌کند. راهنمای کامل '
        'شناسایی duplicate، token یکسان، merge، پاکسازی هفتگی و '
        'Dataset آماده Analyze — برای مشاور و آژانس.'
    ),
    'category': {
        'slug': 'filing-amlak',
        'name': 'فایلینگ املاک',
        'description': 'راهنمای کامل ساخت بانک فایل، فایلینگ و سیستم مدیریت آگهی مشاوران املاک',
        'order': 4,
    },
    'tags': [
        'حذف آگهی تکراری',
        'فایلینگ املاک',
        'فایلینگ دیوار',
        'بانک فایل املاک',
        'تحلیل بازار املاک',
        'سیستم فایلینگ املاک',
        'پاکسازی Dataset',
    ],
    'content': """
<p>Dataset ۲۰۰ تایی import کردید؛ Analyze میانه ۵۲ میلیون نشان می‌دهد. مشتری می‌گوید «غلط است — من ارزان‌تر دیدم». نگاه می‌کنید: همان آپارتمان <strong>۳ بار</strong> با قیمت‌های مختلف در لیست است. یا Compare می‌گوید «۵۰ فایل جدید» در حالی که ۴۰ تایشان duplicate هستند.</p>

<p><strong>حذف آگهی تکراری در فایلینگ</strong> کار unsexy اما <strong>حیاتی</strong> است — پایه <a href="/blog/tahlil-bazar-amlak-divar-gheymat-gozari/">تحلیل بازار</a>، <a href="/blog/compare-dataset-rasad-bazar-mahalle/">Compare Dataset</a> و <a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش قیمت مالک</a>. بدون پاکسازی، <a href="/real-estate-market-analysis/">تحلیل بازار</a> و <a href="/property-pricing/">قیمت‌گذاری</a> روی داده کثیف ساخته می‌شود.</p>

<p>این راهنما بعد از <a href="/blog/estekhraj-agahi-divar-rahnama-kamel/">استخراج دیوار</a> و قبل از Analyze می‌آید — بخشی از <a href="/blog/filing-amlak-yani-chi/">فایلینگ املاک</a> و <a href="/blog/sazmandehi-agahi-haye-divar/">سازماندهی آگهی</a>.</p>

<div class="mk-blog-tip-box">
    <strong>خلاصه برای عجله‌ای‌ها</strong>
    <p>بعد هر import: sort/token → ابزار duplicate میزکار → نگه‌داشتن جدیدترین قیمت → حذف پرت → Analyze sanity check. زمان: ۱۰–۱۵ دقیقه. قبل Compare حتماً duplicate = ۰.</p>
</div>

<h2>تکراری یعنی چه — انواع duplicate</h2>

<table>
    <thead>
        <tr><th>نوع</th><th>علت</th><th>خطر</th><th>راه‌حل</th></tr>
    </thead>
    <tbody>
        <tr><td>Token یکسان</td><td>Import دوباره همان Export</td><td>میانه artificial</td><td>Merge / حذف</td></tr>
        <tr><td>Append بدون Compare</td><td>Export روی Dataset قدیمی</td><td>تعداد inflated</td><td>Dataset هفتگی جدا</td></tr>
        <tr><td>ملک یکسان، چند token</td><td>مالک + مشاور هر دو آگهی</td><td>double-count در Analyze</td><td>قضاوت — یک ردیف برای Analyze</td></tr>
        <tr><td>کپی همکار</td><td>لینک یکسان در Datasetهای مختلف</td><td>گاهی OK در CRM</td><td>برچسب منبع</td></tr>
        <tr><td>Excel چند فایل</td><td>export(1), export(2) merge</td><td>هرج‌ومرج</td><td>نام‌گذاری + یک مسئول import</td></tr>
    </tbody>
</table>

<h2>چرا duplicate برای مشاور خطرناک است؟</h2>

<table>
    <thead>
        <tr><th>بدون پاکسازی</th><th>Dataset تمیز</th></tr>
    </thead>
    <tbody>
        <tr><td>میانه قیمت غلط</td><td>میانه نزدیک بازار <a href="https://divar.ir" rel="noopener noreferrer" target="_blank">دیوار</a></td></tr>
        <tr><td>Compare fake «جدید»</td><td>Delta واقعی</td></tr>
        <tr><td>۳ بار همان فایل برای مشتری</td><td>اعتبار حرفه‌ای</td></tr>
        <tr><td>عمق بازار inflated</td><td>«۸۷ فایل» = ۸۷ ملک</td></tr>
        <tr><td>گزارش مالک قابل حمله</td><td>گزارش دفاع‌پذیر</td></tr>
    </tbody>
</table>

<p>ارتباط با <a href="/blog/eshtebahat-gheymat-gozari-moshaver/">۷ اشتباه قیمت‌گذاری</a>: «Dataset بزرگ = بهتر» بدون پاکسازی یکی از بدترین‌هاست.</p>

<h2>فرآیند پاکسازی — ۶ مرحله</h2>

<h3>۱. Sort بر اساس token / لینک</h3>
<p>duplicate واضح کنار هم دیده می‌شود. لینک آگهی دیوار معمولاً token یکتا دارد.</p>

<h3>۲. ابزار duplicate میزکار</h3>
<p>در <a href="/real-estate-filing/">فایلینگ دیوار</a> duplicate token شناسایی و merge یا حذف. نگه دارید: <strong>جدیدترین Export</strong> و <strong>کامل‌ترین فیلد</strong>.</p>

<h3>۳. ملک یکسان — دو token (سخت‌تر)</h3>
<p>متراژ + محله + طبقه + قیمت نزدیک — قضاوت انسانی. برای Analyze یک ردیف؛ برای CRM هر دو با برچسب «منبع: مالک / مشاور».</p>

<h3>۴. حذف پرت</h3>
<p>قیمت/متراژ غیرمنطقی — <a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت و پرت</a>.</p>

<h3>۵. Sanity check Analyze</h3>
<p>تعداد و میانه با «حس بازار» جور درمی‌آید؟</p>

<h3>۶. ثبت نسخه نهایی</h3>
<p>یادداشت: «W12 — ۸۷ فایل پس از duplicate» — برای Compare.</p>

<div class="mk-blog-inline-cta">
    <strong>Dataset تمیز = گزارش درست</strong>
    <p>Import → duplicate → Analyze — ۱۵ دقیقه.</p>
    <p><a href="/accounts/register/" class="mk-blog-cta-btn mk-blog-cta-btn--primary">شروع رایگان</a>
    <a href="/real-estate-filing/" class="mk-blog-cta-btn mk-blog-cta-btn--ghost">فایلینگ املاک</a>
    <a href="/blog/gozaresh-gheymat-malek-dade-divar/" class="mk-blog-cta-btn mk-blog-cta-btn--ghost">گزارش قیمت</a></p>
</div>

<h2>قوانین نگه‌داشتن یک ردیف از چند duplicate</h2>
<ul>
    <li><strong>جدیدترین تاریخ Export</strong></li>
    <li><strong>قیمت به‌روز</strong> — اگر یکی تغییر کرده</li>
    <li><strong>کامل‌ترین ستون‌ها</strong> (طبقه، پارکینگ، …)</li>
    <li>یادداشت: «dup حذف — نگه W12»</li>
</ul>

<h2>پاکسازی در زنجیره کار</h2>
<ol>
    <li><a href="/blog/estekhraj-agahi-divar-rahnama-kamel/">استخراج</a></li>
    <li><strong>پاکسازی duplicate</strong> (همین مطلب)</li>
    <li><a href="/blog/tahlil-bazar-amlak-divar/">Analyze</a></li>
    <li><a href="/blog/compare-dataset-rasad-bazar-mahalle/">Compare</a></li>
    <li><a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش</a></li>
    <li><a href="/blog/gardesh-kar-roozane-moshaver-amlak/">CRM روزانه</a></li>
</ol>

<h2>Compare فقط با Dataset تمیز</h2>
<p>Compare دو Dataset کثیف = «۱۰۰ فایل جدید» که نصفشان duplicate. قوانین:</p>
<ul>
    <li>هر دو Dataset duplicate-free</li>
    <li>فیلتر یکسان (متراژ، نوع، محله)</li>
    <li>نام هفته واضح</li>
</ul>

<h2>پیشگیری — import درست</h2>
<ul>
    <li>Dataset هفتگی <strong>جدید</strong> — نه overwrite بی‌نام</li>
    <li>یک مسئول import در آژانس — <a href="/blog/modiriyat-ajans-amlak-crm/">مدیریت تیم</a></li>
    <li>Export کامل محله — <a href="/robot-divar/">ربات</a> — نه patch قاطی</li>
    <li>قبل merge به Dataset اصلی، Compare — <a href="/blog/import-excel-agahi-amlak/">import</a></li>
    <li>استاندارد نام: «[محله] — [نوع] — WXX» — <a href="/blog/bank-file-mantaghe-amlak/">بانک فایل</a></li>
</ul>

<h2>برنامه هفتگی پاکسازی</h2>

<table>
    <thead>
        <tr><th>قدم</th><th>کار</th><th>زمان</th><th>ابزار</th></tr>
    </thead>
    <tbody>
        <tr><td>۱</td><td>Import Export جدید</td><td>۵ دقیق</td><td>ربات / Excel</td></tr>
        <tr><td>۲</td><td>Duplicate token</td><td>۵ دقیق</td><td>میزکار duplicate</td></tr>
        <tr><td>۳</td><td>حذف پرت</td><td>۳ دقیق</td><td>فیلتر + چشم</td></tr>
        <tr><td>۴</td><td>Analyze + ثبت N نهایی</td><td>۲ دقیق</td><td>Analyze</td></tr>
        <tr><td>۵</td><td>Compare با هفته قبل</td><td>۵ دقیق</td><td>Compare</td></tr>
    </tbody>
</table>

<p>جمع: ~۲۰ دقیقه — بخشی از <a href="/blog/filing-hooshmand-amlak/">فایلینگ هوشمند</a> و <a href="/blog/filing-khodkar-amlak/">فایلینگ خودکار</a>.</p>

<h2>تکراری vs دو منبع — CRM vs Analyze</h2>

<table>
    <thead>
        <tr><th>سناریو</th><th>برای Analyze</th><th>برای CRM</th></tr>
    </thead>
    <tbody>
        <tr><td>مالک + مشاور، یک ملک</td><td>یک ردیف (میانه)</td><td>دو لینک + برچسب منبع</td></tr>
        <tr><td>همان token دوبار import</td><td>حذف قطعی</td><td>—</td></tr>
        <tr><td>قیمت‌های مختلف، token یکسان</td><td>جدیدترین</td><td>تاریخچه در یادداشت</td></tr>
    </tbody>
</table>

<h2>مثال واقعی: قبل و بعد پاکسازی</h2>
<p><strong>قبل:</strong> ۱۴۲ ردیف import — Analyze median 51M/m — مالک شک می‌کند.<br/>
<strong>بعد duplicate + پرت:</strong> ۱۱۸ ردیف — median 46M/m — با ۳ comparable مالک قبول کرد.<br/>
<strong>زمان پاکسازی:</strong> ۱۲ دقیقه.<br/>
<strong>درس:</strong> ۲۴ ردیف اضافه میانه را ~۱۰٪ بالا برده بود.</p>

<h2>مثال ۲: Compare غلط</h2>
<p>Compare بدون پاکسازی: «+۴۵ جدید». بعد duplicate: «+۶ جدید، ۳۹ duplicate import اشتباه». گزارش به تیم: استاندارد import — <a href="/blog/sazmandehi-agahi-haye-divar/">سازماندهی</a>.</p>

<h2>اشتباهات رایج</h2>
<ul>
    <li>Skip پاکسازی — «بعداً» = never</li>
    <li>حذف تصادفی unique — sort قبل delete</li>
    <li>Dataset ۱۰ هزار تایی بدون پاکسازی</li>
    <li>Compare قبل duplicate</li>
    <li>فقط Excel روی دسکتاپ — بدون ابزار duplicate</li>
    <li>ارسال comparable بدون چک لینک — <a href="/blog/moghayese-gheymat-melk-divar/">مقایسه</a></li>
</ul>

<h2>چک‌لیست Dataset آماده</h2>
<ul>
    <li>Duplicate token = ۰ (یا merge)</li>
    <li>پرت‌های شدید حذف</li>
    <li>N نهایی در Analyze ثبت</li>
    <li>نام Dataset + تاریخ/هفته</li>
    <li>Compare هم‌فیلتر با هفته قبل</li>
    <li>آماده <a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش مالک</a></li>
</ul>

<h2>مدیر آژانس: SOP پاکسازی</h2>
<p>یک صفحه SOP برای تیم: نام Dataset، duplicate، مسئول، KPI «هیچ Analyze بدون duplicate check». Dataset مشترک — <a href="/blog/modiriyat-ajans-amlak-crm/">مدیریت آژانس</a>.</p>

<h2>ملاحظات</h2>
<ul>
    <li>پاکسازی روی داده عمومی <a href="https://divar.ir/terms" rel="noopener noreferrer" target="_blank">دیوار</a> — رعایت terms</li>
    <li>حذف duplicate ≠ حذف آگهی از دیوار — فقط در Dataset شما</li>
</ul>

<h2>مطالب مرتبط</h2>
<ul>
    <li><a href="/blog/import-excel-agahi-amlak/">Import اکسل</a></li>
    <li><a href="/blog/estekhraj-agahi-divar-rahnama-kamel/">استخراج دیوار</a></li>
    <li><a href="/blog/compare-dataset-rasad-bazar-mahalle/">Compare Dataset</a></li>
    <li><a href="/blog/narm-afzar-filing-amlak/">نرم‌افزار فایلینگ</a></li>
    <li><a href="/real-estate-software/">نرم‌افزار مشاور</a></li>
</ul>

<h2>جمع‌بندی</h2>
<p><strong>حذف آگهی تکراری</strong> پایه تحلیل درست است. ۱۰–۱۵ دقیقه بعد هر import — گزارشی که مالک باور کند و Compareی که به دروغ «+delta» نگوید.</p>
<p><em>نویسنده: <a href="/author/hossein-qashqaeii/">حسین قشقایی</a> — <a href="/">فایلینگ دیوار</a>.</em></p>

<h2>سوالات متداول</h2>

<h3>چطور duplicate را سریع پیدا کنم؟</h3>
<p>Sort token/لینک؛ ابزار duplicate میزکار.</p>

<h3>دو قیمت برای یک token؟</h3>
<p>جدیدترین Export را نگه دارید.</p>

<h3>هر import پاکسازی لازم است؟</h3>
<p>بله — حداقل duplicate check.</p>

<h3>بدون ربات؟</h3>
<p>Excel — sort و حذف دستی؛ کندتر.</p>

<h3>duplicate Analyze را چقدر خراب می‌کند؟</h3>
<p>بسته به درصد — گاهی ۵–۱۵٪ خطا در میانه.</p>

<h3>CRM جدا از Analyze؟</h3>
<p>بله — دو منبع یک ملک در CRM OK؛ Analyze یک ردیف.</p>

<h3>ابزار duplicate رایگان است؟</h3>
<p>در میزکار فایلینگ — CRM رایگان؛ جزئیات <a href="/blog/crm-amlak-raygan-rahnama/">اینجا</a>.</p>

<h3>نویسنده؟</h3>
<p><a href="/author/hossein-qashqaeii/">حسین قشقایی</a>.</p>
""",
}
