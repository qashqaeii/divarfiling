---
id: crm-property-archive
title: بایگانی و بازگردانی ملک شخصی
category: CRM
summary: بایگانی فایل شخصی — وضعیت معامله در pre_archive_transaction_status؛ بازگردانی به وضعیت قبلی.
platforms:
  - web
synonyms:
  - بایگانی ملک
  - آرشیو فایل شخصی
  - وضعیت معامله بایگانی
links:
  - label: املاک شخصی
    url: /workspace/crm/properties/
technical_refs:
  - workspace/services/crm_property_archive.py
reviewed_at: '2026-10-27'
is_public: true
is_active: true
---

## بایگانی
- از لیست یا جزئیات ملک: **بایگانی** (تکی یا گروهی تا حدود **۱۰۰** فایل).
- قبل از بایگانی، **وضعیت معامله** فعلی (فعال، در مذاکره، …) در `pre_archive_transaction_status` ذخیره می‌شود.

## بازگردانی
- از تب/فیلتر **بایگانی** → **بازگردانی**.
- وضعیت معامله معمولاً به مقدار ذخیره‌شده قبل از بایگانی برمی‌گردد؛ اگر نامعتبر بود **فعال** می‌شود.
- فیلد `pre_archive_transaction_status` پس از بازگردانی پاک می‌شود.

## نکته
بایگانی با «فروخته‌شده/اجاره‌رفته» متفاوت است — بایگانی فقط فایل را از لیست جاری پنهان می‌کند.
