"""Pillar Article — نقشه املاک دیوار / Map Pro / تحلیل محله."""

CONTENT = r'''<p>مشتری می‌گوید: «آقا، سعادت‌آباد می‌خوام — ولی دقیقاً نمی‌دونم کدوم بخشش.» شما لیست ۱۲۰ آگهی را باز می‌کنید. قیمت‌ها قاطی‌پاتی. محله‌ها شبیه هم. کدام خیابان ارزان‌تر است؟ کجا فقط مشاور پنهان داریم؟ کجا مالک واقعی زیر بازار گذاشته؟ با جدول اکسل، مغزتان دود می‌کند.</p>

<p>یا بدتر: صبح برای بازدید می‌روید محله — بدون نقشه ذهنی از توزیع قیمت. سه خانه می‌بینید؛ دو تا overpriced بوده. وقت و بنزین رفته.</p>

<p>اینجا <strong>نقشه املاک دیوار</strong> فرق می‌کند — نه نقشه خود دیوار که فقط یک نقطه نشان می‌دهد، بلکه <strong>تحلیل مکانی کل آگهی‌های محله</strong> روی یک نقشه تعاملی. در میزکار فایلینگ دیوار به این قابلیت می‌گوییم <strong>Map Pro</strong> — نام داخلی محصول، نه چیزی که مشتری در گوگل جستجو می‌کند. شما دنبال این‌ها هستید: <strong>نقشه آگهی دیوار</strong>، <strong>تحلیل محله</strong>، <strong>نقشه قیمت ملک</strong> و جواب ساده: «بازار این محله روی نقشه چه شکلی است؟»</p>

<p>من <a href="/author/hossein-qashqaeii/">حسین قشقایی</a>، سازنده <a href="/real-estate-filing/">فایلینگ دیوار</a>، سال‌ها دیده‌ام مشاورانی که داده دارند ولی «نقشه ذهنی» ندارند — تصمیم دیر می‌گیرند یا اشتباه. این راهنمای مرجع را نوشتم تا بفهمید چطور Dataset محله را روی نقشه باز کنید، هر حالت نمایش چه می‌گوید، و چطور برای مشتری، مالک یا گزارش آژانس ازش خروجی بگیرید.</p>

<div class="mk-blog-tip-box">
    <strong>خلاصه برای عجله‌ای‌ها</strong>
    <p>از صفحه Dataset دکمه «نقشه» را بزنید. هزاران آگهی با مختصات روی نقشه می‌آیند. فیلتر مالک واقعی / مشاور، حالت «بازار» (زیر/بالای بازار)، «رنگ قیمت»، «شبکه تراکم» — همه روی یک محله. برای گزارش، تصویر نقشه را export کنید.</p>
</div>

<h2>چرا تحلیل مکانی املاک برای مشاور حیاتی است؟</h2>

<ul>
    <li><strong>انتخاب خیابان درست:</strong> دو خیابان هم‌جوار، ۲۰٪ اختلاف قیمت — روی نقشه یک‌نگاهه</li>
    <li><strong>بازدید هدفمند:</strong> قبل از رفتن به محله، ببینید کجا فایل زیر بازار متمرکز است</li>
    <li><strong>گزارش به مشتری:</strong> «این ناحیه گران است، آن طرف ارزان‌تر» — با نقشه، نه حدس</li>
    <li><strong>شناخت رقابت:</strong> کجا مشاور پنهان انبوه است و کجا مالک واقعی</li>
    <li><strong>صرفه‌جویی وقت:</strong> به‌جای اسکرول ۲۰۰ ردیف، زوم روی همان بلوک</li>
</ul>

<div class="mk-blog-inline-cta">
    <strong>همین الان نقشه محله‌تان را ببینید</strong>
    <p>یک Dataset از محله کاری‌تان بسازید و دکمه نقشه را بزنید — توزیع واقعی بازار را می‌بینید.</p>
    <a href="/real-estate-filing/">شروع فایلینگ املاک</a>
</div>

<h2>نقشه دیوار vs نقشه فایلینگ — چه فرقی دارد؟</h2>

<table>
    <thead>
        <tr>
            <th>ویژگی</th>
            <th>نقشه داخل دیوار</th>
            <th>Map Pro فایلینگ دیوار</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>تعداد آگهی</td>
            <td>معمولاً یک آگهی</td>
            <td>کل Dataset — تا ۲۵۰۰ نقطه همزمان</td>
        </tr>
        <tr>
            <td>فیلتر مالک واقعی</td>
            <td>ندارد</td>
            <td>مشاور / مشاور پنهان / مالک واقعی</td>
        </tr>
        <tr>
            <td>رنگ بر اساس بازار</td>
            <td>ندارد</td>
            <td>حالت بازار + Value Score</td>
        </tr>
        <tr>
            <td>تراکم و شبکه</td>
            <td>ندارد</td>
            <td>حالت شبکه + خوشه‌بندی</td>
        </tr>
        <tr>
            <td>فیلتر قیمت و متراژ</td>
            <td>محدود</td>
            <td>فیلتر پیشرفته روی نقشه</td>
        </tr>
        <tr>
            <td>خروجی گزارش</td>
            <td>ندارد</td>
            <td>ذخیره تصویر نقشه</td>
        </tr>
        <tr>
            <td>منبع داده</td>
            <td>همان لحظه دیوار</td>
            <td>Dataset شما (ربات یا import)</td>
        </tr>
    </tbody>
</table>

<p>دیوار برای پیدا کردن یک آگهی خوب است. فایلینگ برای <strong>خواندن کل بازار یک محله</strong> — همان کاری که مشاور حرفه‌ای هر روز باید بکند.</p>

<h2>چطور به نقشه املاک دیوار در میزکار برسم؟</h2>

<ol>
    <li>آگهی‌های محله را با <a href="/robot-divar/">ربات استخراج دیوار</a> یا <a href="/blog/chetor-agahi-divar-download/">دانلود آگهی</a> وارد کنید</li>
    <li>یک <strong>Dataset</strong> بسازید (مثلاً «سعادت‌آباد فروش ۱۴۰۵»)</li>
    <li>از صفحه Dataset یا لیست آگهی‌ها، دکمه <strong>نقشه</strong> را بزنید</li>
    <li>فقط آگهی‌هایی که <strong>مختصات</strong> دارند روی نقشه می‌آیند — در هدر آمار «با مختصات» را می‌بینید</li>
    <li>اگر تعداد زیاد است، تا ۲۵۰۰ نقطه نمایش داده می‌شود (بقیه در آمار هستند)</li>
</ol>

<div class="mk-blog-warning-box">
    <strong>نکته فنی</strong>
    <p>اگر نقشه یا لایه‌ها لود نشد، گاهی به‌خاطر محدودیت شبکه tile است — VPN را روشن کنید و صفحه را رفرش کنید. این محدودیت مربوط به نقشه پایه (OSM/CARTO) است، نه داده آگهی‌های شما.</p>
</div>

<h2>آمار بالای نقشه — اولین نگاه به محله</h2>

<p>قبل از زوم، چهار عدد مهم را می‌بینید:</p>

<table>
    <thead>
        <tr>
            <th>آمار</th>
            <th>یعنی چی؟</th>
            <th>کاربرد</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>با مختصات</td>
            <td>چند آگهی موقعیت جغرافیایی دارند</td>
            <td>کیفیت پوشش نقشه</td>
        </tr>
        <tr>
            <td>مشاور</td>
            <td>حساب رسمی مشاور/آژانس</td>
            <td>قدرت رقابت آژانس‌ها</td>
        </tr>
        <tr>
            <td>مشاور پنهان</td>
            <td>شخصی با متن مشکوک</td>
            <td>رقبای پنهان — راهنما: <a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">مالک واقعی</a></td>
        </tr>
        <tr>
            <td>مالک واقعی</td>
            <td>شخصی بدون نشانه مشاور</td>
            <td>فایل تماس مستقیم</td>
        </tr>
    </tbody>
</table>

<h2>فیلتر نوع آگهی روی نقشه</h2>

<p>چهار دکمه سریع — همان منطق فیلتر لیست، ولی روی نقشه:</p>

<table>
    <thead>
        <tr>
            <th>فیلتر</th>
            <th>چه می‌بینید؟</th>
            <th>کی بزنم؟</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>همه</td>
            <td>کل بازار محله</td>
            <td>گزارش کلی، تحلیل تراکم</td>
        </tr>
        <tr>
            <td>مشاور</td>
            <td>فقط آژانس‌های رسمی</td>
            <td>همکاری یا رقابت آژانس</td>
        </tr>
        <tr>
            <td>مشاور پنهان</td>
            <td>شخصی‌های مشکوک</td>
            <td>شناخت رقبای پنهان</td>
        </tr>
        <tr>
            <td>مالک واقعی</td>
            <td>تماس مستقیم‌تر</td>
            <td>مشتری «بدون واسطه»</td>
        </tr>
    </tbody>
</table>

<h2>پنج حالت نمایش — زبان نقشه</h2>

<p>این بخش قلب <strong>تحلیل مکانی املاک</strong> است. هر حالت یک سؤال را جواب می‌دهد:</p>

<table>
    <thead>
        <tr>
            <th>حالت</th>
            <th>سؤالی که جواب می‌دهد</th>
            <th>رنگ‌ها / نمایش</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>نقاط</strong></td>
            <td>هر آگهی کجاست؟</td>
            <td>مارکر استاندارد — کلیک → popup جزئیات</td>
        </tr>
        <tr>
            <td><strong>بازار</strong></td>
            <td>کجا زیر بازار / متعارف / بالای بازار؟</td>
            <td>سبز / خاکستری / قرمز بر اساس <a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">Value Score</a></td>
        </tr>
        <tr>
            <td><strong>رنگ قیمت</strong></td>
            <td>گران‌ترین و ارزان‌ترین کجاست؟</td>
            <td>گرادیان از ارزان (آبی) تا گران (قرمز)</td>
        </tr>
        <tr>
            <td><strong>رهن کامل</strong> (اجاره)</td>
            <td>توزیع رهن کامل معادل کجاست؟</td>
            <td>فقط Dataset اجاره — معادل ودیعه+اجاره</td>
        </tr>
        <tr>
            <td><strong>شبکه</strong></td>
            <td>تراکم آگهی در کدام بلوک بیشتر است؟</td>
            <td>شبکه منطقه‌ای — مناطق داغ و سرد</td>
        </tr>
    </tbody>
</table>

<p>برای مشاور فروش، معمولاً «بازار» + فیلتر «مالک واقعی» ترکیب طلایی است. برای اجاره، «رهن کامل» + «رنگ قیمت».</p>

<h2>فیلتر پیشرفته روی نقشه</h2>

<p>دکمه «فیلتر پیشرفته» باز می‌شود:</p>
<ul>
    <li>حداقل / حداکثر قیمت (یا رهن کامل در اجاره) — میلیون تومان</li>
    <li>حداقل / حداکثر متراژ</li>
    <li>تعداد اتاق: ۱، ۲، ۳، ۴+</li>
    <li>تازگی: ۲۴ ساعت، ۷ روز، ۳۰ روز</li>
    <li>چک‌باکس «فقط زیر بازار»</li>
    <li>چک‌باکس «نمایش شعاع موقعیت تقریبی»</li>
</ul>

<p>ترکیب «فقط زیر بازار» + «مالک واقعی» + محدوده قیمت مشتری = نقشه‌ای که دقیقاً همان چیزی را نشان می‌دهد که صبح باید زنگ می‌زدید — بدون ۵۰ تماس بیهوده.</p>

<h2>موقعیت دقیق vs تقریبی — چرا شعاع مهم است؟</h2>

<p>دیوار گاهی موقعیت را <strong>تقریبی</strong> می‌دهد — یک دایره به‌جای نقطه دقیق. در Map Pro:</p>
<ul>
    <li>موقعیت دقیق → مارکر روی خانه</li>
    <li>موقعیت تقریبی → با فعال کردن «شعاع»، حلقه نمایش داده می‌شود</li>
</ul>

<p>قبل از بازدید حتماً چک کنید: اگر شعاع ۳۰۰ متری است، آدرس دقیق را از مالک بپرسید — نروید سر خیابان اشتباه.</p>

<h2>نوع نقشه (Basemap) — برای بازدید و گزارش</h2>

<table>
    <thead>
        <tr>
            <th>نوع</th>
            <th>بهترین کاربرد</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>شهری (Voyager)</td>
            <td>پیش‌فرض روزانه — خیابان و محله خوانا</td>
        </tr>
        <tr>
            <td>ماهواره / ترکیبی</td>
            <td>بازدید میدانی — ساختمان و کوچه واقعی</td>
        </tr>
        <tr>
            <td>روشن / تاریک</td>
            <td>اسکرین‌شات گزارش — تمیز برای ارائه</td>
        </tr>
        <tr>
            <td>توپوگرافی</td>
            <td>محله‌های شیب‌دار یا حاشیه شهر</td>
        </tr>
    </tbody>
</table>

<p>انتخاب نقشه در مرورگر ذخیره می‌شود — دفعه بعد همان لایه را می‌بینید.</p>

<h2>ابزارهای کنار نقشه</h2>

<ul>
    <li><strong>لیست:</strong> آگهی‌های فیلترشده کنار نقشه — کلیک = فوکوس روی نقطه</li>
    <li><strong>همه نقاط:</strong> زوم به کل Dataset</li>
    <li><strong>ذخیره تصویر:</strong> export نقشه برای واتساپ مشتری یا گزارش PDF</li>
    <li><strong>خوشه‌بندی:</strong> از تنظیمات میزکار — نقاط نزدیک در زوم کم، یکی می‌شوند</li>
    <li><strong>نقشه حرارتی:</strong> از تنظیمات میزکار (اختیاری) — تراکم با گرادیان رنگی</li>
</ul>

<h2>جدول تصمیم: کدام حالت نقشه را بزنم؟</h2>

<table>
    <thead>
        <tr>
            <th>هدف شما</th>
            <th>حالت + فیلتر</th>
            <th>خروجی</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>مشتری خریدار — فایل داغ</td>
            <td>بازار + مالک واقعی + فقط زیر بازار</td>
            <td>۳–۸ نقطه تماس‌پذیر</td>
        </tr>
        <tr>
            <td>قیمت‌گذاری مالک</td>
            <td>رنگ قیمت + همه آگهی‌ها</td>
            <td>مقایسه بصری با همسایه‌ها</td>
        </tr>
        <tr>
            <td>گزارش محله برای تیم</td>
            <td>شبکه + export تصویر</td>
            <td>اسلاید جلسه هفتگی</td>
        </tr>
        <tr>
            <td>بازدید امروز</td>
            <td>نقاط + ماهواره + لیست کنار نقشه</td>
            <td>مسیر بهینه در محله</td>
        </tr>
        <tr>
            <td>اجاره — رهن کامل</td>
            <td>رهن کامل + فیلتر متراژ</td>
            <td>نقاط در بودجه مشتری</td>
        </tr>
        <tr>
            <td>تحلیل رقابت</td>
            <td>مشاور + مشاور پنهان</td>
            <td>کجا آژانس‌ها غالب‌اند</td>
        </tr>
    </tbody>
</table>

<h2>سناریو ۱: مشتری می‌گوید «سعادت‌آباد، ولی نمی‌دونم کجا»</h2>

<p><strong>آقای کریمی</strong> بودجه ۵.۵ میلیارد، ۹۰ متری. مشاور Dataset «سعادت‌آباد فروش» را باز می‌کند:</p>
<ol>
    <li>نقشه → حالت <strong>رنگ قیمت</strong> — می‌بیند شمال محله گران‌تر است</li>
    <li>فیلتر قیمت تا ۵.۵ میلیارد + متراژ ۸۵–۱۰۰</li>
    <li>حالت <strong>بازار</strong> — نواحی سبز (زیر بازار) در جنوب‌غربی</li>
    <li>فیلتر <strong>مالک واقعی</strong> — ۶ نقطه باقی می‌ماند</li>
    <li>اسکرین‌شات + ۳ لینک برای مشتری: «این بخش‌ها ارزان‌تر و مالک مستقیم»</li>
    <li>ظهر بازدید در همان بلوک — بدون گشتن کل سعادت‌آباد</li>
</ol>

<h2>سناریو ۲: جلسه مالک — «خونه من گرونه؟»</h2>

<p>مالک در بلوک A زندگی می‌کند. مشاور نقشه را با حالت بازار باز می‌کند: بلوک A پر از قرمز (بالای بازار)، بلوک B هم‌جوار سبزتر. با export تصویر به مالک نشان می‌دهد: «همسایه‌ها ۱۰٪ ارزان‌تر گذاشته‌اند — یا ویژگی خاص دارید، یا قیمت را بازنگری کنیم.» ترکیب با <a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت</a> قوی‌تر است.</p>

<h2>سناریو ۳: مدیر آژانس — گزارش هفتگی محله‌ها</h2>

<p>هر دوشنبه سه Dataset: جردن، ونک، پاسداران. حالت <strong>شبکه</strong> + آمار مشاور/مالک. می‌بیند در ونک ۶۲٪ مشاور پنهان است — تیم را به جردن هدایت می‌کند که مالک واقعی بیشتر دارد. گزارش در <a href="/blog/modiriyat-ajans-amlak-crm/">CRM آژانس</a> ثبت می‌شود.</p>

<h2>ترکیب Map Pro با سایر ابزارهای فایلینگ</h2>

<table>
    <thead>
        <tr>
            <th>ابزار</th>
            <th>+ نقشه</th>
            <th>نتیجه</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">Value Score</a></td>
            <td>حالت بازار</td>
            <td>نقشه زیر/بالای بازار</td>
        </tr>
        <tr>
            <td><a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">مالک واقعی</a></td>
            <td>فیلتر روی نقشه</td>
            <td>نقاط تماس مستقیم</td>
        </tr>
        <tr>
            <td><a href="/robot-divar/">ربات دیوار</a></td>
            <td>Dataset تازه</td>
            <td>نقشه به‌روز</td>
        </tr>
        <tr>
            <td><a href="/blog/bank-file-mantaghe-amlak/">بانک فایل</a></td>
            <td>یک Dataset per محله</td>
            <td>کتابخانه نقشه‌ای</td>
        </tr>
        <tr>
            <td><a href="/real-estate-crm/">CRM</a></td>
            <td>بازدید از نقشه → پرونده</td>
            <td>پیگیری مکان‌محور</td>
        </tr>
        <tr>
            <td><a href="/blog/moghayese-gheymat-melk-divar/">مقایسه قیمت</a></td>
            <td>دو نقطه روی نقشه</td>
            <td>انتخاب بهتر برای مشتری</td>
        </tr>
    </tbody>
</table>

<h2 id="checklist">چک‌لیست قبل از اتکا به نقشه</h2>

<ol>
    <li>Dataset حداقل ۳۰ آگهی با مختصات دارد؟</li>
    <li>داده هفته اخیر است؟</li>
    <li>نوع معامله (فروش/اجاره) درست انتخاب شده؟</li>
    <li>برای بازدید، موقعیت دقیق است یا تقریبی؟</li>
    <li>حالت «بازار» را با <a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">Value Score</a> در لیست هم چک کردید؟</li>
    <li>برای مشتری گفته‌اید «بر اساس آگهی‌های فعلی دیوار»؟</li>
    <li>اسکرین‌شات export برای ارائه آماده است؟</li>
</ol>

<h2>محدودیت‌ها — صادقانه</h2>

<table>
    <thead>
        <tr>
            <th>محدودیت</th>
            <th>اثر</th>
            <th>راه‌حل</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>آگهی بدون مختصات</td>
            <td>روی نقشه نیست</td>
            <td>در لیست Dataset ببینید — شاید ۲۰٪ بدون موقعیت</td>
        </tr>
        <tr>
            <td>سقف ۲۵۰۰ نقطه</td>
            <td>Dataset خیلی بزرگ — نمونه</td>
            <td>فیلتر محله یا قیمت تنگ‌تر</td>
        </tr>
        <tr>
            <td>موقعیت تقریبی دیوار</td>
            <td>خطای چندصد متری</td>
            <td>شعاع را ببینید + تأیید تماس</td>
        </tr>
        <tr>
            <td>tile نقشه</td>
            <td>گاهی لود نمی‌شود</td>
            <td>VPN + رفرش</td>
        </tr>
        <tr>
            <td>Dataset قدیمی</td>
            <td>نقشه گمراه‌کننده</td>
            <td>هفتگی به‌روزرسانی با ربات</td>
        </tr>
    </tbody>
</table>

<h2>اشتباهات رایج</h2>

<ul>
    <li><strong>فقط لیست، بدون نقشه:</strong> الگوی مکانی را از دست می‌دهید</li>
    <li><strong>نقشه بدون فیلتر مالک:</strong> ساعت‌ها تماس با مشاور پنهان</li>
    <li><strong>اعتماد به نقطه تقریبی:</strong> بازدید اشتباه</li>
    <li><strong>Dataset کل تهران:</strong> نقشه شلوغ و بی‌معنی — محله را جدا کنید</li>
    <li><strong>export بدون توضیح:</strong> مشتری نمی‌فهمد سبز یعنی زیر بازار</li>
    <li><strong>نادیده گرفتن حالت شبکه:</strong> تراکم را نمی‌بینید</li>
</ul>

<div class="mk-blog-tip-box">
    <strong>نکته حرفه‌ای</strong>
    <p>قبل از جلسه با مالک یا مشتری، ۲ دقیقه نقشه را با حالت «بازار» باز کنید. یک جمله آماده دارید: «در این بلوک ۷ فایل مشابه دارید — ۴ تا زیر بازارند.»</p>
</div>

<h2>جمع‌بندی</h2>

<p><strong>نقشه املاک دیوار</strong> وقتی معنی دارد که همه آگهی‌های محله را با هم ببینید — نه تک‌تک در اپ دیوار. Map Pro در فایلینگ دیوار همان کار را با فیلتر مالک واقعی، Value Score روی نقشه، تراکم و export گزارش انجام می‌دهد.</p>

<p>برای مشاور یعنی بازدید هدفمند. برای مشتری یعنی اعتماد به انتخاب محله. برای آژانس یعنی گزارش داده‌محور.</p>

<div class="mk-blog-inline-cta">
    <strong>تحلیل بازار + نقشه</strong>
    <p>Dataset بسازید، نقشه را باز کنید، بازار محله را ببینید.</p>
    <a href="/real-estate-market-analysis/">تحلیل بازار املاک</a>
</div>

<p>مطالب مرتبط: <a href="/blog/tahlil-bazar-amlak-divar/">تحلیل بازار دیوار</a> · <a href="/blog/tahlil-gheymat-amlak-divar/">تحلیل قیمت</a> · <a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">ملک زیر بازار</a> · <a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">مالک واقعی</a> · <a href="/blog/bank-file-mantaghe-amlak/">بانک فایل</a> · <a href="/real-estate-filing/">فایلینگ املاک</a></p>

<p><em>نویسنده: <a href="/author/hossein-qashqaeii/">حسین قشقایی</a> — سازنده فایلینگ دیوار. Map Pro را برای مشاورانی طراحی کردم که می‌خواهند محله را «ببینند»، نه فقط بخوانند.</em></p>

<section class="blog-faq" itemscope itemtype="https://schema.org/FAQPage">
    <h2>سوالات متداول — نقشه املاک دیوار</h2>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">نقشه املاک دیوار در فایلینگ چطور کار می‌کند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">آگهی‌های Dataset شما که مختصات دارند روی نقشه تعاملی نمایش داده می‌شوند. از صفحه Dataset دکمه نقشه را بزنید. فیلتر، رنگ‌بندی بازار و export تصویر در همان صفحه است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">Map Pro یعنی چی؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">نام قابلیت نقشه پیشرفته داخل میزکار فایلینگ دیوار — شامل فیلتر مالک/مشاور، حالت بازار، رنگ قیمت، شبکه تراکم و ذخیره تصویر. برای جستجو معمولاً «نقشه املاک دیوار» یا «تحلیل محله» را تایپ می‌کنید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">تفاوت نقشه دیوار و نقشه فایلینگ چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">دیوار یک آگهی را نشان می‌دهد. فایلینگ کل Dataset محله را با فیلتر مالک واقعی، Value Score روی نقشه و تحلیل تراکم — برای مشاور و تحلیل بازار.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چرا بعضی آگهی‌ها روی نقشه نیستند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">آگهی بدون latitude/longitude در دیوار روی نقشه نمی‌آید. عدد «با مختصات» در هدر نقشه را ببینید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">حالت «بازار» روی نقشه یعنی چی؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">نقاط بر اساس Value Score رنگ می‌شوند: زیر بازار (سبز)، متعارف، بالای بازار (قرمز). راهنما: <a href="/blog/melk-zir-bazar-bala-bazar-value-score-rahnama/">ملک زیر بازار</a>.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چطور فقط مالک واقعی را روی نقشه ببینم؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">فیلتر «مالک واقعی» را بزنید. راهنمای تشخیص: <a href="/blog/tashkhis-malek-vaghei-divar-rahnama/">تشخیص مالک واقعی دیوار</a>.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">تحلیل مکانی املاک برای چه کسی مفید است؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">مشاور مستقل، تیم آژانس، سرمایه‌گذار و هر کسی که باید بداند در یک محله قیمت و تراکم آگهی کجا متمرکز است — قبل از بازدید یا قیمت‌گذاری.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چطور نقشه را برای مشتری بفرستم؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">دکمه ذخیره تصویر (دوربین) در نوار ابزار نقشه — اسکرین‌شات با فیلتر و حالت فعلی. همراه با توضیح کوتاه: سبز = زیر بازار، و غیره.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">موقعیت تقریبی دیوار روی نقشه چطور دیده می‌شود؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">در فیلتر پیشرفته «نمایش شعاع موقعیت تقریبی» را فعال کنید — حلقه دور نقطه نشان می‌دهد دقت موقعیت پایین است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">حداکثر چند آگهی روی نقشه نمایش داده می‌شود؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">تا ۲۵۰۰ نقطه همزمان برای سرعت و خوانایی. اگر Dataset بزرگ‌تر است، فیلتر محله یا قیمت بزنید یا آمار کل را در هدر ببینید.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">نقشه برای رهن و اجاره هم هست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">بله. Dataset اجاره حالت «رهن کامل» دارد — توزیع معادل ودیعه+اجاره روی نقشه.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">خوشه‌بندی نقشه چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">در زوم دور، نقاط نزدیک در یک خوشه جمع می‌شوند — از تنظیمات میزکار قابل فعال/غیرفعال است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">نقشه لود نمی‌شود — چه کنم؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">گاهی tile نقشه پایه (OSM/CARTO) نیاز به VPN دارد. VPN را روشن کنید و صفحه را رفرش کنید. داده آگهی‌های شما محلی است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">آیا در اپ موبایل هم نقشه هست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">نقشه کامل Map Pro در میزکار وب است؛ جزئیات ملک در اپ موقعیت را نشان می‌دهد. Dataset از همان حساب همگام است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">بهترین ترکیب فیلتر برای فایل زیر بازار روی نقشه؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">حالت بازار + فیلتر مالک واقعی + چک‌باکس «فقط زیر بازار» + محدوده قیمت مشتری.</p>
        </div>
    </details>
</section>'''
