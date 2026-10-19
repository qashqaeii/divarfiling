---
id: plans-trial-7d
title: هدیه آزمایشی هفت‌روزه پس از ثبت‌نام
category: اشتراک و لایسنس
summary: کمپین خوش‌آمدگویی ۷ روزه در صورت فعال بودن تنظیمات سرور.
platforms:
- web
- android
- windows
subscription_note: ''
prerequisites: ''
limitations: وابسته به Feature Flag و تاریخ کمپین روی سرور.
synonyms: []
links: []
technical_refs:
- licenses/services/signup_welcome_gift.py
reviewed_at: '2026-10-19'
is_public: true
is_active: true
---

## شرایط واقعی
هدیه ۷ روزه تابع تنظیمات `SIGNUP_WELCOME_GIFT_ENABLED` و تاریخ شروع کمپین روی سرور است. اگر feature غیرفعال یا تاریخ شروع نرسیده باشد، هدیه اعطا نمی‌شود.

## نمایش در میزکار
پس از اعطا، مودال خوش‌آمدگویی در میزکار (تا تأیید کاربر) نمایش داده می‌شود.

## مدت
طبق سرویس کمپین هفتگی، مدت هدیه ۷ روز است (منطق در `signup_welcome_gift` و `weekly_trial_campaign`).

## نکته
این هدیه جایگزین خرید پلن بلندمدت نیست و ممکن است برای کاربران قبلی یا خارج از بازه کمپین اعمال نشود.
