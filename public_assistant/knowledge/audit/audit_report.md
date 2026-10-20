# گزارش ممیزی دانش محصول — Phase 1.1 (Audit Hardening)

**تاریخ:** 2026-10-20

## ۱. کاتالوگ

- ورودی‌های کاتالوگ (همه entityها): **80**
- قابلیت‌های منطقی (`entity_type=feature`): **33**
- توزیع entity: {'feature': 33, 'help_section': 2, 'help_topic': 45}
- وضعیت انتشار: {'shipped': 32, 'gated': 1, 'documented_in_help': 47}
- تأیید `code_reviewed` (feature): **24**

### پلتفرم‌ها

- URL inventory (parsed): {'total_parsed': 220, 'user_page': 165, 'api': 53, 'internal': 2, 'with_params': 96}
- **اندروید:** 62 route — ok
- **ویندوز:** inferred_from_src_layout

## ۲. پوشش دانشنامه

### heuristic_coverage (تخمین ساختار متن)

| عمق | تعداد |
|-----|------:|
| `howto` | 18 |
| `overview` | 16 |
| `none` | 1 |

### verified_coverage (تأییدشده / نیازمند بازبینی)

| وضعیت | تعداد |
|--------|------:|
| `overview` | 1 |
| `needs_review` | 33 |
| `none` | 1 |

- **full تأییدشده:** 0
- **needs_review:** 33

> وضعیت `full` فقط با `code_reviewed` + `last_verified_at` + `technical_refs` + مراحل واقعی مجاز است.

## ۳. بازیابی (offline markdown — بدون تغییر DB)

- mode: **offline_markdown**
- سؤالات eval: **97**

| معیار | Article (dedup) | Chunk |
|-------|----------------:|------:|
| hit@1 | 70.1% | 70.1% |
| hit@3 | 85.6% | 81.4% |
| hit@5 | 85.6% | 85.6% |

- out-of-scope accuracy: **0.0%** (4 سؤال)
- scenario how-to hit@5: **1.0**

## ۴. Gap backlog (فقط feature)

- P0: **15** | P1: **7** | P2: **11**

## ۵. Source index

- missing files: **0**
- feature بدون article/path: **1**

## ۶. Staleness

فایل `staleness_registry.yaml` + `staleness_diff.json` — diff نسبت به snapshot قبلی.

## ۷. محدودیت‌ها / QA دستی

- رفتار UI اندروید/ویندوز و feature flagهای production
- تطبیق `documented_in_help` با نسخه اجرایی
- تأیید `needs_review` → `full` در فاز ۲
