"""مدل‌های دامنه قرارداد دیجیتال."""
from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from contracts.constants import (
    ATTACHMENT_TYPES,
    CLAUSE_REVIEW_STATUSES,
    CONTRACT_STATUSES,
    CONTRACT_TYPES,
    HANDOVER_STATUSES,
    HANDOVER_TYPES,
    IDENTITY_STATUS_CLAIMED,
    IDENTITY_STATUS_MOBILE_VERIFIED,
    IDENTITY_STATUS_UNVERIFIED,
    IDENTITY_STATUS_VERIFIED,
    PERSON_TYPES,
    SIGNATURE_TYPES,
    SMS_STATUS_QUEUED,
)


def _gen_token() -> str:
    return secrets.token_urlsafe(32)


def _gen_public_token() -> str:
    return secrets.token_urlsafe(24)


def contract_attachment_path(instance, filename: str) -> str:
    return f'contracts/{instance.contract_id}/{uuid.uuid4().hex}_{filename}'


class ContractLegalSource(models.Model):
    """منبع حقوقی (قانون، ماده، اصلاحیه)."""
    code = models.CharField(max_length=64, unique=True, verbose_name='کد')
    title = models.CharField(max_length=300, verbose_name='عنوان')
    article = models.CharField(max_length=120, blank=True, verbose_name='ماده/بند')
    reference = models.CharField(max_length=300, blank=True, verbose_name='ارجاع')
    effective_from = models.DateField(null=True, blank=True, verbose_name='اعتبار از')
    effective_to = models.DateField(null=True, blank=True, verbose_name='اعتبار تا')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'منبع حقوقی'
        verbose_name_plural = 'منابع حقوقی'
        ordering = ['title']

    def __str__(self):
        return self.title


class ContractClauseDefinition(models.Model):
    """کتابخانه بندهای قرارداد — نسخه‌دار و قابل بررسی حقوقی."""
    code = models.CharField(max_length=80, db_index=True, verbose_name='کد')
    title = models.CharField(max_length=300, verbose_name='عنوان')
    category = models.CharField(max_length=120, db_index=True, verbose_name='دسته')
    contract_type = models.CharField(
        max_length=12, choices=CONTRACT_TYPES, db_index=True, verbose_name='نوع قرارداد',
    )
    body_template = models.TextField(verbose_name='متن الگو')
    plain_explanation = models.TextField(blank=True, verbose_name='توضیح ساده')
    is_required = models.BooleanField(default=False, verbose_name='الزامی')
    is_recommended = models.BooleanField(default=False, verbose_name='پیشنهادی')
    is_optional = models.BooleanField(default=True, verbose_name='اختیاری')
    condition_expression = models.JSONField(
        default=dict, blank=True, verbose_name='شرط نمایش',
    )
    legal_source = models.ForeignKey(
        ContractLegalSource, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='clauses', verbose_name='منبع حقوقی',
    )
    legal_reference = models.CharField(max_length=300, blank=True, verbose_name='ارجاع حقوقی')
    legal_note = models.TextField(blank=True, verbose_name='یادداشت حقوقی')
    effective_from = models.DateField(null=True, blank=True, verbose_name='اعتبار از')
    effective_to = models.DateField(null=True, blank=True, verbose_name='اعتبار تا')
    version = models.PositiveIntegerField(default=1, verbose_name='نسخه بند')
    review_status = models.CharField(
        max_length=20, choices=CLAUSE_REVIEW_STATUSES,
        default='review_pending', verbose_name='وضعیت بررسی',
    )
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    inline_fields = models.JSONField(default=list, blank=True, verbose_name='فیلدهای inline')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تعریف بند قرارداد'
        verbose_name_plural = 'تعاریف بندهای قرارداد'
        ordering = ['contract_type', 'category', 'code']
        indexes = [
            models.Index(fields=['contract_type', 'category', 'is_active']),
            models.Index(fields=['code', 'version']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'version'], name='contracts_clause_code_version_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.code} v{self.version} — {self.title}'


class ContractLegalRule(models.Model):
    """قواعد حقوقی قابل پیکربندی و تاریخ‌دار."""
    code = models.CharField(max_length=80, unique=True, verbose_name='کد')
    name = models.CharField(max_length=200, verbose_name='نام')
    contract_type = models.CharField(
        max_length=12, choices=CONTRACT_TYPES, blank=True, verbose_name='نوع قرارداد',
    )
    rule_type = models.CharField(max_length=40, verbose_name='نوع قاعده')
    rule_payload = models.JSONField(default=dict, blank=True, verbose_name='محتوای قاعده')
    effective_from = models.DateField(null=True, blank=True, verbose_name='اعتبار از')
    effective_to = models.DateField(null=True, blank=True, verbose_name='اعتبار تا')
    source_title = models.CharField(max_length=300, blank=True, verbose_name='منبع')
    source_article = models.CharField(max_length=120, blank=True, verbose_name='ماده')
    source_reference = models.CharField(max_length=300, blank=True, verbose_name='ارجاع')
    status = models.CharField(max_length=20, default='active', verbose_name='وضعیت')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان بررسی')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_legal_rules', verbose_name='بررسی‌کننده',
    )
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    warning_level = models.CharField(max_length=12, default='info', verbose_name='سطح هشدار')
    warning_message = models.TextField(blank=True, verbose_name='پیام هشدار')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قاعده حقوقی'
        verbose_name_plural = 'قواعد حقوقی'
        ordering = ['code']

    def __str__(self):
        return self.name


class Contract(models.Model):
    """قرارداد دیجیتال متصل به معامله CRM."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='contracts', verbose_name='ایجادکننده',
    )
    agency = models.ForeignKey(
        'workspace.CRMAgency', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contracts', verbose_name='آژانس',
    )
    deal = models.ForeignKey(
        'workspace.CRMDeal', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='digital_contracts', verbose_name='معامله',
    )
    contract_type = models.CharField(max_length=12, choices=CONTRACT_TYPES, verbose_name='نوع')
    internal_number = models.CharField(
        max_length=40, unique=True, db_index=True, verbose_name='شناسه داخلی',
    )
    title = models.CharField(max_length=300, blank=True, verbose_name='عنوان')
    status = models.CharField(
        max_length=24, choices=CONTRACT_STATUSES,
        default='draft', db_index=True, verbose_name='وضعیت',
    )
    current_version = models.ForeignKey(
        'ContractVersion', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='نسخه جاری',
    )
    verification_token_hash = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name='هش توکن تأیید عمومی',
    )
    cancel_reason = models.TextField(blank=True, verbose_name='دلیل لغو')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان لغو')
    finalized_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان نهایی‌سازی')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='انقضا')
    copied_from = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='copies', verbose_name='کپی از',
    )
    wizard_step = models.CharField(max_length=20, default='type', verbose_name='مرحله ویزارد')
    wizard_data = models.JSONField(default=dict, blank=True, verbose_name='داده ویزارد')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قرارداد'
        verbose_name_plural = 'قراردادها'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['deal', '-updated_at']),
            models.Index(fields=['agency', 'status']),
        ]

    def __str__(self):
        return f'{self.internal_number} — {self.get_contract_type_display()}'

    @property
    def is_editable(self) -> bool:
        if self.status in ('finalized', 'cancelled', 'superseded'):
            return False
        if self.current_version_id and self.current_version.has_acceptances:
            return False
        return True


class ContractVersion(models.Model):
    """نسخه قرارداد — پس از ارسال immutable."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='versions', verbose_name='قرارداد',
    )
    version_number = models.PositiveIntegerField(verbose_name='شماره نسخه')
    is_published = models.BooleanField(default=False, verbose_name='منتشرشده')
    is_locked = models.BooleanField(default=False, verbose_name='قفل‌شده')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان انتشار')
    content_hash = models.CharField(max_length=64, blank=True, verbose_name='هش محتوا')
    snapshot_json = models.JSONField(default=dict, blank=True, verbose_name='اسنپ‌شات')
    financial_data = models.JSONField(default=dict, blank=True, verbose_name='داده مالی')
    jv_data = models.JSONField(default=dict, blank=True, verbose_name='داده مشارکت')
    disclaimer_acknowledged_at = models.DateTimeField(
        null=True, blank=True, verbose_name='تأیید disclaimer',
    )
    creator_acknowledged_at = models.DateTimeField(
        null=True, blank=True, verbose_name='تأیید مسئولیت سازنده',
    )
    pdf_file = models.FileField(
        upload_to='contracts/pdf/', blank=True, null=True, verbose_name='فایل PDF',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_versions', verbose_name='ایجادکننده',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نسخه قرارداد'
        verbose_name_plural = 'نسخه‌های قرارداد'
        ordering = ['contract', '-version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['contract', 'version_number'],
                name='contracts_version_number_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.contract.internal_number} v{self.version_number}'

    @property
    def has_acceptances(self) -> bool:
        return self.acceptances.exists()

    @property
    def is_locked_version(self) -> bool:
        """پس از publish یا اولین acceptance — ویرایش مستقیم ممنوع."""
        return self.is_locked or self.is_published or self.has_acceptances

    @property
    def is_immutable(self) -> bool:
        return self.is_locked_version


class ContractParty(models.Model):
    """طرف قرارداد."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='parties', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        related_name='parties', verbose_name='نسخه',
    )
    customer = models.ForeignKey(
        'workspace.Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_parties', verbose_name='مخاطب CRM',
    )
    role = models.CharField(max_length=20, verbose_name='نقش')
    person_type = models.CharField(
        max_length=10, choices=PERSON_TYPES, default='natural', verbose_name='نوع شخص',
    )
    first_name = models.CharField(max_length=100, blank=True, verbose_name='نام')
    last_name = models.CharField(max_length=100, blank=True, verbose_name='نام خانوادگی')
    father_name = models.CharField(max_length=100, blank=True, verbose_name='نام پدر')
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    birth_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تولد')
    mobile = models.CharField(max_length=20, blank=True, verbose_name='موبایل')
    address = models.TextField(blank=True, verbose_name='نشانی')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='کد پستی')
    position_title = models.CharField(max_length=120, blank=True, verbose_name='سمت')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='نام شرکت')
    company_national_id = models.CharField(max_length=20, blank=True, verbose_name='شناسه ملی')
    company_registration_no = models.CharField(max_length=50, blank=True, verbose_name='شماره ثبت')
    representative_name = models.CharField(max_length=200, blank=True, verbose_name='نماینده')
    representative_national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی نماینده')
    representative_mobile = models.CharField(max_length=20, blank=True, verbose_name='موبایل نماینده')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب')
    ownership_share = models.CharField(max_length=40, blank=True, verbose_name='قدرالسهم')
    identity_verification_method = models.CharField(max_length=40, blank=True, verbose_name='روش احراز')
    identity_verification_status = models.CharField(
        max_length=24, default=IDENTITY_STATUS_UNVERIFIED, verbose_name='وضعیت احراز',
    )
    identity_verification_provider = models.CharField(max_length=60, blank=True, verbose_name='ارائه‌دهنده احراز')
    mobile_verified = models.BooleanField(default=False, verbose_name='موبایل تأییدشده')
    national_id_claimed = models.BooleanField(default=False, verbose_name='کد ملی اظهارشده')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'طرف قرارداد'
        verbose_name_plural = 'طرفین قرارداد'
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return f'{self.role}: {self.first_name} {self.last_name}'.strip()

    @property
    def display_name(self) -> str:
        if self.person_type == 'legal' and self.company_name:
            return self.company_name
        return f'{self.first_name} {self.last_name}'.strip()


class ContractPropertySnapshot(models.Model):
    """اسنپ‌شات اطلاعات ملک در نسخه قرارداد."""
    version = models.OneToOneField(
        ContractVersion, on_delete=models.CASCADE,
        related_name='property_snapshot', verbose_name='نسخه',
    )
    data = models.JSONField(default=dict, verbose_name='داده ملک')
    declared_by_parties = models.BooleanField(
        default=True, verbose_name='بر اساس اظهار طرفین',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اسنپ‌شات ملک'
        verbose_name_plural = 'اسنپ‌شات‌های ملک'


class ContractClause(models.Model):
    """بند انتخاب‌شده در نسخه — با اسنپ‌شات متن."""
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        related_name='clauses', verbose_name='نسخه',
    )
    definition = models.ForeignKey(
        ContractClauseDefinition, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='usages', verbose_name='تعریف بند',
    )
    code = models.CharField(max_length=80, blank=True, verbose_name='کد')
    title = models.CharField(max_length=300, verbose_name='عنوان')
    category = models.CharField(max_length=120, blank=True, verbose_name='دسته')
    body_text = models.TextField(verbose_name='متن بند')
    plain_explanation = models.TextField(blank=True, verbose_name='توضیح ساده')
    is_custom = models.BooleanField(default=False, verbose_name='شرط اختصاصی')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    inline_values = models.JSONField(default=dict, blank=True, verbose_name='مقادیر inline')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')
    definition_version = models.PositiveIntegerField(default=1, verbose_name='نسخه تعریف')

    class Meta:
        verbose_name = 'بند قرارداد'
        verbose_name_plural = 'بندهای قرارداد'
        ordering = ['sort_order', 'pk']


class ContractPaymentSchedule(models.Model):
    """برنامه پرداخت (فروش و ...)."""
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        related_name='payment_schedules', verbose_name='نسخه',
    )
    title = models.CharField(max_length=200, blank=True, verbose_name='عنوان')
    total_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مجموع')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'برنامه پرداخت'
        verbose_name_plural = 'برنامه‌های پرداخت'


class ContractPayment(models.Model):
    """قسط/پرداخت."""
    schedule = models.ForeignKey(
        ContractPaymentSchedule, on_delete=models.CASCADE,
        related_name='payments', verbose_name='برنامه',
    )
    label = models.CharField(max_length=120, verbose_name='عنوان')
    amount = models.BigIntegerField(verbose_name='مبلغ')
    due_date = models.DateField(null=True, blank=True, verbose_name='سررسید')
    payment_method = models.CharField(max_length=40, blank=True, verbose_name='روش پرداخت')
    notes = models.TextField(blank=True, verbose_name='توضیحات')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب')

    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['sort_order', 'pk']


class ContractWitness(models.Model):
    """شاهد قرارداد."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='witnesses', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        related_name='witnesses', verbose_name='نسخه',
    )
    witness_number = models.PositiveSmallIntegerField(verbose_name='شماره شاهد')
    witness_role = models.CharField(max_length=30, blank=True, verbose_name='نقش شاهد')
    first_name = models.CharField(max_length=100, verbose_name='نام')
    last_name = models.CharField(max_length=100, verbose_name='نام خانوادگی')
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    mobile = models.CharField(max_length=20, verbose_name='موبایل')
    mobile_verified = models.BooleanField(default=False, verbose_name='موبایل تأییدشده')
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان تأیید')

    class Meta:
        verbose_name = 'شاهد'
        verbose_name_plural = 'شاهدان'
        constraints = [
            models.UniqueConstraint(
                fields=['version', 'witness_number'],
                name='contracts_witness_number_uniq',
            ),
        ]


class ContractInvitation(models.Model):
    """دعوتنامه برای طرف/شاهد."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='invitations', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        related_name='invitations', verbose_name='نسخه',
    )
    party = models.ForeignKey(
        ContractParty, on_delete=models.CASCADE,
        null=True, blank=True, related_name='invitations', verbose_name='طرف',
    )
    witness = models.ForeignKey(
        ContractWitness, on_delete=models.CASCADE,
        null=True, blank=True, related_name='invitations', verbose_name='شاهد',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='هش توکن')
    mobile = models.CharField(max_length=20, verbose_name='موبایل')
    is_revoked = models.BooleanField(default=False, verbose_name='ابطال‌شده')
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان ابطال')
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name='اولین بازدید')
    viewed_at = models.DateTimeField(null=True, blank=True, verbose_name='مشاهده قرارداد')
    resend_count = models.PositiveSmallIntegerField(default=0, verbose_name='تعداد ارسال مجدد')
    last_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='آخرین ارسال')
    sms_status = models.CharField(
        max_length=12, choices=(
            ('queued', 'در صف'), ('sent', 'ارسال‌شده'),
            ('delivered', 'تحویل'), ('failed', 'ناموفق'),
        ),
        default='queued', verbose_name='وضعیت پیامک',
    )
    sms_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان ارسال پیامک')
    sms_provider_ref = models.CharField(max_length=120, blank=True, verbose_name='ارجاع provider')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='انقضا')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'دعوتنامه'
        verbose_name_plural = 'دعوتنامه‌ها'
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['contract', 'version']),
        ]


class ContractOTP(models.Model):
    """OTP اختصاصی قرارداد — جدا از OTP حساب کاربری."""
    invitation = models.ForeignKey(
        ContractInvitation, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='otp_requests', verbose_name='دعوتنامه',
    )
    handover_invitation = models.ForeignKey(
        'ContractHandoverInvitation', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='otp_requests', verbose_name='دعوتنامه تحویل',
    )
    access_token = models.ForeignKey(
        'ContractAccessToken', on_delete=models.CASCADE,
        null=True, blank=True, related_name='otp_requests', verbose_name='توکن دسترسی',
    )
    phone = models.CharField(max_length=20, db_index=True, verbose_name='موبایل')
    code_hash = models.CharField(max_length=64, verbose_name='هش کد')
    purpose = models.CharField(max_length=32, default='acceptance', verbose_name='هدف')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='انقضا')
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name='تلاش‌ها')
    max_attempts = models.PositiveSmallIntegerField(default=5, verbose_name='سقف تلاش')
    is_consumed = models.BooleanField(default=False, db_index=True, verbose_name='مصرف‌شده')
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان مصرف')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')

    class Meta:
        verbose_name = 'OTP قرارداد'
        verbose_name_plural = 'OTPهای قرارداد'
        ordering = ['-created_at']


class ContractAcceptance(models.Model):
    """تأیید طرف قرارداد."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='acceptances', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        related_name='acceptances', verbose_name='نسخه',
    )
    party = models.ForeignKey(
        ContractParty, on_delete=models.CASCADE,
        null=True, blank=True, related_name='acceptances', verbose_name='طرف',
    )
    witness = models.ForeignKey(
        ContractWitness, on_delete=models.CASCADE,
        null=True, blank=True, related_name='acceptances', verbose_name='شاهد',
    )
    invitation = models.ForeignKey(
        ContractInvitation, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acceptances', verbose_name='دعوتنامه',
    )
    accepted_content_hash = models.CharField(max_length=64, verbose_name='هش محتوای تأییدشده')
    content_hash = models.CharField(max_length=64, verbose_name='هش نسخه (legacy)')
    mobile = models.CharField(max_length=20, verbose_name='موبایل')
    national_id_entered = models.CharField(max_length=10, blank=True, verbose_name='کد ملی واردشده')
    otp_verified_at = models.DateTimeField(verbose_name='زمان تأیید OTP')
    accepted_at = models.DateTimeField(default=timezone.now, verbose_name='زمان تأیید')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')
    session_identifier = models.CharField(max_length=64, blank=True, verbose_name='شناسه نشست')
    ack_checkboxes = models.JSONField(default=list, blank=True, verbose_name='تأییدها')

    def is_hash_valid(self) -> bool:
        from contracts.services.hashing import acceptance_hash_valid
        return acceptance_hash_valid(self)

    class Meta:
        verbose_name = 'تأیید قرارداد'
        verbose_name_plural = 'تأییدهای قرارداد'
        constraints = [
            models.UniqueConstraint(
                fields=['version', 'party'],
                condition=models.Q(party__isnull=False),
                name='contracts_one_acceptance_per_party',
            ),
            models.UniqueConstraint(
                fields=['version', 'witness'],
                condition=models.Q(witness__isnull=False),
                name='contracts_one_acceptance_per_witness',
            ),
        ]


class ContractSignature(models.Model):
    """امضای دیجیتال/دستی."""
    acceptance = models.OneToOneField(
        ContractAcceptance, on_delete=models.CASCADE,
        related_name='signature', verbose_name='تأیید',
    )
    signature_type = models.CharField(
        max_length=30, choices=SIGNATURE_TYPES, default='otp_acceptance', verbose_name='نوع',
    )
    image = models.ImageField(
        upload_to='contracts/signatures/', blank=True, null=True, verbose_name='تصویر امضا',
    )
    signed_at = models.DateTimeField(default=timezone.now, verbose_name='زمان امضا')

    class Meta:
        verbose_name = 'امضا'
        verbose_name_plural = 'امضاها'


class ContractAttachment(models.Model):
    """ضمیمه قرارداد یا صورت‌جلسه تحویل."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='attachments', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='attachments', verbose_name='نسخه',
    )
    handover = models.ForeignKey(
        'ContractHandover', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='attachments', verbose_name='صورت‌جلسه تحویل',
    )
    attachment_type = models.CharField(
        max_length=20, choices=ATTACHMENT_TYPES, default='other', verbose_name='نوع',
    )
    title = models.CharField(max_length=200, blank=True, verbose_name='عنوان')
    file = models.FileField(upload_to=contract_attachment_path, verbose_name='فایل')
    mime_type = models.CharField(max_length=100, blank=True, verbose_name='MIME')
    file_size = models.PositiveIntegerField(default=0, verbose_name='حجم')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_attachments', verbose_name='آپلودکننده',
    )
    is_visible_to_parties = models.BooleanField(default=True, verbose_name='قابل مشاهده طرفین')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ضمیمه'
        verbose_name_plural = 'ضمائم'


class ContractAccessToken(models.Model):
    """توکن دسترسی دائم پس از نهایی‌سازی."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='access_tokens', verbose_name='قرارداد',
    )
    party = models.ForeignKey(
        ContractParty, on_delete=models.CASCADE,
        null=True, blank=True, related_name='access_tokens', verbose_name='طرف',
    )
    witness = models.ForeignKey(
        ContractWitness, on_delete=models.CASCADE,
        null=True, blank=True, related_name='access_tokens', verbose_name='شاهد',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='هش توکن')
    is_revoked = models.BooleanField(default=False, verbose_name='ابطال‌شده')
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان ابطال')
    trusted_until = models.DateTimeField(null=True, blank=True, verbose_name='دستگاه مورداعتماد تا')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'توکن دسترسی'
        verbose_name_plural = 'توکن‌های دسترسی'


class ContractAuditEvent(models.Model):
    """لاگ ممیزی — فقط افزودنی."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='audit_events', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_events', verbose_name='نسخه',
    )
    event_type = models.CharField(max_length=40, db_index=True, verbose_name='رویداد')
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contract_audit_events', verbose_name='کاربر',
    )
    party = models.ForeignKey(
        ContractParty, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_events', verbose_name='طرف',
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='User-Agent')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'رویداد ممیزی'
        verbose_name_plural = 'رویدادهای ممیزی'
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Audit events are append-only')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit events cannot be deleted')


class ContractHandover(models.Model):
    """صورت‌جلسه تحویل دیجیتال."""
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='handovers', verbose_name='قرارداد',
    )
    version = models.ForeignKey(
        ContractVersion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='handovers', verbose_name='نسخه قرارداد',
    )
    deal = models.ForeignKey(
        'workspace.CRMDeal', on_delete=models.CASCADE,
        related_name='contract_handovers', verbose_name='معامله',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='contract_handovers', verbose_name='ایجادکننده',
    )
    handover_type = models.CharField(
        max_length=30, choices=HANDOVER_TYPES, default='initial_delivery', verbose_name='نوع تحویل',
    )
    status = models.CharField(
        max_length=20, choices=HANDOVER_STATUSES, default='draft', db_index=True, verbose_name='وضعیت',
    )
    handover_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تحویل')
    handover_time = models.TimeField(null=True, blank=True, verbose_name='ساعت تحویل')
    snapshot_json = models.JSONField(default=dict, blank=True, verbose_name='اسنپ‌شات')
    content_hash = models.CharField(max_length=64, blank=True, verbose_name='هش محتوا')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    pdf_file = models.FileField(upload_to='contracts/handovers/', blank=True, verbose_name='PDF')
    is_locked = models.BooleanField(default=False, verbose_name='قفل‌شده')
    replaced_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='replaces', verbose_name='جایگزین‌شده با',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان نهایی‌سازی')

    class Meta:
        verbose_name = 'صورت‌جلسه تحویل'
        verbose_name_plural = 'صورت‌جلسه‌های تحویل'
        ordering = ['-created_at']

    def __str__(self):
        return f'تحویل {self.contract.internal_number} — {self.get_handover_type_display()}'


class ContractHandoverInvitation(models.Model):
    """دعوتنامه تأیید صورت‌جلسه تحویل."""
    handover = models.ForeignKey(
        ContractHandover, on_delete=models.CASCADE,
        related_name='invitations', verbose_name='صورت‌جلسه',
    )
    side = models.CharField(max_length=20, verbose_name='سمت')  # delivered_by / received_by
    first_name = models.CharField(max_length=100, blank=True, verbose_name='نام')
    last_name = models.CharField(max_length=100, blank=True, verbose_name='نام خانوادگی')
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    mobile = models.CharField(max_length=20, verbose_name='موبایل')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='هش توکن')
    expires_at = models.DateTimeField(verbose_name='انقضا')
    is_revoked = models.BooleanField(default=False, verbose_name='ابطال‌شده')
    sms_status = models.CharField(max_length=20, default='queued', verbose_name='وضعیت SMS')
    sms_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان ارسال SMS')
    last_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='آخرین ارسال')
    resend_count = models.PositiveSmallIntegerField(default=0, verbose_name='تعداد ارسال مجدد')
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان باز شدن')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'دعوتنامه تحویل'
        verbose_name_plural = 'دعوتنامه‌های تحویل'


class ContractHandoverAcceptance(models.Model):
    """تأیید صورت‌جلسه تحویل."""
    handover = models.ForeignKey(
        ContractHandover, on_delete=models.CASCADE,
        related_name='acceptances', verbose_name='صورت‌جلسه',
    )
    invitation = models.ForeignKey(
        ContractHandoverInvitation, on_delete=models.CASCADE,
        related_name='acceptances', verbose_name='دعوتنامه',
    )
    side = models.CharField(max_length=20, verbose_name='سمت')
    accepted_content_hash = models.CharField(max_length=64, verbose_name='هش تأییدشده')
    mobile = models.CharField(max_length=20, verbose_name='موبایل')
    national_id_entered = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    otp_verified_at = models.DateTimeField(verbose_name='زمان OTP')
    ack_checkboxes = models.JSONField(default=list, blank=True, verbose_name='تأییدها')
    accepted_at = models.DateTimeField(default=timezone.now, verbose_name='زمان تأیید')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')

    class Meta:
        verbose_name = 'تأیید تحویل'
        verbose_name_plural = 'تأییدهای تحویل'
        constraints = [
            models.UniqueConstraint(fields=['handover', 'side'], name='contracts_handover_side_uniq'),
        ]
