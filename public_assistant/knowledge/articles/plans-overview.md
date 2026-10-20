---
id: plans-overview
title: پلن‌ها و اشتراک — نمای کلی
category: اشتراک و لایسنس
summary: پلن شخصی، آزمایشی خریدنی و آژانس — قیمت زنده از فروشگاه.
platforms:
- web
- android
- windows
subscription_note: ''
prerequisites: ''
limitations: قیمت در دانشنامه ثابت نیست.
synonyms:
- قیمت
- اشتراک
- لایسنس
- خرید پلن
- چنده
- هزینه
links:
- label: خرید ربات استخراج
  url: /products/divar-extraction-bot/buy/
- label: محصولات
  url: /products/
- label: راهنمای لایسنس
  url: /license-guide/
technical_refs:
- shop/models.py LicensePlan
- shop/services/plan_pricing.py
reviewed_at: '2026-10-19'
is_public: true
is_active: true
---

## منبع معتبر قیمت
**قیمت، مدت و تخفیف حجمی** روی کارت محصول در فروشگاه تعریف می‌شود و ممکن است تغییر کند. دستیار عمومی برای اعداد به‌روز از **همان منطق فروشگاه** استفاده می‌کند؛ این مقاله قیمت ثابت نگه نمی‌دارد.

## دسته پلن‌ها
- **شخصی:** یک مشاور — ماهانه، سه‌ماهه، سالانه (+ پلن آزمایشی ۷روزه **خریدنی**)
- **آژانس:** چند لایسنس مستقل در یک سفارش (معمولاً ۲ تا ۲۵) با تخفیف حجمی

## مسیر خرید
`/products/divar-extraction-bot/buy/` — یا از `/products/` محصول «ربات استخراج دیوار».

## لایسنس
پس از پرداخت موفق، کلید در حساب شما صادر می‌شود. راهنما: `/license-guide/`.

## تمدید
از حساب: `/licenses/<id>/renew/` برای لایسنس موجود.
