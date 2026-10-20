# گزارش ممیزی دانش محصول — دستیار عمومی فایلینگ دیوار

**تاریخ:** 2026-10-20

## ۱. قابلیت‌های کاربرمحور

- تعداد ورودی کاتالوگ: **80** (قابلیت منطقی، نه تعداد URL)
- وضعیت انتشار (از seed): {'shipped': 79, 'gated': 1}
- تأیید `code_reviewed`: **24** | سایر/نیازمند تأیید: **56**

### پلتفرم‌ها

- **وب (Django):** 213 مسیر در `workspace/urls.py`
- **راهنمای میزکار:** 15 بخش در `help_content.py`
- **اندروید:** در دسترس در monorepo — 62 route در `Routes` (ok)
- **ویندوز:** src موجود — inferred_from_src_layout

> برای قابلیت‌های اندروید/ویندوز بدون مقاله یا help وب، پوشش دانشنامه **نباید** از روی API وب استنتاج شود.

## ۲. پوشش دانشنامه

| عمق | تعداد |
|-----|------:|
| `full` | 18 |
| `howto` | 0 |
| `overview` | 61 |
| `none` | 1 |

## ۳. بازیابی RAG (baseline — بدون تغییر retrieval)

- سؤالات `eval_dataset`: **97**
- hit@1: **70.1%**
- hit@3: **81.4%** (همان cutoff تست `test_hardening` با `hits[:3]`)
- hit@5: **85.6%**
- تعداد miss در hit@5: **14**

### موانع کیفیت پاسخ (مشاهده‌شده)

- سقف ۱۰۰ نامزد قبل از امتیازدهی در `retrieval.py`
- وابستگی شدید به `_intent_boost` / `_intent_penalty`
- مقالات overview برای سؤالات how-to تخصصی
- `technical_refs` خالی در اکثر مقالات — نگهداری ضعیف

## ۴. شکاف‌ها و فاز ۲

- آیتم P0 در backlog: **38**
- جزئیات: `knowledge_gap_backlog.md`

## ۵. Source Index

- مراجع فایل گم‌شده (exists=false): **0**

## ۶. زیرساخت نگهداری

طراحی در `knowledge/audit/staleness_registry.yaml` و قالب مقاله در `knowledge/templates/article_specialist_template.md`. بدون migration در این فاز.
