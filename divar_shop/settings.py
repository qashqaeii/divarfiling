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
    'mobile_api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'divar_shop.middleware.SSLRedirectMiddleware',  # جلوگیری از redirect IP به HTTPS
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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

# گفتینو — فقط در قالب عمومی (base.html) بارگذاری می‌شود
GOFTINO_WIDGET_ID = config('GOFTINO_WIDGET_ID', default='')

# Zibal Payment Gateway Settings
ZIBAL_MERCHANT_ID = config('ZIBAL_MERCHANT_ID', default='')
ZIBAL_CALLBACK_URL = config('ZIBAL_CALLBACK_URL', default='https://divarfiling.ir/payment/callback/')
ZIBAL_REQUEST_URL = 'https://gateway.zibal.ir/v1/request'
ZIBAL_VERIFY_URL = 'https://gateway.zibal.ir/v1/verify'
ZIBAL_START_PAY_URL = 'https://gateway.zibal.ir/start/'

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

# میزکار — فقط با سفارش paid و لایسنس active (بدون bypass خودکار staff)
WORKSPACE_LICENSE_STAFF_BYPASS = config('WORKSPACE_LICENSE_STAFF_BYPASS', default=False, cast=bool)

# AI Workspace — فاز صفر (Gemini + OpenRouter backup)
AI_ENABLED = config('AI_ENABLED', default=False, cast=bool)
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-3.1-flash-lite')
GEMINI_FALLBACK_MODEL = config('GEMINI_FALLBACK_MODEL', default='gemini-2.5-flash-lite')
GEMINI_TIMEOUT_SECONDS = config('GEMINI_TIMEOUT_SECONDS', default=10, cast=int)
OPENROUTER_API_KEY = config('OPENROUTER_API_KEY', default='')
OPENROUTER_BASE_URL = config('OPENROUTER_BASE_URL', default='https://openrouter.ai/api/v1')
OPENROUTER_FREE_MODELS = config(
    'OPENROUTER_FREE_MODELS',
    default='',
)
OPENROUTER_TIMEOUT_SECONDS = config('OPENROUTER_TIMEOUT_SECONDS', default=8, cast=int)
AI_GLOBAL_DAILY_CAP = config('AI_GLOBAL_DAILY_CAP', default=350, cast=int)
AI_DAILY_TOKEN_LIMIT = config('AI_DAILY_TOKEN_LIMIT', default=30000, cast=int)

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
FARAZSMS_API_KEY = config('FARAZSMS_API_KEY', default='')
FARAZSMS_LINE_NUMBER = config('FARAZSMS_LINE_NUMBER', default='90008361')
FARAZSMS_BASE_URL = config('FARAZSMS_BASE_URL', default='https://api.iranpayamak.com')
FARAZSMS_TIMEOUT = config('FARAZSMS_TIMEOUT', default=15, cast=int)
# هشدار موجودی کم در پنل ادمین (تومان)
FARAZSMS_LOW_BALANCE = config('FARAZSMS_LOW_BALANCE', default=50000, cast=int)
# نام متغیر الگو در پنل فراز (مثلاً code یا verification-code)
FARAZSMS_OTP_ATTR = config('FARAZSMS_OTP_ATTR', default='code')
FARAZSMS_PATTERNS = {
    'login': config('FARAZSMS_PATTERN_LOGIN', default=''),
    'register': config('FARAZSMS_PATTERN_REGISTER', default=''),
    'verify_phone': config('FARAZSMS_PATTERN_VERIFY_PHONE', default=''),
    'license_renewal': config('FARAZSMS_PATTERN_LICENSE_RENEWAL', default=''),
    'system': config('FARAZSMS_PATTERN_SYSTEM', default=''),
    'marketing': config('FARAZSMS_PATTERN_MARKETING', default=''),
}
# اگر الگوی جداگانه ندارید، یک الگو برای همه OTPها:
_FARAZSMS_PATTERN_OTP = config('FARAZSMS_PATTERN_OTP', default='')
if _FARAZSMS_PATTERN_OTP:
    for _otp_key in ('login', 'register', 'verify_phone'):
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
        'rest_framework_simplejwt.authentication.JWTAuthentication',
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
