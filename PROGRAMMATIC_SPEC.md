# مشخصات Programmatic SEO — divarfiling.ir

**تاریخ:** ۲۴ ژوئن ۲۰۲۶  
**نسخه:** ۱.۰  
**وضعیت:** مشخصات پیاده‌سازی — قبل از کد  
**مرجع استراتژیک:** `SEO_ROADMAP.md` §۷ ، `SEO_CONTENT_PLAN.md` (پیش‌شرط انتشار)  
**اولویت:** P2 — Wave 6 (بعد از Wave 4: `/real-estate-market-analysis/` و `/property-pricing/`)

---

## ۱. خلاصه اجرایی

Programmatic SEO در فایلینگ دیوار یعنی تولید **خودکار** هزاران صفحه محلی (`/market/{city}/` و `/market/{city}/{neighborhood}/`) بر پایه **همان موتور تحلیل میزکار** — نه محتوای دستی و نه صفحه per-user.

**مزیت رقابتی:** داده واقعی دیوار + تحلیل حرفه‌ای (میانه، P25–P75، عمق بازار، احساس بازار، روند، محله‌های مرتبط) که رقبا با لندینگ ثابت ندارند.

**اصل طلایی:** صفحه فقط وقتی **ایندکس** می‌شود که gate کیفیت پاس شده باشد؛ تا آن زمان `noindex` یا عدم وجود در sitemap.

---

## ۲. اهداف و KPI

| هدف | معیار موفقیت |
|-----|-------------|
| پوشش long-tail محلی | رتبه برای «قیمت ملک {شهر}»، «بازار املاک {محله}» |
| Useful Content | ۱۲۰۰–۱۸۰۰ کلمه **با ارزش** — عمدتاً از داده، نه padding |
| مقیاس | Wave 6: ۶ شهر + ۲۰ محله تهران → Wave 8: ۴۰۰+ شهر، ۳۰۰۰+ محله |
| تبدیل | CTA به ثبت‌نام CRM، ربات، لندینگ‌های pillar |
| E-E-A-T | بازه تاریخ داده، امتیاز اعتماد، لینک نویسنده و pillar |
| فنی | تحلیل در request نیاید — snapshot از پیش cache شده |

---

## ۳. وابستگی‌ها و پیش‌نیاز

| وابستگی | وضعیت | توضیح |
|---------|--------|--------|
| Wave 4 — `/real-estate-market-analysis/` | برنامه‌ریزی | pillar لینک داخلی از market |
| Wave 4 — `/property-pricing/` | برنامه‌ریزی | لینک programmatic → قیمت‌گذاری |
| موتور تحلیل workspace | ✅ موجود | `build_professional_report` و زیرسیستم‌ها |
| مدل `Dataset` / `Listing` | ✅ موجود | منبع خام داده |
| اپ `market` | ❌ ساخته نشده | این سند مشخصات آن است |
| Celery | اختیاری | فاز ۱: management command + cron کافی است |

---

## ۴. معماری کلی

```
┌─────────────────────────────────────────────────────────────────┐
│                        منابع داده                                │
├──────────────────────┬──────────────────────────────────────────┤
│ Reference Datasets   │  Federated (فاز ۲ — opt-in کاربران)       │
│ (ادمین / ربات سایت)  │  تجمیع ناشناس چند dataset معتبر         │
└──────────┬───────────┴──────────────────┬───────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Snapshot Builder (market/services/snapshot_builder.py)            │
│  ─ listings_to_dataframe → filter_outliers → analyze_market       │
│  ─ build_analysis_dashboard → resolve_report_confidence           │
│  ─ evaluate_publication_gates                                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  MarketSnapshot (DB) — report_json + status + meta سئو           │
└──────────────────────────┬───────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    /market/        /market/{city}/   /market/{city}/{nb}/
    MarketSitemap   schema + FAQ      city landings (Wave 7)
```

### ۴.۱ اصل طراحی: Snapshot-Driven

- **هر URL ثابت**؛ محتوا از `MarketSnapshot.report_json` رندر می‌شود.
- **Rebuild** با signal/cron — نه analyze در هر HTTP request.
- **همان pipeline میزکار** — بدون duplicate logic تحلیل.

---

## ۵. URLها و ساختار صفحات

### ۵.۱ الگوی URL

| لایه | URL | وضعیت انتشار |
|------|-----|--------------|
| ایندکس | `/market/` | همیشه — فقط شهرهای `published` لیست می‌شوند |
| شهر | `/market/{city_slug}/` | `status=published` |
| محله | `/market/{city_slug}/{neighborhood_slug}/` | `status=published` |
| استان (اختیاری — Wave 8+) | `/market/ostan/{province_slug}/` | بعداً |

**قواعد slug:** انگلیسی، lowercase، hyphen — مثال: `tehran` ، `jordan` ، `saadatabad`

### ۵.۲ شهرهای seed — Wave 6

| شهر | slug | محله‌های اولویت |
|-----|------|-----------------|
| تهران | `tehran` | جردن، سعادت‌آباد، نارمک، تهران‌پارس، شهرک غرب (+ ۱۵ محله دیگر) |
| مشهد | `mashhad` | — |
| اصفهان | `isfahan` | — |
| شیراز | `shiraz` | — |
| کرج | `karaj` | — |
| تبریز | `tabriz` | — |

### ۵.۳ ساختار محتوای هر صفحه

**صفحه شهر** (`/market/tehran/`):

| بخش | منبع داده |
|-----|-----------|
| H1 | قالب: «بازار املاک {شهر} — تحلیل قیمت بر اساس آگهی دیوار» |
| خلاصه اجرایی | `professional_summary` / `summary` / `market_brief` |
| کارت‌های KPI | `price_analysis` ، `data_quality.valid_count` ، `confidence` |
| جدول قیمت | median، P25، P75، min/max — `distribution_stats` |
| عمق بازار | `market_depth` (زیر بازار / سر به سر / بالای بازار) |
| احساس بازار | `market_sentiment` |
| نقدشوندگی | `liquidity` |
| بخش متراژ | `area_segments` |
| Grid محله‌ها | فقط محله‌های `published` — لینک به `/market/{city}/{nb}/` |
| روند (در صورت داده) | `price_trends` |
| FAQ داینامیک | `market/services/content.py` — از آمار واقعی |
| CTA | ثبت‌نام، `/property-pricing/` ، `/real-estate-crm/` |
| یادداشت داده | `publication_scope.line` |

**صفحه محله** — همان ساختار + breadcrumb + «محله‌های مرتبط» از `neighborhoods` (تا ۶ همسایه قیمتی).

**طول هدف:** ۱۲۰۰–۱۸۰۰ کلمه معادل — ترکیب بلوک‌های داده‌محور + FAQ؛ بدون پاراگراف خالی.

### ۵.۴ لندینگ‌های شهر — Wave 7 (جدا ولی هم‌داده)

| الگو | مثال | منبع آمار |
|------|------|-----------|
| `/crm-amlak-{city}/` | `/crm-amlak-tehran/` | همان `MarketSnapshot` شهر |
| `/robot-divar-{city}/` | `/robot-divar-tehran/` | همان snapshot + CTA ربات |

متن ثابت سئو + بلوک آمار داینامیک — الگوی `shop/seo_landings.py`.

---

## ۶. موتور تحلیل — reuse از workspace

### ۶.۱ مسیر pipeline (موجود — تغییر ندهید)

```text
listings_to_dataframe(listings)          # workspace/services/analyzer.py
    → filter_outliers(df, transaction_type)
    → compute_statistics(df_clean, transaction_type)
    → analyze_market(df_clean, transaction_type)    # workspace/services/valuation.py
    → compute_outliers_report(df, transaction_type)
    → build_analysis_dashboard(...)                 # workspace/services/analyzer.py
         └→ build_professional_report(...)           # workspace/services/market_analytics.py
              └→ enrich_report_for_agents(...)      # workspace/services/market_copy.py
    → resolve_report_confidence(prof)              # workspace/services/market_agent.py
```

### ۶.۲ فیلدهای کلیدی `report` برای رندر سئو

| کلید | کاربرد در صفحه market |
|------|------------------------|
| `price_analysis` | جدول قیمت، meta description |
| `market_depth` | بخش عمق بازار، نمودار توزیع |
| `neighborhoods` | grid محله، مقایسه |
| `area_segments` | بخش متراژ |
| `build_year` | بخش سن بنا |
| `amenities_coverage` / `amenity_valuation` | امکانات و اثر قیمت |
| `confidence` | badge اعتماد، gate |
| `data_quality` | تعداد آگهی، outlier |
| `publication_scope` | «بر اساس X فایل از تاریخ … تا …» |
| `liquidity` | نقدشوندگی |
| `market_sentiment` | وضعیت بازار خریدار/فروشنده |
| `price_trends` | روند (اگر `published_at` کافی باشد) |
| `insights` / `insight_sections` | پاراگراف‌های تحلیلی |
| `negotiation` | نکات مذاکره (بخش consultant) |
| `context` | از `detect_market_context` — نوع ملک/معامله |

### ۶.۳ امتیاز اعتماد — `compute_confidence_score`

فرمول موجود (`workspace/services/market_analytics.py`):

| جزء | وزن تقریبی |
|-----|------------|
| پایه | ۳۰ |
| نمونه (`sample_pts`) | تا ۲۰ — `8 + n_valid/40` |
| کیفیت (`quality_pts`) | تا ۲۸ — بر اساس `outlier_pct` |
| پایداری (`stability_pts`) | تا ۲۲ — بر اساس CV قیمت |

خروجی: `score` ، `display_score` ، `level` — برای gate و نمایش badge.

### ۶.۴ تحلیل محله‌ای — `neighborhood_price_analysis`

- گروه‌بندی روی ستون `neighborhood` در `Listing`
- حداقل `min_count=3` (برای صفحه عمومی محله: gate جدا — §۷)
- مرتب‌سازی بر اساس median — حداکثر ۱۲ محله در گزارش workspace؛ در market همه qualified نمایش داده می‌شوند

### ۶.۵ تشخیص زمینه — `detect_market_context`

برای تفکیک فروش/اجاره، مسکونی/اداری/کلنگی و برچسب‌های UI — از `dataset_name` ، `subcategory` ، `transaction_type` استفاده می‌شود. صفحات market **یک transaction_type غالب** دارند (gate §۷).

### ۶.۶ هشدار کیفیت — `_data_quality_warning`

اگر ملک اداری/تجاری با قیمت غیرواقعی باشد، هشدار در گزارش می‌آید — در صفحه عمومی هم نمایش داده شود (شفافیت E-E-A-T).

---

## ۷. Quality Gate — موتور انتشار

### ۷.۱ آستانه‌های تأییدشده (roadmap)

| # | معیار | آستانه | فیلد منبع |
|---|--------|--------|-----------|
| G1 | تعداد رکورد معتبر | **> ۲۵۰** | `data_quality.valid_count` |
| G2 | اعتماد تحلیل | **> ۷۵** | `confidence.display_score` |

### ۷.۲ آستانه‌های تکمیلی (پیشنهاد حرفه‌ای)

| # | معیار | آستانه | دلیل |
|---|--------|--------|------|
| G3 | تازگی داده | `publication_scope.date_to` ≤ ۹۰ روز | داده کهنه = misleading |
| G4 | انسجام جغرافیایی | ≥ ۸۰٪ listing با city/neighborhood مطابق geo entity | جلوگیری از آلودگی cross-city |
| G5 | outlier | `data_quality.outlier_pct` < ۲۵٪ | کیفیت فایل |
| G6 | یکنواختی معامله | یک `transaction_type` > ۷۰٪ نمونه | صفحه واحد per نوع معامله |
| G7 | حداقل محله (صفحه شهر) | ≥ ۳ محله neighborhood-level `published` **یا** یک city-wide dataset qualified | شهر بدون زیرمحله معتبر publish نشود |
| G8 | CV حداکثر | `price_analysis.*.cv` < ۴۵ (قابل تنظیم per segment) | بازارهای پراکنده غیرقابل تفسیر |

### ۷.۳ وضعیت‌های snapshot

| status | معنی | robots | sitemap |
|--------|------|--------|---------|
| `draft` | تحلیل شده، gate رد | `noindex, follow` | ❌ |
| `qualified` | gate پاس، منتظر تأیید ادمین (فاز ۱) | `noindex` یا preview | ❌ |
| `published` | منتشر | `index, follow` | ✅ |
| `stale` | قبلاً published، داده منقضی | `noindex` | ❌ تا rebuild |
| `blocked` | تطبیق geo ضعیف / نقض حریم | 404 یا noindex | ❌ |

**فاز ۱ (محافظه‌کار):** `qualified` → تأیید دستی ادمین → `published`  
**فاز ۲ (اتوماتیک کامل):** gate پاس → مستقیم `published`

### ۷.۴ پیاده‌سازی — `evaluate_publication_gates(report, geo, level)`

```python
# market/services/qualify.py (مفهومی)
@dataclass
class GateVerdict:
    ok: bool
    status: str          # published | draft | stale | blocked
    failures: list[str]  # ['G1: valid_count=180 < 250', ...]
    warnings: list[str]  # هشدار بدون block

def evaluate_publication_gates(report, *, level, geo_entity, settings) -> GateVerdict: ...
```

تست واحد اجباری — `market/tests/test_qualify.py`.

---

## ۸. منبع داده و حریم خصوصی

### ۸.۱ اصل

صفحات `/market/` **عمومی** هستند. دیتاست کاربر **خصوصی** است (`Dataset.user`). هیچ‌گاه روی صفحه عمومی نمایش داده نمی‌شود:

- `token` آگهی، `link` ، `title` کامل، `description` ، `images`
- نام فایل کاربر، `dataset_id` ، `user_id`

فقط **آمار تجمیعی** منتشر می‌شود.

### ۸.۲ منابع مجاز

| منبع | `source` | فاز | توضیح |
|------|----------|-----|--------|
| Reference | `reference` | ۱ | فایل‌های آپلودشده توسط ادمین با flag `is_public_reference=True` |
| Bot internal | `reference` | ۱ | خروجی ربات استخراج سایت |
| Federated | `federated` | ۲ | چند dataset با `allow_public_aggregate=True` از کاربران |

### ۸.۳ تجمیع federated (فاز ۲)

- چند snapshot معتبر برای یک `GeoNeighborhood`
- میانه وزن‌دار بر اساس `valid_count`
- `SnapshotSource` audit trail — بدون افشای منبع به بازدیدکننده

### ۸.۴ تطبیق جغرافیایی

از منطق موجود `folder_import.py` الهام بگیرد:

- `_parse_location_dirs` — استان/شهر/منطقه از مسیر فایل
- `Dataset.city` ، `Dataset.district` ، `Listing.neighborhood`
- `GeoNeighborhood.aliases` — JSON لیست نام‌های جایگزین (مثلاً «سعادت آباد» = «سعادت‌آباد»)

**Fuzzy match ضعیف** → `status=blocked` + صف admin — نه auto-publish.

---

## ۹. مدل داده — اپ `market`

### ۹.۱ ساختار پیشنهادی فایل‌ها

```text
market/
  __init__.py
  apps.py
  models.py
  admin.py
  urls.py
  views.py
  sitemaps.py
  signals.py                    # post_save Dataset → enqueue rebuild
  management/commands/
    seed_geo_registry.py        # شهرها و محله‌های Wave 6
    rebuild_market_snapshots.py
  services/
    qualify.py                  # evaluate_publication_gates
    slugify_fa.py               # نرمال‌سازی فارسی → slug
    geo_match.py                # تطبیق dataset → GeoCity/GeoNeighborhood
    aggregate.py                  # rollup شهر از محله‌ها
    snapshot_builder.py         # wrap workspace pipeline
    content.py                  # meta_title, faq_items, prose blocks
    schema.py                   # JSON-LD
  tests/
    test_qualify.py
    test_snapshot_builder.py
    test_geo_match.py
    test_views.py
templates/market/
  index.html
  city.html
  neighborhood.html
  includes/
    kpi_cards.html
    price_table.html
    neighborhood_grid.html
    faq.html
    data_freshness.html
static/css/mizkar-market.css
```

### ۹.۲ مدل‌ها

#### `GeoCity`

| فیلد | نوع | توضیح |
|------|-----|--------|
| `name_fa` | CharField | تهران |
| `slug` | SlugField unique | tehran |
| `province_fa` | CharField | تهران |
| `province_slug` | SlugField | tehran |
| `priority` | PositiveSmallInteger | برای sort در `/market/` |
| `is_active` | BooleanField | |
| `aliases` | JSONField | `["تهران", "Tehran"]` |

#### `GeoNeighborhood`

| فیلد | نوع |
|------|-----|
| `city` | FK → GeoCity |
| `name_fa` | CharField |
| `slug` | SlugField |
| `aliases` | JSONField |
| `is_active` | BooleanField |

`unique_together`: `(city, slug)`

#### `MarketSnapshot`

| فیلد | نوع | توضیح |
|------|-----|--------|
| `level` | choices: `city` \| `neighborhood` |
| `city` | FK GeoCity |
| `neighborhood` | FK GeoNeighborhood null |
| `transaction_type` | CharField | مثلاً `فروش آپارتمان` |
| `subcategory` | CharField blank |
| `status` | choices: draft/qualified/published/stale/blocked |
| `report_json` | JSONField | خروجی کامل `build_professional_report` + enrich |
| `confidence_score` | PositiveSmallInteger | denormalized |
| `valid_count` | PositiveIntegerField | denormalized |
| `gate_failures` | JSONField | آخرین دلایل رد |
| `content_hash` | CharField(64) | SHA256 از metrics کلیدی — skip rebuild |
| `published_at` | DateTimeField null |
| `rebuilt_at` | DateTimeField |
| `data_through` | DateField null | از `publication_scope.date_to` |

ایندکس: `(status, city)` ، `(city, neighborhood, status)`

#### `SnapshotSource` (audit)

| فیلد | نوع |
|------|-----|
| `snapshot` | FK MarketSnapshot |
| `dataset` | FK workspace.Dataset |
| `weight` | FloatField |
| `included_at` | DateTimeField |
| `valid_count` | PositiveIntegerField |

#### تغییرات `workspace.Dataset` (فاز ۱)

| فیلد جدید | نوع | پیش‌فرض |
|-----------|-----|---------|
| `is_public_reference` | BooleanField | False |
| `allow_public_aggregate` | BooleanField | False |
| `geo_city` | FK market.GeoCity null | |
| `geo_neighborhood` | FK market.GeoNeighborhood null | |

---

## ۱۰. Snapshot Builder — جریان rebuild

### ۱۰.۱ تریگرها

| رویداد | اقدام |
|--------|--------|
| `post_save` Dataset (بعد از import listings) | `rebuild_for_dataset.delay(dataset_id)` |
| Cron شبانه ۰۳:۰۰ | `rebuild_market_snapshots --stale-only` |
| دستی | `rebuild_market_snapshots --city=tehran --force` |

### ۱۰.۲ الگوریتم `rebuild_snapshot(geo_entity, datasets)`

1. جمع‌آوری `Listing` از datasets مرتبط (فیلتر `is_active` ، geo match)
2. اجرای pipeline §۶.۱
3. `resolve_report_confidence`
4. `evaluate_publication_gates`
5. مقایسه `content_hash` — اگر برابر و status=published → skip
6. `MarketSnapshot.objects.update_or_create(...)`
7. اگر شهر: `aggregate_city_from_neighborhoods()` برای rollup
8. log در admin / structlog

### ۱۰.۳ Rollup شهر

اگر city-wide dataset نباشد:

- از snapshots محله‌های `published` در همان شهر
- میانه وزن‌دار `price_per_sqm.median` ، sum `valid_count`
- `neighborhoods` grid از لیست snapshots فرزند

---

## ۱۱. تولید محتوای سئو — `market/services/content.py`

### ۱۱.۱ Meta tags

| صفحه | title (الگو) |
|------|--------------|
| شهر | `قیمت ملک {شهر} \| تحلیل بازار املاک دیوار — فایلینگ دیوار` |
| محله | `بازار املاک {محله} {شهر} \| قیمت هر متر — فایلینگ دیوار` |

`meta_description`: median قیمت/متر + تعداد آگهی + بازه تاریخ — حداکثر ۱۵۵ کاراکتر.

### ۱۱.۲ FAQ داینامیک (حداقل ۵ سؤال)

قالب‌ها — مقادیر از `report`:

1. «میانگین قیمت هر متر در {محله/شهر} چقدر است؟» → `price_analysis.price_per_sqm.median_fmt`
2. «این تحلیل بر اساس چند آگهی است؟» → `valid_count` + `publication_scope`
3. «بازه قیمت ۵۰٪ بازار چقدر است؟» → `range_50_fmt`
4. «وضعیت بازار برای خریدار چگونه است؟» → `market_sentiment.label`
5. «داده‌ها چقدر قابل اعتماد است؟» → `confidence.level` + `display_score`

برای schema: الگوی `blog/seo_schema.py` — `FAQPage` JSON-LD.

### ۱۱.۳ پاراگراف‌های تحلیلی

اولویت منبع (بدون LLM):

1. `professional_summary.intro`
2. `insights` / `insight_sections`
3. `build_market_brief` fallback
4. `publication_scope.line`

**فاز اختیاری:** یک پاراگراف LLM فقط اگر `confidence > 85` — cache در `report_json['seo_narrative']`.

### ۱۱.۴ robots

```django
{# templates/market/base — مفهومی #}
<meta name="robots" content="{% if snapshot.status == 'published' %}index, follow{% else %}noindex, follow{% endif %}">
```

صفحه `draft`/`blocked`: 404 برای slug نامعتبر geo — یا 200 با noindex (ترجیح: 404 برای blocked).

---

## ۱۲. SEO فنی

### ۱۲.۱ Sitemap — `market/sitemaps.py`

```python
class MarketSnapshotSitemap(SiteAwareSitemap):
    changefreq = 'weekly'
    priority = 0.8  # neighborhood: 0.75

    def items(self):
        return MarketSnapshot.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.rebuilt_at
```

ثبت در `divar_shop/sitemaps.py`:

```python
sitemaps = {
  ...
  'market': MarketSnapshotSitemap,
}
```

### ۱۲.۲ Schema.org — `market/services/schema.py`

| نوع | کاربرد |
|-----|--------|
| `BreadcrumbList` | خانه → market → شهر → محله |
| `FAQPage` | FAQ داینامیک |
| `Dataset` | نام، `temporalCoverage` ، `variableMeasured` ، `provider` |
| `WebPage` | `dateModified` = `rebuilt_at` |

الگوی پیاده‌سازی: `shop/seo_landings.py` → `landing_schema_json`.

### ۱۲.۳ Canonical

همیشه URL کامل با `SITE_URL` — مثل `shop/templatetags/seo_tags.py`.

### ۱۲.۴ Internal linking

| از | به |
|----|-----|
| `/market/{city}/` | `/property-pricing/` ، `/real-estate-market-analysis/` |
| `/market/{city}/{nb}/` | شهر parent، ۳ محله مرتبط، pillar |
| `/real-estate-market-analysis/` | grid شهرهای published |
| `/property-pricing/` | لینک به تهران + محله‌های برتر |
| footer | بعد از Wave 6: «بازار املاک» → `/market/` |
| بلاگ (#36, #38) | `/market/tehran/` ، `/market/tehran/jordan/` |

### ۱۲.۵ UI/CSS

- تم روشن — هم‌راستا با `mizkar-seo-landing.css` و `data-theme="light"`
- CSS جدا: `mizkar-market.css` — بدون بار workspace
- جدول قیمت responsive، badge اعتماد، lazy charts (اگر نمودار اضافه شد)
- CWV: بدون JS اجباری برای محتوا؛ `mk-reveal` فقط با JS

---

## ۱۳. Admin و عملیات

### ۱۳.۱ پنل ادمین

- لیست snapshots با فیلتر `status` ، `confidence_score` ، `city`
- نمایش `gate_failures` — یک کلیک «Publish» برای فاز ۱
- لینک به datasetهای منبع (`SnapshotSource`)
- Action: `rebuild selected`

### ۱۳.۲ مانیتورینگ

| متریک | هشدار |
|-------|--------|
| تعداد `published` | گزارش هفتگی |
| snapshots `stale` | > ۱۰٪ → بررسی cron |
| میانگین confidence published | < ۸۰ → بازبینی gate |
| 404 spike روی `/market/` | log nginx |

### ۱۳.۳ Deploy checklist

```bash
python manage.py migrate
python manage.py seed_geo_registry
python manage.py rebuild_market_snapshots --publish  # فقط qualified
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop
```

---

## ۱۴. تست‌ها

| فایل | پوشش |
|------|------|
| `test_qualify.py` | G1–G8 edge cases |
| `test_geo_match.py` | aliases، مسیر فایل، city/district |
| `test_snapshot_builder.py` | mock listings → report shape |
| `test_content.py` | FAQ و meta طول |
| `test_views.py` | 200 published، 404 blocked، noindex draft |
| `test_sitemaps.py` | فقط published در sitemap |

استفاده از fixtures مشابه `workspace/tests.py` — `listings_to_dataframe` با ۳۰۰+ رکورد synthetic.

---

## ۱۵. فازبندی پیاده‌سازی

| فاز | محتوا | خروجی |
|-----|--------|--------|
| **M0** | اپ `market` + migrations + geo seed | مدل‌ها |
| **M1** | `qualify.py` + tests | gate بدون UI |
| **M2** | `snapshot_builder.py` + command | snapshot در DB |
| **M3** | views + templates + CSS | صفحات با noindex |
| **M4** | sitemap + schema + robots | SEO فنی |
| **M5** | reference datasets تهران | اولین صفحات published |
| **M6** | signals/cron + admin | اتوماسیون |
| **M7** | ۶ شهر Wave 6 | deploy |
| **M8** | federated + auto-discovery | Wave 8 scale |
| **M9** | city landings Wave 7 | `/crm-amlak-{city}/` |

**وابستگی:** M5 بعد از Wave 4 لندینگ‌ها (لینک داخلی pillar).

---

## ۱۶. ریسک‌ها و mitigation

| ریسک | mitigation |
|------|------------|
| Thin content / Google Useful Content | gate سخت + داده واقعی + FAQ |
| داده کهنه | `stale` auto + تاریخ روی صفحه |
| Cannibalization با بلاگ | بلاگ = آموزش؛ market = آمار؛ لینک یک‌طرفه |
| آلودگی geo (تهران/تهران/قیطریه) | `geo_match` + aliases + G4 |
| حریم خصوصی | فقط aggregate؛ audit `SnapshotSource` |
| Performance | snapshot cache؛ بدون pandas در view |
| مقیاس ۳۰۰۰ URL | sitemap index؛ pagination در `/market/` |

---

## ۱۷. تنظیمات — `settings.py`

```python
# پیشنهاد — market/programmatic.py یا constants
MARKET_GATE_MIN_VALID_COUNT = 250
MARKET_GATE_MIN_CONFIDENCE = 75
MARKET_GATE_MAX_OUTLIER_PCT = 25
MARKET_GATE_MAX_DATA_AGE_DAYS = 90
MARKET_GATE_MIN_GEO_COHERENCE_PCT = 80
MARKET_AUTO_PUBLISH = False          # True در فاز ۲
MARKET_NEIGHBORHOOD_MIN_VALID = 250  # همان G1 برای محله
MARKET_CITY_MIN_NEIGHBORHOODS = 3
```

---

## ۱۸. ارجاع فایل‌های موجود

| فایل | نقش در programmatic |
|------|----------------------|
| `workspace/services/analyzer.py` | `build_analysis_dashboard` ، `filter_outliers` |
| `workspace/services/market_analytics.py` | `build_professional_report` ، `compute_confidence_score` ، `neighborhood_price_analysis` |
| `workspace/services/market_agent.py` | `resolve_report_confidence` ، `enrich_report_for_agents` |
| `workspace/services/market_copy.py` | `build_market_brief` ، متن تحلیل |
| `workspace/services/market_context.py` | `detect_market_context` |
| `workspace/services/valuation.py` | `analyze_market` ، `listings_to_dataframe` |
| `workspace/services/folder_import.py` | تطبیق مسیر استان/شهر/محله |
| `workspace/services/tools.py` | `build_market_snapshot` (سبک — فقط ابزار) |
| `workspace/models.py` | `Dataset` ، `Listing` |
| `shop/seo_landings.py` | الگوی لندینگ + schema |
| `divar_shop/sitemaps.py` | الگوی sitemap |
| `blog/seo_schema.py` | الگوی FAQ schema |
| `templates/shop/seo_meta.html` | meta tags |
| `templates/workspace/analyze/index.html` | مرجع UI بلوک‌های تحلیل |

---

## ۱۹. چک‌لیست قبل از اولین publish

- [ ] Wave 4 لندینگ‌ها live و لینک به `/market/` دارند
- [ ] حداقل ۱ محله تهران: valid_count > 250 ، confidence > 75
- [ ] صفحه `published` در sitemap.xml دیده می‌شود
- [ ] صفحه `draft` در sitemap نیست و noindex است
- [ ] Schema FAQ در Rich Results Test معتبر است
- [ ] هیچ token/link آگهی در HTML نیست
- [ ] `publication_scope.line` روی صفحه visible است
- [ ] تست‌های `test_qualify` و `test_views` پاس
- [ ] `collectstatic` + cache bust CSS

---

*پایان مشخصات v1.0 — آماده برای شروع M0 (اپ market)*
