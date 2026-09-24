"""ثابت‌های workspace — هماهنگ با app_crm_links.py در Tkinter."""

CRM_TYPES = [
    'خریدار', 'فروشنده', 'سازنده', 'مالک', 'مستاجر', 'موجر',
    'سرمایه‌گذار', 'سرنخ', 'متقاضی خرید', 'متقاضی اجاره',
    'فروشنده ملک', 'اشخاص حقوقی',
]
CRM_STATUSES = ['جدید', 'در حال پیگیری', 'بازدید انجام شد', 'قرارداد', 'بایگانی']
CRM_PRIORITIES = ['بالا', 'متوسط', 'پایین']
CRM_PROPERTIES = ['آپارتمان', 'ویلا', 'کلنگی', 'اداری', 'مغازه', 'زمین', 'سایر']
PROPERTY_ADVERTISER_TYPES = ['شخصی', 'مشاور', 'مشاور املاک', 'business', 'مالک']
CRM_SOURCES = ['دیوار', 'معرف', 'ورود به املاک', 'تماس ورودی', 'اینستاگرام', 'سایت', 'تلگرام', 'موبایل', 'سایر']
ACTIVITY_TYPES = [
    'تماس', 'پیامک', 'واتساپ', 'پیام', 'بازدید', 'جلسه', 'پیگیری',
    'یادداشت', 'وظیفه', 'یادآور', 'تغییر وضعیت', 'املاک', 'ایمیل',
]
QUICK_ACTIVITY_TYPES = ['تماس', 'واتساپ', 'بازدید', 'جلسه', 'پیگیری', 'یادداشت']
LISTING_ROLES = [
    'مالک', 'فروشنده', 'خریدار', 'سازنده', 'مستاجر', 'موجر',
    'سرمایه‌گذار', 'سرنخ', 'پیشنهادی', 'متقاضی خرید', 'متقاضی اجاره',
]
DEAL_TYPES = ['فروش', 'خرید', 'رهن و اجاره', 'رهن کامل', 'اجاره', 'پیش‌فروش', 'سرمایه‌گذاری', 'سایر']

PROPERTY_DEAL_MODES = ['فروش', 'رهن و اجاره', 'اجاره', 'پیش‌فروش']
PROPERTY_TX_STATUSES = ['فعال', 'در مذاکره', 'قرارداد', 'فروخته‌شده', 'اجاره‌رفته', 'بایگانی']

PROPERTY_TX_COLORS = {
    'فعال': ('#ecfdf5', '#047857', '#10b981'),
    'در مذاکره': ('#fffbeb', '#b45309', '#f59e0b'),
    'قرارداد': ('#f5f3ff', '#6d28d9', '#8b5cf6'),
    'فروخته‌شده': ('#eff6ff', '#1d4ed8', '#2563eb'),
    'اجاره‌رفته': ('#ecfeff', '#0e7490', '#06b6d4'),
    'بایگانی': ('#f8fafc', '#64748b', '#94a3b8'),
}

CRM_FILTER_SCOPES = ['contacts', 'properties', 'deals', 'listings']

CRM_FILTER_PARAMS = {
    'contacts': {'q', 'customer_type', 'status', 'priority', 'due', 'sort', 'tag', 'match_alerts'},
    'properties': {
        'q', 'deal_mode', 'transaction_status', 'property_type', 'publish_status', 'city', 'sort',
        'folder_id',
        'parking', 'storage', 'elevator', 'rooms',
        'area_min', 'area_max', 'price_min', 'price_max',
        'year_min', 'year_max', 'age_max',
    },
    'deals': {'q', 'stage', 'bucket', 'sort'},
    'listings': {
        'q', 'neighborhood', 'rooms', 'consultant', 'duplicates', 'unique', 'new_only',
        'elevator', 'parking', 'storage', 'value', 'sort', 'dataset_id',
        'area_min', 'area_max', 'price_min', 'price_max',
        'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
        'year_min', 'year_max', 'favorites', 'tag', 'has_geo',
    },
}
PROPERTY_PUBLISH_STATUSES = ['پیش‌نویس', 'منتشرشده', 'مخفی', 'بایگانی']
INTEREST_LEVELS = ['بالا', 'متوسط', 'پایین']

LISTING_TAGS = ['تماس', 'بازدید', 'علاقه‌مند', 'رد', '']

# ستون‌های ویژگی/امکانات خروجی ربات — هماهنگ با export_divar_items.FEATURE_EXCEL_COLUMNS
LISTING_FEATURE_COLUMNS = [
    'تعداد واحد در طبقه',
    'تعداد کل طبقات ساختمان',
    'جهت ساختمان',
    'حیوان خانگی مجاز',
    'نوع آشپزخانه',
    'مناسب برای',
    'جنس کابینت',
    'بازسازی شده',
    'وضعیت واحد',
    'حداقل مدت قرارداد',
    'جنس کف',
    'بالکن',
    'سرویس بهداشتی',
    'سرمایش',
    'گرمایش',
    'تأمین‌کننده آب گرم',
    'تعداد حمام',
    'تعداد سرویس بهداشتی',
    'تعداد پارکینگ',
    'جکوزی',
    'سند',
    'سونا',
    'عرض ملک',
    'قابل معاوضه',
    'مجوز ساخت',
    'نمای ساختمان',
    'وضعیت سند',
    'وضعیت سکونت',
    'تاریخ تخلیه',
]

LISTING_FEATURE_COMBINED_KEYS = ('ویژگی‌ها و امکانات', 'ویژگی_ها_و_امکانات')

LISTING_FEATURE_GROUPS = (
    {
        'id': 'building',
        'title': 'ویژگی‌های ساختمان',
        'icon': 'fa-building',
        'accent': 'sky',
        'keys': (
            'تعداد واحد در طبقه', 'تعداد کل طبقات ساختمان', 'جهت ساختمان',
            'وضعیت واحد', 'بازسازی شده',
        ),
    },
    {
        'id': 'comfort',
        'title': 'امکانات رفاهی',
        'icon': 'fa-couch',
        'accent': 'violet',
        'keys': (
            'جنس کف', 'بالکن', 'سرویس بهداشتی', 'سرمایش', 'گرمایش',
            'تأمین‌کننده آب گرم', 'نوع آشپزخانه', 'جنس کابینت',
        ),
    },
    {
        'id': 'lifestyle',
        'title': 'شرایط سکونت',
        'icon': 'fa-users',
        'accent': 'emerald',
        'keys': ('حیوان خانگی مجاز', 'مناسب برای', 'حداقل مدت قرارداد', 'وضعیت سکونت', 'تاریخ تخلیه', 'نام مستاجر', 'شماره مستاجر'),
    },
    {
        'id': 'legal',
        'title': 'سند و مجوزها',
        'icon': 'fa-file-contract',
        'accent': 'slate',
        'keys': ('سند', 'وضعیت سند', 'مجوز ساخت', 'قابل معاوضه'),
    },
    {
        'id': 'counts',
        'title': 'تعداد و ظرفیت',
        'icon': 'fa-hashtag',
        'accent': 'blue',
        'keys': ('تعداد پارکینگ', 'تعداد حمام', 'تعداد سرویس بهداشتی'),
    },
    {
        'id': 'luxury',
        'title': 'امکانات لوکس',
        'icon': 'fa-spa',
        'accent': 'rose',
        'keys': ('جکوزی', 'سونا'),
    },
    {
        'id': 'exterior',
        'title': 'نما و ابعاد',
        'icon': 'fa-building-columns',
        'accent': 'orange',
        'keys': ('نمای ساختمان', 'عرض ملک'),
    },
)

LISTING_CORE_AMENITIES = (
    {'key': 'آسانسور', 'field': 'elevator', 'icon': 'fa-elevator'},
    {'key': 'پارکینگ', 'field': 'parking', 'icon': 'fa-square-parking'},
    {'key': 'انباری', 'field': 'storage', 'icon': 'fa-box-archive'},
)

# چک‌باکس‌های امکانات در فرم ویرایش ملک CRM (گروه‌بندی‌شده)
PROPERTY_AMENITY_CHECKBOX_GROUPS = (
    {
        'id': 'core',
        'title': 'امکانات اصلی',
        'icon': 'fa-star',
        'items': (
            ('پارکینگ', 'fa-square-parking'),
            ('انباری', 'fa-box-archive'),
            ('آسانسور', 'fa-elevator'),
        ),
    },
    {
        'id': 'building',
        'title': 'امکانات ساختمان',
        'icon': 'fa-building',
        'items': (
            ('بالکن', 'fa-fan'),
            ('تراس', 'fa-tree'),
            ('لابی', 'fa-hotel'),
            ('آیفون تصویری', 'fa-video'),
            ('درب ضدسرقت', 'fa-shield-halved'),
            ('نگهبانی', 'fa-user-shield'),
            ('سرایداری', 'fa-bell-concierge'),
            ('آنتن مرکزی', 'fa-satellite-dish'),
        ),
    },
    {
        'id': 'luxury',
        'title': 'رفاهی و لوکس',
        'icon': 'fa-spa',
        'items': (
            ('استخر', 'fa-water-ladder'),
            ('روف گاردن', 'fa-seedling'),
            ('جکوزی', 'fa-hot-tub-person'),
            ('سونا', 'fa-temperature-high'),
            ('سالن ورزش', 'fa-dumbbell'),
        ),
    },
    {
        'id': 'conditions',
        'title': 'شرایط و وضعیت',
        'icon': 'fa-clipboard-check',
        'items': (
            ('حیوان خانگی مجاز', 'fa-paw'),
            ('قابل معاوضه', 'fa-right-left'),
            ('بازسازی شده', 'fa-hammer'),
            ('سند', 'fa-file-signature'),
            ('مجوز ساخت', 'fa-hard-hat'),
        ),
    },
)

# برچسب‌های بولین شناخته‌شده (چک‌باکس CRM + چیپ‌های دیوار)
PROPERTY_BOOL_AMENITY_LABELS = frozenset(
    label
    for group in PROPERTY_AMENITY_CHECKBOX_GROUPS
    for label, _icon in group['items']
)

BUILDER_BUY_PROPERTY_TYPES = ['ویلا', 'کلنگی', 'زمین']
BUILDER_SELL_PROPERTY_TYPES = ['آپارتمان']

TYPE_PROFILES = {
    'خریدار': {
        'money_mode': 'budget',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'section_hint': 'محدوده قیمت خرید (تومان)',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات جستجو',
        'prefs_hint': 'نوع ملک، متراژ، خواب، سال ساخت، طبقه و امکانات مورد نظر',
    },
    'فروشنده': {
        'money_mode': 'budget',
        'budget_labels': ('قیمت فروش از', 'قیمت فروش تا'),
        'section_hint': 'محدوده قیمت پیشنهادی فروش',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک',
        'prefs_hint': 'ویژگی‌های ملک در حال فروش',
    },
    'فروشنده ملک': {
        'money_mode': 'budget',
        'budget_labels': ('قیمت فروش از', 'قیمت فروش تا'),
        'section_hint': 'قیمت فروش ملک',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک',
        'prefs_hint': 'ویژگی‌های ملک در حال فروش',
    },
    'سازنده': {
        'money_mode': 'builder',
        'budget_labels': ('قیمت واحد از', 'قیمت واحد تا'),
        'section_hint': 'محدوده قیمت آپارتمان‌های فروش',
        'sell_section_title': 'خط فروش — آپارتمان',
        'sell_section_hint': 'نوع ملک فروش معمولاً آپارتمان است؛ محله و متراژ واحدهای در حال ساخت یا فروش را ثبت کنید.',
        'buy_section_title': 'تأمین پروژه — خرید زمین و کلنگی',
        'buy_section_hint': 'بودجه و منطقه خرید ویلا، کلنگی و زمین برای توسعه پروژه',
        'default_property_type': 'آپارتمان',
        'buy_property_types': BUILDER_BUY_PROPERTY_TYPES,
        'prefs_mode': 'builder',
        'prefs_title': 'مشخصات واحد فروش',
        'prefs_hint': 'مشخصات آپارتمان‌های فروش و محله‌های پروژه',
    },
    'مالک': {
        'money_mode': 'both',
        'budget_labels': ('قیمت فروش از', 'قیمت فروش تا'),
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره ماهانه از', 'اجاره ماهانه تا'),
        'section_hint': 'فروش یا رهن و اجاره',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک',
        'prefs_hint': 'ویژگی‌های ملک مالک',
    },
    'مستاجر': {
        'money_mode': 'rent',
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره ماهانه از', 'اجاره ماهانه تا'),
        'section_hint': 'محدوده رهن و اجاره مورد نظر',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات اجاره',
        'prefs_hint': 'نوع ملک، متراژ، خواب و امکانات مورد نظر برای اجاره',
    },
    'موجر': {
        'money_mode': 'rent',
        'deposit_labels': ('ودیعه درخواستی از', 'ودیعه درخواستی تا'),
        'rent_labels': ('اجاره درخواستی از', 'اجاره درخواستی تا'),
        'section_hint': 'ودیعه و اجاره اعلامی موجر',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک اجاره‌ای',
        'prefs_hint': 'ویژگی‌های ملک برای اجاره',
    },
    'متقاضی خرید': {
        'money_mode': 'budget',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'section_hint': 'محدوده بودجه خرید',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات جستجو',
        'prefs_hint': 'نوع ملک، متراژ، خواب، سال ساخت، طبقه و امکانات مورد نظر',
    },
    'متقاضی اجاره': {
        'money_mode': 'rent',
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره ماهانه از', 'اجاره ماهانه تا'),
        'section_hint': 'محدوده رهن و اجاره',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات اجاره',
        'prefs_hint': 'نوع ملک، متراژ، خواب و امکانات مورد نظر برای اجاره',
    },
    'سرمایه‌گذار': {
        'money_mode': 'budget',
        'budget_labels': ('سرمایه از', 'سرمایه تا'),
        'section_hint': 'محدوده سرمایه‌گذاری',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات سرمایه‌گذاری',
        'prefs_hint': 'نوع ملک و محدوده مورد نظر برای سرمایه‌گذاری',
    },
    'سرنخ': {
        'money_mode': 'flexible',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره از', 'اجاره تا'),
        'section_hint': 'اطلاعات مالی اختیاری',
        'prefs_mode': 'flexible',
        'prefs_title': 'ترجیحات ملک',
        'prefs_hint': 'ترجیحات اختیاری برای پیشنهاد هوشمند',
    },
    'اشخاص حقوقی': {
        'money_mode': 'flexible',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره از', 'اجاره تا'),
        'section_hint': 'اطلاعات مالی شرکت',
        'prefs_mode': 'flexible',
        'prefs_title': 'ترجیحات ملک',
        'prefs_hint': 'ترجیحات اختیاری شرکت',
    },
}

ROLE_COLORS = {
    'مالک': ('#dbeafe', '#1d4ed8'),
    'فروشنده': ('#e0e7ff', '#4338ca'),
    'سازنده': ('#ccfbf1', '#0f766e'),
    'فروشنده ملک': ('#e0e7ff', '#4338ca'),
    'خریدار': ('#dcfce7', '#15803d'),
    'مستاجر': ('#fef3c7', '#b45309'),
    'موجر': ('#ffedd5', '#c2410c'),
    'سرمایه‌گذار': ('#f3e8ff', '#7c3aed'),
    'سرنخ': ('#f1f5f9', '#475569'),
    'متقاضی خرید': ('#ecfdf5', '#047857'),
    'متقاضی اجاره': ('#fff7ed', '#ea580c'),
    'پیشنهادی': ('#e5e7eb', '#374151'),
    'اشخاص حقوقی': ('#fae8ff', '#a21caf'),
}

LEAD_TYPES = {'سرنخ', 'متقاضی خرید', 'متقاضی اجاره'}

# نوع ذخیره‌شده «متقاضی اجاره» است؛ در برخی نماها «متقاضی رهن و اجاره» نمایش داده می‌شود.
LEASE_DEADLINE_TYPES = frozenset({'مستاجر', 'متقاضی اجاره', 'متقاضی رهن و اجاره'})


def shows_lease_deadline(customer_type: str) -> bool:
    return (customer_type or '').strip() in LEASE_DEADLINE_TYPES

CONVERT_TYPE_MAP = {
    'سرنخ': ['خریدار', 'مستاجر', 'مالک', 'موجر', 'سرمایه‌گذار', 'سازنده'],
    'متقاضی خرید': ['خریدار'],
    'متقاضی اجاره': ['مستاجر'],
}

QUICK_LINK_ACTIONS = [
    {'label': 'ثبت مالک', 'role': 'مالک', 'deal_type': 'فروش', 'customer_type': 'مالک'},
    {'label': 'ثبت موجر', 'role': 'موجر', 'deal_type': 'رهن و اجاره', 'customer_type': 'موجر'},
    {'label': 'ثبت مستأجر', 'role': 'مستاجر', 'deal_type': 'اجاره', 'customer_type': 'مستاجر'},
    {'label': 'ثبت خریدار', 'role': 'خریدار', 'deal_type': 'خرید', 'customer_type': 'خریدار'},
    {'label': 'ثبت سرنخ', 'role': 'سرنخ', 'deal_type': 'سایر', 'customer_type': 'سرنخ'},
]

TABLE_COLUMNS_DEFAULT = [
    'شناسه', 'عنوان', 'قیمت', 'ودیعه', 'اجاره', 'متراژ', 'اتاق',
    'محله', 'شهر', 'نوع آگهی دهنده', 'لینک',
]

SUPPORTED_UPLOAD_EXTENSIONS = ('.xlsx', '.xls', '.csv', '.json')

# ── معاملات CRM (فاز ۲) ──
DEAL_STAGES = ['سرنخ', 'مذاکره', 'بازدید', 'پیش‌قرارداد', 'قرارداد', 'بسته‌شده', 'از دست رفته']
DEAL_ACTIVE_STAGES = ['سرنخ', 'مذاکره', 'بازدید', 'پیش‌قرارداد', 'قرارداد']
LOST_REASONS = [
    'قیمت', 'عدم توافق مالک', 'عدم توافق مشتری', 'ملک نامناسب',
    'رقیب', 'عدم پاسخ', 'زمان‌بندی', 'سایر',
]
DEFAULT_COMMISSION_RATE = 1.0

# ── اقدام بعدی و پیگیری معامله ──
DEAL_ACTION_CALL = 'call'
DEAL_ACTION_MESSAGE = 'message'
DEAL_ACTION_SEND_FILE = 'send_file'
DEAL_ACTION_VISIT = 'visit'
DEAL_ACTION_NEGOTIATION = 'negotiation'
DEAL_ACTION_CONTRACT = 'contract_followup'
DEAL_ACTION_DOCUMENTS = 'documents'
DEAL_ACTION_COMMISSION = 'commission'
DEAL_ACTION_OTHER = 'other'

DEAL_NEXT_ACTION_TYPES = [
    (DEAL_ACTION_CALL, 'تماس'),
    (DEAL_ACTION_MESSAGE, 'پیام'),
    (DEAL_ACTION_SEND_FILE, 'ارسال فایل'),
    (DEAL_ACTION_VISIT, 'بازدید'),
    (DEAL_ACTION_NEGOTIATION, 'مذاکره'),
    (DEAL_ACTION_CONTRACT, 'پیگیری قرارداد'),
    (DEAL_ACTION_DOCUMENTS, 'دریافت مدارک'),
    (DEAL_ACTION_COMMISSION, 'پیگیری کمیسیون'),
    (DEAL_ACTION_OTHER, 'سایر'),
]
DEAL_NEXT_ACTION_LABELS = dict(DEAL_NEXT_ACTION_TYPES)
DEAL_NEXT_ACTION_KEYS = {k for k, _ in DEAL_NEXT_ACTION_TYPES}

DEAL_FOLLOWUP_NOTE = 'note'
DEAL_FOLLOWUP_TYPES = [
    (DEAL_ACTION_CALL, 'تماس'),
    (DEAL_ACTION_MESSAGE, 'پیام'),
    (DEAL_ACTION_VISIT, 'بازدید'),
    (DEAL_ACTION_NEGOTIATION, 'مذاکره'),
    (DEAL_ACTION_SEND_FILE, 'ارسال فایل'),
    (DEAL_ACTION_CONTRACT, 'پیگیری قرارداد'),
    (DEAL_FOLLOWUP_NOTE, 'یادداشت'),
    (DEAL_ACTION_OTHER, 'سایر'),
]
DEAL_FOLLOWUP_LABELS = dict(DEAL_FOLLOWUP_TYPES)
DEAL_FOLLOWUP_KEYS = {k for k, _ in DEAL_FOLLOWUP_TYPES}

DEAL_ACTION_ICONS = {
    DEAL_ACTION_CALL: 'fa-phone',
    DEAL_ACTION_MESSAGE: 'fa-comment-dots',
    DEAL_ACTION_SEND_FILE: 'fa-paper-plane',
    DEAL_ACTION_VISIT: 'fa-door-open',
    DEAL_ACTION_NEGOTIATION: 'fa-handshake',
    DEAL_ACTION_CONTRACT: 'fa-file-signature',
    DEAL_ACTION_DOCUMENTS: 'fa-folder-open',
    DEAL_ACTION_COMMISSION: 'fa-coins',
    DEAL_FOLLOWUP_NOTE: 'fa-note-sticky',
    DEAL_ACTION_OTHER: 'fa-ellipsis',
}

DEAL_KIND_SALE = 'sale'
DEAL_KIND_RENT = 'rent'
DEAL_KIND_CHOICES = [
    (DEAL_KIND_SALE, 'فروش'),
    (DEAL_KIND_RENT, 'اجاره'),
]
DEAL_KIND_LABELS = dict(DEAL_KIND_CHOICES)

COMMISSION_MODE_PERCENT = 'percent'
COMMISSION_MODE_FIXED = 'fixed'
COMMISSION_MODE_CHOICES = [
    (COMMISSION_MODE_PERCENT, 'درصد از ارزش معامله'),
    (COMMISSION_MODE_FIXED, 'مبلغ ثابت'),
]
COMMISSION_MODE_LABELS = dict(COMMISSION_MODE_CHOICES)

PAYOUT_UNPAID = 'unpaid'
PAYOUT_PARTIAL = 'partial'
PAYOUT_PAID = 'paid'
PAYOUT_WAIVED = 'waived'
PAYOUT_STATUS_CHOICES = [
    (PAYOUT_UNPAID, 'وصول نشده'),
    (PAYOUT_PARTIAL, 'نیمه‌وصول'),
    (PAYOUT_PAID, 'وصول شده'),
    (PAYOUT_WAIVED, 'بخشوده'),
]
PAYOUT_STATUS_LABELS = dict(PAYOUT_STATUS_CHOICES)

DEFAULT_ADVISOR_SHARE_PERCENT = 70.0
DEFAULT_AGENCY_SHARE_PERCENT = 30.0
DEFAULT_SALE_BUYER_RATE = 0.5
DEFAULT_SALE_SELLER_RATE = 0.5
DEFAULT_RENT_BUYER_RATE = 50.0
DEFAULT_RENT_SELLER_RATE = 50.0

DEFAULT_DEAL_FINANCE = {
    'sale_buyer_rate': DEFAULT_SALE_BUYER_RATE,
    'sale_seller_rate': DEFAULT_SALE_SELLER_RATE,
    'rent_buyer_rate': DEFAULT_RENT_BUYER_RATE,
    'rent_seller_rate': DEFAULT_RENT_SELLER_RATE,
    'advisor_share_percent': DEFAULT_ADVISOR_SHARE_PERCENT,
    'agency_share_percent': DEFAULT_AGENCY_SHARE_PERCENT,
}

DEAL_STAGE_WON = 'بسته‌شده'
DEAL_STAGE_LOST = 'از دست رفته'
DEAL_TERMINAL_STAGES = (DEAL_STAGE_WON, DEAL_STAGE_LOST)

# ── آژانس CRM (فاز ۴) ──
AGENCY_ROLES = [
    ('owner', 'مالک'),
    ('manager', 'مدیر'),
    ('advisor', 'مشاور'),
    ('secretary', 'منشی'),
]
AGENCY_ROLE_OWNER = 'owner'
AGENCY_ROLE_MANAGER = 'manager'
AGENCY_ROLE_ADVISOR = 'advisor'
AGENCY_ROLE_SECRETARY = 'secretary'
AGENCY_MANAGER_ROLES = {AGENCY_ROLE_OWNER, AGENCY_ROLE_MANAGER}
AGENCY_FULL_VIEW_ROLES = {AGENCY_ROLE_OWNER, AGENCY_ROLE_MANAGER, AGENCY_ROLE_SECRETARY}
AGENCY_INBOX_ROLES = AGENCY_FULL_VIEW_ROLES

TEAM_VISIBILITY_PRIVATE = 'private'
TEAM_VISIBILITY_INBOX = 'team_inbox'
TEAM_VISIBILITY_ASSIGNED = 'assigned'
TEAM_VISIBILITY_CHOICES = [
    (TEAM_VISIBILITY_PRIVATE, 'خصوصی'),
    (TEAM_VISIBILITY_INBOX, 'صندوق تیم'),
    (TEAM_VISIBILITY_ASSIGNED, 'تخصیص‌یافته'),
]

LEAD_ROUTING_OWNER = 'owner'
LEAD_ROUTING_INBOX = 'inbox'
LEAD_ROUTING_ROUND_ROBIN = 'round_robin'
LEAD_ROUTING_CHOICES = [
    (LEAD_ROUTING_OWNER, 'مالک آژانس'),
    (LEAD_ROUTING_INBOX, 'صندوق سرنخ تیم'),
    (LEAD_ROUTING_ROUND_ROBIN, 'چرخشی بین مشاوران'),
]

AUDIT_EVENTS = [
    'agency.updated', 'api_key.regenerated', 'member.invited', 'member.role_changed',
    'member.removed', 'lead.assigned', 'lead.bulk_assigned', 'customer.transferred',
    'sync.export', 'sync.import', 'webhook.created', 'webhook.deleted', 'webhook.tested',
    'message.sent', 'message.broadcast', 'message.deleted', 'announcement.created',
    'announcement.updated', 'announcement.deleted', 'knowledge.created', 'knowledge.updated',
]

# ── مرکز فرماندهی آژانس — Feature Flags ماژولار ──
AGENCY_COMMAND_CENTER_FEATURES = {
    'messages': True,
    'announcements': True,
    'activity_feed': True,
    'kpi_leaderboard': True,
    'knowledge_base': True,
    'team_calendar': True,
    'heatmap': True,
    'tv_mode': True,
    'agency_space': False,
}

MESSAGE_RETENTION_DAYS = 30

# فایلینگ — نگه‌داری موقت آگهی‌های استخراج‌شده (روز)
FILING_LISTING_RETENTION_DAYS_DEFAULT = 31
FILING_RETENTION_WARNING_DAYS_DEFAULT = 3
FILING_RETENTION_CLEANUP_DAY_DEFAULT = 1
FILING_RETENTION_CLEANUP_HOUR_DEFAULT = 3

WORKFLOW_RETENTION_TAGS = ('تماس', 'بازدید', 'علاقه‌مند')

# سرکوب آگهی — دلیل حذف عمدی توسط کاربر
LISTING_SUPPRESSION_REASON_USER_DELETED = 'user_deleted'
LISTING_SUPPRESSION_REASONS = [
    (LISTING_SUPPRESSION_REASON_USER_DELETED, 'حذف توسط کاربر'),
]

# حالت ingest — snapshot = محتوای payload معتبر کل دیتاست؛ incremental = فقط افزودن/به‌روزرسانی
INGEST_MODE_SNAPSHOT = 'snapshot'
INGEST_MODE_INCREMENTAL = 'incremental'
MESSAGE_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MESSAGE_ALLOWED_EXTENSIONS = frozenset({
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.webp',
})

WEBHOOK_EVENTS = [
    'customer.created',
    'customer.assigned',
    'deal.created',
    'deal.closed',
    'deal.lost',
]

WEBHOOK_EVENT_LABELS = {
    'customer.created': 'ثبت مخاطب جدید',
    'customer.assigned': 'تخصیص به مشاور',
    'deal.created': 'معامله جدید',
    'deal.closed': 'بستن معامله',
    'deal.lost': 'از دست رفتن معامله',
}

AGENCY_ROLE_STYLES = {
    'owner': ('#f3e8ff', '#7c3aed'),
    'manager': ('#dbeafe', '#1d4ed8'),
    'advisor': ('#dcfce7', '#15803d'),
    'secretary': ('#fef3c7', '#b45309'),
}

DEAL_STAGE_COLORS = {
    'سرنخ': ('#f1f5f9', '#475569'),
    'مذاکره': ('#dbeafe', '#1d4ed8'),
    'بازدید': ('#fef3c7', '#b45309'),
    'پیش‌قرارداد': ('#e0e7ff', '#4338ca'),
    'قرارداد': ('#fce7f3', '#be185d'),
    'بسته‌شده': ('#dcfce7', '#15803d'),
    'از دست رفته': ('#fee2e2', '#b91c1c'),
}

DEAL_STAGE_ICONS = {
    'سرنخ': 'fa-seedling',
    'مذاکره': 'fa-comments',
    'بازدید': 'fa-door-open',
    'پیش‌قرارداد': 'fa-file-signature',
    'قرارداد': 'fa-file-contract',
    'بسته‌شده': 'fa-trophy',
    'از دست رفته': 'fa-circle-xmark',
}

DEAL_STAGE_ICON_CATALOG = [
    'fa-seedling', 'fa-lightbulb', 'fa-phone', 'fa-comments', 'fa-handshake',
    'fa-door-open', 'fa-building', 'fa-calendar-check', 'fa-file-signature',
    'fa-file-contract', 'fa-key', 'fa-coins', 'fa-star', 'fa-bolt',
    'fa-trophy', 'fa-circle-xmark',
]

DEAL_STAGE_COLOR_PALETTE = [
    '#475569', '#1d4ed8', '#0ea5e9', '#0d9488', '#15803d',
    '#b45309', '#d97706', '#be185d', '#4338ca', '#7c3aed',
    '#b91c1c', '#64748b',
]

DEAL_STAGE_KIND_ACTIVE = 'active'
DEAL_STAGE_KIND_WON = 'won'
DEAL_STAGE_KIND_LOST = 'lost'

DEFAULT_DEAL_STAGE_DEFS = [
    {
        'id': 'lead',
        'name': 'سرنخ',
        'color': '#475569',
        'bg': '#f1f5f9',
        'icon': 'fa-seedling',
        'probability': 15,
        'rot_days': 3,
        'kind': DEAL_STAGE_KIND_ACTIVE,
        'description': 'اولین تماس و ثبت نیاز یا فایل مشتری',
    },
    {
        'id': 'negotiate',
        'name': 'مذاکره',
        'color': '#1d4ed8',
        'bg': '#dbeafe',
        'icon': 'fa-comments',
        'probability': 35,
        'rot_days': 5,
        'kind': DEAL_STAGE_KIND_ACTIVE,
        'description': 'مذاکره قیمت، شرایط و انتظارات طرفین',
    },
    {
        'id': 'visit',
        'name': 'بازدید',
        'color': '#b45309',
        'bg': '#fef3c7',
        'icon': 'fa-door-open',
        'probability': 55,
        'rot_days': 4,
        'kind': DEAL_STAGE_KIND_ACTIVE,
        'description': 'بازدید ملک یا جلسه حضوری با طرفین',
    },
    {
        'id': 'precontract',
        'name': 'پیش‌قرارداد',
        'color': '#4338ca',
        'bg': '#e0e7ff',
        'icon': 'fa-file-signature',
        'probability': 75,
        'rot_days': 7,
        'kind': DEAL_STAGE_KIND_ACTIVE,
        'description': 'توافق اولیه، بیعانه و پیش‌نویس قرارداد',
    },
    {
        'id': 'contract',
        'name': 'قرارداد',
        'color': '#be185d',
        'bg': '#fce7f3',
        'icon': 'fa-file-contract',
        'probability': 90,
        'rot_days': 10,
        'kind': DEAL_STAGE_KIND_ACTIVE,
        'description': 'تنظیم و امضای قرارداد نهایی',
    },
    {
        'id': 'won',
        'name': DEAL_STAGE_WON,
        'color': '#15803d',
        'bg': '#dcfce7',
        'icon': 'fa-trophy',
        'probability': 100,
        'rot_days': 0,
        'kind': DEAL_STAGE_KIND_WON,
        'description': 'معامله با موفقیت بسته شد',
        'locked': True,
    },
    {
        'id': 'lost',
        'name': DEAL_STAGE_LOST,
        'color': '#b91c1c',
        'bg': '#fee2e2',
        'icon': 'fa-circle-xmark',
        'probability': 0,
        'rot_days': 0,
        'kind': DEAL_STAGE_KIND_LOST,
        'description': 'فرصت از دست رفته یا منتفی شده',
        'locked': True,
    },
]

DEAL_STAGE_PRESETS = {
    'default': {
        'id': 'default',
        'name': 'فروش کامل',
        'description': 'قیف استاندارد مشاوره املاک — از سرنخ تا قرارداد',
        'definitions': DEFAULT_DEAL_STAGE_DEFS,
    },
    'sale': {
        'id': 'sale',
        'name': 'فروش حرفه‌ای',
        'description': 'تماس، بازدید، پیشنهاد و قرارداد برای معاملات فروش',
        'definitions': [
            {
                'id': 'lead', 'name': 'سرنخ', 'color': '#475569', 'bg': '#f1f5f9',
                'icon': 'fa-seedling', 'probability': 10, 'rot_days': 2,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'ثبت فایل یا تقاضای خرید',
            },
            {
                'id': 'contact', 'name': 'تماس اولیه', 'color': '#0ea5e9', 'bg': '#e0f2fe',
                'icon': 'fa-phone', 'probability': 25, 'rot_days': 2,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'برقراری تماس و صلاحیت‌سنجی',
            },
            {
                'id': 'visit', 'name': 'بازدید', 'color': '#b45309', 'bg': '#fef3c7',
                'icon': 'fa-door-open', 'probability': 45, 'rot_days': 4,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'بازدید ملک توسط خریدار',
            },
            {
                'id': 'offer', 'name': 'پیشنهاد', 'color': '#7c3aed', 'bg': '#f3e8ff',
                'icon': 'fa-star', 'probability': 65, 'rot_days': 5,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'ارائه پیشنهاد قیمت و شرایط',
            },
            {
                'id': 'negotiate', 'name': 'مذاکره', 'color': '#1d4ed8', 'bg': '#dbeafe',
                'icon': 'fa-comments', 'probability': 80, 'rot_days': 6,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'چانه‌زنی و توافق نهایی',
            },
            {
                'id': 'contract', 'name': 'قرارداد', 'color': '#be185d', 'bg': '#fce7f3',
                'icon': 'fa-file-contract', 'probability': 92, 'rot_days': 8,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'امضا و انتقال',
            },
            {
                'id': 'won', 'name': DEAL_STAGE_WON, 'color': '#15803d', 'bg': '#dcfce7',
                'icon': 'fa-trophy', 'probability': 100, 'rot_days': 0,
                'kind': DEAL_STAGE_KIND_WON, 'description': 'فروش موفق', 'locked': True,
            },
            {
                'id': 'lost', 'name': DEAL_STAGE_LOST, 'color': '#b91c1c', 'bg': '#fee2e2',
                'icon': 'fa-circle-xmark', 'probability': 0, 'rot_days': 0,
                'kind': DEAL_STAGE_KIND_LOST, 'description': 'از دست رفته', 'locked': True,
            },
        ],
    },
    'rent': {
        'id': 'rent',
        'name': 'اجاره و رهن',
        'description': 'قیف کوتاه‌تر برای معاملات اجاره و رهن',
        'definitions': [
            {
                'id': 'lead', 'name': 'سرنخ', 'color': '#475569', 'bg': '#f1f5f9',
                'icon': 'fa-seedling', 'probability': 15, 'rot_days': 2,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'تقاضای اجاره یا فایل موجر',
            },
            {
                'id': 'visit', 'name': 'بازدید', 'color': '#b45309', 'bg': '#fef3c7',
                'icon': 'fa-door-open', 'probability': 50, 'rot_days': 3,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'بازدید ملک توسط مستاجر',
            },
            {
                'id': 'negotiate', 'name': 'مذاکره رهن', 'color': '#0d9488', 'bg': '#ccfbf1',
                'icon': 'fa-comments', 'probability': 70, 'rot_days': 4,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'توافق رهن، اجاره و موعد تخلیه',
            },
            {
                'id': 'contract', 'name': 'قرارداد اجاره', 'color': '#be185d', 'bg': '#fce7f3',
                'icon': 'fa-key', 'probability': 90, 'rot_days': 5,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'تنظیم اجاره‌نامه',
            },
            {
                'id': 'won', 'name': DEAL_STAGE_WON, 'color': '#15803d', 'bg': '#dcfce7',
                'icon': 'fa-trophy', 'probability': 100, 'rot_days': 0,
                'kind': DEAL_STAGE_KIND_WON, 'description': 'اجاره موفق', 'locked': True,
            },
            {
                'id': 'lost', 'name': DEAL_STAGE_LOST, 'color': '#b91c1c', 'bg': '#fee2e2',
                'icon': 'fa-circle-xmark', 'probability': 0, 'rot_days': 0,
                'kind': DEAL_STAGE_KIND_LOST, 'description': 'از دست رفته', 'locked': True,
            },
        ],
    },
    'short': {
        'id': 'short',
        'name': 'قیف سریع',
        'description': 'حداقل مراحل برای مشاورانی که گردش کار کوتاه دارند',
        'definitions': [
            {
                'id': 'lead', 'name': 'سرنخ', 'color': '#475569', 'bg': '#f1f5f9',
                'icon': 'fa-seedling', 'probability': 20, 'rot_days': 3,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'فرصت جدید',
            },
            {
                'id': 'visit', 'name': 'بازدید', 'color': '#b45309', 'bg': '#fef3c7',
                'icon': 'fa-door-open', 'probability': 55, 'rot_days': 4,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'بازدید و ارزیابی',
            },
            {
                'id': 'contract', 'name': 'قرارداد', 'color': '#be185d', 'bg': '#fce7f3',
                'icon': 'fa-file-contract', 'probability': 85, 'rot_days': 7,
                'kind': DEAL_STAGE_KIND_ACTIVE, 'description': 'بستن معامله',
            },
            {
                'id': 'won', 'name': DEAL_STAGE_WON, 'color': '#15803d', 'bg': '#dcfce7',
                'icon': 'fa-trophy', 'probability': 100, 'rot_days': 0,
                'kind': DEAL_STAGE_KIND_WON, 'description': 'موفق', 'locked': True,
            },
            {
                'id': 'lost', 'name': DEAL_STAGE_LOST, 'color': '#b91c1c', 'bg': '#fee2e2',
                'icon': 'fa-circle-xmark', 'probability': 0, 'rot_days': 0,
                'kind': DEAL_STAGE_KIND_LOST, 'description': 'از دست رفته', 'locked': True,
            },
        ],
    },
}

DEFAULT_DEAL_CHECKLIST = [
    {'id': 'deed', 'label': 'سند ملک', 'required': True},
    {'id': 'inquiry', 'label': 'استعلام', 'required': True},
    {'id': 'owner_id', 'label': 'مدارک هویتی مالک', 'required': True},
    {'id': 'buyer_id', 'label': 'مدارک هویتی خریدار', 'required': False},
    {'id': 'deposit', 'label': 'پیش‌پرداخت / بیعانه', 'required': False},
    {'id': 'draft', 'label': 'پیش‌نویس قرارداد', 'required': True},
]

VISIT_OUTCOMES = ['پسندید', 'رد', 'در انتظار', 'بازدید مجدد']
VISIT_REJECT_REASONS = ['قیمت', 'موقعیت', 'متراژ', 'نور و تهویه', 'طبقه', 'سایر']

IMPORT_CONTACT_COLUMNS = {
    'نام': 'name',
    'تلفن': 'phone',
    'تلفن دوم': 'phone_alt',
    'ایمیل': 'email',
    'نوع': 'customer_type',
    'وضعیت': 'status',
    'اولویت': 'priority',
    'منبع': 'source',
    'شهر': 'city',
    'منطقه': 'district',
    'یادداشت': 'notes',
    'برچسب‌ها': 'tags',
}

IMPORT_PROPERTY_COLUMNS = {
    'عنوان': 'title',
    'نوع ملک': 'property_type',
    'نوع معامله': 'deal_mode',
    'وضعیت معامله': 'transaction_status',
    'وضعیت انتشار': 'publish_status',
    'نوع آگهی دهنده': 'business_type',
    'شماره تماس': 'phone',
    'شهر': 'city',
    'منطقه': 'district',
    'محله': 'neighborhood',
    'آدرس': 'address',
    'متراژ (متر)': 'area',
    'اتاق': 'rooms',
    'طبقه': 'floor',
    'تعداد طبقات': 'total_floors',
    'سال ساخت': 'build_year',
    'پارکینگ': 'has_parking',
    'انباری': 'has_storage',
    'آسانسور': 'has_elevator',
    'قیمت فروش (تومان)': 'sale_price',
    'رهن (تومان)': 'deposit',
    'اجاره ماهانه (تومان)': 'monthly_rent',
    'امکانات': 'amenities',
    'شناسه آگهی': 'token',
    'لینک': 'link',
    'عرض جغرافیایی': 'latitude',
    'طول جغرافیایی': 'longitude',
    'یادداشت': 'notes',
}

IMPORT_PROPERTY_HEADER_ALIASES = {
    'نوع آگهی‌دهنده': 'business_type',
    'business_type': 'business_type',
    'تلفن': 'phone',
    'موبایل': 'phone',
    'تماس': 'phone',
}

# ── اتوماسیون CRM (فاز ۳) ──
MESSAGE_TEMPLATE_CATEGORIES = ['پیگیری', 'بازدید', 'پیشنهاد', 'خوش‌آمد', 'سفارشی']
MESSAGE_CHANNELS = ['واتساپ', 'پیامک']
MESSAGE_PLACEHOLDERS = ['{name}', '{phone}', '{type}', '{status}', '{areas}', '{agency}']

AUTOMATION_TRIGGERS = [('inactive_days', 'بدون فعالیت (روز)')]
AUTOMATION_ACTIONS = [
    ('set_status', 'تغییر وضعیت'),
    ('create_reminder', 'ایجاد یادآور'),
]

REMINDER_RECURRENCE = [
    ('', 'یک‌بار'),
    ('daily', 'روزانه'),
    ('weekly', 'هفتگی'),
    ('biweekly', 'دو هفته‌ای'),
    ('monthly', 'ماهانه'),
]

FUNNEL_STAGES = ['سرنخ', 'پیگیری', 'بازدید', 'قرارداد']
DEFAULT_STAGNANT_DAYS = 7
