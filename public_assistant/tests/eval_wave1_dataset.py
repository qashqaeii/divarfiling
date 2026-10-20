"""سؤالات ارزیابی موج ۱ فاز ۲ — how-to و محاوره‌ای."""

WAVE1_EVAL_QUESTIONS: list[tuple[str, str]] = [
    # ساده
    ('چطور مخاطب ثبت کنم', 'crm-contacts'),
    ('چطوری فایل شخصی داشته باشم', 'crm-property-create-edit'),
    ('شماره مالک کجا وارد میشه', 'crm-property-owner-contact'),
    ('چطوری لینک برای مشتری بفرستم', 'share-public-file'),
    # تخصصی
    ('ادغام دو مخاطب با یک شماره', 'crm-contacts-manage'),
    ('زونکن املاک شخصی', 'crm-property-folders-cabinets'),
    ('کمد فایل شخصی crm', 'crm-property-folders-cabinets'),
    ('تب پیشنهادها مخاطب', 'crm-matching'),
    ('غیرفعال کردن لینک share', 'share-public-file'),
    ('افزودن آگهی به فایل شخصی', 'filing-listing-manage'),
    # محاوره‌ای
    ('دو تا مشتری شماره یکسان', 'crm-contacts-manage'),
    ('لینک مشتری باز نمیشه', 'support-wave1-crm-filing'),
    ('استخراج کردم نیست تو میزکار', 'extractor-to-filing'),
    ('پوشه بندی ملک شخصی', 'crm-property-folders-cabinets'),
    # خطا / محدودیت
    ('تطبیق فایل خالیه', 'crm-matching'),
    ('شماره مالک تو لینک نیست', 'share-public-file'),
    # مراحل
    ('مراحل ساخت ملک شخصی', 'crm-property-create-edit'),
    ('از dataset به crm', 'filing-listing-manage'),
]
