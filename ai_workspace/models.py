"""مدل‌های AI — سهمیه، لاگ، کش."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from ai_workspace.constants import DEFAULT_DAILY_LIMIT, FEATURE_DAILY_LIMITS


class AIQuota(models.Model):
    """سهمیه روزانه AI هر کاربر."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_quota',
        verbose_name='کاربر',
    )
    daily_limit = models.PositiveSmallIntegerField(default=DEFAULT_DAILY_LIMIT, verbose_name='سقف روزانه')
    used_today = models.PositiveSmallIntegerField(default=0, verbose_name='مصرف امروز')
    tokens_used_today = models.PositiveIntegerField(default=0, verbose_name='توکن مصرفی امروز')
    reset_date = models.DateField(default=timezone.localdate, verbose_name='تاریخ ریست')
    listing_summary_used = models.PositiveSmallIntegerField(default=0, verbose_name='خلاصه آگهی')
    crm_message_used = models.PositiveSmallIntegerField(default=0, verbose_name='پیام CRM')
    upload_brief_used = models.PositiveSmallIntegerField(default=0, verbose_name='تحلیل آپلود')
    nl_command_used = models.PositiveSmallIntegerField(default=0, verbose_name='فرمان هوشمند')
    is_unlimited = models.BooleanField(default=False, verbose_name='نامحدود')

    class Meta:
        verbose_name = 'سهمیه AI'
        verbose_name_plural = 'سهمیه‌های AI'

    def __str__(self):
        return f'AIQuota({self.user_id}) {self.used_today}/{self.daily_limit}'

    def feature_field(self, feature_code: str) -> str:
        return f'{feature_code}_used'

    def feature_used(self, feature_code: str) -> int:
        return int(getattr(self, self.feature_field(feature_code), 0) or 0)

    def feature_limit(self, feature_code: str) -> int:
        return FEATURE_DAILY_LIMITS.get(feature_code, 0)


class AIUsageLog(models.Model):
    """لاگ هر درخواست AI."""

    STATUS_OK = 'ok'
    STATUS_FALLBACK = 'fallback'
    STATUS_QUOTA = 'quota_exceeded'
    STATUS_ERROR = 'error'
    STATUS_CACHED = 'cached'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_usage_logs',
        verbose_name='کاربر',
    )
    feature_code = models.CharField(max_length=40, verbose_name='قابلیت')
    provider = models.CharField(max_length=30, verbose_name='Provider')
    model = models.CharField(max_length=120, blank=True, verbose_name='مدل')
    input_tokens = models.PositiveIntegerField(null=True, blank=True, verbose_name='توکن ورودی')
    output_tokens = models.PositiveIntegerField(null=True, blank=True, verbose_name='توکن خروجی')
    total_tokens = models.PositiveIntegerField(null=True, blank=True, verbose_name='مجموع توکن')
    provider_attempt = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='تلاش provider',
        help_text='0=کش/validation، 1=Primary، 2=Lite، 3=OpenRouter، 4=Rule',
    )
    latency_ms = models.PositiveIntegerField(default=0, verbose_name='زمان (ms)')
    cache_hit = models.BooleanField(default=False, verbose_name='کش')
    status = models.CharField(max_length=20, verbose_name='وضعیت')
    error_code = models.CharField(max_length=80, blank=True, verbose_name='کد خطا')
    entity_type = models.CharField(max_length=30, blank=True, verbose_name='نوع موجودیت')
    entity_id = models.CharField(max_length=120, blank=True, verbose_name='شناسه موجودیت')
    prompt_hash = models.CharField(max_length=64, blank=True, verbose_name='هش prompt')
    prompt_version = models.CharField(max_length=20, blank=True, verbose_name='نسخه prompt')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان')

    class Meta:
        verbose_name = 'لاگ AI'
        verbose_name_plural = 'لاگ‌های AI'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['feature_code', 'created_at']),
        ]

    def __str__(self):
        return f'{self.feature_code} — {self.provider} ({self.status})'


class AICache(models.Model):
    """کش نتیجه AI."""

    cache_key = models.CharField(max_length=64, unique=True, verbose_name='کلید')
    feature_code = models.CharField(max_length=40, verbose_name='قابلیت')
    result_text = models.TextField(verbose_name='نتیجه')
    result_json = models.JSONField(default=dict, blank=True, verbose_name='JSON')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='انقضا')

    class Meta:
        verbose_name = 'کش AI'
        verbose_name_plural = 'کش‌های AI'
        indexes = [models.Index(fields=['expires_at'])]

    def __str__(self):
        return self.cache_key[:16]
