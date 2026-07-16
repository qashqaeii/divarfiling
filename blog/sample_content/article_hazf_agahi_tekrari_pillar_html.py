"""Pillar Article — حذف آگهی تکراری دیوار / بانک فایل تمیز."""

CONTENT = r'''<p>جمعه شب بود. مشاور Dataset «سعادت‌آباد فروش» را باز کرد: <strong>۴۸۷ آگهی</strong>. خوشحال شد — «بانک فایلم قویه!» هفته بعد تحلیل قیمت زد: میانه عجیب بود. نقشه شلوغ و گیج‌کننده. مشتری گفت: «این فایل رو دیروز از مشاور دیگه هم گرفتم — همونه!»</p>

<p>مشکل از کمبود آگهی نبود — از <strong>آگهی تکراری دیوار</strong> بود. همان ملک چند بار در بانک فایل شما نشسته: یک بار import دوباره، یک بار همان token دو ردیف، یا پنج مشاور مختلف برای یک واحد — و شما فکر می‌کنید بازار ۵۰۰ فایل دارد در حالی که شاید ۲۸۰ فایل واقعی باشد.</p>

<p>این راهنما برای همان لحظه‌ای است که می‌پرسید چرا <strong>بانک فایل دو برابر بزرگ‌تر</strong> به نظر می‌رسد و چطور در <a href="/real-estate-filing/">فایلینگ دیوار</a> تکراری‌ها را پیدا و حذف کنید — بدون از دست دادن فایل واقعی.</p>

<p>من <a href="/author/hossein-qashqaeii/">حسین قشقایی</a>، سال‌ها دیده‌ام مشاورانی که با عدد بزرگ بانک فایل به مشتری فخر می‌فروشند، ولی نصفش تکراری یا مشاور پنهان است. اینجا شفاف می‌گوییم تکراری یعنی چه، سیستم چطور جلوگیری می‌کند، و شما چه کار هفتگی باید بکنید.</p>

<div class="mk-blog-tip-box">
    <strong>خلاصه برای عجله‌ای‌ها</strong>
    <p>هر آگهی دیوار یک <strong>token</strong> (شناسه یکتا) دارد. import مجدد همان فایل = به‌روزرسانی، نه ردیف جدید. فیلتر «تکراری» در Dataset ردیف‌هایی با token تکراری را نشان می‌دهد. برای تمیز کردن بانک: حذف مشاور پنهان + فیلتر تکراری + یک Dataset per محله.</p>
</div>

<h2>چرا بانک فایل «دو برابر» به نظر می‌رسد؟</h2>

<table>
    <thead>
        <tr>
            <th>علت</th>
            <th>چه می‌بینید؟</th>
            <th>راه‌حل</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>import دوباره بدون merge</td>
            <td>همان token چند ردیف</td>
            <td>فیلتر تکراری + حذف اضافه‌ها</td>
        </tr>
        <tr>
            <td>چند مشاور، یک واحد</td>
            <td>۵ آگهی مشابه، token متفاوت</td>
            <td>فیلتر <a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">مالک واقعی</a> یا حذف مشاور</td>
        </tr>
        <tr>
            <td>Dataset کل شهر</td>
            <td>هزاران ردیف بی‌معنی</td>
            <td>تقسیم به محله</td>
        </tr>
        <tr>
            <td>اکسل بدون token</td>
            <td>import تکراری ناشناخته</td>
            <td>ربات دیوار یا ستون شناسه</td>
        </tr>
        <tr>
            <td>آگهی قدیمی + جدید</td>
            <td>قیمت عوض شده، دو نسخه</td>
            <td>import مجدد — سیستم token را update می‌کند</td>
        </tr>
    </tbody>
</table>

<h2>تکراری فنی vs تکراری بازار — فرق مهم</h2>

<p><strong>تکراری فنی:</strong> همان آگهی دیوار (همان token) دو بار در Dataset شماست — مثلاً دو بار Excel یکسان import کرده‌اید. این را فایلینگ با فیلتر «تکراری» نشان می‌دهد و در import بعدی <strong>اضافه نمی‌کند</strong>.</p>

<p><strong>تکراری بازار:</strong> یک آپارتمان واقعی، پنج مشاور مختلف آگهی زده — هر کدام token جدا. این تکراری فنی نیست؛ ولی برای بانک فایل شما «نویز» است. راه‌حل: <strong>حذف مشاور</strong>، <strong>حذف مشاور پنهان</strong>، یا نگه داشتن فقط <strong>مالک واقعی</strong>.</p>

<div class="mk-blog-warning-box">
    <strong>اشتباه رایج</strong>
    <p>فکر نکنید حذف تکراری token = حذف همه آگهی‌های مشابه یک واحد. برای آن باید فیلتر آگهی‌دهنده و قضاوت مشاور را هم بکار ببرید.</p>
</div>

<h2>فایلینگ دیوار چطور از تکراری جلوگیری می‌کند؟</h2>

<p>وقتی فایل را دوباره import می‌کنید (همان Dataset یا همان نام فایل):</p>
<ol>
    <li>سیستم <strong>token</strong> هر ردیف را می‌خواند</li>
    <li>اگر token از قبل در Dataset هست → <strong>به‌روزرسانی</strong> قیمت، متراژ، توضیحات (نه ردیف جدید)</li>
    <li>اگر token جدید است → اضافه می‌شود</li>
    <li>اگر همه تکراری باشند → پیام «همه آگهی‌ها تکراری بودند»</li>
</ol>

<p>یعنی ریتم درست: هر هفته همان محله را با <a href="/robot-divar/">ربات دیوار</a> بگیرید و import کنید — بانک فایل <strong>تازه می‌شود</strong> بدون انباشت ردیف تکراری.</p>

<h2>فیلتر «تکراری» در جدول Dataset</h2>

<p>در صفحه Dataset، نوار فیلتر بالای جدول:</p>
<ul>
    <li>چک‌باکس <strong>تکراری</strong> را بزنید</li>
    <li>فقط آگهی‌هایی که <strong>token آن‌ها بیش از یک بار</strong> در همان Dataset آمده نمایش داده می‌شوند</li>
    <li>معمولاً علت: import اشتباه، ادغام دستی فایل‌ها، یا باگ قدیمی قبل از merge خودکار</li>
</ul>

<p>کار عملی: یکی از ردیف‌های تکراری را نگه دارید (معمولاً جدیدتر با قیمت به‌روز)، بقیه را حذف کنید.</p>

<h2>حذف گروهی — مشاور و مشاور پنهان</h2>

<p>در صفحه Dataset دکمه‌های اختصاصی دارید:</p>

<table>
    <thead>
        <tr>
            <th>عملیات</th>
            <th>چند تا حذف می‌شود؟</th>
            <th>کی بزنم؟</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>حذف مشاورین</td>
            <td>همه آگهی‌های رسمی مشاور/آژانس</td>
            <td>بانک فایل فقط مالک/شخصی می‌خواهید</td>
        </tr>
        <tr>
            <td>حذف مشاور پنهان</td>
            <td>شخصی‌های مشکوک در متن</td>
            <td>تمیزکاری بعد از استخراج</td>
        </tr>
        <tr>
            <td>حذف گروهی انتخاب‌شده</td>
            <td>ردیف‌هایی که تیک زده‌اید</td>
            <td>بعد از فیلتر تکراری</td>
        </tr>
    </tbody>
</table>

<p>قبل از حذف، آمار بالای صفحه را ببینید — مثلاً «۱۲۳ مشاور، ۴۵ مشاور پنهان، ۲۰۱ مالک واقعی».</p>

<div class="mk-blog-inline-cta">
    <strong>بانک فایل تمیز = تحلیل درست</strong>
    <p>یک Dataset محله را باز کنید، فیلتر تکراری و حذف مشاور پنهان را امتحان کنید.</p>
    <a href="/real-estate-filing/">شروع فایلینگ املاک</a>
</div>

<h2>چرا تکراری به Value Score و نقشه آسیب می‌زند؟</h2>

<ul>
    <li><strong>میانه قیمت:</strong> همان ملک سه بار → وزن غلط در محاسبه</li>
    <li><strong>Value Score:</strong> هم‌رده‌ها inflate می‌شوند</li>
    <li><strong>نقشه:</strong> سه نقطه روی یک خانه — <a href="/blog/map-pro-naghshe-amlak-divar-tahlil-mahalle-rahnama/">Map Pro</a> گمراه‌کننده</li>
    <li><strong>تطبیق هوشمند:</strong> یک فایل سه بار به مشتری پیشنهاد می‌شود</li>
    <li><strong>اعتبار:</strong> مشتری می‌فهمد لیست شما کپی است</li>
</ul>

<h2>جدول تصمیم: چه زمانی چه پاکسازی؟</h2>

<table>
    <thead>
        <tr>
            <th>وضعیت بانک فایل</th>
            <th>اقدام اول</th>
            <th>اقدام دوم</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>تازه import کردم</td>
            <td>آمار مشاور/مالک را ببین</td>
            <td>حذف مشاور پنهان (اختیاری)</td>
        </tr>
        <tr>
            <td>عدد خیلی بزرگ است</td>
            <td>فیلتر تکراری</td>
            <td>حذف ردیف‌های اضافه</td>
        </tr>
        <tr>
            <td>مشتری فقط مالک می‌خواهد</td>
            <td>حذف مشاور + مشاور پنهان</td>
            <td>فیلتر مالک واقعی</td>
        </tr>
        <tr>
            <td>تحلیل قیمت می‌خواهم</td>
            <td>تمیزکاری کامل</td>
            <td>Dataset فقط یک محله</td>
        </tr>
        <tr>
            <td>هفته‌ای یک بار</td>
            <td>import مجدد از ربات</td>
            <td>merge خودکار — بدون ردیف تکراری token</td>
        </tr>
    </tbody>
</table>

<h2>سناریو ۱: import دوباره — ۴۸۷ به ۲۶۱</h2>

<p><strong>خانم احمدی</strong> ماه پیش ۴۸۷ آگهی import کرده بود. دوباره همان فایل را انداخته — بدون اینکه بداند merge می‌شود. فیلتر تکراری: ۲۲۶ ردیف token تکراری! علت: قبلاً دو Dataset مختلف از یک محله ساخته و بعد ادغام دستی کرده بود.</p>
<ol>
    <li>فیلتر تکراری → انتخاب همه → حذف قدیمی‌ترها</li>
    <li>حذف مشاور پنهان → ۸۹ ردیف کمتر</li>
    <li>نتیجه: ۲۶۱ فایل قابل اتکا — تحلیل قیمت منطقی شد</li>
</ol>

<h2>سناریو ۲: مدیر آژانس — KPI واقعی</h2>

<p>آژانس به مشاوران می‌گفت «هر کدام ۳۰۰ فایل داشته باشید». بعد فهمیدند ۴۰٪ مشاور و تکراری است. قانون جدید: «تعداد مؤثر = بعد از حذف مشاور و تکراری.» کیفیت تماس بالا رفت.</p>

<h2>سناریو ۳: Excel قدیمی بدون token</h2>

<p>مشاور ۳ سال اکسل دارد — ستون شناسه ندارد. import می‌کند؛ هر بار ردیف جدید. راه‌حل: یک بار با <a href="/robot-divar/">ربات</a> همان محله را بگیرد (با token)، Dataset جدید بسازد، اکسل قدیمی را آرشیو کند. راهنما: <a href="/blog/import-excel-agahi-amlak/">ایمپورت Excel آگهی</a>.</p>

<h2>چک‌لیست هفتگی بانک فایل تمیز</h2>

<ol>
    <li>import مجدد محله‌های فعال (merge با token)</li>
    <li>فیلتر تکراری — اگر چیزی بود، حذف</li>
    <li>آمار مشاور پنهان — در صورت نیاز حذف گروهی</li>
    <li>یک Dataset per محله — نه کل تهران در یک فایل</li>
    <li>ستون token در export ربات پر است؟</li>
    <li>قبل از گزارش به مالک، تعداد «مؤثر» را بگویید نه خام</li>
</ol>

<h2>اشتباهات رایج</h2>

<ul>
    <li><strong>شمارش خام:</strong> «۵۰۰ فایل دارم» — بدون تمیزکاری</li>
    <li><strong>Datasetهای هم‌پوشان:</strong> سه فایل سعادت‌آباد جدا — بدون دلیل</li>
    <li><strong>حذف تکراری token و فراموش مشاور:</strong> هنوز نویز زیاد</li>
    <li><strong>عدم به‌روزرسانی هفتگی:</strong> آگهی مرده انباشته می‌شود</li>
    <li><strong>ارسال لیست ۵۰ تایی:</strong> مشتری تکراری می‌بیند — اعتماد می‌رود</li>
</ul>

<h2>جمع‌بندی</h2>

<p><strong>حذف آگهی تکراری دیوار</strong> فقط یک دکمه نیست — عادت نگهداری بانک فایل است. token یکتا، import هوشمند، فیلتر تکراری، حذف مشاور پنهان — تا بانک فایل شما <strong>واقعاً</strong> بزرگ باشد، نه فقط روی کاغذ.</p>

<div class="mk-blog-inline-cta">
    <strong>فایلینگ + CRM</strong>
    <p>بانک تمیز → تحلیل درست → پیشنهاد سریع به مشتری.</p>
    <a href="/blog/bank-file-mantaghe-amlak/">بانک فایل منطقه‌ای</a>
</div>

<p>مطالب مرتبط: <a href="/blog/bank-file-mantaghe-amlak/">بانک فایل املاک</a> · <a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">مالک واقعی</a> · <a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">Value Score</a> · <a href="/blog/map-pro-naghshe-amlak-divar-tahlil-mahalle-rahnama/">نقشه املاک</a> · <a href="/blog/chetor-agahi-divar-download/">دانلود آگهی دیوار</a></p>

<p><em>نویسنده: <a href="/author/hossein-qashqaeii/">حسین قشقایی</a> — سازنده فایلینگ دیوار. merge خودکار import را برای جلوگیری از انباشت تکراری طراحی کردم؛ تمیزکاری هفتگی همچنان به عادت مشاور بستگی دارد.</em></p>

<section class="blog-faq" itemscope itemtype="https://schema.org/FAQPage">
    <h2>سوالات متداول — آگهی تکراری دیوار</h2>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چرا بانک فایل من بزرگ‌تر از واقعیت است؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">معمولاً به‌خاطر token تکراری در import، چند مشاور برای یک واحد، یا Datasetهای هم‌پوشان. فیلتر تکراری و حذف مشاور/مشاور پنهان را بزنید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">token آگهی دیوار چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">شناسه یکتای هر آگهی در دیوار. ربات و import فایلینگ آن را ذخیره می‌کند — پایه merge و تشخیص تکراری فنی.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">فیلتر تکراری در فایلینگ کجاست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">صفحه Dataset → نوار فیلتر بالای جدول → چک‌باکس «تکراری». فقط ردیف‌هایی که token آن‌ها بیش از یک بار در همان Dataset است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">import مجدد ردیف تکراری اضافه می‌کند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">خیر — اگر token موجود باشد، همان ردیف به‌روز می‌شود (قیمت، متراژ و...). فقط tokenهای جدید اضافه می‌شوند.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">تفاوت تکراری فنی و تکراری بازار چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">فنی = همان token دوبار. بازار = چند مشاور برای یک ملک با token مختلف — با حذف مشاور یا فیلتر مالک واقعی مدیریت می‌شود.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">حذف مشاور پنهان چه کمکی به بانک فایل می‌کند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">آگهی‌های شخصی مشکوک را یک‌جا حذف می‌کند — بانک فایل برای تماس مالک و تحلیل قیمت تمیزتر می‌شود. راهنما: <a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">مالک واقعی</a>.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">تکراری روی Value Score اثر دارد؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">بله. هم‌رده‌های تکراری میانه را منحرف می‌کنند. قبل از تحلیل، بانک را تمیز کنید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">Excel بدون ستون شناسه چه مشکلی دارد؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">هر import ممکن است ردیف جدید بسازد — حتی برای همان آگهی. از ربات با token استفاده کنید یا ستون شناسه اضافه کنید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چند وقت یکبار بانک فایل را تمیز کنم؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">محله فعال: هفتگی import + چک فیلتر تکراری. بعد از ادغام دستی Datasetها: حتماً فیلتر تکراری.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">آیا حذف تکراری فایل را از دیوار پاک می‌کند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">خیر. فقط از Dataset شما در میزکار حذف می‌شود — آگهی روی دیوار همچنان هست.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">بهترین ساختار Dataset برای جلوگیری از تکراری؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">یک Dataset per محله + نوع معامله (فروش/اجاره). از ساختن چند فایل هم‌پوشان برای همان محله پرهیز کنید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">export CSV/JSON بعد از تمیزکاری؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">بله. از جدول Dataset می‌توانید export بگیرید — بانک تمیز برای آرشیو یا اشتراک با تیم.</p>
        </div>
    </details>
</section>'''
