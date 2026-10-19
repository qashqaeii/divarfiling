---
id: license-activation
title: فعال‌سازی لایسنس و ربات
category: اشتراک و لایسنس
summary: اتصال کلید لایسنس به دستگاه یا اپ.
platforms:
- web
- android
- windows
subscription_note: ''
prerequisites: ''
limitations: ''
synonyms: []
links:
- label: راهنمای لایسنس
  url: /license-guide/
technical_refs:
- workspace/services/access.py
- licenses/models.py
reviewed_at: '2026-10-19'
is_public: true
is_active: true
---

## فعال‌سازی
کلید لایسنس پس از خرید در حساب شما ظاهر می‌شود. در اپ اندروید یا ابزار ویندوز طبق راهنمای همان محصول فعال‌سازی کنید.

## چند دستگاه
فیلد `max_activations` روی هر پلن در فروشگاه تعیین می‌کند چند فعال‌سازی مجاز است.

## وضعیت‌ها
لایسنس می‌تواند منقضی، معلق یا تخصیص‌یافته به عضو تیم باشد؛ دسترسی میزکار تابع `has_active_bot_license` و قوانین سفارش پرداخت‌شده است.

## راهنما
صفحه `/license-guide/` و آموزش‌های `/amoozesh/` را ببینید.
