---
id: agency-vs-personal
title: اشتراک شخصی در برابر آژانس
category: اشتراک و لایسنس
summary: تفاوت استفاده تک‌نفره و خرید چند لایسنس برای تیم.
platforms:
- web
- android
- windows
subscription_note: ''
prerequisites: ''
limitations: ''
synonyms:
- فرق شخصی و آژانس
- تیم
- چند مشاور
links:
- label: خرید
  url: /products/divar-extraction-bot/buy/
technical_refs:
- shop/models.py LicensePlan.allow_bulk_purchase
- shop/services/plan_pricing.py
reviewed_at: '2026-10-19'
is_public: true
is_active: true
---

## شخصی
یک مشاور با **یک لایسنس** فایل، CRM و استخراج خود را مدیریت می‌کند. برای کار مستقل مناسب است.

## آژانس
پلن آژانس **چند کلید مستقل** در یک سفارش می‌دهد (هر مشاور کلید خودش). مدیر می‌تواند کلیدها را به اعضا تخصیص دهد و فضای آژانس را مدیریت کند.

## تخفیف حجمی
برای خرید آنلاین آژانس، تخفیف بر اساس **تعداد لایسنس** در سفارش اعمال می‌شود (طبق فروشگاه). حداقل و حداکثر تعداد روی کارت پلن نوشته شده است.

## امکانات
هسته محصول (فایلینگ، CRM، استخراج) در پلن‌های زمانی مشابه یکسان است؛ تفاوت اصلی **مدل استفاده** (تک‌نفره vs تیم) است.

## Seat
تخصیص صندلی/کلید — مقاله «صندلی و لایسنس آژانس».
