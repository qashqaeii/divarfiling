---
id: agency-vs-personal
title: اشتراک شخصی در برابر آژانس
category: اشتراک و لایسنس
summary: خرید تک‌کاربره در برابر چند لایسنس و فضای آژانس.
platforms:
- web
- android
- windows
subscription_note: ''
prerequisites: ''
limitations: ''
synonyms: []
links: []
technical_refs:
- shop/models.py LicensePlan.allow_bulk_purchase
reviewed_at: '2026-10-19'
is_public: true
is_active: true
---

## شخصی
یک مشاور با لایسنس خود فایل و CRM شخصی را مدیریت می‌کند.

## آژانس
پلن‌های با `allow_bulk_purchase` امکان خرید چند کلید در یک سفارش را می‌دهند. اعضا با نقش‌های مالک، مدیر، منشی و مشاور در فضای آژانس همکاری می‌کنند.

## Seat
برخی سناریوها تخصیص صندلی/کلید به عضو تیم را دارند؛ جزئیات در مقالات «مدیریت آژانس».

## محدودیت
همه گزارش‌ها و داده‌های تیمی به رضایت اشتراک‌گذاری و نقش RBAC بستگی دارد.
