---
id: filing-listing-duplicates
title: آگهی تکراری در فایلینگ
category: فایلینگ
summary: یکتایی token در هر dataset؛ تکرار در datasetهای مختلف؛ استخراج مجدد ادغام می‌شود.
platforms:
  - web
  - android
  - windows
synonyms:
  - آگهی تکراری
  - duplicate listing
  - همان آگهی دو بار
links:
  - label: مجموعه فایل
    url: /workspace/datasets/
technical_refs:
  - workspace/models.py
  - workspace/services/importer.py
reviewed_at: '2026-10-27'
is_public: true
is_active: true
---

## در یک dataset
- شناسه **token** دیوار کلید یکتا است.
- استخراج دوباره همان آگهی → **به‌روزرسانی** رکورد قبلی، نه دو ردیف هم‌نام.

## در چند dataset
- همان آگهی می‌تواند در datasetهای جدا **چند رکورد** داشته باشد (هر کدام مالک dataset خودش).

## انتقال به فایل شخصی
- از token، ملک CRM **یک‌بار per کاربر** شناسایی می‌شود؛ انتقال مجدد معمولاً همان ملک را برمی‌گرداند.

## حذف تکراری دستی
اگر دو token متفاوت برای یک ملک واقعی دارید (نادر)، باید یکی را دستی حذف یا ادغام کنید — سیستم خودکار ادغام نمی‌کند.
