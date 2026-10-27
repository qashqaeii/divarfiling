---
id: filing-listing-fields
title: چه داده‌هایی از آگهی دیوار ذخیره می‌شود؟
category: فایلینگ
summary: فیلدهای Listing — عنوان، قیمت، متراژ، موقعیت، توضیحات، تصاویر، data خام؛ تماس و ویدئو مشروط.
platforms:
  - web
  - android
  - windows
synonyms:
  - فیلدهای استخراج
  - چه اطلاعاتی ذخیره میشه
  - محتوای آگهی
links:
  - label: مجموعه فایل
    url: /workspace/datasets/
technical_refs:
  - workspace/services/columns.py
  - workspace/models.py
reviewed_at: '2026-10-27'
is_public: true
is_active: true
---

## فیلدهای ساختاری رایج
- **token** شناسه یکتا آگهی در دیوار
- **title**, **price** / **deposit** / **rent** (بسته به نوع آگهی)
- **area**, **rooms**, **business_type**
- **city**, **neighborhood**, **latitude/longitude** در صورت موجود بودن در منبع
- **description**, **link**, **images**
- **published_at**, **expires_at**
- **data** — JSON خام سایر ویژگی‌ها و امکانات استخراج‌شده

## موارد مشروط
- **شماره تماس:** بسته به روش استخراج/OTP و نوع آگهی — همیشه برای همه آگهی‌ها تضمین نمی‌شود.
- **ویدئو:** فقط اگر در داده منبع باشد؛ ممکن است در برخی استخراج‌ها خالی باشد.
- فیلدهای خالی در UI «—» یا خالی نمایش داده می‌شوند.

## اگر فیلدی خالی است
سیستم مقدار را حدس نمی‌زند؛ بعداً در میزکار یا پس از استخراج مجدد ممکن است پر شود.
