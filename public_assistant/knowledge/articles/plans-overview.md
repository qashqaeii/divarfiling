---
id: plans-overview
title: پلن‌ها و اشتراک — نمای کلی
category: اشتراک و لایسنس
summary: پلن‌ها از فروشگاه تعریف می‌شوند؛ قیمت و مدت را همیشه از صفحه خرید بخوانید.
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
links:
- label: محصولات
  url: /products/
- label: راهنمای لایسنس
  url: /license-guide/
technical_refs:
- shop/models.py LicensePlan
- shop/urls.py
reviewed_at: '2026-10-19'
is_public: true
is_active: true
---

## منبع معتبر قیمت
قیمت، مدت و ویژگی‌های روی **کارت هر محصول** در فروشگاه خوانده می‌شود و ممکن است به‌روز شود. این دستیار قیمت ثابت در حافظه نگه نمی‌دارد.

## مسیر خرید
`/products/` لیست محصولات؛ صفحه هر محصول و `/buy/` برای خرید.

## لایسنس
پس از پرداخت موفق، کلید لایسنس صادر و در حساب شما قابل فعال‌سازی است. راهنما: `/license-guide/`.

## تمدید
مسیر تمدید لایسنس موجود: `/licenses/<id>/renew/` (از حساب و سفارش‌های خودتان).
