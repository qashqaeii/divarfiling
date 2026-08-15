"""موج D — مقاله ۲: Compare Dataset (نسخه غنی)"""

ARTICLE = {
    'keyword': 'Compare Dataset تحلیل بازار',
    'slug_base': 'compare-dataset-rasad-bazar-mahalle',
    'title': 'Compare Dataset: چطور هر هفته تغییرات بازار محله را رصد کنیم؟',
    'excerpt': (
        'تحلیل بازار یک‌باره کافی نیست — بازار هر هفته عوض می‌شود. راهنمای کامل Compare Dataset: '
        'دو Export محله، delta قیمت، فایل جدید و حذف‌شده، گزارش به مالک و خریدار، '
        'اشتباهات رایج و برنامه هفتگی مشاور.'
    ),
    'category': {
        'slug': 'market-analysis',
        'name': 'تحلیل بازار املاک',
        'description': 'تحلیل قیمت، روند بازار و قیمت‌گذاری حرفه‌ای بر پایه داده دیوار',
        'order': 3,
    },
    'tags': [
        'تحلیل بازار املاک',
        'Compare Dataset',
        'تحلیل بازار املاک بر اساس دیوار',
        'فایلینگ دیوار',
        'قیمت گذاری ملک',
        'ربات دیوار',
        'روند قیمت محله',
    ],
    'content': """
<p>هفته پیش به مالک گفتید: «میانه قیمت هر متر ۴۶ میلیون است.» امروز زنگ می‌زند: «پس چرا همسایه با ۴۴ فروخت؟» اگر snapshot هفته قبل را نگه نداشته باشید، فقط می‌توانید بگویید «نمی‌دانم» — و اعتبارتان می‌رود. <strong>Compare Dataset</strong> یعنی دو وضعیت بازار را کنار هم ببینید: چه آمده، چه رفته، قیمت کجا رفته، عمق بازار چقدر عوض شده.</p>

<p>پربازدیدترین مطلب وبلاگ ما <a href="/blog/tahlil-bazar-amlak-divar-gheymat-gozari/">تحلیل بازار املاک با داده واقعی دیوار</a> بود (بیش از هزار بازدید). آن مقاله «چطور یک بار تحلیل کنیم» را آموخت. Compare گام بعدی است: <strong>رصد مداوم</strong> — تبدیل تحلیل از پروژه یک‌باره به عادت ۱۵ دقیقه‌ای هفتگی.</p>

<p>در <a href="/">فایلینگ دیوار</a> Compare روی Dataset‌های import‌شده از <a href="/robot-divar/">ربات دیوار</a> یا <a href="/blog/import-excel-agahi-amlak/">اکسل</a> انجام می‌شود. خروجی Compare مستقیماً به <a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش قیمت مالک</a>، مذاکره خریدار و <a href="/real-estate-crm/">CRM</a> وصل می‌شود.</p>

<div class="mk-blog-tip-box">
    <strong>خلاصه برای عجله‌ای‌ها</strong>
    <p>هر هفته Export جدید با نام «[محله] — هفته XX» → import → Compare با هفته قبل (همان فیلتر!) → یادداشت: Δتعداد، Δمیانه، N حذف‌شده، N جدید → پیام کوتاه CRM برای مالک/خریدار فعال. زمان: ۱۵–۲۵ دقیقه.</p>
</div>

<h2>Compare Dataset دقیقاً چه می‌کند؟</h2>

<p>دو Dataset (دو snapshot زمانی از یک محله با فیلتر یکسان) را مقایسه می‌کنید و این deltaها را می‌بینید:</p>

<table>
    <thead>
        <tr><th>شاخص delta</th><th>معنی برای مشاور</th><th>اقدام پیشنهادی</th></tr>
    </thead>
    <tbody>
        <tr><td>آگهی جدید (+)</td><td>ورود فایل تازه به بازار</td><td>بررسی رقیب مالک / فرصت خریدار</td></tr>
        <tr><td>حذف‌شده (−)</td><td>فروش، انقضا، پایین آوردن از دیوار</td><td>سیگنال «قیمت منطقی فروخته»</td></tr>
        <tr><td>تغییر قیمت (token ثابت)</td><td>مالک یا بازار قیمت را جابه‌جا کرد</td><td>مذاکره / بازنگری گزارش</td></tr>
        <tr><td>Δ عمق بازار (تعداد کل)</td><td>شلوغ‌تر یا خلوت‌تر</td><td>فشار رقابت / فرصت</td></tr>
        <tr><td>Δ میانه / P25 / P75</td><td>روند قیمت هفتگی</td><td>به‌روزرسانی <a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش قیمت</a></td></tr>
    </tbody>
</table>

<h2>فرق Compare، Analyze و تحلیل بازار</h2>

<table>
    <thead>
        <tr><th>ابزار</th><th>سؤال</th><th>بازه زمانی</th><th>مطلب مرتبط</th></tr>
    </thead>
    <tbody>
        <tr><td>Analyze</td><td>الان بازار چطوره؟</td><td>یک لحظه</td><td><a href="/blog/tahlil-bazar-amlak-divar/">تحلیل بازار</a></td></tr>
        <tr><td>Compare</td><td>نسبت به قبل چه تغییر کرد؟</td><td>دو نقطه زمانی</td><td>همین مطلب</td></tr>
        <tr><td>تحلیل قیمت</td><td>میانه و پرت چطور محاسبه می‌شود؟</td><td>پایه Analyze</td><td><a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت</a></td></tr>
        <tr><td>گزارش مالک</td><td>ملک شما چنده؟</td><td>خروجی برای یک نفر</td><td><a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش قیمت</a></td></tr>
    </tbody>
</table>

<h2>چرا Compare هفتگی، نه ماهانه؟</h2>

<p>بازار املاک تهران و شهرهای بزرگ در مقیاس هفته عوض می‌شود — نه فقط ماه. ماهانه Compare برای گزارش سالانه خوب است؛ برای مذاکره روزانه دیر است.</p>

<ul>
    <li><strong>مالک با آگهی ۱۴ روزه:</strong> هر هفته ۱–۳٪ تغییر میانه در محله‌های فعال عادی است</li>
    <li><strong>خریدار جدی:</strong> فایلی که دیروز بود امروز حذف شده — Compare زودتر از دیوار manual می‌گوید</li>
    <li><strong>رقبای شما:</strong> مشاوری که «گزارش هفتگی محله» می‌فرستد در ذهن می‌ماند</li>
</ul>

<p>منبع داده: آگهی‌های عمومی <a href="https://divar.ir/s/tehran" rel="noopener noreferrer" target="_blank">دیوار</a> — همان منبعی که خریدار هم می‌بیند.</p>

<h2>پیش‌نیاز: نام‌گذاری و فیلتر یکسان</h2>

<p>Compare فقط وقتی معتبر است که:</p>
<ol>
    <li><strong>نام Dataset:</strong> «نارمک — فروش — ۹۰–۱۱۰m — هفته ۱۲» نه «export_final2»</li>
    <li><strong>فیلتر یکسان:</strong> همان متراژ، نوع، محله در هر دو هفته</li>
    <li><strong>پاکسازی duplicate:</strong> — <a href="/blog/hazf-agahi-tekrari-filing/">حذف تکراری</a></li>
    <li><strong>استخراج منظم:</strong> — <a href="/blog/estekhraj-agahi-divar-rahnama-kamel/">راهنمای استخراج</a></li>
</ol>

<h2>گردش کار هفتگی Compare — قدم‌به‌قدم</h2>

<h3>شنبه یا یکشنبه — جمع‌آوری (۱۰–۱۵ دقیقه)</h3>
<ol>
    <li>ربات دیوار: Export محله(های) اصلی کاری — <a href="/blog/filing-khodkar-amlak/">فایلینگ خودکار</a></li>
    <li>Import با نام هفته جاری</li>
    <li>Duplicate check</li>
</ol>

<h3>دوشنبه — Compare و یادداشت (۱۰ دقیقه)</h3>
<ol>
    <li>Compare: Dataset این هفته vs هفته قبل</li>
    <li>ثبت در یک فایل ثابت (یا یادداشت CRM):<br/>
    «نارمک W12: 87 فایل (−11), median 46.5M (−3%), removed 14, new 6»</li>
    <li>۲ observation انسانی: مثلاً «۳ فایل زیر 44M حذف شد — فروش سریع»</li>
</ol>

<h3>سه‌شنبه تا پنجشنبه — استفاده عملی (۵ دقیقه/روز)</h3>
<ul>
    <li>پیام CRM به مالک‌های فعال با خلاصه Compare</li>
    <li>به‌روزرسانی گزارش قیمت اگر Δمیانه &gt; ۲٪</li>
    <li>فیلتر فایل جدید برای خریدار — <a href="/blog/tatbiq-hooshmand-melk-moshtari/">تطبیق هوشمند</a></li>
</ul>

<div class="mk-blog-inline-cta">
    <strong>رصد بازار محله‌تان</strong>
    <p>دو Dataset بسازید، Compare کنید، گزارش هفتگی بدهید.</p>
    <p><a href="/accounts/register/" class="mk-blog-cta-btn mk-blog-cta-btn--primary">شروع رایگان</a>
    <a href="/real-estate-market-analysis/" class="mk-blog-cta-btn mk-blog-cta-btn--ghost">تحلیل بازار</a>
    <a href="/robot-divar/" class="mk-blog-cta-btn mk-blog-cta-btn--ghost">ربات دیوار</a></p>
</div>

<h2>تعبیر Compare برای مشتری — نمونه جملات</h2>

<h3>فروشنده (مالک)</h3>
<ul>
    <li>«این هفته ۱۲ فایل جدید وارد بازار شد — رقابت بیشتر شده.»</li>
    <li>«۱۴ آگهی مشابه از لیست خارج شد — احتمالاً با قیمت منطقی فروخته یا منقضی شده.»</li>
    <li>«میانه ۱.۵٪ پایین آمد — اگر ۲ هفته است آگهی دارید، بازنگری ۲–۳٪ پیشنهاد می‌کنم.»</li>
    <li>«عمق بازار از ۹۸ به ۸۷ رسید — هنوز شلوغ است اما نسبت به هفته قبل آرام‌تر.»</li>
</ul>

<h3>خریدار</h3>
<ul>
    <li>«فقط ۸ فایل در بودجه شما ماند — عمق کم، فرصت محدود.»</li>
    <li>«۵ فایل جدید زیر میانه اضافه شد — ارزش بازدید این هفته.»</li>
    <li>«۳ فایل محبوب هفته قبل حذف شد — نشانه حرکت بازار.»</li>
</ul>

<h3>سرمایه‌گذار / مشاور محتوا</h3>
<p>خلاصه Compare را در کانال، اینستاگرام یا وبلاگ محله منتشر کنید — منبع: Dataset خودتان. <a href="/blog/filing-hooshmand-amlak/">فایلینگ هوشمند</a> در بخش «سئو محتوا با داده واقعی» توضیح داده شده.</p>

<h2>Compare در زنجیره کار مشاور</h2>

<p>Compare وسط زنجیره است:</p>
<ol>
    <li><a href="/blog/estekhraj-agahi-divar-rahnama-kamel/">استخراج</a> → ۲. <a href="/blog/hazf-agahi-tekrari-filing/">پاکسازی</a> → ۳. Analyze → ۴. <strong>Compare</strong> → ۵. <a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش</a> → ۶. <a href="/blog/peigiri-moshtari-moshaver-amlak/">پیگیری CRM</a></li>
</ol>
<p>Compare را skip کنید، گزارش‌هایتان «عکس لحظه‌ای» می‌مانند بدون «روند» — مالک باهوش متوجه می‌شود.</p>

<h2>۸ اشتباه رایج Compare</h2>
<ul>
    <li><strong>نام Dataset نامشخص:</strong> بعد از ۴ هفته گیج می‌شوید</li>
    <li><strong>فیلتر متفاوت:</strong> هفته قبل ۸۰–۱۰۰m، این هفته ۷۰–۱۲۰m — delta غلط</li>
    <li><strong>Compare روی Dataset کثیف:</strong> duplicate → fake «جدید»</li>
    <li><strong>نادیده گرفتن حذف‌شده‌ها:</strong> کاهش تعداد = سیگنال فروش</li>
    <li><strong>فقط عدد، بدون action:</strong> Compare برای CRM و گزارش است</li>
    <li><strong>Compare ماهانه برای بازار داغ:</strong> دیر است</li>
    <li><strong>عدم ثبت یادداشت:</strong> هفته بعد «فکر کنم پایین بود»</li>
    <li><strong>Compare بدون Analyze پایه:</strong> اول <a href="/blog/tahlil-bazar-amlak-divar/">تحلیل بازار</a> را یاد بگیرید</li>
</ul>

<h2>مثال واقعی: نارمک — دو هفته</h2>

<table>
    <thead>
        <tr><th>شاخص</th><th>هفته ۱۱</th><th>هفته ۱۲</th><th>Δ</th></tr>
    </thead>
    <tbody>
        <tr><td>تعداد فایل</td><td>98</td><td>87</td><td>−11</td></tr>
        <tr><td>میانه / متر</td><td>48M</td><td>46.5M</td><td>−3.1%</td></tr>
        <tr><td>حذف‌شده (token)</td><td>—</td><td>14</td><td>—</td></tr>
        <tr><td>جدید</td><td>—</td><td>6</td><td>—</td></tr>
    </tbody>
</table>

<p>اقدام: پیام به ۲ مالک فعال — «بازار کمی نرم‌تر؛ پیشنهاد بازنگری ۲–۳٪ برای فروش سریع.» یکی قرارداد با قیمت بازنگری‌شده بست.</p>

<h2>مثال ۲: خریدار پاسداران — فرصت محدود</h2>
<p>Compare نشان داد: بودجه ۳.۸ میلیارد، هفته قبل ۱۱ فایل → این هفته ۶ فایل (−۵ حذف). پیام: «۵ فایل از بازار رفت؛ ۶ گزینه مانده — این هفته بازدید اولویت‌دار.» خریدار همان هفته بازدید رفت.</p>

<h2>مدیر آژانس: Compare تیمی</h2>

<table>
    <thead>
        <tr><th>نقش</th><th>مسئولیت</th><th>KPI</th></tr>
    </thead>
    <tbody>
        <tr><td>مسئول Dataset</td><td>Export + Compare + ۵ خط خلاصه</td><td>هر دوشنبه قبل ۱۰ صبح</td></tr>
        <tr><td>مشاور فروش</td><td>ارسال خلاصه به مالک/خریدار CRM</td><td>≥ ۵ پیام/هفته</td></tr>
        <tr><td>مدیر</td><td>بررسی Δمیانه محله‌های اصلی</td><td>جلسه ۱۵ دقیقه</td></tr>
    </tbody>
</table>

<p>جزئیات تیم: <a href="/blog/modiriyat-ajans-amlak-crm/">مدیریت آژانس با CRM</a>. Dataset مشترک: <a href="/blog/bank-file-mantaghe-amlak/">بانک فایل منطقه‌ای</a>.</p>

<h2>Compare و ابزارهای تکمیلی</h2>
<ul>
    <li><strong>Map Pro / نقشه:</strong> — <a href="/real-estate-market-analysis/">تحلیل بازار</a> برای دید جغرافیایی</li>
    <li><strong>Value Score:</strong> اولویت فایل جدید برای ارسال</li>
    <li><strong>اپ موبایل:</strong> — <a href="/blog/app-android-filing-divar-moshaver/">CRM موبایل</a> برای پیام Compare در محل</li>
    <li><strong>قیف فروش:</strong> — <a href="/blog/ghif-forush-moshaver-amlak/">مرحله مذاکره</a> با داده Compare</li>
</ul>

<h2>برنامه ۴ هفته‌ای — عادت Compare</h2>
<p><strong>هفته ۱:</strong> فقط Export + نام‌گذاری.<br/>
<strong>هفته ۲:</strong> اولین Compare + یادداشت ۳ خط.<br/>
<strong>هفته ۳:</strong> پیام CRM به ۳ مشتری فعال.<br/>
<strong>هفته ۴:</strong> یک پست محتوا با خلاصه Compare.<br/>
اگر هفته ۴ بدون فکر Compare می‌زنید، عادت ساخته شده.</p>

<h2>ملاحظات</h2>
<ul>
    <li>Compare روی آگهی عمومی است — معاملات خصوصی بدون آگهی در delta نیست</li>
    <li>رعایت <a href="https://divar.ir/terms" rel="noopener noreferrer" target="_blank">قوانین دیوار</a></li>
    <li>delta کوچک (&lt;۱٪) ممکن است نویز باشد — با ۲–۳ هفته روند تأیید کنید</li>
</ul>

<h2>مطالب مرتبط</h2>
<ul>
    <li><a href="/blog/tahlil-bazar-amlak-divar-gheymat-gozari/">تحلیل بازار با داده واقعی دیوار</a></li>
    <li><a href="/blog/tahlil-bazar-amlak-divar/">تحلیل بازار بر اساس دیوار</a></li>
    <li><a href="/blog/gozaresh-gheymat-malek-dade-divar/">گزارش قیمت به مالک</a></li>
    <li><a href="/blog/gardesh-kar-roozane-moshaver-amlak/">گردش کار روزانه مشاور</a></li>
    <li><a href="/blog/moghayese-dasti-vs-robot-divar/">دستی vs ربات</a></li>
</ul>

<h2>جمع‌بندی</h2>
<p><strong>Compare Dataset</strong> تحلیل بازار را از «یک بار خواندم» به «هر هفته می‌دانم چه خبر است» تبدیل می‌کند. ۱۵–۲۵ دقیقه در هفته — اعتبار حرفه‌ای، مذاکره بهتر، نرخ بستن بالاتر.</p>
<p><em>نویسنده: <a href="/author/hossein-qashqaeii/">حسین قشقایی</a> — <a href="/">فایلینگ دیوار</a>.</em></p>

<h2>سوالات متداول</h2>

<h3>چند Dataset نگه دارم؟</h3>
<p>حداقل ۲ (جاری + قبل)； ایده‌آل ۴–۸ هفته برای روند. قدیمی‌تر را آرشیو یا حذف کنید.</p>

<h3>Compare بدون ربات ممکن است؟</h3>
<p>بله — دو Export دستی. ربات زمان <a href="/blog/estekhraj-agahi-divar-rahnama-kamel/">استخراج</a> را کم می‌کند.</p>

<h3>فرق Compare با Analyze؟</h3>
<p>Analyze یک snapshot؛ Compare delta بین دو snapshot.</p>

<h3>محله کم‌فایل — Compare معتبر است؟</h3>
<p>اگر هر هفته &lt;۲۰ فایل، دو محله هم‌جوار با برچسب یا بازه ۲ هفته‌ای Compare کنید.</p>

<h3>Compare را به مشتری نشان می‌دهید؟</h3>
<p>خلاصه انسانی کافی است؛ اسکرین Compare برای مالک جدی عالی است.</p>

<h3>با Excel هم می‌شود؟</h3>
<p>بله — import به Dataset؛ Compare در میزکار. <a href="/blog/import-excel-agahi-amlak/">راهنمای import</a>.</p>

<h3>CRM رایگان؟</h3>
<p>بله — <a href="/blog/crm-amlak-raygan-rahnama/">CRM رایگان</a>.</p>

<h3>نویسنده؟</h3>
<p><a href="/author/hossein-qashqaeii/">حسین قشقایی</a>.</p>
""",
}
