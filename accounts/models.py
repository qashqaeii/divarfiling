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
    marketing_sms_opt_out = models.BooleanField(
        default=False,
        verbose_name='عدم دریافت پیامک بازاریابی',
    )
    marketing_sms_opt_out_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان Opt-out',
    )
    marketing_sms_opt_out_source = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='منبع Opt-out',
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


class MarketingCampaign(models.Model):
    """کمپین بازاریابی پیامکی — پنل ادمین."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'پیش‌نویس'
        SENDING = 'sending', 'در حال ارسال'
        COMPLETED = 'completed', 'تکمیل‌شده'
        FAILED = 'failed', 'ناموفق'

    class DiscountMode(models.TextChoices):
        NONE = 'none', 'بدون تخفیف'
        SHARED = 'shared', 'کد مشترک'
        UNIQUE = 'unique', 'کد یکتا برای هر کاربر'

    name = models.CharField(max_length=200, verbose_name='نام کمپین')
    segment_key = models.CharField(max_length=64, db_index=True, verbose_name='سگمنت')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name='وضعیت',
    )
    message_template = models.TextField(verbose_name='قالب پیام')
    discount_mode = models.CharField(
        max_length=16,
        choices=DiscountMode.choices,
        default=DiscountMode.NONE,
        verbose_name='حالت تخفیف',
    )
    shared_discount = models.ForeignKey(
        'shop.DiscountCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_campaigns',
        verbose_name='کد تخفیف مشترک',
    )
    stale_hours = models.PositiveIntegerField(null=True, blank=True, verbose_name='حداقل سن سفارش (ساعت)')
    days_lookback = models.PositiveIntegerField(null=True, blank=True, verbose_name='بازه روز')
    product_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='شناسه محصول')
    dedupe_days = models.PositiveIntegerField(default=7, verbose_name='فاصله عدم تکرار (روز)')
    discount_type = models.CharField(max_length=20, blank=True, verbose_name='نوع تخفیف')
    discount_value = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='مقدار تخفیف',
    )
    discount_valid_days = models.PositiveIntegerField(null=True, blank=True, verbose_name='اعتبار تخفیف (روز)')
    recipients_total = models.PositiveIntegerField(default=0, verbose_name='تعداد گیرندگان')
    sent_count = models.PositiveIntegerField(default=0, verbose_name='ارسال‌شده')
    failed_count = models.PositiveIntegerField(default=0, verbose_name='ناموفق')
    skipped_count = models.PositiveIntegerField(default=0, verbose_name='ردشده')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_campaigns',
        verbose_name='ایجادکننده',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='اتمام')

    class Meta:
        verbose_name = 'کمپین بازاریابی'
        verbose_name_plural = 'کمپین‌های بازاریابی'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} [{self.get_status_display()}]'


class MarketingCampaignRecipient(models.Model):
    """گیرنده یک کمپین بازاریابی."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        SENT = 'sent', 'ارسال‌شده'
        FAILED = 'failed', 'ناموفق'
        SKIPPED = 'skipped', 'ردشده'

    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name='کمپین',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_recipients',
        verbose_name='کاربر',
    )
    phone = models.CharField(max_length=20, db_index=True, verbose_name='موبایل')
    discount_code = models.ForeignKey(
        'shop.DiscountCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_recipients',
        verbose_name='کد تخفیف',
    )
    context_json = models.JSONField(default=dict, blank=True, verbose_name='زمینه پیام')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='وضعیت',
    )
    skip_reason = models.CharField(max_length=200, blank=True, verbose_name='دلیل رد')
    sms_log = models.ForeignKey(
        SmsMessageLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_recipients',
        verbose_name='لاگ پیامک',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='به‌روزرسانی')

    class Meta:
        verbose_name = 'گیرنده کمپین'
        verbose_name_plural = 'گیرندگان کمپین'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'phone'],
                name='uniq_marketing_campaign_phone',
            ),
        ]

    def __str__(self):
        return f'{self.phone} @ {self.campaign_id}'


class MarketingAutomationRun(models.Model):
    """اجرای Automation بازاریابی — فاز ۲.۱ فقط dry_run."""

    class Mode(models.TextChoices):
        DRY_RUN = 'dry_run', 'Dry Run'
        LIVE = 'live', 'Live'

    class Status(models.TextChoices):
        RUNNING = 'running', 'در حال اجرا'
        COMPLETED = 'completed', 'تکمیل‌شده'
        FAILED = 'failed', 'ناموفق'

    flow_key = models.CharField(max_length=64, db_index=True, verbose_name='کلید Flow')
    mode = models.CharField(
        max_length=16,
        choices=Mode.choices,
        default=Mode.DRY_RUN,
        verbose_name='حالت',
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='شروع')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='پایان')
    examined_count = models.PositiveIntegerField(default=0, verbose_name='بررسی‌شده')
    eligible_count = models.PositiveIntegerField(default=0, verbose_name='واجد شرایط')
    suppressed_count = models.PositiveIntegerField(default=0, verbose_name='حذف‌شده')
    would_send_count = models.PositiveIntegerField(default=0, verbose_name='would_send')
    error_count = models.PositiveIntegerField(default=0, verbose_name='خطا')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
        verbose_name='وضعیت',
    )
    config_snapshot = models.JSONField(default=dict, blank=True, verbose_name='تنظیمات')

    class Meta:
        verbose_name = 'اجرای Automation بازاریابی'
        verbose_name_plural = 'اجراهای Automation بازاریابی'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.flow_key} [{self.get_mode_display()}] @ {self.started_at:%Y-%m-%d %H:%M}'


class MarketingAutomationActionLog(models.Model):
    """لاگ اقدام Automation — would_send شبیه‌سازی؛ ارسال Live با state machine."""

    class Action(models.TextChoices):
        WOULD_SEND = 'would_send', 'Would Send'
        SEND_REQUESTED = 'send_requested', 'Send Requested'
        PROVIDER_ACCEPTED = 'provider_accepted', 'Provider Accepted'
        TEST_PROVIDER_ACCEPTED = 'test_provider_accepted', 'Test Provider Accepted'
        DELIVERED = 'delivered', 'Delivered'
        SENT = 'sent', 'Sent (legacy)'
        FAILED = 'failed', 'Failed'
        SUPPRESSED = 'suppressed', 'Suppressed'
        CANCELLED = 'cancelled', 'Cancelled'

    run = models.ForeignKey(
        MarketingAutomationRun,
        on_delete=models.CASCADE,
        related_name='actions',
        verbose_name='اجرای Run',
    )
    flow_key = models.CharField(max_length=64, db_index=True, verbose_name='کلید Flow')
    step_key = models.CharField(max_length=32, db_index=True, verbose_name='مرحله')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_automation_actions',
        verbose_name='کاربر',
    )
    phone_hash = models.CharField(max_length=64, db_index=True, verbose_name='هش شماره')
    masked_phone = models.CharField(max_length=20, blank=True, verbose_name='شماره Mask')
    order = models.ForeignKey(
        'shop.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_automation_actions',
        verbose_name='سفارش',
    )
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_automation_actions',
        verbose_name='محصول',
    )
    action = models.CharField(
        max_length=24,
        choices=Action.choices,
        default=Action.WOULD_SEND,
        db_index=True,
        verbose_name='اقدام',
    )
    reason = models.CharField(max_length=200, blank=True, verbose_name='دلیل')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    decision_key = models.CharField(
        max_length=220,
        unique=True,
        verbose_name='کلید تصمیم (شبیه‌سازی)',
    )
    send_idempotency_key = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        unique=True,
        verbose_name='کلید Idempotency ارسال واقعی',
    )
    sms_log = models.ForeignKey(
        'SmsMessageLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recovery_actions',
        verbose_name='لاگ پیامک',
    )
    provider_message_id = models.CharField(max_length=128, blank=True, verbose_name='شناسه Provider')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='به‌روزرسانی')

    class Meta:
        verbose_name = 'لاگ اقدام Automation'
        verbose_name_plural = 'لاگ‌های اقدام Automation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['flow_key', 'step_key', 'phone_hash']),
        ]

    def __str__(self):
        return f'{self.action} {self.step_key} @ {self.masked_phone}'
