# گزارش Audit سئو — divarfiling.ir

**تاریخ:** ۲۴ ژوئن ۲۰۲۶ (۳ تیر ۱۴۰۵)  
**دامنه:** `https://divarfiling.ir`  
**فریم‌ورک:** Django  
**هدف:** ارزیابی وضعیت فعلی سئو قبل از اجرای ۱۵ مرحله ارتقا

---

## خلاصه اجرایی

پروژه **پایه سئوی فنی قابل قبولی** دارد: `base.html` با `lang="fa"` و `dir="rtl"`، سیستم مرکزی meta/OG/Twitter/canonical از طریق `{% seo_meta %}`، `robots.txt` و `sitemap.xml` داینامیک، و schema برای Organization، SoftwareApplication (خانه)، Product (محصول)، Article/FAQ/Breadcrumb (بلاگ).

با این حال، **بخش عمده استراتژی سئو هنوز پیاده‌سازی نشده**: صفحات لندینگ اختصاصی کلمات کلیدی، Programmatic SEO شهر/محله، مدل مرکزی SEO، Topic Cluster، صفحه نویسنده، و محتوای pillar طولانی. فایل‌های `SEO_CONTENT_PLAN.md` و `SEO_IMPLEMENTATION_REPORT.md` وجود ندارند.

| حوزه | وضعیت | امتیاز تقریبی |
|------|--------|---------------|
| Meta / OG / Canonical | خوب — ناقص در برخی صفحات | ۷/۱۰ |
| Schema.org | متوسط — انواع اصلی جزئی | ۶/۱۰ |
| Sitemap / Robots | خوب | ۸/۱۰ |
| URL Strategy | ضعیف — لندینگ‌های هدف وجود ندارد | ۳/۱۰ |
| محتوا / Topic Cluster | خیلی ضعیف — ۱ مقاله سئو seed شده | ۲/۱۰ |
| Programmatic SEO | وجود ندارد | ۰/۱۰ |
| Performance (CWV) | متوسط — بهینه‌سازی جزئی | ۵/۱۰ |
| Mobile | خوب — CSS responsive موجود | ۷/۱۰ |

---

## ۱. ساختار URLها

### ۱.۱ مسیرهای عمومی (قابل ایندکس)

| URL | نام | توضیح |
|-----|-----|--------|
| `/` | `home` | صفحه اصلی — لندینگ برند |
| `/products/` | `product_list` | ریدایرکت به محصول ربات |
| `/products/divar-extraction-bot/` | `product_detail` | صفحه محصول ربات (معادل غیررسمی «ربات دیوار») |
| `/about/` | `about` | درباره ما |
| `/contact/` | `contact` | تماس |
| `/terms/` | `terms` | قوانین |
| `/license-guide/` | `license_guide` | راهنمای نصب |
| `/amoozesh/` | `education` | مرکز آموزش |
| `/blog/` | `blog:post_list` | لیست مقالات |
| `/blog/<slug>/` | `blog:post_detail` | جزئیات مقاله |
| `/robots.txt` | `robots_txt` | robots داینامیک |
| `/sitemap.xml` | `sitemap_index` | sitemap چندبخشی |

**فایل‌های مرجع:** `divar_shop/urls.py`, `shop/urls.py`, `blog/urls.py`

### ۱.۲ مسیرهای خصوصی (نباید ایندکس شوند)

| پیشوند | کاربرد |
|--------|--------|
| `/admin/` | پنل ادمین |
| `/accounts/` | ورود، ثبت‌نام، داشبورد، پروفایل |
| `/workspace/` | میزکار CRM و ابزارها (~۱۰۰+ route) |
| `/api/` | API لایسنس |
| `/payment/` | درگاه پرداخت |
| `/affiliate/` | پنل همکاری در فروش |
| `/products/*/buy/` و مسیرهای rating/review | صفحات تراکنشی |

در `robots.txt` این مسیرها `Disallow` شده‌اند (`divar_shop/robots.py`).

### ۱.۳ URLهای هدف استراتژی که **وجود ندارند**

طبق پرامپت سئو و `seo-keywords.txt`، این لندینگ‌ها هنوز ساخته نشده‌اند:

| URL پیشنهادی | معادل فعلی (در صورت وجود) |
|--------------|---------------------------|
| `/robot-divar/` | `/products/divar-extraction-bot/` |
| `/robot-divar-real-estate/` | — |
| `/extract-divar-ads/` | — |
| `/divar-filing/` | `/` (برند کلی) |
| `/real-estate-filing/` | — |
| `/real-estate-crm/` | — |
| `/real-estate-crm-software/` | — |
| `/real-estate-software/` | — |
| `/real-estate-market-analysis/` | — |
| `/property-pricing/` | — |
| `/market/<city_slug>/` | — (ابزار market فقط در `/workspace/tools/`) |
| `/market/<city_slug>/<neighborhood_slug>/` | — |
| `/author/hossein-qashqaeii/` | — (نویسنده فقط inline در بلاگ) |

### ۱.۴ نکات URL

- فیلتر دسته بلاگ فقط با `?cat=<slug>` — route اختصاصی `/blog/category/<slug>/` ندارد.
- `product_list` در sitemap ثبت شده ولی به محصول ریدایرکت می‌کند.
- هیچ `hreflang` یا نسخه چندزبانه وجود ندارد (فقط فارسی).

---

## ۲. فایل‌های Template

### ۲.۱ قالب پایه

**`templates/base.html`**
- `lang="fa"` و `dir="rtl"` ✅
- `{% seo_meta %}` برای meta داینامیک ✅
- `{% schema_organization %}` در همه صفحات عمومی ✅
- منوی اصلی: خانه، ربات استخراج، مقالات، آموزش، درباره، تماس
- فونت Vazirmatn (Google Fonts + CDN تکراری)
- Font Awesome 6.5.1 از CDN
- CSS: `design-system.css` (workspace) + `main.css` + `mizkar-public.css` + `responsive-base.css`

**`templates/shop/seo_meta.html`**
- description, keywords, author, robots
- Open Graph کامل
- Twitter Card (`summary_large_image`)
- canonical + لینک sitemap
- JSON-LD اختیاری از `schema_data`

### ۲.۲ صفحات عمومی و وضعیت SEO context

| Template | meta سفارشی در view | schema |
|----------|---------------------|--------|
| `shop/home.html` | ✅ | SoftwareApplication |
| `shop/product_bot.html` | ✅ | Product + AggregateRating |
| `shop/about.html` | ✅ | — |
| `shop/contact.html` | ✅ | — |
| `shop/education.html` | ✅ | — (FAQ UI بدون JSON-LD) |
| `shop/license_guide.html` | ❌ پیش‌فرض | — |
| `shop/terms.html` | ❌ پیش‌فرض | — |
| `blog/post_list.html` | ✅ | — |
| `blog/post_detail.html` | ✅ | Article + FAQPage + BreadcrumbList |

### ۲.۳ قالب‌های بدون stack سئو

- `templates/workspace/base.html` — فقط `<title>`؛ بدون canonical/OG (منطقی برای بخش خصوصی)
- `templates/errors/base_error.html` — `noindex, nofollow` ✅

### ۲.۴ Breadcrumbs

- بصری در بلاگ (`post_detail.html`) ✅
- schema BreadcrumbList در بلاگ ✅
- breadcrumb محصول در UI کامنت/غیرفعال شده

---

## ۳. فایل‌های Static

### ۳.۱ ساختار

```
static/
├── css/          # صفحات عمومی (mizkar-home, blog, education, ...)
├── js/           # main.js, mizkar-home.js, mizkar-blog.js, ...
└── workspace/    # CSS/JS میزکار (جدا از عمومی)
```

`STATIC_URL=/static/`, `STATIC_ROOT=staticfiles/`

### ۳.۲ موارد مهم

| مورد | وضعیت |
|------|--------|
| `logo.png`, `logo.ico` | در repo ردیابی نشده — در template و OG به `/static/logo.png` ارجاع داده می‌شود |
| `static/images/` | پوشه در repo خالی/وجود ندارد |
| `images/og/blog/crm-amlak.jpg` | در seed مقاله #۹ ارجاع شده — فایل فیزیکی نیست |
| تصاویر education | از `static/images/` در `education_content.py` — نیاز به deploy جداگانه |
| WebP | پیاده‌سازی نشده |
| Service Worker / cache | وجود ندارد |

---

## ۴. مدل‌ها — Blog / Page / SEO

### ۴.۱ Blog (`blog/models.py`)

| مدل | فیلدها | فیلدهای SEO اختصاصی |
|-----|--------|---------------------|
| `Category` | name, slug, description, order | — |
| `Tag` | name, slug | — |
| `Post` | title, slug, author, category, tags, content, excerpt, featured_image, is_published, views_count, created_at, updated_at, published_at | **ندارد** — meta از title/excerpt مشتق می‌شود |

### ۴.۲ مدل‌های SEO / Programmatic — **وجود ندارند**

- `Page` / `SEOPage` — برای meta قابل تنظیم per-page
- `City`, `Neighborhood` — entity عمومی SEO
- `MarketSnapshot` — داده بازار برای صفحات programmatic

### ۴.۳ داده مرتبط در workspace

- `city` و `neighborhood` به‌صورت `CharField` در مدل‌های CRM/listing
- `build_market_snapshot()` در `workspace/services/tools.py` — فقط برای ابزار داخلی میزکار

### ۴.۴ Shop Product (`shop/models.py`)

- `short_description` برای meta استفاده می‌شود
- فیلد اختصاصی `meta_title` / `meta_description` / `canonical_url` ندارد

---

## ۵. Meta Title و Meta Description

### ۵.۱ سیستم مرکزی

**`shop/templatetags/seo_tags.py` → `seo_meta`**

اولویت: kwargs → `context.meta_title` / `context.meta_description` → پیش‌فرض سایت

پیش‌فرض description:
> فروشگاه رسمی ربات هوشمند تحلیل املاک دیوار...

### ۵.۲ صفحات با meta اختصاصی

| صفحه | meta_title نمونه |
|------|------------------|
| خانه | فایلینگ دیوار — میزکار CRM رایگان + ربات استخراج املاک |
| محصول | `{product.title} - فروشگاه ربات دیوار` |
| بلاگ لیست | مقالات تخصصی املاک و فایلینگ دیوار |
| بلاگ جزئیات | `{post.title}` |
| آموزش | آموزش — مرکز یادگیری فایلینگ دیوار |
| درباره / تماس | اختصاصی ولی عمومی |

### ۵.۳ شکاف‌ها

- `terms` و `license_guide` از meta پیش‌فرض استفاده می‌کنند
- صفحات accounts (login/register) از `base.html` ارث می‌برند → `index, follow` در حالی که `/accounts/` در robots مسدود است
- امکان `noindex` per-page در template وجود ندارد (`robots` همیشه `index, follow` در `seo_meta.html`)
- `<title>` در block جدا از `meta_title` است — معمولاً هماهنگ ولی دو منبع جدا

---

## ۶. Canonical

- `<link rel="canonical" href="{{ url }}">` در `seo_meta.html`
- `url` = `request.build_absolute_uri()` — URL فعلی درخواست
- **نکته:** نرمال‌سازی www/non-www یا trailing slash در لایه SEO انجام نمی‌شود
- بلاگ و محصول canonical صحیح دارند
- فیلتر `?cat=` در بلاگ canonical همان URL با query string می‌ماند

---

## ۷. Open Graph

| تگ | وضعیت |
|----|--------|
| og:type | داینامیک (`website` / `article`) |
| og:title | از meta_title |
| og:description | از meta_description |
| og:image | featured_image / static seed / fallback logo |
| og:url | URL فعلی |
| og:site_name | `SITE_NAME` از settings |
| og:locale | `fa_IR` |
| article:published_time / modified_time | فقط مقالات |

**شکاف:** تصویر OG اختصاصی برای اکثر صفحات وجود ندارد؛ fallback به لوگو.

---

## ۸. Schema.org (JSON-LD)

### ۸.۱ پیاده‌سازی شده

| نوع Schema | محل | فایل |
|------------|-----|------|
| Organization | همه صفحات عمومی | `seo_tags.schema_organization` |
| SoftwareApplication | صفحه اصلی | `shop/views.py` HomeView → `schema_data` |
| Product (+ Offer, AggregateRating) | جزئیات محصول | `shop/views.py` ProductDetailView |
| Article | جزئیات بلاگ | `seo_tags.schema_article` |
| FAQPage | بلاگ با بخش «سوالات متداول» | `blog/seo_schema.py` + `schema_faq_page` |
| BreadcrumbList | جزئیات بلاگ | `seo_tags.schema_breadcrumb` |

### ۸.۲ تعریف شده ولی استفاده نشده

- `schema_product` — منطق تکراری inline در view
- `schema_software_application` — home از JSON inline استفاده می‌کند

### ۸.۳ **وجود ندارد**

| نوع | کاربرد پیشنهادی |
|-----|-----------------|
| WebSite (+ SearchAction) | صفحه اصلی |
| FAQPage | `education.html` (FAQ با `<details>` دارد) |
| Person | صفحه نویسنده |
| WebPage | about, contact, terms |
| Product/SoftwareApplication | لندینگ‌های آینده |

---

## ۹. Sitemap

**فایل:** `divar_shop/sitemaps.py`

| بخش | محتوا | changefreq | priority |
|-----|-------|------------|----------|
| `static` | home, product_list, about, contact, terms, license_guide, education, blog:post_list | varied | 0.4–1.0 |
| `products` | Product فعال | weekly | 0.85 |
| `blog` | Post منتشرشده | monthly | 0.75 |

**نکات:**
- دامنه از `SITE_URL` و `django.contrib.sites` (`SiteAwareSitemap`)
- `lastmod` برای blog و products از DB
- لندینگ‌های آینده، شهر/محله، author در sitemap نیست
- تست خودکار sitemap وجود ندارد (`divar_shop/tests_seo.py` فقط robots و FAQ)

---

## ۱۰. robots.txt

**فایل:** `divar_shop/robots.py`

- User-agentهای OpenAI (`OAI-SearchBot`, `GPTBot`, `ChatGPT-User`) با `Allow: /` + Disallow مسیرهای خصوصی
- `User-agent: *` با همان Disallowها
- `Sitemap: {SITE_URL}/sitemap.xml`

**Disallow:** admin, accounts, workspace, api, payment, affiliate, buy/discount/rating/review, reviews

**تست:** `divar_shop/tests_seo.py` ✅

---

## ۱۱. Headingها (H1–H6)

| صفحه | H1 | یکتا؟ |
|------|-----|-------|
| خانه | `home_page.hero.title_main` + accent | ✅ یک H1 |
| محصول ربات | `product.title` | ✅ |
| بلاگ جزئیات | `post.title` | ✅ |
| آموزش | `edu.hero.title` | ✅ |
| درباره | ابزار حرفه‌ای برای بازار املاک | ✅ |
| تماس | در دسترس هستیم | ✅ |
| قوانین | قوانین و مقررات | ✅ |

**نکات:**
- ساختار H2/H3 در home و product_bot غنی است
- مقالات seed شده ساختار heading منظم دارند
- برخی H1ها کلمه کلیدی هدف را مستقیم پوشش نمی‌دهند (مثلاً تماس/درباره عمومی‌اند)

---

## ۱۲. تصاویر و Alt

### ۱۲.۱ نقاط قوت

- `loading="lazy"` در home، blog، education، product gallery
- `width` و `height` در بسیاری تصاویر home و gallery_card
- alt معنادار در blog cards و education captions

### ۱۲.۲ شکاف‌ها

| محل | مشکل |
|-----|------|
| `accounts/login.html`, `register.html` | `alt=""` خالی |
| `education.html` برخی lesson images | `alt=""` |
| enamad logo | `alt=''` |
| workspace listings | alt خالی (بخش خصوصی) |
| WebP / srcset | وجود ندارد |
| OG images | فایل‌های static گم‌شده |

---

## ۱۳. Mobile Responsive

- `responsive-base.css` + `mizkar-public.css` + viewport meta ✅
- منوی موبایل با toggle در `base.html` ✅
- صفحات home، blog، education، product_bot استایل اختصاصی responsive دارند
- **نیاز به تست دستی:** جداول workspace، فرم‌های auth، صفحات market (هنوز ساخته نشده)
- اسکرول افقی: بدون تست Lighthouse تأیید نشده — در CSS عمومی overflow-x کنترل شده

---

## ۱۴. Performance

### ۱۴.۱ بهینه‌سازی‌های موجود

- Lazy load تصاویر (بخشی از صفحات)
- Cache busting با `?v=` روی CSS
- preconnect به Google Fonts

### ۱۴.۲ مشکلات احتمالی Core Web Vitals

| مورد | تأثیر |
|------|--------|
| بارگذاری دوگانه فونت (Google + jsDelivr Vazir) | LCP / FCP |
| Font Awesome کامل از CDN (~۷۰KB+) | Render blocking |
| `design-system.css` workspace روی همه صفحات عمومی | CSS اضافی |
| بدون preload فونت critical | LCP |
| بدون WebP / responsive images | LCP |
| اسکریپت inline طولانی در base.html (announcement/banner) | TBT جزئی |

### ۱۴.۳ اهداف Lighthouse (پرامپت)

| معیار | هدف | وضعیت فعلی (تخمینی) |
|-------|-----|---------------------|
| Performance | >90 | نیاز به اندازه‌گیری — احتمالاً ۶۰–۸۰ |
| SEO | >95 | احتمالاً ۸۵–۹۲ (به‌خاطر missing alt، duplicate fonts) |
| Accessibility | >90 | alt خالی‌ها مانع |
| Best Practices | >90 | CDN third-party |

---

## ۱۵. بلاگ و محتوا

| قابلیت | وضعیت |
|--------|--------|
| category / tag | ✅ مدل + UI |
| author | ✅ ForeignKey — بدون صفحه archive |
| reading_time | ✅ در view و template |
| updated_at | ✅ نمایش در UI + schema |
| table_of_contents | بررسی نشده در همه مقالات — seed ممکن است داشته باشد |
| FAQ | ✅ در seed + schema |
| related_articles | ✅ بر اساس category |
| breadcrumbs | ✅ UI + schema |
| article schema | ✅ |
| canonical | ✅ |
| slug | انگلیسی transliterated (`narm-afzar-crm-amlak-...`) |
| مقالات seed | **فقط ۱ مقاله** (کلمه #۹ از `seo-keywords.txt`) |

**فایل‌های مرتبط:** `blog/seo_article_seed.py`, `blog/seo_helpers.py`, `blog/seo_schema.py`, `blog/tests_seo.py`

---

## ۱۶. Internal Linking

### موجود
- منوی header/footer به صفحات اصلی
- footer: محصول، آموزش، بلاگ، میزکار
- related posts در بلاگ
- لینک‌های CTA در home به register و product

### **وجود ندارد**
- زنجیره لندینگ: ربات دیوار → استخراج → فایلینگ → CRM
- لینک متنی بین pillar و cluster
- لینک author به `/author/...`
- cross-link شهر → محله

---

## ۱۷. تست‌ها

| فایل | پوشش |
|------|------|
| `divar_shop/tests_seo.py` | FAQ extraction, robots.txt |
| `blog/tests_seo.py` | meta article, OG image, Twitter, Article+FAQ JSON-LD |

**بدون تست:** sitemap XML، home meta، canonical، education FAQ schema

---

## ۱۸. نگاشت مراحل ۲–۱۵ (وضعیت فعلی)

| مرحله | عنوان | وضعیت |
|-------|--------|--------|
| 1 | Audit اولیه | **این گزارش** |
| 2 | SEO Foundation (مدل مرکزی meta) | ❌ انجام نشده |
| 3 | Template Base SEO | 🟡 جزئی — نیاز به robots_index per-page و حذف تکراری |
| 4 | Schema کامل | 🟡 جزئی — WebSite, Person, FAQ education مانده |
| 5 | Sitemap و robots | 🟢 پایه موجود — نیاز به لندینگ/market |
| 6 | صفحات لندینگ اصلی (۱۰ URL) | ❌ انجام نشده |
| 7 | Topic Cluster + SEO_CONTENT_PLAN | ❌ انجام نشده |
| 8 | Programmatic SEO شهر/محله | ❌ انجام نشده |
| 9 | Blog SEO پیشرفته | 🟡 پایه خوب — فیلدهای SEO مدل مانده |
| 10 | Author / E-E-A-T | ❌ انجام نشده |
| 11 | Internal Linking سیستماتیک | 🟡 جزئی |
| 12 | Core Web Vitals | 🟡 lazy load هست — WebP/preload/کاهش CSS مانده |
| 13 | Mobile SEO | 🟡 CSS موجود — نیاز به QA |
| 14 | Conversion SEO (CTA) | 🟡 CTA در home — استانداردسازی ۳ نقطه‌ای مانده |
| 15 | SEO_IMPLEMENTATION_REPORT | ❌ انجام نشده |

---

## ۱۹. اولویت‌های پیشنهادی برای مراحل بعد

### فوری (بیشترین اثر سئو)
1. **مرحله ۶** — لندینگ‌های `/robot-divar/`, `/divar-filing/`, `/real-estate-crm/` و ...
2. **مرحله ۲** — فیلدهای SEO روی Post + context processor یکپارچه
3. **مرحله ۷** — `SEO_CONTENT_PLAN.md` + seed مقالات pillar

### میان‌مدت
4. **مرحله ۸** — City/Neighborhood/MarketSnapshot + صفحات `/market/`
5. **مرحله ۱۰** — صفحه author + Person schema
6. **مرحله ۴** — WebSite schema + FAQ education

### فنی
7. **مرحله ۱۲** — حذف فونت تکراری، preload، WebP
8. اضافه کردن `static/images/og/` و لوگو به repo
9. meta اختصاصی برای terms و license_guide
10. `noindex` برای صفحات accounts در seo_meta

---

## ۲۰. فایل‌های کلیدی مرجع

```
divar_shop/urls.py          # routing اصلی + sitemap + robots
divar_shop/sitemaps.py      # sitemap
divar_shop/robots.py        # robots.txt
divar_shop/settings.py      # SITE_URL, SITE_NAME, TWITTER_SITE
shop/urls.py                # صفحات عمومی
shop/views.py               # SEO context صفحات shop
shop/templatetags/seo_tags.py
templates/base.html
templates/shop/seo_meta.html
blog/models.py, blog/views.py, blog/seo_*.py
seo-keywords.txt            # استراتژی ۵۰ کلمه
```

---

## ۲۱. ریسک‌ها و محدودیت‌ها

- **تغییر URLهای موجود** بدون redirect 301 به رتبه آسیب می‌زند — لندینگ‌های جدید باید مسیر جدا باشند یا redirect از مسیر قدیم.
- **workspace** نباید در sitemap یا index بیاید — فعلاً درست مسدود است.
- **محتوای ۱۸۰۰–۲۵۰۰ کلمه** برای ۱۰ لندینگ حجم زیادی است — بهتر مرحله‌ای و با کیفیت انجام شود.
- **logo.png** در OG همه صفحات بدون تصویر اختصاصی — برای share در شبکه‌های اجتماعی ضعیف است.

---

*پایان گزارش Audit — مرحله ۱*
