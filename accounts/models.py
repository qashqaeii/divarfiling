"""
مدل‌های کاربری، OTP و لاگ پیامک
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """مدل کاربر سفارشی"""
    phone = models.CharField(max_length=20, unique=True, verbose_name='شماره موبایل')
    phone_verified = models.BooleanField(default=False, verbose_name='موبایل تأییدشده')
    phone_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تأیید موبایل',
    )
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت‌نام')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    is_affiliate = models.BooleanField(default=False, verbose_name='مشاور فروش')
    referred_by = models.ForeignKey(
        'affiliates.Affiliate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users',
        verbose_name='معرف',
    )

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'
        ordering = ['-date_joined']

    def __str__(self):
        return self.phone or self.username or self.email

    def mark_phone_verified(self):
        self.phone_verified = True
        self.phone_verified_at = timezone.now()
        self.save(update_fields=['phone_verified', 'phone_verified_at', 'updated_at'])


class UserProfile(models.Model):
    """پروفایل تکمیلی کاربر"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='کاربر',
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='تصویر پروفایل')
    bio = models.TextField(blank=True, verbose_name='درباره من')
    address = models.TextField(blank=True, verbose_name='آدرس')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='کد پستی')

    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل‌های کاربران'

    def __str__(self):
        return f'پروفایل {self.user.username}'


class OtpRequest(models.Model):
    """درخواست OTP — فقط هش کد ذخیره می‌شود."""

    class Purpose(models.TextChoices):
        LOGIN = 'login', 'ورود'
        REGISTER = 'register', 'ثبت‌نام'
        VERIFY_PHONE = 'verify_phone', 'تأیید موبایل'
        LICENSE_RENEWAL = 'license_renewal', 'تمدید لایسنس'
        SYSTEM = 'system', 'سیستمی'

    phone = models.CharField(max_length=20, db_index=True, verbose_name='شماره موبایل')
    purpose = models.CharField(
        max_length=32,
        choices=Purpose.choices,
        db_index=True,
        verbose_name='هدف',
    )
    code_hash = models.CharField(max_length=64, verbose_name='هش کد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    expires_at = models.DateTimeField(verbose_name='انقضا')
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name='تلاش‌ها')
    max_attempts = models.PositiveSmallIntegerField(default=5, verbose_name='سقف تلاش')
    is_consumed = models.BooleanField(default=False, db_index=True, verbose_name='مصرف‌شده')
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان مصرف')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')

    class Meta:
        verbose_name = 'درخواست OTP'
        verbose_name_plural = 'درخواست‌های OTP'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'purpose', '-created_at']),
        ]

    def __str__(self):
        return f'{self.phone} / {self.purpose} / {"مصرف" if self.is_consumed else "فعال"}'

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class SmsMessageLog(models.Model):
    """لاگ ارسال پیامک — بدون متن حساس و بدون کد OTP خام."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        SENT = 'sent', 'ارسال‌شده'
        FAKE = 'fake', 'جعلی/کنسول'
        FAILED = 'failed', 'ناموفق'

    class Channel(models.TextChoices):
        PATTERN = 'pattern', 'الگو'
        SIMPLE = 'simple', 'ساده'

    phone = models.CharField(max_length=20, db_index=True, verbose_name='گیرنده')
    purpose = models.CharField(max_length=32, blank=True, db_index=True, verbose_name='هدف')
    channel = models.CharField(
        max_length=16,
        choices=Channel.choices,
        default=Channel.PATTERN,
        verbose_name='کانال',
    )
    provider = models.CharField(max_length=32, blank=True, verbose_name='ارائه‌دهنده')
    pattern_code = models.CharField(max_length=64, blank=True, verbose_name='کد الگو')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='وضعیت',
    )
    provider_message_id = models.CharField(max_length=128, blank=True, verbose_name='شناسه پیامک')
    error_message = models.CharField(max_length=500, blank=True, verbose_name='پیام خطا')
    otp_request = models.ForeignKey(
        OtpRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs',
        verbose_name='درخواست OTP',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='به‌روزرسانی')

    class Meta:
        verbose_name = 'لاگ پیامک'
        verbose_name_plural = 'لاگ‌های پیامک'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone} [{self.status}]'

    def mark_sent(self, *, provider: str = '', message_id: str = '', status: str | None = None):
        self.provider = provider or self.provider
        self.provider_message_id = message_id or self.provider_message_id
        self.status = status or self.Status.SENT
        self.error_message = ''
        self.save(
            update_fields=[
                'provider',
                'provider_message_id',
                'status',
                'error_message',
                'updated_at',
            ]
        )

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.error_message = (error or '')[:500]
        self.save(update_fields=['status', 'error_message', 'updated_at'])
