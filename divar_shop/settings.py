"""
Django settings for divar_shop project.
"""

import os
from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-change-this-in-production-!@#$%^&*()' if DEBUG else '',
)

# در production فقط دامنه‌های واقعی؛ localhost فقط در DEBUG
_DEFAULT_ALLOWED_HOSTS = (
    'divarfiling.ir,www.divarfiling.ir,212.80.29.56,62.60.204.73,localhost,127.0.0.1'
    if DEBUG
    else 'divarfiling.ir,www.divarfiling.ir,212.80.29.56,62.60.204.73'
)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default=_DEFAULT_ALLOWED_HOSTS, cast=Csv())

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://divarfiling.ir,https://www.divarfiling.ir',
    cast=Csv(),
)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    
    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    
    # Local apps
    'shop',
    'accounts',
    'licenses',
    'affiliates',
    'blog',
    'workspace',
    'ai_workspace',
    'public_assistant',
    'product_hub',
    'mobile_api',
    'desktop_api',
    'contracts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'divar_shop.middleware.SSLRedirectMiddleware',  # جلوگیری از redirect IP به HTTPS
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'mobile_api.middleware.MobileAuthLoggingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'affiliates.middleware.AffiliateTrackingMiddleware',  # پیگیری لینک‌های افیلیت
]

ROOT_URLCONF = 'divar_shop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                *(['django.template.context_processors.debug'] if DEBUG else []),
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.shop_context',
                'workspace.context_processors.workspace_context',
                'affiliates.context_processors.affiliate_context',
                'accounts.context_processors.admin_panel_shell',
                'public_assistant.context_processors.public_assistant',
            ],
        },
    },
]

WSGI_APPLICATION = 'divar_shop.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

_DATABASE_ENGINE = config(
    'DATABASE_ENGINE',
    default='django.db.backends.sqlite3',
)
if _DATABASE_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DATABASE_NAME', default='divarfilingDb'),
            'USER': config('DATABASE_USER', default='divarfilingAdmin'),
            'PASSWORD': config('DATABASE_PASSWORD', default=''),
            'HOST': config('DATABASE_HOST', default='localhost'),
            'PORT': config('DATABASE_PORT', default='5432'),
            'CONN_MAX_AGE': config('DATABASE_CONN_MAX_AGE', default=600, cast=int),
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / config('DATABASE_NAME', default='db.sqlite3'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'accounts.backends.PhoneAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Site ID
SITE_ID = 1

# Site Information for SEO
SITE_NAME = 'فایلینگ دیوار'
SITE_URL = config('SITE_URL', default='https://divarfiling.ir')
# هندل توییتر/X — فقط اگر مقدار دارد در meta نمایش داده می‌شود (مثلاً divarfiling)
TWITTER_SITE = config('TWITTER_SITE', default='').strip()

# Zibal Payment Gateway Settings
ZIBAL_MERCHANT_ID = config('ZIBAL_MERCHANT_ID', default='')
ZIBAL_CALLBACK_URL = config('ZIBAL_CALLBACK_URL', default='https://divarfiling.ir/payment/callback/')
ZIBAL_REQUEST_URL = 'https://gateway.zibal.ir/v1/request'
ZIBAL_VERIFY_URL = 'https://gateway.zibal.ir/v1/verify'
ZIBAL_START_PAY_URL = 'https://gateway.zibal.ir/start/'

# Job رها کردن Checkout (مرحله 1.4 — فقط Event + Preview؛ بدون SMS)
CHECKOUT_ABANDON_HOURS = config('CHECKOUT_ABANDON_HOURS', default=2, cast=int)
CHECKOUT_ABANDON_BATCH_LIMIT = config('CHECKOUT_ABANDON_BATCH_LIMIT', default=500, cast=int)

# نگه‌داری موقت آگهی‌های فایلینگ (روز) — CRM و سرکوب کاربر مستقل می‌مانند
from workspace.constants import (
    FILING_LISTING_RETENTION_DAYS_DEFAULT,
    FILING_RETENTION_CLEANUP_DAY_DEFAULT,
    FILING_RETENTION_CLEANUP_HOUR_DEFAULT,
    FILING_RETENTION_WARNING_DAYS_DEFAULT,
)

FILING_LISTING_RETENTION_DAYS = config(
    'FILING_LISTING_RETENTION_DAYS',
    default=FILING_LISTING_RETENTION_DAYS_DEFAULT,
    cast=int,
)
FILING_RETENTION_WARNING_DAYS = config(
    'FILING_RETENTION_WARNING_DAYS',
    default=FILING_RETENTION_WARNING_DAYS_DEFAULT,
    cast=int,
)
FILING_RETENTION_CLEANUP_DAY = config(
    'FILING_RETENTION_CLEANUP_DAY',
    default=FILING_RETENTION_CLEANUP_DAY_DEFAULT,
    cast=int,
)
FILING_RETENTION_CLEANUP_HOUR = config(
    'FILING_RETENTION_CLEANUP_HOUR',
    default=FILING_RETENTION_CLEANUP_HOUR_DEFAULT,
    cast=int,
)
RETENTION_WARNING_FEATURE_DEPLOYED_AT = config(
    'RETENTION_WARNING_FEATURE_DEPLOYED_AT',
    default='',
)

# Recovery Audience — فاز ۲.۱ (Dry Run؛ بدون SMS)
RECOVERY_STEP_1_MIN_HOURS = config('RECOVERY_STEP_1_MIN_HOURS', default=2, cast=int)
RECOVERY_STEP_2_MIN_HOURS = config('RECOVERY_STEP_2_MIN_HOURS', default=24, cast=int)
RECOVERY_MAX_AGE_HOURS = config('RECOVERY_MAX_AGE_HOURS', default=72, cast=int)
RECOVERY_LOOKBACK_DAYS = config('RECOVERY_LOOKBACK_DAYS', default=7, cast=int)
RECOVERY_FREQUENCY_CAP_HOURS = config('RECOVERY_FREQUENCY_CAP_HOURS', default=24, cast=int)
RECOVERY_BATCH_LIMIT = config('RECOVERY_BATCH_LIMIT', default=100, cast=int)
PENDING_RECOVERY_FLOW_ENABLED = config('PENDING_RECOVERY_FLOW_ENABLED', default=False, cast=bool)
# فاز ۲.۲ — ارسال Live (Kill Switch جدا؛ پیش‌فرض خاموش)
RECOVERY_LIVE_SEND_ENABLED = config('RECOVERY_LIVE_SEND_ENABLED', default=False, cast=bool)
RECOVERY_LIVE_TEST_ONLY = config('RECOVERY_LIVE_TEST_ONLY', default=True, cast=bool)
RECOVERY_LIVE_TEST_PHONE = config('RECOVERY_LIVE_TEST_PHONE', default='')
RECOVERY_LIVE_MAX_SENDS_PER_RUN = config('RECOVERY_LIVE_MAX_SENDS_PER_RUN', default=1, cast=int)
RECOVERY_MAX_SMS_PER_DAY = config('RECOVERY_MAX_SMS_PER_DAY', default=5, cast=int)
RECOVERY_SMS_TEMPLATE = config(
    'RECOVERY_SMS_TEMPLATE',
    default='{name_part}سفارش «{product}» ({amount} ت) منتظر پرداخت است. {link}',
)
RECOVERY_PROVIDER_TIMEOUT_SECONDS = config('RECOVERY_PROVIDER_TIMEOUT_SECONDS', default=15, cast=int)

# Growth pipeline — license renewal automation
LICENSE_RENEWAL_FLOW_ENABLED = config('LICENSE_RENEWAL_FLOW_ENABLED', default=True, cast=bool)
LICENSE_RENEWAL_WITHIN_DAYS = config('LICENSE_RENEWAL_WITHIN_DAYS', default=7, cast=int)
LICENSE_RENEWAL_CHURN_AFTER_DAYS = config('LICENSE_RENEWAL_CHURN_AFTER_DAYS', default=3, cast=int)
# خالی = لینک خودکار صفحه buy محصول ربات (accounts.services.growth_links)
LICENSE_RENEWAL_LANDING_URL = config('LICENSE_RENEWAL_LANDING_URL', default='')

# License Settings
LICENSE_SECRET_KEY = config('LICENSE_SECRET_KEY', default='change-this-secret-key-in-production')
LICENSE_ACTIVATION_LIMIT = 1  # تعداد فعال‌سازی مجاز (legacy)
LICENSE_OFFLINE_GRACE_HOURS = config('LICENSE_OFFLINE_GRACE_HOURS', default=72, cast=int)
LICENSE_RATE_LIMIT_ACTIVATE = config('LICENSE_RATE_LIMIT_ACTIVATE', default=5, cast=int)
LICENSE_RATE_LIMIT_VALIDATE = config('LICENSE_RATE_LIMIT_VALIDATE', default=60, cast=int)
LICENSE_RATE_LIMIT_DEACTIVATE = config('LICENSE_RATE_LIMIT_DEACTIVATE', default=10, cast=int)
LICENSE_RATE_LIMIT_WINDOW = config('LICENSE_RATE_LIMIT_WINDOW', default=300, cast=int)
LICENSE_ALLOW_LOCAL_DEV = config('LICENSE_ALLOW_LOCAL_DEV', default=DEBUG, cast=bool)
LICENSE_BOT_API_KEY = config('LICENSE_BOT_API_KEY', default='')

# ورود حساب کاربری در اپ ویندوز (API /api/desktop/v1/)
DESKTOP_ACCOUNT_LOGIN_ENABLED = config('DESKTOP_ACCOUNT_LOGIN_ENABLED', default=True, cast=bool)

# میزکار — فقط با سفارش paid و لایسنس active (بدون bypass خودکار staff)
WORKSPACE_LICENSE_STAFF_BYPASS = config('WORKSPACE_LICENSE_STAFF_BYPASS', default=False, cast=bool)

# AI Workspace — Gemini primary + Arvan AIaaS backup + rule-based fallback
AI_ENABLED = config('AI_ENABLED', default=False, cast=bool)
ADMIN_MANAGEMENT_AI_ENABLED = config('ADMIN_MANAGEMENT_AI_ENABLED', default=False, cast=bool)
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-3.1-flash-lite')
GEMINI_FALLBACK_MODEL = config('GEMINI_FALLBACK_MODEL', default='gemini-2.5-flash-lite')
GEMINI_TIMEOUT_SECONDS = config('GEMINI_TIMEOUT_SECONDS', default=10, cast=int)

# ArvanCloud AIaaS (production backup — OpenAI-compatible chat/completions)
ARVAN_AI_ENABLED = config('ARVAN_AI_ENABLED', default=False, cast=bool)
ARVAN_AI_BASE_URL = config('ARVAN_AI_BASE_URL', default='')
ARVAN_AI_API_KEY = config('ARVAN_AI_API_KEY', default='')
ARVAN_AI_MODEL = config('ARVAN_AI_MODEL', default='Gemini-2.5-Flash-lite')
ARVAN_AI_FALLBACK_MODEL = config('ARVAN_AI_FALLBACK_MODEL', default='')
ARVAN_AI_TIMEOUT_SECONDS = config('ARVAN_AI_TIMEOUT_SECONDS', default=10, cast=int)
ARVAN_AI_MAX_RETRIES = config('ARVAN_AI_MAX_RETRIES', default=1, cast=int)
ARVAN_AI_TEMPERATURE = config('ARVAN_AI_TEMPERATURE', default=0.4, cast=float)
ARVAN_AI_MAX_TOKENS = config('ARVAN_AI_MAX_TOKENS', default=1200, cast=int)

# OpenRouter — backup after Arvan (:free models only)
OPENROUTER_API_KEY = config('OPENROUTER_API_KEY', default='')
OPENROUTER_BASE_URL = config('OPENROUTER_BASE_URL', default='https://openrouter.ai/api/v1')
OPENROUTER_FREE_MODELS = config(
    'OPENROUTER_FREE_MODELS',
    default='',
)
OPENROUTER_TIMEOUT_SECONDS = config('OPENROUTER_TIMEOUT_SECONDS', default=8, cast=int)
AI_GLOBAL_DAILY_CAP = config('AI_GLOBAL_DAILY_CAP', default=1050, cast=int)
AI_DAILY_TOKEN_LIMIT = config('AI_DAILY_TOKEN_LIMIT', default=90000, cast=int)
# True: کاربر بدون لایسنس سهمیه رایگان؛ لایسنس فعال = AI نامحدود. False: سیاست قبلی (فقط با لایسنس).
AI_LICENSED_UNLIMITED = config('AI_LICENSED_UNLIMITED', default=True, cast=bool)
# bump هنگام تغییر provider chain تا پاسخ‌های cache شدهٔ provider قبلی reuse نشوند
AI_CACHE_VERSION = config('AI_CACHE_VERSION', default='v2')

# دستیار عمومی سایت (RAG + ویجت) — پیش‌فرض خاموش تا استقرار کنترل‌شده
PUBLIC_ASSISTANT_ENABLED = config('PUBLIC_ASSISTANT_ENABLED', default=False, cast=bool)
PUBLIC_ASSISTANT_RATE_LIMIT_PER_HOUR = config('PUBLIC_ASSISTANT_RATE_LIMIT_PER_HOUR', default=40, cast=int)
PUBLIC_ASSISTANT_SESSION_RATE_LIMIT_PER_HOUR = config(
    'PUBLIC_ASSISTANT_SESSION_RATE_LIMIT_PER_HOUR', default=25, cast=int
)
PUBLIC_ASSISTANT_TEMPERATURE = config('PUBLIC_ASSISTANT_TEMPERATURE', default=0.35, cast=float)
PUBLIC_ASSISTANT_MAX_TOKENS = config('PUBLIC_ASSISTANT_MAX_TOKENS', default=900, cast=int)

# CARTO raster basemaps (Leaflet tile layers) — free tier with API key
CARTO_BASEMAP_API_KEY = config('CARTO_BASEMAP_API_KEY', default='')

# امکانات اطراف فایل شخصی — Overpass/OSM (on-demand)
NEARBY_POI_USER_DAILY_LIMIT = config('NEARBY_POI_USER_DAILY_LIMIT', default=25, cast=int)
NEARBY_POI_GLOBAL_DAILY_LIMIT = config('NEARBY_POI_GLOBAL_DAILY_LIMIT', default=400, cast=int)
NEARBY_POI_SEARCH_RADIUS_M = config('NEARBY_POI_SEARCH_RADIUS_M', default=3000, cast=int)
NEARBY_POI_OVERPASS_TIMEOUT = config('NEARBY_POI_OVERPASS_TIMEOUT', default=30, cast=int)
NEARBY_POI_OVERPASS_CONNECT_TIMEOUT = config('NEARBY_POI_OVERPASS_CONNECT_TIMEOUT', default=6, cast=int)
NEARBY_POI_FORCE_IPV4 = config('NEARBY_POI_FORCE_IPV4', default=True, cast=bool)
NEARBY_POI_STREET_RADIUS_M = config('NEARBY_POI_STREET_RADIUS_M', default=120, cast=int)
PROPERTY_ACCESSIBILITY_PENDING_TIMEOUT_MIN = config(
    'PROPERTY_ACCESSIBILITY_PENDING_TIMEOUT_MIN', default=15, cast=int,
)
PROPERTY_ACCESSIBILITY_JOB_MAX_ATTEMPTS = config(
    'PROPERTY_ACCESSIBILITY_JOB_MAX_ATTEMPTS', default=3, cast=int,
)
PROPERTY_ACCESSIBILITY_OVERPASS_RETRIES = config(
    'PROPERTY_ACCESSIBILITY_OVERPASS_RETRIES', default=2, cast=int,
)
PROPERTY_ACCESSIBILITY_OVERPASS_RETRY_BACKOFF_S = config(
    'PROPERTY_ACCESSIBILITY_OVERPASS_RETRY_BACKOFF_S', default=2, cast=int,
)
NEARBY_POI_OVERPASS_URLS = config(
    'NEARBY_POI_OVERPASS_URLS',
    default=(
        'https://maps.mail.ru/osm/tools/overpass/api/interpreter,'
        'https://overpass.openstreetmap.ru/api/interpreter,'
        'https://overpass.private.coffee/api/interpreter,'
        'https://overpass.osm.ch/api/interpreter,'
        'https://overpass-api.de/api/interpreter,'
        'https://overpass.kumi.systems/api/interpreter'
    ),
    cast=Csv(),
)

# Cache — برای rate limit لایسنس (در production از Redis استفاده کنید)
CACHES = {
    'default': {
        'BACKEND': config(
            'CACHE_BACKEND',
            default='django.core.cache.backends.locmem.LocMemCache',
        ),
        'LOCATION': config('CACHE_LOCATION', default='divar-shop-default'),
    }
}

# Affiliate Settings
AFFILIATE_DEFAULT_COMMISSION = 10  # درصد پیش‌فرض کمیسیون
AFFILIATE_DEFAULT_DISCOUNT = 5  # درصد پیش‌فرض تخفیف برای کاربران دعوت‌شده
AFFILIATE_MIN_PAYOUT = 100000  # حداقل مبلغ برای تسویه (تومان)
AFFILIATE_MIN_WITHDRAWAL = 10000  # حداقل مبلغ برای برداشت (تومان)
AFFILIATE_COOKIE_NAME = 'affiliate_ref'  # نام cookie برای ذخیره کد معرف
AFFILIATE_COOKIE_DAYS = 30  # مدت اعتبار cookie (روز)
AFFILIATE_DISCOUNT_ENABLED = True
AFFILIATE_DISCOUNT_FIRST_ORDER_ONLY = True  # تخفیف معرف فقط روی اولین خرید موفق

# ── SMS / FarazSMS (IranPayamak) — https://docs.iranpayamak.com/ ──
# SMS_PROVIDER=console برای توسعه بدون ارسال واقعی؛ faraz برای تولید
SMS_ENABLED = config('SMS_ENABLED', default=True, cast=bool)
SMS_PROVIDER = config('SMS_PROVIDER', default='console')
LEAD_SMS_COST_PER_PART_RIAL = config('LEAD_SMS_COST_PER_PART_RIAL', default=2480, cast=int)
# حداکثر SMS در هر کلیک «ارسال مرحله» — جلوگیری از timeout گunicorn (پیش‌فرض ۳۰ث)
LEAD_CAMPAIGN_SEND_BATCH_SIZE = config('LEAD_CAMPAIGN_SEND_BATCH_SIZE', default=10, cast=int)
# اتوماسیون جذب لید از phone-detector
ACQUISITION_AUTOMATION_ENABLED = config('ACQUISITION_AUTOMATION_ENABLED', default=True, cast=bool)
ACQUISITION_COOLDOWN_HOURS = config('ACQUISITION_COOLDOWN_HOURS', default=4, cast=int)
ACQUISITION_WORKER_POLL_SECONDS = config('ACQUISITION_WORKER_POLL_SECONDS', default=30, cast=int)
PHONE_DETECTOR_DIR = config('PHONE_DETECTOR_DIR', default='')
# Fernet key (url-safe base64) برای رمزنگاری نشست‌های دیوار در DB
DIVAR_SESSION_ENCRYPTION_KEY = config('DIVAR_SESSION_ENCRYPTION_KEY', default='')
# کلید قبلی برای رمزگشایی نشست‌های ذخیره‌شده قبل از چرخش کلید
DIVAR_SESSION_ENCRYPTION_KEY_LEGACY = config('DIVAR_SESSION_ENCRYPTION_KEY_LEGACY', default='')
# سازگاری قدیمی (تومان برای هر بخش) — اگر PER_PART_RIAL ست نباشد استفاده می‌شود
LEAD_SMS_COST_TOMAN = config('LEAD_SMS_COST_TOMAN', default=0, cast=int)
FARAZSMS_API_KEY = config('FARAZSMS_API_KEY', default='')
# خط پیش‌فرض — بازاریابی، سیستمی، تمدید لایسنس و پیامک متنی
FARAZSMS_LINE_NUMBER = config('FARAZSMS_LINE_NUMBER', default='90008361')
# خط جدا برای OTP (ورود، ثبت‌نام، تأیید موبایل، بازیابی رمز)
FARAZSMS_OTP_LINE_NUMBER = config('FARAZSMS_OTP_LINE_NUMBER', default='90008361')
FARAZSMS_OTP_PURPOSES = (
    'login',
    'register',
    'verify_phone',
    'password_reset',
    'contract_otp',
)
FARAZSMS_BASE_URL = config('FARAZSMS_BASE_URL', default='https://api.iranpayamak.com')
FARAZSMS_TIMEOUT = config('FARAZSMS_TIMEOUT', default=15, cast=int)
# هشدار موجودی کم در پنل ادمین (تومان)
FARAZSMS_LOW_BALANCE = config('FARAZSMS_LOW_BALANCE', default=50000, cast=int)
# دفترچه تلفن «کاربران» در پنل فراز — برای کمپین‌های بازاریابی
FARAZSMS_PHONEBOOK_USERS_ID = config('FARAZSMS_PHONEBOOK_USERS_ID', default=119558, cast=int)
# نام متغیر الگو در پنل فراز (مثلاً code یا verification-code)
FARAZSMS_OTP_ATTR = config('FARAZSMS_OTP_ATTR', default='code')
FARAZSMS_PATTERNS = {
    'login': config('FARAZSMS_PATTERN_LOGIN', default=''),
    'register': config('FARAZSMS_PATTERN_REGISTER', default=''),
    'verify_phone': config('FARAZSMS_PATTERN_VERIFY_PHONE', default=''),
    'password_reset': config('FARAZSMS_PATTERN_PASSWORD_RESET', default=''),
    'license_renewal': config('FARAZSMS_PATTERN_LICENSE_RENEWAL', default=''),
    'system': config('FARAZSMS_PATTERN_SYSTEM', default=''),
    'marketing': config('FARAZSMS_PATTERN_MARKETING', default=''),
    'contract_otp': config('FARAZSMS_PATTERN_CONTRACT_OTP', default=''),
    'card_transfer_admin_review': config('FARAZSMS_PATTERN_CARD_TRANSFER_ADMIN', default=''),
    'card_transfer_license_activated': config('FARAZSMS_PATTERN_CARD_TRANSFER_ACTIVATED', default=''),
    'card_transfer_rejected': config('FARAZSMS_PATTERN_CARD_TRANSFER_REJECTED', default=''),
    'agency_invite': config('FARAZSMS_PATTERN_AGENCY_INVITE', default='mPibtIrJSo'),
    'weekly_trial_campaign': config('FARAZSMS_PATTERN_WEEKLY_TRIAL_CAMPAIGN', default=''),
}
WEEKLY_TRIAL_CAMPAIGN_DEFAULT_KEY = config(
    'WEEKLY_TRIAL_CAMPAIGN_DEFAULT_KEY',
    default='weekly_professional_gift_v1',
)
WEEKLY_TRIAL_CAMPAIGN_SMS_BATCH_SIZE = config(
    'WEEKLY_TRIAL_CAMPAIGN_SMS_BATCH_SIZE',
    default=10,
    cast=int,
)
# هدیه خوش‌آمدگویی ۷روزه — فقط ثبت‌نام‌های جدید پس از تاریخ شروع
SIGNUP_WELCOME_GIFT_ENABLED = config('SIGNUP_WELCOME_GIFT_ENABLED', default=False, cast=bool)
SIGNUP_WELCOME_GIFT_START_AT = config('SIGNUP_WELCOME_GIFT_START_AT', default='')
SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY = config(
    'SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY',
    default='signup_welcome_7d_v1',
)
# شماره‌های مدیر برای اعلان کارت‌به‌کارت (جدا با کاما) — در صورت خالی، staff فعال
CARD_TRANSFER_ADMIN_PHONES = config('CARD_TRANSFER_ADMIN_PHONES', default='')
# اگر الگوی جداگانه ندارید، یک الگو برای همه OTPها:
_FARAZSMS_PATTERN_OTP = config('FARAZSMS_PATTERN_OTP', default='')
if _FARAZSMS_PATTERN_OTP:
    for _otp_key in ('login', 'register', 'verify_phone', 'password_reset'):
        if not FARAZSMS_PATTERNS[_otp_key]:
            FARAZSMS_PATTERNS[_otp_key] = _FARAZSMS_PATTERN_OTP

OTP_LENGTH = config('OTP_LENGTH', default=6, cast=int)
OTP_EXPIRY_SECONDS = config('OTP_EXPIRY_SECONDS', default=120, cast=int)
OTP_RESEND_SECONDS = config('OTP_RESEND_SECONDS', default=60, cast=int)
OTP_MAX_ATTEMPTS = config('OTP_MAX_ATTEMPTS', default=5, cast=int)
OTP_MAX_SENDS_PER_HOUR = config('OTP_MAX_SENDS_PER_HOUR', default=5, cast=int)
OTP_PEPPER = config('OTP_PEPPER', default='')
# فقط برای تست خودکار — کد را در پاسخ/چالش برنگردانید در تولید
OTP_DEBUG_RETURN_CODE = config('OTP_DEBUG_RETURN_CODE', default=DEBUG, cast=bool)

# Email Settings
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default=(
        'django.core.mail.backends.console.EmailBackend'
        if DEBUG
        else 'django.core.mail.backends.smtp.EmailBackend'
    ),
)
EMAIL_HOST = config('EMAIL_HOST', default='mail.divarfiling.ir')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='noreply@divarfiling.ir')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@divarfiling.ir')

# REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'mobile_api.authentication.MobileJWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'mobile_api.throttles.MobileUserThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'mobile_login': '10/minute',
        'mobile_refresh': '30/minute',
        'mobile_user': '1200/hour',
        'mobile_extraction': '30/hour',
        'desktop_login': '10/minute',
        'desktop_refresh': '30/minute',
        'desktop_bind': '20/hour',
        'desktop_validate': '120/hour',
    },
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    "https://divarfiling.ir",
    "https://www.divarfiling.ir",
]
if DEBUG:
    CORS_ALLOWED_ORIGINS += [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Security Settings
if not DEBUG:
    # تنظیمات امنیتی برای HTTPS
    # SECURE_SSL_REDIRECT غیرفعال شده - redirect در Nginx انجام می‌شود
    # این به ما اجازه می‌دهد که IP را بدون redirect نگه داریم
    SECURE_SSL_REDIRECT = False  # Redirect در Nginx انجام می‌شود
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# آپلود پوشه output — تعداد زیاد فایل Excel/CSV
DATA_UPLOAD_MAX_NUMBER_FILES = 5000
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_MEMORY_SIZE = 52_428_800  # 50 MB

# Firebase Cloud Messaging — HTTP v1 (پروژه‌های جدید؛ Legacy غیرفعال است)
FCM_PROJECT_ID = config('FCM_PROJECT_ID', default='divarfiling')
FCM_SERVICE_ACCOUNT_FILE = config(
    'FCM_SERVICE_ACCOUNT_FILE',
    default=str(BASE_DIR / 'secrets' / 'firebase-service-account.json'),
)
FCM_SERVER_KEY = config('FCM_SERVER_KEY', default='')  # فقط اگر Legacy API فعال باشد

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'skip_disallowed_host': {
            '()': 'divar_shop.logging_filters.SkipDisallowedHostFilter',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'filters': ['skip_disallowed_host'],
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['skip_disallowed_host'],
        },
    },
    'loggers': {
        'django.security.DisallowedHost': {
            'handlers': [],
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
