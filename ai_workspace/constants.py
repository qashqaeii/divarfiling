"""ثابت‌ها و Feature Flag — فاز صفر AI."""
from __future__ import annotations

from django.conf import settings

from workspace.services.access import has_active_bot_license

FEATURE_LISTING_SUMMARY = 'listing_summary'
FEATURE_CRM_MESSAGE = 'crm_message'
FEATURE_UPLOAD_BRIEF = 'upload_brief'
FEATURE_NL_COMMAND = 'nl_command'

AI_FEATURES = {
    FEATURE_LISTING_SUMMARY: True,
    FEATURE_CRM_MESSAGE: True,
    # غیرفعال محصولی — endpoint فقط پاسخ کنترل‌شده می‌دهد؛ LLM صدا زده نمی‌شود.
    FEATURE_UPLOAD_BRIEF: False,
    FEATURE_NL_COMMAND: True,
}

FEATURE_DAILY_LIMITS = {
    FEATURE_LISTING_SUMMARY: 30,
    FEATURE_CRM_MESSAGE: 24,
    FEATURE_NL_COMMAND: 30,
}

FEATURE_GENERATION = {
    FEATURE_NL_COMMAND: {
        'temperature': 0.1,
        'max_tokens': 700,
    },
}

DEFAULT_DAILY_LIMIT = 30

FEATURE_LABELS = {
    FEATURE_LISTING_SUMMARY: 'خلاصه آگهی',
    FEATURE_CRM_MESSAGE: 'پیام CRM',
    FEATURE_UPLOAD_BRIEF: 'تحلیل آپلود',
    FEATURE_NL_COMMAND: 'فرمان هوشمند',
}

DEFAULT_CRM_TONE = 'رسمی'

CRM_MESSAGE_TONES = {
    'رسمی': {
        'label': 'رسمی و حرفه‌ای',
        'guide': 'محترمانه، منظم و مناسب مشاور املاک؛ جملات کوتاه و شفاف.',
        'emoji': False,
    },
    'صمیمی': {
        'label': 'صمیمی و گرم',
        'guide': 'دوستانه ولی حرفه‌ای؛ از «شما» استفاده کنید و لحن گفت‌وگویی داشته باشید.',
        'emoji': False,
    },
    'کوتاه': {
        'label': 'کوتاه و مستقیم',
        'guide': 'حداکثر ۵ خط؛ مستقیم به معرفی ملک‌ها و دعوت به اقدام برسید؛ بدون مقدمه طولانی.',
        'emoji': False,
    },
    'مشاورانه': {
        'label': 'مشاورانه',
        'guide': 'لحن راهنما و مشاور؛ دلیل پیشنهاد هر ملک را در یک عبارت کوتاه بگویید.',
        'emoji': False,
    },
    'پیگیری': {
        'label': 'پیگیری ملایم',
        'guide': 'ملایم و پیگیر؛ مناسب پیام پیگیری بدون فشار؛ تأکید بر آمادگی برای همکاری.',
        'emoji': False,
    },
}

CRM_MESSAGE_TONE_CHOICES = tuple(
    (key, meta['label']) for key, meta in CRM_MESSAGE_TONES.items()
)

JSON_FEATURES = frozenset({FEATURE_LISTING_SUMMARY, FEATURE_NL_COMMAND})

# نسخه دستی prompt — فقط وقتی محتوا عوض شد افزایش دهید (نه mtime)
PROMPT_VERSIONS = {
    FEATURE_LISTING_SUMMARY: 'listing_summary_v6',
    FEATURE_CRM_MESSAGE: 'crm_message_v5',
    FEATURE_UPLOAD_BRIEF: 'upload_brief_v1',
    FEATURE_NL_COMMAND: 'nl_command_v3',
}

NL_COMMAND_INTENT_CREATE_REMINDER = 'create_reminder'
NL_COMMAND_INTENT_CREATE_CONTACT = 'create_contact'
NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY = 'create_personal_property'
NL_COMMAND_INTENT_UNKNOWN = 'unknown'
NL_COMMAND_ALLOWED_INTENTS = frozenset({
    NL_COMMAND_INTENT_CREATE_REMINDER,
    NL_COMMAND_INTENT_CREATE_CONTACT,
    NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
    NL_COMMAND_INTENT_UNKNOWN,
})

NL_COMMAND_UNKNOWN_MESSAGE = (
    'فعلاً فرمان هوشمند برای ثبت یادآوری، مخاطب و فایل شخصی فعال است.'
)

NL_COMMAND_PARSE_FAILED_MESSAGE = (
    'فرمان قابل تشخیص نبود. دوباره ساده‌تر بنویسید.'
)

NL_COMMAND_PROVIDER_UNAVAILABLE_MESSAGE = (
    'سرویس هوشمند موقتاً در دسترس نیست. دوباره تلاش کنید.'
)

NL_COMMAND_EXAMPLE_PHRASES = (
    'فردا ساعت ۱۰ یادم بنداز به احمدی زنگ بزنم',
    'خانم احمدی رو با شماره ۰۹۱۲۱۲۳۴۵۶۷ ذخیره کن',
    'یه آپارتمان ۱۲۰ متری پونک برای فروش، ۱۲ میلیارد',
)

MAX_NL_COMMAND_CHARS = 1500

NL_COMMAND_INPUT_TOO_LONG_MESSAGE = (
    'فرمان خیلی طولانی است. لطفاً کوتاه‌تر بگویید یا بنویسید.'
)


def nl_command_contact_not_found_message(contact_name: str) -> str:
    name = (contact_name or '').strip() or 'موردنظر'
    return f'مخاطبی با نام {name} پیدا نشد.'


def is_ai_enabled() -> bool:
    return bool(getattr(settings, 'AI_ENABLED', False))


def is_feature_enabled(feature: str, user) -> bool:
    if not is_ai_enabled():
        return False
    if feature not in AI_FEATURES or not AI_FEATURES[feature]:
        return False
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    return has_active_bot_license(user)


def feature_uses_json(feature: str) -> bool:
    return feature in JSON_FEATURES


def normalize_crm_tone(tone: str | None) -> str:
    key = (tone or '').strip()
    # لحن قدیمی ایموجی — به صمیمی نگاشت می‌شود
    if key in {'ایموجی‌دار', 'ایموجیدار', 'ایموجی دار'}:
        return 'صمیمی'
    if key in CRM_MESSAGE_TONES:
        return key
    return DEFAULT_CRM_TONE


def crm_tone_meta(tone: str | None) -> dict:
    return CRM_MESSAGE_TONES[normalize_crm_tone(tone)]


INTERNAL_MODEL_LABEL = 'مدل داخلی سیستم'


def resolve_model_label(
    *,
    provider: str = '',
    model: str = '',
    is_fallback: bool = False,
    source: str = 'ai',
) -> str:
    """برچسب نمایشی مدل تولید متن — fallback سیستمی: «مدل داخلی سیستم»."""
    provider = (provider or '').strip()
    model = (model or '').strip()
    source = (source or 'ai').strip()

    if source == 'fallback' or provider == 'rule_based':
        return INTERNAL_MODEL_LABEL
    if is_fallback and not model:
        return INTERNAL_MODEL_LABEL
    if model:
        return model
    if provider == 'openrouter':
        return 'مدل پشتیبان'
    if provider == 'arvan':
        return model or 'Arvan AI'
    if provider == 'gemini':
        return 'Gemini'
    if is_fallback:
        return INTERNAL_MODEL_LABEL
    return ''
