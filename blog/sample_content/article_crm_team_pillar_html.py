"""Pillar Article — صفحه تیم CRM / مدیریت آژانس."""

CONTENT = r'''<p>دوشنبه ۸:۵۰. مدیر آژانس پنج‌نفره می‌خواهد بداند: چند سرنخ دیروز آمده؟ کی تخصیص نشده؟ کدام مشاور پیگیری معوق دارد؟ در مدل قدیمی، گروه واتساپ را باز می‌کند — چهل پیام، دو ویس، یک فوروارد بدون نام. نیم‌ساعت بعد هنوز مطمئن نیست. در مدل حرفه‌ای، همان لحظه <strong>صفحه تیم CRM</strong> را باز می‌کند — مسیر <code dir="ltr">/workspace/crm/team/</code> در میزکار فایلینگ دیوار — و در یک نگاه می‌بیند: ۳ سرنخ در صندوق، ۷ پیگیری معوق، ۱۲ معامله فعال، نرخ تبدیل ماه جاری.</p>

<p>این صفحه <strong>مرکز فرماندهی آژانس</strong> است — نه جایگزین CRM شخصی هر مشاور، بلکه لایه‌ای که مدیر، منشی و اعضا روی آن هماهنگ می‌شوند: تخصیص سرنخ، گزارش عملکرد، پیام و اطلاعیه داخلی، اهداف تیم، API و وب‌هوک، همگام‌سازی با دسکتاپ، و <strong>Agency TV</strong> روی مانیتور دفتر. این راهنما برای کسی است که می‌خواهد بداند هر تب چه می‌کند، هر <strong>نقش</strong> (مالک، مدیر، مشاور، منشی) چه می‌بیند، و چطور بدون قورت دادن حریم خصوصی مشتری، تیم را مدیریت کند.</p>

<p>من <a href="/author/hossein-qashqaeii/">حسین قشقایی</a>، این ماژول را بعد از شنیدن «مدیر همه پرونده‌ها را می‌خواهد ببیند» و «مشاور نمی‌خواهد شماره مشتریش لو برود» طراحی کردم — تعادل در همان URL تیم است.</p>

<div class="mk-blog-tip-box">
    <strong>خلاصه برای عجله‌ای‌ها</strong>
    <p><strong>صفحه تیم</strong> = آژانس مشترک در CRM. <strong>مالک/مدیر:</strong> داشبورد، گزارش کل تیم، inbox، تنظیمات، API. <strong>منشی:</strong> inbox و تخصیص سرنخ. <strong>مشاور:</strong> عملکرد شخصی، پیام و اطلاعیه — بدون دیدن پرونده‌های دیگران مگر با <strong>اشتراک صریح</strong>. داده مشتری پیش‌فرض خصوصی است.</p>
</div>

<h2>صفحه تیم CRM چیست؟</h2>

<p>وقتی در <a href="/real-estate-crm/">CRM فایلینگ دیوار</a> یک <strong>آژانس</strong> می‌سازید یا به آژانس موجود می‌پیوندید، صفحه تیم هاب مرکزی شما می‌شود. هر عضو با همان حساب قبلی کار می‌کند — مخاطبین و فایل‌های شخصی‌اش منتقل می‌شوند — ولی حالا زیر چتر یک سازمان با نام، شناسه (slug)، نقش و قوانین تخصیص سرنخ.</p>

<p>این صفحه جای «همه‌چیز مشترک» نیست. فلسفه طراحی این است: <strong>پیش‌فرض خصوصی، اشتراک آگاهانه</strong>. مشاور الف پرونده مشتری خودش را می‌بیند؛ مدیر به‌طور خودکار به آن دسترسی ندارد — فقط آمار تماس و بازدید در گزارش عملکرد. اگر مشاور فایل یا مخاطب را به هم‌تیمی بدهد، آن وقت — با حالت محرمانه یا مشارکتی — طرف دوم می‌بیند. جزئیات در <a href="/blog/eshterak-file-moshaveran-ajans-5-ghanoon-rahnama/">راهنمای اشتراک فایل تیم</a>.</p>

<h2>چهار نقش کاربری — چه کسی چه می‌بیند؟</h2>

<table>
    <thead>
        <tr>
            <th>نقش</th>
            <th>در یک جمله</th>
            <th>دسترسی‌های کلیدی صفحه تیم</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>مالک آژانس</strong></td>
            <td>سازنده فضای تیم — بالاترین سطح مدیریت</td>
            <td>همه تب‌های مدیر + مالکیت آژانس، TV، API، وب‌هوک، ممیزی</td>
        </tr>
        <tr>
            <td><strong>مدیر</strong></td>
            <td>مدیریت روزانه عملیات و اعضا</td>
            <td>داشبورد مدیریت، گزارش عملکرد تیم، inbox، تنظیمات، اهداف، همگام‌سازی</td>
        </tr>
        <tr>
            <td><strong>منشی</strong></td>
            <td>پذیرش سرنخ و تخصیص اولیه</td>
            <td>صندوق سرنخ، تخصیص به مشاور — بدون تنظیمات API و وب‌هوک</td>
        </tr>
        <tr>
            <td><strong>مشاور</strong></td>
            <td>کار میدانی — CRM شخصی خودش</td>
            <td>تب «عملکرد من»، اعضا (لیست)، پیام و اطلاعیه — نه inbox کل تیم</td>
        </tr>
    </tbody>
</table>

<p>تفاوت مهم: <strong>گزارش عملکرد کل تیم</strong> فقط برای مالک و مدیر است. مشاور نمودار رتبه‌بندی همکاران و مقایسه تفصیلی را در همان سطح نمی‌بیند — «عملکرد شخصی» با تماس، بازدید، معامله فعال و امتیاز دوره‌ای. انگیزه سالم بدون نظارت تهاجمی روی محتوای تماس‌ها.</p>

<h2>شروع کار — ایجاد، دعوت، پیوستن</h2>

<p>اگر هنوز آژانس ندارید، در همان صفحه تیم:</p>

<ol>
    <li><strong>ایجاد آژانس:</strong> نام بزنید — داده‌های فعلی CRM شما به آژانس وصل می‌شود</li>
    <li><strong>دعوت عضو:</strong> با شماره موبایل + انتخاب نقش (مشاور، منشی، مدیر) — طرف باید دعوت را بپذیرد</li>
    <li><strong>پیوستن:</strong> با شناسه slug که مدیر می‌دهد — درخواست عضویت تا تأیید مدیر معلق می‌ماند</li>
</ol>

<p>شناسه آژانس را در تنظیمات کپی کنید و به مشاور جدید بدهید — نه در گروه عمومی که رقیب هم ببیند.</p>

<h2>تب‌ها و امکانات — نقشه کامل صفحه تیم</h2>

<h3>۱. داشبورد مدیریت (Command) — فقط مالک/مدیر</h3>

<p>تب پیش‌فرض مدیر برای <strong>عملیات امروز</strong>، نه تحلیل عمیق. KPIهای زنده:</p>

<ul>
    <li>سرنخ‌های بدون تخصیص در صندوق</li>
    <li>پیگیری‌های معوق تیم</li>
    <li>معاملات فعال</li>
    <li>نرخ تبدیل دوره</li>
    <li>جمع کمیسیون معاملات بسته‌شده</li>
</ul>

<p>اگر سرنخ بیش از ۴۸ ساعت تخصیص نشده یا عضوی در دوره بدون فعالیت مانده، <strong>هشدار عملیاتی</strong> نمایش داده می‌شود. خروجی CSV گزارش، لینک مستقیم به inbox و Agency TV از همین تب در دسترس است. بازه ۷ / ۳۰ / ۹۰ روز قابل تعویض است.</p>

<h3>۲. گزارش عملکرد (Overview)</h3>

<p><strong>مدیر:</strong> جدول و نمودار مقایسه اعضا — مخاطب، فایل، تماس، بازدید، معامله بسته، معامله فعال، امتیاز و رتبه. برای جلسه هفتگی کوتاه و تشخیص گلوگاه — مثلاً بازدید زیاد ولی قرارداد کم.</p>

<p><strong>مشاور:</strong> کارت «عملکرد شخصی من» — همان شاخص‌ها فقط برای خودش. مشاور جدی از همین کارت برای خودارزیابی استفاده می‌کند؛ مدیر از نسخه تیمی.</p>

<h3>۳. صندوق سرنخ (Inbox) — مدیر و منشی</h3>

<p>مخاطبانی که به آژانس وصل شده‌اند ولی هنوز <strong>مشاور مسئول</strong> ندارند. منشی صبح inbox را باز می‌کند، پروفایل را می‌خواند، «تخصیص» می‌زند. سیاست ورود سرنخ در تنظیمات تعریف می‌شود:</p>

<ul>
    <li><strong>صندوق تیم:</strong> همه در inbox بمانند تا دستی تخصیص شوند</li>
    <li><strong>مالک آژانس:</strong> مستقیم به پرونده مالک</li>
    <li><strong>چرخشی:</strong> round robin بین مشاوران فعال</li>
</ul>

<p>راهنمای کامل: <a href="/blog/inbox-etelaie-ajans-whatsapp-rahnama/">Inbox و اطلاعیه داخلی</a>.</p>

<h3>۴. پیام‌های داخلی</h3>

<p>صندوق پیام آژانس — <strong>خصوصی</strong> بین دو نفر یا <strong>گروهی</strong> (broadcast) برای نقش‌های خاص. خوانده‌نشده شمارش می‌شود. ضمیمه با محدودیت نوع و حجم. جای گفت‌وگوی رسمی تیم — «این سرنخ را به کی بدهم؟» — نه جای اسپم مشتری. Real-time مثل تلگرام نیست؛ عمداً سبک و آرشیوشده در CRM.</p>

<h3>۵. اطلاعیه‌ها</h3>

<p>تابلو رسمی: عنوان، متن، سطح اهمیت (عادی تا فوری)، سنجاق، نقش هدف، تاریخ انتشار و انقضا، ضمیمه. مدیر می‌فهمد چه کسی «خواندم» زده. اطلاعیه مهم روی <a href="/blog/agency-tv-dashboard-ajans-amlak/">Agency TV</a> هم می‌آید — بدون نام مشتری.</p>

<h3>۶. اعضا (Members)</h3>

<p>لیست فعال، دعوت‌های معلق، درخواست‌های عضویت، تغییر نقش، حذف عضو. هر ردیف می‌تواند خلاصه عملکرد دوره را نشان دهد. دکمه «عضو جدید» از drawer دعوت با شماره.</p>

<h3>۷. همگام‌سازی (Sync) — مدیر</h3>

<p>خروجی و ورود JSON مخاطبین، فایل‌ها و معاملات — برای پشتیبان، مهاجرت، یا ابزار دسکتاپ. لاگ هر sync با آمار ثبت می‌شود. حالت agency برای کل تیم (با دسترسی مدیر) یا personal برای خود کاربر.</p>

<h3>۸. وب‌هوک (Webhooks) — مدیر</h3>

<p>اتصال رویدادهای CRM به سیستم خارجی: ثبت مخاطب، تخصیص، معامله جدید، بستن یا از دست رفتن معامله. برای فرم سایت، اتوماسیون مارکتینگ، یا داشبورد اختصاصی. تست وب‌هوک از پنل.</p>

<h3>۹. انتقال‌ها (Transfers)</h3>

<p>وقتی پرونده مشتری از یک مشاور به دیگری منتقل می‌شود — با لاگ: چه کسی، چه زمانی، از کی به کی. شفافیت برای کمیسیون و پیگیری. تفاوت با <strong>اشتراک</strong>: انتقال مسئولیت اصلی را عوض می‌کند.</p>

<h3>۱۰. تنظیمات — مدیر</h3>

<ul>
    <li>نام و هویت آژانس، slug عضویت</li>
    <li>سیاست توزیع سرنخ API</li>
    <li><strong>اهداف عملکرد:</strong> تماس، بازدید، یا معامله بسته — برای کل تیم یا هر مشاور، با بازه زمانی</li>
    <li>کلید API CRM — برای دریافت سرنخ از وب‌سایت (با امکان تجدید کلید)</li>
</ul>

<h3>۱۱. ممیزی (Audit) — مدیر</h3>

<p>تایم‌لاین رویدادهای مدیریتی: دعوت عضو، تغییر نقش، تخصیص سرنخ، sync، وب‌هوک. وقتی مشکلی پیش آمد — «چه کسی این مخاطب را assign کرد؟» — جواب اینجاست.</p>

<h3>۱۲. Agency TV — نمایش دفتر</h3>

<p>مسیر جدا: <code dir="ltr">/workspace/crm/team/tv/</code> — تمام‌صفحه روی TV یا مانیتور. KPI امروز، رتبه ۳۰ روزه، اهداف، اطلاعیه — <strong>بدون شماره مشتری و یادداشت خصوصی</strong>. برای انگیزه تیم و کم کردن جلسه صبحگاهی طولانی.</p>

<div class="mk-blog-inline-cta">
    <strong>صفحه تیم را باز کنید</strong>
    <p>CRM → آژانس — یا مستقیم از منوی میزکار.</p>
    <a href="/real-estate-crm/">CRM املاک</a>
</div>

<h2>حریم خصوصی — خط قرمز طراحی</h2>

<p>در هدر صفحه تیم صریح نوشته شده: مشاور داده خودش را می‌بیند؛ مدیر <strong>آمار</strong> می‌بیند نه محتوای پرونده. این یعنی:</p>

<ul>
    <li>مدیر نمی‌تواند بدون اشتراک، یادداشت مذاکره مشاور دیگر را بخواند</li>
    <li>گزارش عملکرد بر اساس <strong>فعالیت ثبت‌شده</strong> است — پس «تماس» باید در CRM log شود</li>
    <li>اشتراک فایل محرمانه = همکار محله و قیمت می‌بیند، نه آدرس مالک</li>
    <li>TV فقط نام نمایشی مشاور — نه phone/email مشتری</li>
</ul>

<p>آژانس حرفه‌ای اعتماد مشاور را حفظ می‌کند؛ وگرنه تیم از CRM فرار می‌کند به واتساپ شخصی.</p>

<h2>روز کاری با صفحه تیم — سه نقش</h2>

<h3>مدیر — ۱۵ دقیقه صبح</h3>
<p>داشبورد → اگر inbox &gt; 0، تخصیص یا یادآوری به منشی → هشدار پیگیری معوق → نگاه به اهداف دوره → اگر TV دارید، یک بار چک کنید روشن است.</p>

<h3>منشی — ورود سرنخ</h3>
<p>تماس یا فرم سایت → ثبت مخاطب (یا API خودکار) → inbox → تخصیص بر اساس محله/بار کاری → پیام به مشاور در تب پیام‌ها اگر فوری است.</p>

<h3>مشاور — بدون استرس نظارت</h3>
<p>CRM شخصی برای کار روزانه؛ صفحه تیم فقط برای «عملکرد من»، اطلاعیه‌های خوانده‌نشده، و دیدن لیست همکاران. سرنخ تخصیص‌یافته در مخاطبین خودش ظاهر می‌شود.</p>

<h2>اتصال به بقیه میزکار</h2>

<table>
    <thead>
        <tr>
            <th>ماژول</th>
            <th>ارتباط با صفحه تیم</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><a href="/blog/noe-mokhatab-vaziat-crm-amlak-rahnama/">نوع مخاطب</a></td>
            <td>سرنخ inbox با نوع درست ثبت شود → تخصیص معنی‌دار</td>
        </tr>
        <tr>
            <td><a href="/blog/modiriyat-moamele-amlak-parvande-komision-rahnama/">معاملات</a></td>
            <td>KPI معامله فعال و کمیسیون در داشبورد</td>
        </tr>
        <tr>
            <td><a href="/blog/automation-crm-5-ghanon-pigiri-rahnama/">اتوماسیون</a></td>
            <td>کمتر پیگیری معوق در هشدار مدیر</td>
        </tr>
        <tr>
            <td><a href="/blog/app-android-filing-divar-meydan-rahnama/">اپ اندروید</a></td>
            <td>ثبت فعالیت در میدان → گزارش تیم درست</td>
        </tr>
        <tr>
            <td>API سرنخ</td>
            <td>فرم سایت → inbox یا round robin</td>
        </tr>
    </tbody>
</table>

<h2>اشتباهات رایج مدیر آژانس</h2>

<ul>
    <li><strong>انتظار دسترسی به همه پرونده‌ها:</strong> سیستم اجازه نمی‌دهد — عمداً</li>
    <li><strong>inbox پر بدون تخصیص:</strong> سرنخ می‌میرد — صبح اولویت اول</li>
    <li><strong>گزارش بدون ثبت فعالیت:</strong> مشاور تماس می‌گیرد ولی log نمی‌زند → آمار دروغین</li>
    <li><strong>هدف غیرواقعی:</strong> ۲۰۰ تماس در ماه برای تیم ۳ نفره → انگیزه می‌شود استرس</li>
    <li><strong>واتساپ جای inbox:</strong> دوباره‌کاری و از دست رفتن سرنخ</li>
    <li><strong>نقش اشتباه:</strong> منشی را مدیر نکنید اگر نباید API ببیند</li>
</ul>

<h2>چک‌لیست راه‌اندازی صفحه تیم</h2>

<ol>
    <li>آژانس ساخته و slug به تیم داده شده؟</li>
    <li>نقش هر عضو (مشاور / منشی / مدیر) درست است؟</li>
    <li>سیاست توزیع سرنخ (inbox / چرخشی / مالک) انتخاب شده؟</li>
    <li>حداقل یک هدف دوره‌ای (تماس یا بازدید) تعریف شده؟</li>
    <li>منشی یا مدیر می‌داند صبح inbox را چک کند؟</li>
    <li>قوانین اشتراک فایل با تیم هماهنگ شده؟</li>
    <li>در صورت نیاز: API یا وب‌هوک فرم سایت تست شده؟</li>
    <li>Agency TV روی مانیتور دفتر (اختیاری ولی توصیه‌شده)؟</li>
</ol>

<h2>جمع‌بندی</h2>

<p><strong>صفحه تیم CRM</strong> آژانس را از مجموعه مشاورهای پراکنده به یک سازمان با قوانین روشن تبدیل می‌کند: چه کسی سرنخ می‌گیرد، عملکرد چطور دیده می‌شود، خبر رسمی کجا منتشر می‌شود، هدف ماه چیست. مالک و مدیر از داشبورد و گزارش استفاده می‌کنند؛ منشی از inbox؛ مشاور از CRM شخصی و عملکرد خودش — همه زیر یک سقف، بدون لو دادن مشتری. اگر یک آدرس برای مدیریت حرفه‌ای آژانس در فایلینگ دیوار داشته باشید، همین است: <code dir="ltr">/workspace/crm/team/</code>.</p>

<div class="mk-blog-inline-cta">
    <strong>آژانس املاک خود را بسازید</strong>
    <p>تیم، inbox، گزارش، TV، API — یک میزکار.</p>
    <a href="/real-estate-crm/">شروع CRM املاک</a>
</div>

<p>مطالب مرتبط: <a href="/blog/modiriyat-ajans-amlak-crm/">مدیریت آژانس</a> · <a href="/blog/inbox-etelaie-ajans-whatsapp-rahnama/">Inbox آژانس</a> · <a href="/blog/eshterak-file-moshaveran-ajans-5-ghanoon-rahnama/">اشتراک فایل تیم</a> · <a href="/blog/agency-tv-dashboard-ajans-amlak/">Agency TV</a> · <a href="/blog/behtarin-crm-moshaver-amlak-iran-1405/">بهترین CRM</a></p>

<p><em>نویسنده: <a href="/author/hossein-qashqaeii/">حسین قشقایی</a> — صفحه تیم را ساختم تا مدیر «کنترل» داشته باشد بدون اینکه مشاور «مراقب» باشد.</em></p>

<section class="blog-faq" itemscope itemtype="https://schema.org/FAQPage">
    <h2>سوالات متداول — صفحه تیم CRM</h2>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">صفحه تیم CRM کجاست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">در میزکار فایلینگ دیوار: مسیر /workspace/crm/team/ — از منوی CRM یا بخش آژانس.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چهار نقش آژانس کدام‌اند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">مالک آژانس، مدیر، مشاور، منشی — هر کدام سطح دسترسی متفاوت در تب‌های تیم.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">آیا مدیر همه مخاطبین را می‌بیند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">خیر — پیش‌فرض خصوصی است. مدیر آمار عملکرد و inbox را می‌بیند؛ محتوای پرونده فقط با اشتراک صریح از طرف مشاور.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">تب داشبورد مدیریت چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">Command center برای مالک/مدیر: سرنخ بدون تخصیص، پیگیری معوق، معاملات فعال، نرخ تبدیل، هشدارها.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">صندوق سرنخ چه کسانی می‌بینند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">مالک، مدیر و منشی — برای تخصیص مخاطب بدون مشاور مسئول.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">Agency TV چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">نمای تمام‌صفحه /workspace/crm/team/tv/ برای TV دفتر — KPI و رتبه بدون داده حساس مشتری.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">اهداف تیم چگونه تعریف می‌شود؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">تب تنظیمات — شاخص تماس، بازدید یا معامله بسته — برای کل تیم یا هر عضو، با بازه تاریخ.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">وب‌هوک و API برای چیست؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">دریافت سرنخ از فرم سایت و اطلاع‌رسانی رویدادها (مخاطب جدید، معامله بسته…) به سیستم‌های خارجی.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">همگام‌سازی JSON چه می‌کند؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">خروجی/ورود مخاطب، فایل و معامله — پشتیبان یا اتصال ابزار دسکتاپ؛ لاگ در تب sync.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">تفاوت اشتراک و انتقال پرونده؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">اشتراک = دیگری هم می‌بیند؛ مالک اصلی می‌ماند. انتقال = مسئولیت به مشاور دیگر — در تب انتقال‌ها ثبت می‌شود.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">مشاور به گزارش کل تیم دسترسی دارد؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">خیر — فقط «عملکرد شخصی». گزارش مقایسه‌ای اعضا برای مالک و مدیر است.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">چطور به آژانس بپیوندم؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">شناسه slug از مدیر → درخواست عضویت در صفحه تیم → تأیید مدیر.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">ممیزی چه رویدادهایی را نشان می‌دهد؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">دعوت عضو، تغییر نقش، تخصیص سرنخ، sync، وب‌هوک و عملیات مدیریتی دیگر.</p>
        </div>
    </details>
    <details itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
        <summary itemprop="name">بدون آژانس می‌توان از CRM استفاده کرد؟</summary>
        <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
            <p itemprop="text">بله — مشاور مستقل CRM شخصی دارد. صفحه تیم وقتی معنی دارد که آژانس بسازید یا بپیوندید.</p>
        </div>
    </details>
</section>'''
