# Wave 1 Release Gate — گزارش کوتاه قبل از Merge

**تاریخ:** 2026-10-20  
**شاخه:** `feature/public-assistant-knowledge-phase2-wave1`

## ۱. اصلاح ادعای شماره مالک در لینک عمومی

**بررسی کد:** `property_public_share._property_display_data` شماره مالک را در دادهٔ صفحه عمومی قرار نمی‌دهد؛ `public_share_modal.html` در تب «صفحه مشتری» فقط سوئیچ‌هایی مثل لینک دیوار، آدرس کامل، یادداشت داخلی و … دارد؛ **موبایل مشاور** در تب **پروفایل من** است.

**متن اصلاح‌شده در:** `crm-property-owner-contact.md`, `share-public-file.md`, `support-wave1-crm-filing.md` — حذف ادعای «سوئیچ نمایش شماره مالک»؛ تأکید بر تماس مشاور و عدم انتشار شماره مالک CRM روی `/p/`.

## ۲. بازیابی Production (Django DB)

**ریشه:** پس از افزایش مقالات، `retrieve()` فقط **۱۰۰ chunk اول** بر اساس ترتیب PK دیتابیس را امتیازدهی می‌کرد؛ chunkهای مرتبط (مثلاً `share-public-file`) اغلب خارج از این ۱۰۰ بودند — مشابه مشکل قبلی در `retrieval_offline.py`.

**اصلاح حداقلی در `retrieval.py`:**
- واکشی تا **۴۰۰** کاندید با OR توکن‌ها
- اگر بیش از ۱۰۰ باشد، **مرتب‌سازی بر اساس تعداد توکن منطبق** روی `search_blob`، سپس برش به ۱۰۰
- بدون boost دستی جدید؛ منطق `_score_chunk` و `_intent_boost` دست‌نخورده

**هزینه:** یک query با حداکثر ۴۰۰ ردیف `KnowledgeChunk` با `only()` — قابل قبول برای مسیر چت.

## ۳. معیارهای قطعی

| معیار | نتیجه |
|--------|--------|
| `EvalRetrievalTest` hit@3 ≥ 80٪ | **گذر** (تست CI) |
| موج ۱ روی DB hit@5 ≥ 85٪ | **گذر** (`test_wave1_db_retrieval_hit_at_5`) |
| ۵ سؤال اسکرین‌شات در DB hit@5 | **گذر** (`test_screenshot_gate_db_retrieval`) |
| ادعای شماره مالک | **اصلاح‌شده** |
| `test_hardening` کامل | **OK** (۱۲ تست) |
| `verified_coverage=full` بدون QA UI | **ادعا نمی‌شود** — بدون تغییر در seed برای full جدید |

## ۴. آمار بازیابی (eval ۹۷ سؤال) — DB در برابر offline

مقادیر از `wave1_release_gate_metrics.json` پس از `sync_public_knowledge` (محیط dev/test):

| معیار | DB (`retrieve`) | Offline (markdown) |
|--------|----------------:|-------------------:|
| article hit@3 | **92.8٪** | **92.8٪** |
| article hit@5 | **92.8٪** | **92.8٪** |

موج ۱ (۱۸ سؤال) روی DB: hit@3 **88.9٪**، hit@5 **94.4٪** — تنها miss در hit@5: «از dataset به crm» (زیر آستانه تست ۸۵٪ نیست).

۵ سؤال اسکرین‌شات: همه در hit@5 DB — `test_screenshot_gate_db_retrieval`.

## ۵. محدوده

- مقاله جدید نه
- UI / migration / production deploy نه
- فقط اصلاح متن سه مقاله + `retrieval.py` + تست‌های gate

## ۶. قبل از Merge

1. `sync_public_knowledge` در staging/production پس از deploy محتوا
2. QA دستی UI اشتراک (تأیید نهایی متن شماره مالک)
3. Merge پس از تأیید شما
