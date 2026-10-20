# گزارش موج ۱ — فاز ۲ (Deep Product Knowledge)

**شاخه:** `feature/public-assistant-knowledge-phase2-wave1`  
**تاریخ:** 2026-10-20  
**مبنا:** خروجی‌های ممیزی فاز ۱.۱ (`feature_catalog.yaml`, `coverage_matrix.csv`, `source_index.json`, `knowledge_gap_backlog.md`, `retrieval_baseline.json`)

---

## ۱. خلاصه

موج اول دانش تخصصی برای **CRM (مخاطب و ملک شخصی)**، **فایلینگ (آگهی/dataset)**، **استخراج→میزکار**، **لینک عمومی مشتری** و **رفع مشکل‌های پرتکرار** تکمیل شد. رفتار از کد backend، templateها و URLهای workspace تأیید شده است؛ مسیر یا قابلیت تأییدنشده اختراع نشده است.

**اصل:** افزایش دانش واقعی و قابلیت آموزش دستیار — نه صرفاً تعداد فایل.

---

## ۲. مقالات

### ایجادشده (۶)

| شناسه | عنوان |
|--------|--------|
| `crm-contacts-manage` | ثبت، ویرایش، ادغام و مدیریت مخاطب |
| `crm-property-owner-contact` | شماره تماس و نام مالک در فرم ملک |
| `crm-property-folders-cabinets` | زونکن و کمد املاک شخصی |
| `crm-property-create-edit` | ساخت و ویرایش فایل شخصی |
| `filing-listing-manage` | مدیریت آگهی در مجموعه فایل |
| `support-wave1-crm-filing` | مشکلات رایج موج ۱ |

### عمیق‌سازی / به‌روزرسانی (۷)

- `crm-contacts.md`
- `crm-personal-properties.md`
- `share-public-file.md`
- `crm-matching.md`
- `extractor-to-filing.md`
- به‌علاوه پیوندها در `catalog_seed.yaml` برای featureهای مرتبط

**جمع:** ۶ مقاله جدید + ۷ مقاله اصلاح‌شده (۱۳ فایل محتوایی در این موج).

---

## ۳. سناریوهای تحت پوشش (موج ۱)

| سناریو | مقاله(های) اصلی |
|--------|------------------|
| ثبت / ویرایش / ادغام مخاطب | `crm-contacts`, `crm-contacts-manage` |
| ساخت و ویرایش فایل شخصی | `crm-property-create-edit`, `crm-personal-properties` |
| شماره و نام مالک | `crm-property-owner-contact` |
| زونکن / کمد | `crm-property-folders-cabinets` |
| مدیریت آگهی dataset | `filing-listing-manage`, `filing-collections` |
| استخراج → میزکار | `extractor-to-filing`, `support-wave1-crm-filing` |
| لینک عمومی مشتری | `share-public-file` |
| ارسال / نمایش / غیرفعال لینک | `share-public-file` |
| تطبیق مخاطب–ملک | `crm-matching` |
| خطاهای رایج موج ۱ | `support-wave1-crm-filing` |

---

## ۴. منابع فنی بررسی‌شده (نمونه)

- `workspace/crm_views.py`, `workspace/views.py`, `workspace/urls.py`
- `workspace/services/crm_matching.py`
- `templates/workspace/crm/includes/property_form_sections.html` (فیلدهای مالک)
- `templates/workspace/crm/contacts/detail.html` (تب پیشنهادها)
- `templates/workspace/includes/public_share_modal.html` (لینک فعال / `is_active`)
- `templates/workspace/listings/detail.html`, `templates/workspace/crm/properties/detail.html`
- `property_folders_tier.html`, `property_cabinets_tier.html`
- تست‌های `public_assistant/tests/test_product_audit.py`, `test_wave1_knowledge.py`, `eval_wave1_dataset.py`

جزئیات پیاده‌سازی حساس یا مسیرهای داخلی در متن عمومی مقالات نیامده است.

---

## ۵. پوشش ممیزی (`verified_coverage`)

پس از `audit_product_knowledge` (read-only):

- چند feature موج ۱ با **`verified_coverage=full`** و `heuristic_coverage=howto` ثبت شد (مثلاً `crm-contacts-hub`, `crm-contacts-merge`, `crm-personal-properties-hub`, `crm-property-owner-contact`, `crm-property-folders-cabinets`) — بر اساس مقاله + `technical_refs` + `code_reviewed` در seed.
- مواردی مثل `filing-listing-detail`, `extractor-sync-filing`, `share-public-file` همچنان **`needs_review`** تا QA دستی UI اندروید/ویندوز و سناریوهای لایسنس.

**نیازمند QA دستی (نمونه):**

- دکمه‌های دقیق در اپ اندروید برای اشتراک و «افزودن به فایل شخصی»
- رفتار لینک `/p/` در نسخه production و فیلدهای واقعاً قابل نمایش
- ادغام مخاطب در edge caseهای مالکیت تیمی
- زمان واقعی sync استخراج در شبکه ضعیف

---

## ۶. ارزیابی و بازیابی

### مجموعه سؤال موج ۱ (`eval_wave1_dataset.py` — ۱۸ سؤال)

شامل سؤالات ساده، تخصصی، محاوره‌ای، مراحل، خطا و محدودیت؛ از جمله:

- «چطوری فایل شخصی داشته باشم؟»
- «شماره مالک کجا وارد میشه؟»
- «چطوری لینک برای مشتری بفرستم؟»

**نتیجه (offline markdown، پس از تکمیل موج):**

- `test_wave1_knowledge`: **گذر** (hit@5 ≥ 70٪؛ در عمل **100٪** پس از اصلاح محتوا و رتبه‌بندی کاندید در audit offline).

### eval کامل (۹۷ سؤال)

| معیار | قبل موج ۱ (`retrieval_baseline_pre_phase2_wave1.json`) | بعد موج ۱ (`retrieval_baseline.json` / گزارش ممیزی) |
|--------|--------------------------------------------------------|------------------------------------------------------|
| article hit@5 | **~85.6٪** | **~92.8٪** |
| article hit@1 | — | **~74.2٪** |

**اصلاح audit (نه موتور RAG production):** در `retrieval_offline.py`، برش اولین ۱۰۰ کاندید بر اساس ترتیب فایل باعث می‌شد مقالات دیررس (مثل `share-public-file`) هرگز امتیازدهی نشوند؛ اکنون قبل از برش، بر اساس **تعداد توکن‌های منطبق** مرتب می‌شوند.

### تست DB + `sync_public_knowledge` (`test_hardening.EvalRetrievalTest`)

- hit@5 حدود **~72٪** (آستانه ۸۰٪) — **شکست باقی‌مانده**.
- علت محتمل: رقابت مقالات جدید با hubهای قبلی در همان eval عمومی، بدون تغییر `retrieval.py`.
- **اقدام پیشنهادی موج بعد / فاز ۳:** بهبود ranker یا تفکیک hub vs specialist در scoring؛ یا به‌روزرسانی انتظارات eval برای سؤالات مرزی — **بدون** boost دستی صرف.

---

## ۷. سؤالاتی که هنوز پاسخ قطعی در eval ندارند (نمونه از eval عمومی)

- «فایلینگ دیوار چیست» → گاهی `extractor-overview` به‌جای intro
- «تفاوت crm و فایلینگ» → پراکندگی بین advisor و intro
- «مجموعه فایل» کوتاه → تداخل با مقالات CRM/استخراج
- سؤالات قیمت/پلن و لایسنس چندحسابی

این‌ها خارج از محدوده موج ۱ هستند و در backlog P0/P1 ممیزی باقی می‌مانند.

---

## ۸. تست‌های اجراشده

| تست | نتیجه |
|-----|--------|
| `public_assistant.tests.test_wave1_knowledge` | **OK** |
| `public_assistant.tests.test_product_audit` | **OK** (۸ تست) |
| `python manage.py audit_product_knowledge` | **OK** (read-only) |
| `public_assistant.tests.test_hardening` (EvalRetrieval DB) | **FAIL** (~72٪ vs 80٪) |

---

## ۹. برنامه موج بعدی (پیشنهاد)

1. **معاملات، پیگیری، یادآوری، تقویم** — مقالات specialist + eval سناریویی
2. **آژانس، نقش‌ها، اشتراک داخلی ملک** — تفکیک از لینک `/p/`
3. **قراردادها، لایسنس پیشرفته، AI CRM**
4. QA دستی موارد `needs_review` موج ۱ → ارتقا به `full` با `last_verified_at`
5. فاز ۳: رتبه‌بازیابی production + کاهش تداخل hub/specialist

---

## ۱۰. قبل از Merge

- [ ] بازبینی محتوای فارسی و مسیرهای UI در staging
- [ ] `sync_public_knowledge` در محیط deploy (برای chat واقعی با DB)
- [ ] تصمیم درباره آستانه `test_hardening` یا اصلاح retrieval در PR جدا
- [ ] تأیید محصول روی لیست QA دستی بالا

**Merge توصیه نمی‌شود** تا بازبینی QA و تصمیم درباره تست hardening گرفته شود.
