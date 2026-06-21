# پلن بازنویسی داشبورد حرفه‌ای Divar Workspace

> **هدف:** کاربر با اپ Tkinter داده‌ها را استخراج می‌کند؛ در وب‌سایت Django همان داده‌ها را آپلود، ذخیره و با تمام امکانات اپ (به‌جز استخراج) مدیریت می‌کند.

---

## اصول معماری

| اصل | توضیح |
|-----|-------|
| جداسازی | اپ جدید `workspace` جدا از `shop` — فقط داشبورد داده |
| مالکیت داده | هر رکورد به `User` متصل است |
| انعطاف ستون‌ها | فیلد `data` (JSON) + فیلدهای ایندکس‌شده برای جستجو/فیلتر |
| اشتراک منطق | سرویس‌های Python مشترک با `src/` برای تحلیل و ابزارها |
| UI | RTL فارسی، مینیمال، sidebar ثابت، responsive |
| امنیت | `@login_required` + بررسی مالکیت در هر view |

---

## فاز ۰ — زیرساخت (انجام می‌شود)

- [x] ایجاد اپ `workspace`
- [x] ثبت در `INSTALLED_APPS` و `urls.py`
- [x] مدل‌های پایگاه داده
- [x] migrations
- [x] لایه `services/` (import، تحلیل، export، ابزار)
- [x] ثابت‌های CRM از `app_crm_links.py`
- [x] قالب پایه `workspace/base.html` + CSS/JS اختصاصی
- [x] وابستگی‌ها: `pandas`, `openpyxl`, `numpy`

---

## فاز ۱ — داشبورد خانه و آپلود

### ۱.۱ صفحه خانه (`/workspace/`)
- کارت‌های آماری: تعداد مجموعه‌داده، آگهی، مشتری، یادآور
- فایل‌های اخیر (۶ مورد آخر)
- یادآورهای فعال (۵ مورد)
- میانبرهای سریع: مشاهده، تحلیل، ابزار، CRM، مقایسه

### ۱.۲ آپلود داده (`/workspace/datasets/upload/`)
- فرمت‌های مجاز: `.xlsx`, `.csv`, `.json`
- پردازش async با progress (AJAX polling)
- استخراج متادیتا: نوع معامله، شهر، تعداد ردیف/ستون
- ذخیره `Dataset` + bulk insert `Listing`
- ثبت `PriceHistory` در صورت وجود قیمت

### ۱.۳ لیست مجموعه‌داده‌ها (`/workspace/datasets/`)
- کارت/جدول با نام، تاریخ، تعداد آگهی، نوع معامله
- حذف، تغییر نام، دانلود export

---

## فاز ۲ — نمایش و جدول آگهی‌ها

### ۲.۱ جدول آگهی (`/workspace/datasets/<id>/`)
- نمایش ستون‌های کلیدی Divar
- صفحه‌بندی server-side (۵۰ ردیف)
- مرتب‌سازی روی ستون‌ها (کلیک هدر)
- جستجو: عنوان، شناسه، توضیحات
- فیلترها: برچسب، مشاور/شخصی، علاقه‌مند، ۲۴ ساعت اخیر
- هایلایت نتایج جستجو
- حالت فشرده جدول
- یافتن تکراری‌ها (token)

### ۲.۲ جزئیات آگهی (`/workspace/datasets/<id>/listings/<token>/`)
- هدر: عنوان، token، لینک دیوار، کپی شناسه
- تب‌ها: مالی، ملک، مکان، متن، تماس، رسانه
- گالری تصاویر
- پنل متادیتا: برچسب، یادداشت، علاقه‌مند
- پنل CRM: پیوند سریع مخاطب
- نقشه تک‌ملک (Leaflet)
- کپی متن واتساپ

---

## فاز ۳ — تحلیل و نمودار

### ۳.۱ صفحه تحلیل (`/workspace/datasets/<id>/analyze/`)
- تشخیص context (فروش/اجاره/ترکیبی)
- بنر اطلاعات فایل
- حذف outlier (IQR)
- گزارش outlier
- کارت‌های آمار پیشرفته
- **راهنمای مشاور** (متن فارسی actionable):
  - وضعیت قیمت، مقایسه محله، موقعیت، پیشنهاد ویژه
  - تأثیر امکانات، سن بنا، امتیاز خرید، تکراری‌ها
  - توصیه اجاره (در صورت rent)
- Benchmark تک‌آگهی

### ۳.۲ نمودارها (Chart.js)
- هیستوگرام قیمت/متر
- هیستوگرام قیمت کل
- هیستوگرام متراژ
- پراکندگی قیمت-متراژ
- هیستوگرام ودیعه/اجاره (rent)
- نمودار میله‌ای قیمت/متر بر اساس محله
- نمودار اتاق‌ها
- Lite mode برای >۲۰۰ ردیف

### ۳.۳ نقشه تحلیل (`/workspace/datasets/<id>/map/`)
- Leaflet با رنگ‌بندی quartile قیمت/متر
- خوشه‌بندی (cluster)
- heatmap (اختیاری)
- تفکیک مشاور/شخصی

---

## فاز ۴ — ابزارها

### ۴.۱ صفحه ابزار (`/workspace/tools/`)
| ابزار | توضیح |
|-------|-------|
| تبدیل ودیعه↔اجاره | نرخ پیش‌فرض ۳۰:۱ |
| ماشین‌حساب متراژ-قیمت | قیمت/متر ↔ کل |
| محاسبه کمیسیون | خریدار/فروشنده/کل |
| قیمت‌گذاری هوشمند | بر اساس dataset فعال |

---

## فاز ۵ — CRM

### ۵.۱ لیست مشتریان (`/workspace/crm/`)
- جستجو، فیلتر وضعیت/نوع/اولویت
- آمار: کل، جدید، در پیگیری، سررسید امروز

### ۵.۲ پروفایل مشتری (`/workspace/crm/<id>/`)
- فرم کامل (نام، تلفن، بودجه، محله، نوع ملک، ...)
- لاگ فعالیت (تماس، بازدید، جلسه، ...)
- یادآورها
- املاک مرتبط
- اکشن: کپی تلفن، قالب واتساپ
- export Excel

### ۵.۳ یادآورها (`/workspace/reminders/`)
- CRUD یادآور با سررسید
- نمایش در داشبورد خانه

---

## فاز ۶ — مقایسه و Export

### ۶.۱ مقایسه دو فایل (`/workspace/compare/`)
- انتخاب دو dataset
- آمار کنار هم + دلتا
- diff توکن‌ها (جدید/حذف/مشترک)
- top ۵ محله

### ۶.۲ Export
- CSV / JSON (فیلترشده یا کل)
- PDF گزارش بازار
- PDF چند آگهی (تا ۲۰)
- Print HTML
- PNG نمودارها

---

## فاز ۷ — تنظیمات و پولیش

### ۷.۱ تنظیمات (`/workspace/settings/`)
- تم (روشن/تیره)
- مقیاس فونت
- تنظیمات نقشه (cluster, heatmap, k-means)
- برندینگ آژانس (نام + لوگو برای PDF)

### ۷.۲ راهنما (`/workspace/help/`)
- بخش‌های: شروع، مشاهده، تحلیل، CRM، میانبرها

### ۷.۳ یکپارچگی با حساب کاربری
- لینک «داشبورد داده» در منوی اصلی سایت
- بررسی لایسنس فعال قبل از دسترسی workspace

---

## ساختار فایل‌ها

```
django/workspace/
├── models.py          # Dataset, Listing, ListingMeta, Customer, ...
├── views/
│   ├── home.py
│   ├── datasets.py
│   ├── listings.py
│   ├── analyze.py
│   ├── tools.py
│   ├── crm.py
│   ├── compare.py
│   ├── export.py
│   └── settings.py
├── services/
│   ├── importer.py    # pandas import
│   ├── analyzer.py    # stats, outliers, consultant guide
│   ├── charts.py      # chart data for Chart.js
│   ├── pricing.py     # smart pricing
│   ├── compare.py     # two-file compare
│   ├── export.py      # CSV/JSON/PDF
│   └── tools.py       # calculators
├── forms.py
├── urls.py
├── admin.py
├── constants.py       # CRM constants
└── templatetags/

templates/workspace/
├── base.html
├── home.html
├── datasets/
├── listings/
├── analyze/
├── tools/
├── crm/
├── compare/
└── settings/

static/workspace/
├── css/workspace.css
└── js/workspace.js
```

---

## مدل‌های دیتابیس

```
User (accounts)
  ├── Dataset (1:N)
  │     └── Listing (1:N) — token unique per dataset
  ├── ListingMeta (1:N) — per user+token
  ├── PriceHistory (1:N) — per user+token
  ├── Customer (1:N)
  │     ├── CustomerActivity (1:N)
  │     ├── CustomerListing (1:N)
  │     └── Reminder (1:N)
  └── WorkspaceSettings (1:1)
```

---

## ترتیب پیاده‌سازی

| مرحله | محتوا | وضعیت |
|-------|-------|-------|
| ۰ | زیرساخت، مدل، قالب پایه | ✅ |
| ۱ | خانه + آپلود + لیست datasets | ✅ |
| ۲ | جدول + جزئیات + فیلتر | ✅ |
| ۳ | تحلیل + نمودار + نقشه | ✅ |
| ۴ | ابزارها | ✅ |
| ۵ | CRM + یادآور | ✅ |
| ۶ | مقایسه + export | ✅ |
| ۷ | تنظیمات + راهنما + polish | ✅ |

---

## یادداشت‌های فنی

- **استخراج:** فقط در Tkinter — هیچ endpoint scrape در workspace نیست
- **لایسنس:** middleware بررسی `License` فعال کاربر
- **Performance:** bulk_create برای import، pagination برای جدول، cache برای آمار
- **فونت:** Vazirmatn (مثل سایت اصلی)
- **نقشه:** Leaflet + leaflet.markercluster (CDN)
- **نمودار:** Chart.js 4 (CDN)

---

*آخرین به‌روزرسانی: ۱۴۰۵/۰۳/۱۹*
