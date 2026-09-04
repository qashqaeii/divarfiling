"""ثابت‌ها و متن‌های حقوقی/محصولی قرارداد."""

from __future__ import annotations

# ——— انواع قرارداد ———
CONTRACT_TYPE_LEASE = 'lease'
CONTRACT_TYPE_SALE = 'sale'
CONTRACT_TYPE_JV = 'jv'

CONTRACT_TYPES = (
    (CONTRACT_TYPE_LEASE, 'رهن و اجاره'),
    (CONTRACT_TYPE_SALE, 'فروش / مبایعه‌نامه'),
    (CONTRACT_TYPE_JV, 'مشارکت در ساخت'),
)

CONTRACT_TYPE_PREFIX = {
    CONTRACT_TYPE_LEASE: 'RNT',
    CONTRACT_TYPE_SALE: 'SAL',
    CONTRACT_TYPE_JV: 'JV',
}

# ——— وضعیت قرارداد ———
CONTRACT_STATUS_DRAFT = 'draft'
CONTRACT_STATUS_READY = 'ready'
CONTRACT_STATUS_SENT = 'sent'
CONTRACT_STATUS_VIEWED = 'viewed'
CONTRACT_STATUS_PARTIALLY_ACCEPTED = 'partially_accepted'
CONTRACT_STATUS_FULLY_ACCEPTED = 'fully_accepted'
CONTRACT_STATUS_FINALIZED = 'finalized'
CONTRACT_STATUS_CANCELLED = 'cancelled'
CONTRACT_STATUS_SUPERSEDED = 'superseded'
CONTRACT_STATUS_EXPIRED = 'expired'

CONTRACT_STATUSES = (
    (CONTRACT_STATUS_DRAFT, 'پیش‌نویس'),
    (CONTRACT_STATUS_READY, 'آماده ارسال'),
    (CONTRACT_STATUS_SENT, 'ارسال‌شده'),
    (CONTRACT_STATUS_VIEWED, 'مشاهده‌شده'),
    (CONTRACT_STATUS_PARTIALLY_ACCEPTED, 'تأیید جزئی'),
    (CONTRACT_STATUS_FULLY_ACCEPTED, 'تأیید کامل'),
    (CONTRACT_STATUS_FINALIZED, 'نهایی‌شده'),
    (CONTRACT_STATUS_CANCELLED, 'لغوشده'),
    (CONTRACT_STATUS_SUPERSEDED, 'جایگزین‌شده'),
    (CONTRACT_STATUS_EXPIRED, 'منقضی'),
)

# انتقال‌های مجاز وضعیت
CONTRACT_STATUS_TRANSITIONS = {
    CONTRACT_STATUS_DRAFT: {CONTRACT_STATUS_READY, CONTRACT_STATUS_CANCELLED},
    CONTRACT_STATUS_READY: {CONTRACT_STATUS_SENT, CONTRACT_STATUS_DRAFT, CONTRACT_STATUS_CANCELLED},
    CONTRACT_STATUS_SENT: {
        CONTRACT_STATUS_VIEWED, CONTRACT_STATUS_PARTIALLY_ACCEPTED,
        CONTRACT_STATUS_FULLY_ACCEPTED, CONTRACT_STATUS_CANCELLED, CONTRACT_STATUS_EXPIRED,
    },
    CONTRACT_STATUS_VIEWED: {
        CONTRACT_STATUS_PARTIALLY_ACCEPTED, CONTRACT_STATUS_FULLY_ACCEPTED,
        CONTRACT_STATUS_CANCELLED, CONTRACT_STATUS_EXPIRED,
    },
    CONTRACT_STATUS_PARTIALLY_ACCEPTED: {
        CONTRACT_STATUS_FULLY_ACCEPTED, CONTRACT_STATUS_CANCELLED, CONTRACT_STATUS_EXPIRED,
    },
    CONTRACT_STATUS_FULLY_ACCEPTED: {CONTRACT_STATUS_FINALIZED, CONTRACT_STATUS_CANCELLED},
    CONTRACT_STATUS_FINALIZED: {CONTRACT_STATUS_SUPERSEDED},
    CONTRACT_STATUS_CANCELLED: set(),
    CONTRACT_STATUS_SUPERSEDED: set(),
    CONTRACT_STATUS_EXPIRED: set(),
}

# ——— نقش طرفین ———
PARTY_ROLE_LANDLORD = 'landlord'
PARTY_ROLE_TENANT = 'tenant'
PARTY_ROLE_SELLER = 'seller'
PARTY_ROLE_BUYER = 'buyer'
PARTY_ROLE_OWNER = 'owner'
PARTY_ROLE_BUILDER = 'builder'
PARTY_ROLE_WITNESS = 'witness'
PARTY_ROLE_OTHER = 'other'

PARTY_ROLES_BY_TYPE = {
    CONTRACT_TYPE_LEASE: (
        (PARTY_ROLE_LANDLORD, 'موجر'),
        (PARTY_ROLE_TENANT, 'مستأجر'),
    ),
    CONTRACT_TYPE_SALE: (
        (PARTY_ROLE_SELLER, 'فروشنده'),
        (PARTY_ROLE_BUYER, 'خریدار'),
    ),
    CONTRACT_TYPE_JV: (
        (PARTY_ROLE_OWNER, 'مالک'),
        (PARTY_ROLE_BUILDER, 'سازنده'),
    ),
}

PERSON_TYPE_NATURAL = 'natural'
PERSON_TYPE_LEGAL = 'legal'
PERSON_TYPES = (
    (PERSON_TYPE_NATURAL, 'حقیقی'),
    (PERSON_TYPE_LEGAL, 'حقوقی'),
)

# ——— امضا ———
SIGNATURE_TYPE_OTP = 'otp_acceptance'
SIGNATURE_TYPE_DRAWN = 'drawn_signature'
SIGNATURE_TYPE_FUTURE_CERT = 'future_digital_certificate'

SIGNATURE_TYPES = (
    (SIGNATURE_TYPE_OTP, 'تأیید OTP'),
    (SIGNATURE_TYPE_DRAWN, 'امضای دستی'),
    (SIGNATURE_TYPE_FUTURE_CERT, 'گواهی دیجیتال (آینده)'),
)

# ——— احراز هویت ———
IDENTITY_STATUS_UNVERIFIED = 'unverified'
IDENTITY_STATUS_MOBILE_VERIFIED = 'mobile_verified'
IDENTITY_STATUS_CLAIMED = 'national_id_claimed'
IDENTITY_STATUS_VERIFIED = 'identity_verified'

# ——— بندها ———
CLAUSE_REVIEW_DRAFT = 'draft'
CLAUSE_REVIEW_PENDING = 'review_pending'
CLAUSE_REVIEW_REVIEWED = 'reviewed'
CLAUSE_REVIEW_DEPRECATED = 'deprecated'

CLAUSE_REVIEW_STATUSES = (
    (CLAUSE_REVIEW_DRAFT, 'پیش‌نویس'),
    (CLAUSE_REVIEW_PENDING, 'در انتظار بررسی حقوقی'),
    (CLAUSE_REVIEW_REVIEWED, 'بررسی‌شده'),
    (CLAUSE_REVIEW_DEPRECATED, 'منسوخ'),
)

# ——— Audit ———
AUDIT_CONTRACT_CREATED = 'CONTRACT_CREATED'
AUDIT_CONTRACT_UPDATED = 'CONTRACT_UPDATED'
AUDIT_VERSION_CREATED = 'VERSION_CREATED'
AUDIT_VERSION_PUBLISHED = 'VERSION_PUBLISHED'
AUDIT_INVITATION_CREATED = 'INVITATION_CREATED'
AUDIT_SMS_SENT = 'SMS_SENT'
AUDIT_INVITATION_OPENED = 'INVITATION_OPENED'
AUDIT_OTP_REQUESTED = 'OTP_REQUESTED'
AUDIT_OTP_VERIFIED = 'OTP_VERIFIED'
AUDIT_OTP_FAILED = 'OTP_FAILED'
AUDIT_CONTRACT_VIEWED = 'CONTRACT_VIEWED'
AUDIT_PARTY_ACCEPTED = 'PARTY_ACCEPTED'
AUDIT_PARTY_SIGNED = 'PARTY_SIGNED'
AUDIT_WITNESS_ACCEPTED = 'WITNESS_ACCEPTED'
AUDIT_CONTRACT_FULLY_ACCEPTED = 'CONTRACT_FULLY_ACCEPTED'
AUDIT_CONTRACT_FINALIZED = 'CONTRACT_FINALIZED'
AUDIT_PDF_GENERATED = 'PDF_GENERATED'
AUDIT_ACCESS_LINK_CREATED = 'ACCESS_LINK_CREATED'
AUDIT_ACCESS_LINK_REVOKED = 'ACCESS_LINK_REVOKED'
AUDIT_CONTRACT_CANCELLED = 'CONTRACT_CANCELLED'

# ——— SMS ———
SMS_STATUS_QUEUED = 'queued'
SMS_STATUS_SENT = 'sent'
SMS_STATUS_DELIVERED = 'delivered'
SMS_STATUS_FAILED = 'failed'

# ——— ضمائم ———
ATTACHMENT_TYPES = (
    ('deed', 'سند'),
    ('national_id', 'کارت ملی'),
    ('cheque', 'چک'),
    ('receipt', 'رسید پرداخت'),
    ('property_photo', 'تصویر ملک'),
    ('power_of_attorney', 'وکالت‌نامه'),
    ('minutes', 'صورت‌جلسه'),
    ('permit', 'پروانه'),
    ('other', 'مدرک دیگر'),
)

ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.doc', '.docx',
}
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB

# ——— هشدارها ———
WARNING_LEVEL_INFO = 'info'
WARNING_LEVEL_WARNING = 'warning'
WARNING_LEVEL_CRITICAL = 'critical'

# ——— Disclaimer ———
LEGAL_DISCLAIMER_FULL = (
    'فایلینگ دیوار ابزار تنظیم و نگهداری دیجیتال قرارداد است و صحت اطلاعات و انتخاب مفاد '
    'قرارداد بر عهده طرفین قرارداد است. این فرایند جایگزین ثبت رسمی، کد رهگیری یا سایر '
    'تشریفات قانونی الزامی در مواردی که قانون مقرر کرده است نیست.'
)

LEGAL_DISCLAIMER_SHORT = (
    'این سند در فایلینگ دیوار ایجاد و نگهداری شده است. شناسه فوق، شناسه داخلی فایلینگ دیوار '
    'است و کد رهگیری یا ثبت رسمی دولتی محسوب نمی‌شود.'
)

CREATOR_ACK_CHECKBOX = (
    'مسئولیت صحت اطلاعات واردشده و انتخاب مفاد قرارداد را پذیرفته و می‌دانم این قرارداد '
    'در فایلینگ دیوار به‌معنای ثبت رسمی دولتی نیست.'
)

JV_WARNING = (
    'قراردادهای مشارکت در ساخت و تعهد به ساخت ممکن است طبق قوانین جاری مشمول تشریفات و '
    'الزامات ثبت رسمی و مقررات پیش‌فروش ساختمان باشند. تنظیم و تأیید این متن در فایلینگ دیوار '
    'جایگزین اقدامات رسمی موردنیاز نیست.'
)

PARTY_ACK_ITEMS = (
    'متن کامل قرارداد را مشاهده کردم.',
    'اطلاعات مربوط به خود را بررسی کردم.',
    'مفاد قرارداد را مطالعه کرده و با آن موافقم.',
    'می‌دانم تأیید من در فایلینگ دیوار به معنی ثبت رسمی دولتی معامله نیست.',
)

# ——— Wizard steps ———
WIZARD_STEPS = (
    'type',
    'parties',
    'property',
    'financial',
    'clauses',
    'witnesses',
    'attachments',
    'review',
)

WIZARD_STEP_LABELS = {
    'type': 'نوع قرارداد',
    'parties': 'طرفین',
    'property': 'ملک',
    'financial': 'مالی',
    'clauses': 'بندها',
    'witnesses': 'شاهدان',
    'attachments': 'ضمائم',
    'review': 'بازبینی',
}

# مراحل نمایشی ویزارد — بر اساس نوع قرارداد (حداکثر ~۶ مرحله)
WIZARD_DISPLAY_STEPS = {
    CONTRACT_TYPE_LEASE: (
        ('parties', 'طرفین'),
        ('property', 'ملک'),
        ('financial', 'مدت و مبلغ'),
        ('clauses', 'شرایط و بندها'),
        ('witnesses', 'شاهدان'),
        ('review', 'مرور و ارسال'),
    ),
    CONTRACT_TYPE_SALE: (
        ('parties', 'طرفین'),
        ('property', 'ملک'),
        ('financial', 'مبلغ و پرداخت'),
        ('clauses', 'شرایط'),
        ('review', 'مرور و ارسال'),
    ),
    CONTRACT_TYPE_JV: (
        ('parties', 'طرفین'),
        ('property', 'ملک'),
        ('financial', 'آورده‌ها و سهم'),
        ('clauses', 'شرایط'),
        ('review', 'مرور و ارسال'),
    ),
}

# ——— Legal rules (codes) ———
RULE_LEASE_REQUIRES_DURATION = 'LEASE_REQUIRES_DURATION'
RULE_LEASE_REQUIRES_RENT = 'LEASE_REQUIRES_RENT_AMOUNT'
RULE_LEASE_REQUIRES_DEPOSIT = 'LEASE_REQUIRES_DEPOSIT_AMOUNT'
RULE_LEASE_REQUIRES_WITNESSES = 'LEASE_REQUIRES_TWO_WITNESSES'

VERIFICATION_MISMATCH_MSG = 'اطلاعات واردشده با دعوتنامه مطابقت ندارد.'

# ——— صورت‌جلسه تحویل ———
HANDOVER_TYPE_INITIAL = 'initial_delivery'
HANDOVER_TYPES = (
    (HANDOVER_TYPE_INITIAL, 'تحویل اولیه'),
)

HANDOVER_STATUS_DRAFT = 'draft'
HANDOVER_STATUS_SENT = 'sent'
HANDOVER_STATUS_FINALIZED = 'finalized'

HANDOVER_STATUSES = (
    (HANDOVER_STATUS_DRAFT, 'پیش‌نویس'),
    (HANDOVER_STATUS_SENT, 'ارسال‌شده'),
    (HANDOVER_STATUS_FINALIZED, 'تأییدشده'),
)

HANDOVER_ACK_ITEMS = (
    'اطلاعات و وضعیت ثبت‌شده ملک را مشاهده کردم.',
    'موارد تحویلی، کلیدها و اطلاعات کنتورها را بررسی کردم.',
    'این صورت‌جلسه وضعیت ملک در زمان تحویل را ثبت می‌کند.',
)

HANDOVER_KEY_TYPES = (
    'کلید درب اصلی', 'کلید واحد', 'کلید انباری', 'کلید پارکینگ',
    'ریموت پارکینگ', 'کارت ورود', 'سایر',
)

HANDOVER_CONDITION_ITEMS = (
    'دیوارها', 'کف', 'سقف', 'درب‌ها', 'پنجره‌ها', 'کابینت',
    'شیرآلات', 'سرویس بهداشتی', 'پکیج', 'رادیاتور', 'کولر', 'آیفون', 'برق', 'روشنایی',
)

HANDOVER_CONDITION_STATUSES = (
    ('ok', 'سالم'),
    ('minor', 'آسیب جزئی'),
    ('repair', 'نیازمند تعمیر'),
    ('damaged', 'آسیب‌دیده'),
    ('unchecked', 'بررسی نشده'),
)

COMMON_AREAS = (
    'راهرو', 'راه‌پله', 'آسانسور', 'پارکینگ', 'لابی', 'حیاط', 'پشت‌بام', 'انباری مشترک', 'سایر',
)

PAYMENT_METHODS = (
    ('cash', 'نقدی'),
    ('card', 'کارت به کارت'),
    ('transfer', 'انتقال بانکی'),
    ('cheque', 'چک'),
    ('other', 'سایر'),
)

USAGE_TYPES = (
    ('residential', 'مسکونی'),
    ('office', 'اداری'),
    ('commercial', 'تجاری'),
    ('other', 'سایر'),
)

COST_RESPONSIBILITY_OPTIONS = ('landlord', 'tenant')

WIZARD_UNIT_DIRECTIONS = (
    'شمالی', 'جنوبی', 'شرقی', 'غربی',
    'شمال‌شرقی', 'شمال‌غربی', 'جنوب‌شرقی', 'جنوب‌غربی',
)
