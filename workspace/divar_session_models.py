"""مدل‌های نشست حساب دیوار — منبع مرکزی برای فایلینگ و Phone Detector."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class DivarContactFeatureConfig(models.Model):
    """تنظیمات انتشار قابلیت «دریافت شماره از دیوار» — singleton."""

    class RolloutMode(models.TextChoices):
        DISABLED = 'disabled', 'غیرفعال برای همه'
        ADMIN_ONLY = 'admin_only', 'فقط Superuser'
        ENABLED_FOR_ALL = 'enabled_for_all', 'فعال برای همه کاربران'

    singleton_key = models.CharField(max_length=16, unique=True, default='default')
    rollout_mode = models.CharField(
        max_length=32,
        choices=RolloutMode.choices,
        default=RolloutMode.ADMIN_ONLY,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        verbose_name = 'تنظیمات دریافت شماره از دیوار'
        verbose_name_plural = 'تنظیمات دریافت شماره از دیوار'

    def __str__(self):
        return self.get_rollout_mode_display()


class DivarContactFeatureAuditLog(models.Model):
    """تغییرات تنظیمات انتشار — بدون داده حساس."""

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    field_name = models.CharField(max_length=64)
    old_value = models.CharField(max_length=128, blank=True)
    new_value = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'لاگ تنظیمات دیوار'
        verbose_name_plural = 'لاگ تنظیمات دیوار'
        ordering = ['-created_at']


class DivarAccountSession(models.Model):
    """نشست احراز هویت دیوار متعلق به یک کاربر فایلینگ."""

    class AuthStatus(models.TextChoices):
        PENDING_OTP = 'pending_otp', 'در انتظار OTP'
        CONNECTED = 'connected', 'متصل'
        EXPIRED = 'expired', 'منقضی'
        CAPTCHA_REQUIRED = 'captcha_required', 'نیاز به کپچا'
        DISCONNECTED = 'disconnected', 'قطع شده'
        ERROR = 'error', 'خطا'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='divar_account_sessions',
    )
    divar_phone = models.CharField(max_length=20, db_index=True)
    encrypted_session = models.TextField(blank=True, help_text='SessionStore JSON — Fernet')
    auth_status = models.CharField(
        max_length=32,
        choices=AuthStatus.choices,
        default=AuthStatus.PENDING_OTP,
        db_index=True,
    )
    hip_status = models.CharField(max_length=64, blank=True, default='')
    captcha_post_url = models.URLField(max_length=500, blank=True, default='')
    connected_at = models.DateTimeField(null=True, blank=True)
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    last_refresh_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True, default='')
    last_error_message = models.CharField(max_length=500, blank=True, default='')
    phone_detector_consent = models.BooleanField(default=False, db_index=True)
    phone_detector_consent_at = models.DateTimeField(null=True, blank=True)
    phone_detector_consent_version = models.CharField(max_length=16, blank=True, default='')
    extraction_auto_opt_out = models.BooleanField(
        default=False,
        db_index=True,
        help_text='مدیر همگام‌سازی خودکار این نشست با خطوط استخراج را قطع کرده است',
    )
    operation_lock_until = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'نشست حساب دیوار'
        verbose_name_plural = 'نشست‌های حساب دیوار'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'divar_phone'],
                name='workspace_divar_session_user_phone_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'auth_status']),
        ]

    def __str__(self):
        return f'{self.divar_phone} ({self.user_id})'

    def mark_disconnected(self):
        self.auth_status = self.AuthStatus.DISCONNECTED
        self.encrypted_session = ''
        self.hip_status = ''
        self.operation_lock_until = None
        self.save(
            update_fields=[
                'auth_status',
                'encrypted_session',
                'hip_status',
                'operation_lock_until',
                'updated_at',
            ],
        )


class DivarPdSessionFileSyncBlock(models.Model):
    """جلوگیری از ایجاد/فعال‌سازی مجدد خط از فایل sessions پس از قطع ارتباط مرکزی."""

    class Reason(models.TextChoices):
        UNLINKED = 'unlinked', 'حذف ارتباط'
        DISCONNECTED = 'disconnected', 'قطع اتصال'
        INVALID = 'invalid', 'نشست نامعتبر'

    phone = models.CharField(max_length=20, unique=True, db_index=True)
    reason = models.CharField(max_length=32, choices=Reason.choices, default=Reason.UNLINKED)
    session = models.ForeignKey(
        'DivarAccountSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pd_sync_blocks',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مسدودیت sync فایل PD'
        verbose_name_plural = 'مسدودیت‌های sync فایل PD'


class DivarContactThrottle(models.Model):
    """Rate limit سراسری (DB) — مستقل از LocMemCache."""

    throttle_key = models.CharField(max_length=128, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = 'Throttle دیوار'
        verbose_name_plural = 'Throttleهای دیوار'


class DivarOtpChallenge(models.Model):
    """OTP ورود دیوار در حال تأیید — جدا از HIP و جدا برای هر کاربر."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='divar_otp_challenges',
    )
    divar_phone = models.CharField(max_length=20, db_index=True)
    encrypted_pending = models.TextField()
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'چالش OTP دیوار'
        verbose_name_plural = 'چالش‌های OTP دیوار'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'divar_phone'],
                name='workspace_divar_otp_user_phone_uniq',
            ),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class DivarPhoneFetchLog(models.Model):
    """آمار دریافت شماره — بدون ذخیره شماره خام در لاگ."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='divar_phone_fetch_logs',
    )
    listing_token = models.CharField(max_length=100, db_index=True)
    success = models.BooleanField(default=False, db_index=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'لاگ دریافت شماره دیوار'
        verbose_name_plural = 'لاگ‌های دریافت شماره دیوار'
        ordering = ['-created_at']
