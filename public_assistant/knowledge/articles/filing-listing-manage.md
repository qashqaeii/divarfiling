---
id: filing-listing-manage
title: مدیریت آگهی در مجموعه فایل
category: فایلینگ
summary: باز کردن و ویرایش آگهی در dataset؛ افزودن آگهی به فایل شخصی CRM؛ انتقال از dataset به CRM؛ اشتراک با مشتری.
platforms:
  - web
prerequisites: مجموعه فایل (dataset) و لایسنس فعال فایلینگ
limitations: برخی عملیات فقط مالک مجموعه یا آگهی
subscription_note: لایسنس ربات/فایلینگ
synonyms:
  - ویرایش آگهی
  - جزئیات آگهی
  - آگهی dataset
  - listing
  - افزودن به فایل شخصی
  - از dataset به crm
  - dataset به crm
  - انتقال آگهی به crm
  - صفحه آگهی فایلینگ
  - مدیریت آگهی
links:
  - label: مجموعه‌ها
    url: /workspace/datasets/
  - label: همه آگهی‌ها
    url: /workspace/listings/
catalog_feature_ids:
  - filing-listing-detail
technical_refs:
  - workspace/urls.py
  - workspace/views.py
  - templates/workspace/listings/detail.html
reviewed_at: '2026-10-20'
is_public: true
is_active: true
---

هر **آگهی** داخل یک **مجموعه فایل (dataset)** صفحه جزئیات خودش را دارد — جدا از لیست کلی `/workspace/listings/`.

## افزودن آگهی به فایل شخصی (از dataset به CRM)
1. آگهی را در مجموعه فایل یا `/workspace/listings/` باز کنید.
2. دکمه **افزودن به فایل شخصی** را بزنید.
3. پس از موفقیت، همان ملک در `/workspace/crm/properties/` دیده می‌شود (رکورد CRM جدا از رکورد dataset است).

## رسیدن به آگهی
1. `/workspace/datasets/` — مجموعه را باز کنید و آگهی را انتخاب کنید، یا
2. `/workspace/listings/` — جست‌وجو در همه مجموعه‌ها

مسیر URL شبیه: `/workspace/datasets/<uuid>/listings/<id>/`

## کارهای روی صفحه آگهی
| عمل | توضیح کوتاه |
|-----|-------------|
| **ویرایش** | اصلاح فیلدهای ثبت‌شده در میزکار |
| **علاقه‌مندی** | نشان‌گذاری برای پیگیری |
| **افزودن به فایل شخصی** | ساخت/اتصال رکورد CRM |
| **اشتراک با مشتری** | مودال لینک عمومی `/p/...` |
| **نقشه / بنچمارک** | در صورت فعال بودن برای حساب |

## افزودن به فایل شخصی
در هدر یا نوار پایین (موبایل): دکمه **افزودن به فایل شخصی** — فرم POST به `listing_add_personal`. پس از موفقیت، ملک در `/workspace/crm/properties/` دیده می‌شود.

## اشتراک با مشتری
دکمه **اشتراک** → مودال **اشتراک با مشتری** (سه تب: ارسال، صفحه مشتری، پروفایل من). جزئیات: مقاله «اشتراک عمومی فایل».

## ویرایش و حذف
از منوی عملیات آگهی **ویرایش** یا **حذف** — حذف فقط روی همان رکورد dataset است، نه ملک CRM مگر جدا حذف شود.

## اگر آگهی را نمی‌بینید
فیلتر مجموعه، فیلتر لیست، یا حساب/sync — مقاله «مشکلات رایج CRM و فایلینگ».
