"""
مدل‌های کاربری، OTP و لاگ پیامک
"""
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def _generate_click_token() -> str:
    return secrets.token_urlsafe(12)


def _generate_lead_token() -> str:
    return secrets.token_urlsafe(10)


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


class RecoveryAttribution(models.Model):
    """سابقه نسبت‌دهی بازیابی — immutable پس از matched/no_match."""

    class AttributionModel(models.TextChoices):
        STRICT = 'strict', 'Strict'
        ASSISTED = 'assisted', 'Assisted'

    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        MATCHED = 'matched', 'منطبق'
        NO_MATCH = 'no_match', 'بدون انطباق'

    action_log = models.OneToOneField(
        MarketingAutomationActionLog,
        on_delete=models.CASCADE,
        related_name='recovery_attribution',
        verbose_name='لاگ اقدام',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recovery_attributions',
        verbose_name='کاربر',
    )
    abandon_order = models.ForeignKey(
        'shop.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recovery_attributions_as_abandon',
        verbose_name='سفارش رها شده',
    )
    attribution_model = models.CharField(
        max_length=16,
        choices=AttributionModel.choices,
        blank=True,
        verbose_name='مدل نسبت‌دهی',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='وضعیت',
    )
    paid_order = models.ForeignKey(
        'shop.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recovery_attributions_as_paid',
        verbose_name='سفارش پرداخت‌شده',
    )
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان پرداخت')
    lag_hours = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name='فاصله تا پرداخت (ساعت)',
    )
    revenue_amount = models.PositiveIntegerField(null=True, blank=True, verbose_name='درآمد (تومان)')
    matched_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='زمان انطباق')
    rule_version = models.CharField(max_length=32, default='strict_v1', verbose_name='نسخه قانون')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='به‌روزرسانی')

    class Meta:
        verbose_name = 'نسبت‌دهی بازیابی'
        verbose_name_plural = 'نسبت‌دهی‌های بازیابی'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'attribution_model'], name='accounts_re_status_8d4f2a_idx'),
            models.Index(fields=['user', 'status'], name='accounts_re_user_id_5c91bb_idx'),
            models.Index(fields=['abandon_order', 'status'], name='accounts_re_abandon_2e8c11_idx'),
        ]

    def __str__(self):
        return f'{self.get_status_display()} — log#{self.action_log_id}'


# ─── Lead Acquisition Center ───────────────────────────────────────────────


class LeadImportBatch(models.Model):
    """بچ آپلود سرنخ (مثلاً خروجی phone-detector)."""

    class Status(models.TextChoices):
        PREVIEW = 'preview', 'پیش‌نمایش'
        COMMITTED = 'committed', 'ثبت‌شده'
        REJECTED = 'rejected', 'ردشده'

    source = models.CharField(max_length=64, default='phone_detector', db_index=True)
    original_filename = models.CharField(max_length=255, blank=True)
    file_hash = models.CharField(max_length=64, unique=True, db_index=True)
    city = models.CharField(max_length=100, blank=True)
    city_id = models.CharField(max_length=32, blank=True)
    district = models.CharField(max_length=100, blank=True)
    district_id = models.CharField(max_length=32, blank=True)
    listing_category = models.CharField(max_length=64, blank=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    preview_stats = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PREVIEW,
        db_index=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_import_batches',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'بچ ایمپورت سرنخ'
        verbose_name_plural = 'بچ‌های ایمپورت سرنخ'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.original_filename or self.file_hash[:12]} [{self.status}]'


class MarketingLead(models.Model):
    """سرنخ یکتای سیستم جذب — جدا از CRM مشاوران."""

    class LeadType(models.TextChoices):
        AGENCY = 'agency', 'آژانس'
        CONSULTANT = 'consultant', 'مشاور'
        UNKNOWN = 'unknown', 'نامشخص'

    class Status(models.TextChoices):
        COLD = 'cold', 'سرد'
        ENGAGED = 'engaged', 'تعامل‌دار'
        EXISTING_USER = 'existing_user', 'کاربر موجود'
        REGISTERED = 'registered', 'ثبت‌نام‌شده'
        CUSTOMER = 'customer', 'مشتری'
        SUPPRESSED = 'suppressed', 'مسدود'

    phone_normalized = models.CharField(max_length=20, unique=True, db_index=True)
    public_token = models.CharField(
        max_length=32,
        unique=True,
        default=_generate_lead_token,
        editable=False,
        help_text='شناسه داخلی ادمین — در لینک پیامک استفاده نشود',
    )
    display_name = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=64, default='phone_detector', db_index=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    listing_category = models.CharField(max_length=64, blank=True)
    lead_type = models.CharField(
        max_length=16,
        choices=LeadType.choices,
        default=LeadType.UNKNOWN,
        db_index=True,
    )
    classification_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COLD,
        db_index=True,
    )
    sighting_count = models.PositiveIntegerField(default=1)
    districts_json = models.JSONField(default=list, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    matched_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_leads',
    )
    first_batch = models.ForeignKey(
        LeadImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='first_leads',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سرنخ بازاریابی'
        verbose_name_plural = 'سرنخ‌های بازاریابی'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.phone_normalized} ({self.display_name or "—"})'


class LeadList(models.Model):
    """لیست/دسته قابل استفاده در کمپین."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    source = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    listing_category = models.CharField(max_length=64, blank=True)
    tags = models.JSONField(default=list, blank=True)
    batch = models.ForeignKey(
        LeadImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lists',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'لیست سرنخ'
        verbose_name_plural = 'لیست‌های سرنخ'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class LeadListMember(models.Model):
    lead_list = models.ForeignKey(LeadList, on_delete=models.CASCADE, related_name='members')
    lead = models.ForeignKey(MarketingLead, on_delete=models.CASCADE, related_name='list_memberships')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'عضو لیست سرنخ'
        verbose_name_plural = 'اعضای لیست سرنخ'
        constraints = [
            models.UniqueConstraint(fields=['lead_list', 'lead'], name='uniq_lead_list_member'),
        ]

    def __str__(self):
        return f'{self.lead_id} ∈ {self.lead_list_id}'


class SuppressionEntry(models.Model):
    """مسدودسازی دائمی ارسال — فقط لغو/شکایت/نامعتبر/fail مکرر."""

    class Reason(models.TextChoices):
        OPT_OUT = 'opt_out', 'لغو دریافت'
        COMPLAINT = 'complaint', 'شکایت'
        INVALID = 'invalid', 'شماره نامعتبر'
        HARD_FAIL = 'hard_fail', 'شکست مکرر ارسال'
        MANUAL = 'manual', 'دستی'

    phone_normalized = models.CharField(max_length=20, unique=True, db_index=True)
    reason = models.CharField(max_length=32, choices=Reason.choices, db_index=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suppression_entries',
    )

    class Meta:
        verbose_name = 'ورودی Suppression'
        verbose_name_plural = 'Suppression'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone_normalized} [{self.reason}]'


class LeadCampaign(models.Model):
    """کمپین جذب سرنخ یا فعال‌سازی کاربر."""

    class Kind(models.TextChoices):
        ACQUISITION = 'acquisition', 'جذب سرنخ'
        ACTIVATION = 'activation', 'فعال‌سازی / تبدیل خرید'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'پیش‌نویس'
        PILOT = 'pilot', 'پایلوت'
        ACTIVE = 'active', 'فعال'
        PAUSED = 'paused', 'متوقف'
        COMPLETED = 'completed', 'تکمیل‌شده'
        ARCHIVED = 'archived', 'بایگانی'

    name = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.ACQUISITION,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    lead_list = models.ForeignKey(
        LeadList,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
    )
    landing_url = models.URLField(
        max_length=500,
        default='https://divarfiling.ir/',
        help_text='مقصد بعد از کلیک روی لینک ردیابی',
    )
    is_pilot = models.BooleanField(default=False)
    pilot_per_variant = models.PositiveIntegerField(default=15)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_campaigns',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'کمپین سرنخ'
        verbose_name_plural = 'کمپین‌های سرنخ'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} [{self.get_kind_display()}]'


class CampaignVariant(models.Model):
    campaign = models.ForeignKey(LeadCampaign, on_delete=models.CASCADE, related_name='variants')
    key = models.CharField(max_length=8, db_index=True)  # A / B
    name = models.CharField(max_length=100, blank=True)
    weight = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'نسخه A/B'
        verbose_name_plural = 'نسخه‌های A/B'
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'key'], name='uniq_campaign_variant_key'),
        ]

    def __str__(self):
        return f'{self.campaign_id}:{self.key}'


class CampaignStep(models.Model):
    class Audience(models.TextChoices):
        ALL_ELIGIBLE = 'all_eligible', 'همه واجد شرایط'
        NOT_REGISTERED = 'not_registered', 'ثبت‌نام‌نشده (یادآوری)'
        ENGAGED_NOT_REGISTERED = 'engaged_not_registered', 'کلیک/لندینگ و ثبت‌نام‌نشده'

    campaign = models.ForeignKey(LeadCampaign, on_delete=models.CASCADE, related_name='steps')
    step_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100, blank=True)
    delay_days = models.PositiveSmallIntegerField(default=0)
    audience = models.CharField(
        max_length=32,
        choices=Audience.choices,
        default=Audience.ALL_ELIGIBLE,
    )
    message_template = models.TextField(
        help_text='از {link} برای لینک ردیابی استفاده کنید',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'مرحله کمپین'
        verbose_name_plural = 'مراحل کمپین'
        ordering = ['campaign_id', 'step_number']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'step_number'],
                name='uniq_campaign_step_number',
            ),
        ]

    def __str__(self):
        return f'{self.campaign_id} step {self.step_number}'


class CampaignEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'فعال'
        EXITED_REGISTERED = 'exited_registered', 'خروج به‌خاطر ثبت‌نام'
        EXITED_PURCHASED = 'exited_purchased', 'خروج به‌خاطر خرید'
        EXITED_OPT_OUT = 'exited_opt_out', 'خروج به‌خاطر لغو'
        EXITED_SUPPRESSED = 'exited_suppressed', 'خروج به‌خاطر suppression'
        COMPLETED = 'completed', 'تکمیل توالی'
        HOLD = 'hold', 'نگه‌داشته'

    campaign = models.ForeignKey(LeadCampaign, on_delete=models.CASCADE, related_name='enrollments')
    lead = models.ForeignKey(MarketingLead, on_delete=models.CASCADE, related_name='enrollments')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_campaign_enrollments',
    )
    assigned_variant = models.ForeignKey(
        CampaignVariant,
        on_delete=models.PROTECT,
        related_name='enrollments',
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    current_step_number = models.PositiveSmallIntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    exited_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'ثبت‌نام در کمپین'
        verbose_name_plural = 'ثبت‌نام‌های کمپین'
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'lead'],
                name='uniq_campaign_lead_enrollment',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'campaign']),
        ]

    def __str__(self):
        return f'enroll {self.lead_id} → {self.campaign_id}'


class CampaignMessage(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'درخواست‌شده'
        PROVIDER_ACCEPTED = 'provider_accepted', 'پذیرفته Provider'
        DELIVERED = 'delivered', 'تحویل‌شده'
        FAILED = 'failed', 'ناموفق'
        SKIPPED = 'skipped', 'ردشده'

    enrollment = models.ForeignKey(
        CampaignEnrollment,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    campaign = models.ForeignKey(LeadCampaign, on_delete=models.CASCADE, related_name='messages')
    variant = models.ForeignKey(CampaignVariant, on_delete=models.PROTECT, related_name='messages')
    step = models.ForeignKey(CampaignStep, on_delete=models.PROTECT, related_name='messages')
    lead = models.ForeignKey(MarketingLead, on_delete=models.CASCADE, related_name='messages')
    click_token = models.CharField(
        max_length=48,
        unique=True,
        default=_generate_click_token,
        db_index=True,
        editable=False,
    )
    idempotency_key = models.CharField(max_length=220, unique=True)
    body_rendered = models.TextField(blank=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.REQUESTED,
        db_index=True,
    )
    skip_reason = models.CharField(max_length=200, blank=True)
    sms_log = models.ForeignKey(
        SmsMessageLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_campaign_messages',
    )
    sms_cost_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='هزینه پیامک به‌ریال در لحظه ارسال (بر اساس تعداد بخش × تعرفه)',
    )
    provider_message_id = models.CharField(max_length=128, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'پیام کمپین سرنخ'
        verbose_name_plural = 'پیام‌های کمپین سرنخ'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['lead', 'status']),
        ]

    def __str__(self):
        return f'msg#{self.pk} {self.click_token[:8]}'


class LeadTouchpoint(models.Model):
    class EventType(models.TextChoices):
        CLICK = 'click', 'کلیک'
        LANDING_VIEW = 'landing_view', 'مشاهده لندینگ'
        SIGNUP_START = 'signup_start', 'شروع ثبت‌نام'
        SIGNUP_COMPLETE = 'signup_complete', 'تکمیل ثبت‌نام'
        WORKSPACE_LOGIN = 'workspace_login', 'ورود میزکار'
        CHECKOUT_START = 'checkout_start', 'شروع خرید'
        PAID = 'paid', 'پرداخت'
        LICENSED = 'licensed', 'فعال‌سازی لایسنس'

    lead = models.ForeignKey(MarketingLead, on_delete=models.CASCADE, related_name='touchpoints')
    message = models.ForeignKey(
        CampaignMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='touchpoints',
    )
    campaign = models.ForeignKey(
        LeadCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='touchpoints',
    )
    variant = models.ForeignKey(
        CampaignVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='touchpoints',
    )
    step = models.ForeignKey(
        CampaignStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='touchpoints',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_touchpoints',
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'نقطه تماس سرنخ'
        verbose_name_plural = 'نقاط تماس سرنخ'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['lead', 'event_type', '-created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} lead#{self.lead_id}'


class LeadAttribution(models.Model):
    """نسبت‌دهی موازی: acquisition (ثبت‌نام) و conversion (خرید)."""

    class Axis(models.TextChoices):
        ACQUISITION = 'acquisition', 'جذب'
        CONVERSION = 'conversion', 'تبدیل خرید'

    class Kind(models.TextChoices):
        DIRECT = 'direct', 'مستقیم'
        MATCHED = 'matched', 'تطبیق شماره'

    class TouchModel(models.TextChoices):
        FIRST = 'first', 'First-touch'
        LAST = 'last', 'Last-touch'

    axis = models.CharField(max_length=16, choices=Axis.choices, db_index=True)
    attribution_kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    touch_model = models.CharField(max_length=8, choices=TouchModel.choices, db_index=True)
    lead = models.ForeignKey(MarketingLead, on_delete=models.CASCADE, related_name='attributions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_attributions',
    )
    campaign = models.ForeignKey(
        LeadCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attributions',
    )
    message = models.ForeignKey(
        CampaignMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attributions',
    )
    variant = models.ForeignKey(
        CampaignVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attributions',
    )
    step = models.ForeignKey(
        CampaignStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attributions',
    )
    order = models.ForeignKey(
        'shop.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_attributions',
    )
    revenue_amount = models.PositiveIntegerField(null=True, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نسبت‌دهی سرنخ'
        verbose_name_plural = 'نسبت‌دهی‌های سرنخ'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['axis', 'attribution_kind', 'touch_model']),
            models.Index(fields=['lead', 'axis']),
            models.Index(fields=['user', 'axis']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['lead', 'user', 'axis', 'touch_model'],
                name='uniq_lead_user_axis_touch',
            ),
        ]

    def __str__(self):
        return f'{self.axis}/{self.attribution_kind}/{self.touch_model} lead#{self.lead_id}'


# ─── Unified Growth Pipeline ───────────────────────────────────────────────


class GrowthJourney(models.Model):
    """وضعیت یکپارچه قیف رشد — پل بین جذب سرنخ و اتوماسیون بازاریابی."""

    class Stage(models.TextChoices):
        COLD_LEAD = 'cold_lead', 'سرنخ سرد'
        ENGAGED = 'engaged', 'تعامل‌دار'
        REGISTERED = 'registered', 'ثبت‌نام‌شده'
        ACTIVATED = 'activated', 'فعال‌شده'
        NURTURE_UNPAID = 'nurture_unpaid', 'پیگیری بدون خرید'
        PENDING_CHECKOUT = 'pending_checkout', 'خرید معلق'
        CUSTOMER = 'customer', 'مشتری'
        EXPIRING_SOON = 'expiring_soon', 'نزدیک انقضا'
        RENEWED = 'renewed', 'تمدیدشده'
        CHURN_RISK = 'churn_risk', 'ریسک ریزش'
        SUPPRESSED = 'suppressed', 'مسدود'

    class Source(models.TextChoices):
        ACQUISITION = 'acquisition', 'جذب سرنخ'
        ORGANIC = 'organic', 'ارگانیک'
        EXISTING_USER = 'existing_user', 'کاربر موجود'

    phone_normalized = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='growth_journeys',
    )
    lead = models.ForeignKey(
        MarketingLead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='growth_journeys',
    )
    stage = models.CharField(
        max_length=24,
        choices=Stage.choices,
        default=Stage.COLD_LEAD,
        db_index=True,
    )
    stage_entered_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.ACQUISITION,
        db_index=True,
    )
    last_touch_at = models.DateTimeField(null=True, blank=True)
    suppressed = models.BooleanField(default=False, db_index=True)
    nurture_paused = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سفر رشد'
        verbose_name_plural = 'سفرهای رشد'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['stage', '-stage_entered_at']),
            models.Index(fields=['suppressed', 'nurture_paused', 'stage']),
        ]

    def __str__(self):
        return f'{self.phone_normalized} [{self.stage}]'


class GrowthJourneyEvent(models.Model):
    """رویداد append-only تغییر مرحله در پایپلاین رشد."""

    journey = models.ForeignKey(
        GrowthJourney,
        on_delete=models.CASCADE,
        related_name='events',
    )
    stage_from = models.CharField(max_length=24, blank=True)
    stage_to = models.CharField(max_length=24, db_index=True)
    event_type = models.CharField(max_length=48, db_index=True)
    ref_model = models.CharField(max_length=64, blank=True)
    ref_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'رویداد سفر رشد'
        verbose_name_plural = 'رویدادهای سفر رشد'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['journey', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def __str__(self):
        return f'{self.event_type}: {self.stage_from or "—"} → {self.stage_to}'
