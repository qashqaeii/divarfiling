"""مدل‌های داشبورد workspace."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .constants import (
    ACTIVITY_TYPES, AUTOMATION_ACTIONS, AUTOMATION_TRIGGERS, CRM_PRIORITIES, CRM_PROPERTIES,
    CRM_SOURCES, CRM_STATUSES, CRM_TYPES, DEAL_STAGES, DEAL_TYPES, INTEREST_LEVELS,
    LISTING_ROLES, LISTING_TAGS, LOST_REASONS, MESSAGE_CHANNELS, MESSAGE_TEMPLATE_CATEGORIES,
    PROPERTY_DEAL_MODES, PROPERTY_PUBLISH_STATUSES, PROPERTY_TX_STATUSES, REMINDER_RECURRENCE,
    VISIT_OUTCOMES, VISIT_REJECT_REASONS,
)


class Dataset(models.Model):
    """مجموعه‌داده آپلودشده توسط کاربر."""
    FILE_FORMATS = [('xlsx', 'Excel'), ('csv', 'CSV'), ('json', 'JSON')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='datasets', verbose_name='کاربر',
    )
    name = models.CharField(max_length=255, verbose_name='نام')
    original_filename = models.CharField(max_length=500, verbose_name='نام فایل اصلی')
    file_format = models.CharField(max_length=10, choices=FILE_FORMATS, verbose_name='فرمت')
    file_size = models.BigIntegerField(default=0, verbose_name='حجم (بایت)')
    row_count = models.PositiveIntegerField(default=0, verbose_name='تعداد ردیف')
    column_count = models.PositiveIntegerField(default=0, verbose_name='تعداد ستون')
    columns = models.JSONField(default=list, blank=True, verbose_name='ستون‌ها')
    transaction_type = models.CharField(max_length=50, blank=True, verbose_name='نوع معامله')
    subcategory = models.CharField(max_length=100, blank=True, verbose_name='زیردسته')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    district = models.CharField(max_length=100, blank=True, verbose_name='محله/منطقه')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    last_opened_at = models.DateTimeField(null=True, blank=True, verbose_name='آخرین بازدید')

    class Meta:
        verbose_name = 'مجموعه‌داده'
        verbose_name_plural = 'مجموعه‌داده‌ها'
        ordering = ['-last_opened_at', '-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return self.name

    def touch(self):
        self.last_opened_at = timezone.now()
        self.save(update_fields=['last_opened_at'])


class Listing(models.Model):
    """یک آگهی در مجموعه‌داده."""
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE,
        related_name='listings', verbose_name='مجموعه‌داده',
    )
    token = models.CharField(max_length=100, db_index=True, verbose_name='شناسه')
    title = models.CharField(max_length=500, blank=True, verbose_name='عنوان')
    price = models.BigIntegerField(null=True, blank=True, verbose_name='قیمت')
    deposit = models.BigIntegerField(null=True, blank=True, verbose_name='ودیعه')
    rent = models.BigIntegerField(null=True, blank=True, verbose_name='اجاره')
    area = models.FloatField(null=True, blank=True, verbose_name='متراژ')
    rooms = models.CharField(max_length=20, blank=True, verbose_name='اتاق')
    neighborhood = models.CharField(max_length=200, blank=True, verbose_name='محله')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    latitude = models.FloatField(null=True, blank=True, verbose_name='عرض جغرافیایی')
    longitude = models.FloatField(null=True, blank=True, verbose_name='طول جغرافیایی')
    business_type = models.CharField(max_length=50, blank=True, verbose_name='نوع آگهی‌دهنده')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    link = models.URLField(max_length=500, blank=True, verbose_name='لینک')
    images = models.JSONField(default=list, blank=True, verbose_name='تصاویر')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انتشار')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انقضا')
    is_expired = models.BooleanField(default=False, verbose_name='منقضی')
    data = models.JSONField(default=dict, verbose_name='داده کامل')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'آگهی'
        verbose_name_plural = 'آگهی‌ها'
        unique_together = [['dataset', 'token']]
        indexes = [
            models.Index(fields=['dataset', 'price']),
            models.Index(fields=['dataset', 'neighborhood']),
            models.Index(fields=['dataset', 'business_type']),
        ]

    def __str__(self):
        return f'{self.token} — {self.title[:50]}'

    @property
    def price_per_sqm(self):
        if self.price and self.area and self.area > 0:
            return int(self.price / self.area)
        return None


class ListingMeta(models.Model):
    """متادیتای کاربر برای هر آگهی (برچسب، یادداشت، علاقه‌مند)."""
    TAG_CHOICES = [(t, t or 'بدون برچسب') for t in LISTING_TAGS]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='listing_metas', verbose_name='کاربر',
    )
    token = models.CharField(max_length=100, db_index=True, verbose_name='شناسه')
    tag = models.CharField(max_length=20, choices=TAG_CHOICES, blank=True, default='', verbose_name='برچسب')
    note = models.TextField(blank=True, verbose_name='یادداشت')
    is_favorite = models.BooleanField(default=False, verbose_name='علاقه‌مند')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'متادیتای آگهی'
        verbose_name_plural = 'متادیتای آگهی‌ها'
        unique_together = [['user', 'token']]

    def __str__(self):
        return f'{self.user_id}:{self.token}'


class PriceHistory(models.Model):
    """تاریخچه قیمت آگهی."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='price_histories', verbose_name='کاربر',
    )
    token = models.CharField(max_length=100, db_index=True, verbose_name='شناسه')
    price = models.BigIntegerField(null=True, blank=True)
    deposit = models.BigIntegerField(null=True, blank=True)
    rent = models.BigIntegerField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تاریخچه قیمت'
        verbose_name_plural = 'تاریخچه قیمت‌ها'
        ordering = ['-recorded_at']


class Customer(models.Model):
    """مشتری CRM."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_customers', verbose_name='کاربر',
    )
    agency = models.ForeignKey(
        'CRMAgency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customers', verbose_name='آژانس',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='crm_assigned_customers', verbose_name='مشاور مسئول',
    )
    name = models.CharField(max_length=200, verbose_name='نام')
    phone = models.CharField(max_length=20, blank=True, verbose_name='تلفن')
    phone_alt = models.CharField(max_length=20, blank=True, verbose_name='تلفن دوم')
    email = models.EmailField(blank=True, verbose_name='ایمیل')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    district = models.CharField(max_length=100, blank=True, verbose_name='منطقه')
    job = models.CharField(max_length=120, blank=True, verbose_name='شغل')
    is_legal_entity = models.BooleanField(default=False, verbose_name='شخص حقوقی')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='نام شرکت')
    national_id = models.CharField(max_length=20, blank=True, verbose_name='کد ملی')
    converted_from = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversions', verbose_name='تبدیل‌شده از',
    )
    customer_type = models.CharField(
        max_length=30, choices=[(t, t) for t in CRM_TYPES],
        default='خریدار', verbose_name='نوع مخاطب',
    )
    status = models.CharField(
        max_length=30, choices=[(s, s) for s in CRM_STATUSES],
        default='جدید', verbose_name='وضعیت',
    )
    priority = models.CharField(
        max_length=20, choices=[(p, p) for p in CRM_PRIORITIES],
        default='متوسط', verbose_name='اولویت',
    )
    property_type = models.CharField(
        max_length=30, choices=[(p, p) for p in CRM_PROPERTIES],
        blank=True, verbose_name='نوع ملک',
    )
    source = models.CharField(
        max_length=30, choices=[(s, s) for s in CRM_SOURCES],
        blank=True, verbose_name='منبع',
    )
    budget_min = models.BigIntegerField(null=True, blank=True, verbose_name='بودجه از')
    budget_max = models.BigIntegerField(null=True, blank=True, verbose_name='بودجه تا')
    deposit_min = models.BigIntegerField(null=True, blank=True, verbose_name='ودیعه از')
    deposit_max = models.BigIntegerField(null=True, blank=True, verbose_name='ودیعه تا')
    rent_min = models.BigIntegerField(null=True, blank=True, verbose_name='اجاره از')
    rent_max = models.BigIntegerField(null=True, blank=True, verbose_name='اجاره تا')
    min_area = models.IntegerField(null=True, blank=True, verbose_name='متراژ از')
    max_area = models.IntegerField(null=True, blank=True, verbose_name='متراژ تا')
    rooms = models.CharField(max_length=50, blank=True, verbose_name='اتاق')
    areas = models.TextField(blank=True, verbose_name='محله‌های مورد نظر')
    tags = models.CharField(max_length=500, blank=True, verbose_name='برچسب‌ها')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    next_follow_up = models.DateField(null=True, blank=True, verbose_name='پیگیری بعدی')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مشتری'
        verbose_name_plural = 'مشتریان'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['agency', 'assigned_to']),
        ]

    def __str__(self):
        return self.name


class CRMProperty(models.Model):
    """ملک CRM — موجودیت مستقل."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_properties', verbose_name='کاربر',
    )
    agency = models.ForeignKey(
        'CRMAgency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='properties', verbose_name='آژانس',
    )
    title = models.CharField(max_length=300, verbose_name='عنوان')
    property_type = models.CharField(
        max_length=30, choices=[(p, p) for p in CRM_PROPERTIES],
        default='آپارتمان', verbose_name='نوع ملک',
    )
    deal_mode = models.CharField(
        max_length=30, choices=[(d, d) for d in PROPERTY_DEAL_MODES],
        default='فروش', verbose_name='نوع معامله',
    )
    transaction_status = models.CharField(
        max_length=30, choices=[(s, s) for s in PROPERTY_TX_STATUSES],
        default='فعال', verbose_name='وضعیت معامله',
    )
    publish_status = models.CharField(
        max_length=30, choices=[(s, s) for s in PROPERTY_PUBLISH_STATUSES],
        default='پیش‌نویس', verbose_name='وضعیت انتشار',
    )
    address = models.TextField(blank=True, verbose_name='آدرس')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    district = models.CharField(max_length=100, blank=True, verbose_name='منطقه')
    neighborhood = models.CharField(max_length=200, blank=True, verbose_name='محله')
    latitude = models.FloatField(null=True, blank=True, verbose_name='عرض جغرافیایی')
    longitude = models.FloatField(null=True, blank=True, verbose_name='طول جغرافیایی')
    area = models.FloatField(null=True, blank=True, verbose_name='متراژ')
    rooms = models.CharField(max_length=20, blank=True, verbose_name='اتاق')
    floor = models.IntegerField(null=True, blank=True, verbose_name='طبقه')
    total_floors = models.IntegerField(null=True, blank=True, verbose_name='تعداد طبقات')
    has_parking = models.BooleanField(default=False, verbose_name='پارکینگ')
    has_storage = models.BooleanField(default=False, verbose_name='انباری')
    has_elevator = models.BooleanField(default=False, verbose_name='آسانسور')
    build_year = models.IntegerField(null=True, blank=True, verbose_name='سال ساخت')
    sale_price = models.BigIntegerField(null=True, blank=True, verbose_name='قیمت فروش')
    deposit = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ رهن')
    monthly_rent = models.BigIntegerField(null=True, blank=True, verbose_name='اجاره ماهانه')
    amenities = models.TextField(blank=True, verbose_name='امکانات')
    images = models.JSONField(default=list, blank=True, verbose_name='تصاویر')
    videos = models.JSONField(default=list, blank=True, verbose_name='ویدئوها')
    token = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='شناسه آگهی')
    link = models.URLField(max_length=500, blank=True, verbose_name='لینک')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان حذف')
    pipeline_order = models.PositiveIntegerField(default=0, verbose_name='ترتیب کانبان')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ملک CRM'
        verbose_name_plural = 'املاک CRM'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['user', 'deal_mode', 'transaction_status'])]

    def __str__(self):
        return self.title or f'ملک #{self.pk}'


class PropertyContact(models.Model):
    """پیوند چند-به-چند مخاطب ↔ ملک."""
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='property_links', verbose_name='مخاطب',
    )
    property = models.ForeignKey(
        CRMProperty, on_delete=models.CASCADE,
        related_name='contact_links', verbose_name='ملک',
    )
    role = models.CharField(
        max_length=30, choices=[(r, r) for r in LISTING_ROLES],
        default='پیشنهادی', verbose_name='نقش',
    )
    deal_type = models.CharField(
        max_length=30, choices=[(d, d) for d in DEAL_TYPES],
        default='سایر', verbose_name='نوع معامله',
    )
    interest_level = models.CharField(
        max_length=20, choices=[(i, i) for i in INTEREST_LEVELS],
        blank=True, verbose_name='سطح علاقه',
    )
    is_primary = models.BooleanField(default=False, verbose_name='نقش اصلی')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ارتباط مخاطب-ملک'
        verbose_name_plural = 'ارتباطات مخاطب-ملک'
        ordering = ['-is_primary', '-created_at']
        unique_together = [['customer', 'property', 'role']]


class CustomerDocument(models.Model):
    """فایل و مدرک مخاطب یا ملک."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_documents', verbose_name='کاربر',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE, null=True, blank=True,
        related_name='documents', verbose_name='مخاطب',
    )
    property = models.ForeignKey(
        CRMProperty, on_delete=models.CASCADE, null=True, blank=True,
        related_name='documents', verbose_name='ملک',
    )
    title = models.CharField(max_length=200, verbose_name='عنوان')
    file = models.FileField(upload_to='workspace/crm/docs/', verbose_name='فایل')
    doc_type = models.CharField(max_length=50, blank=True, verbose_name='نوع مدرک')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مدرک CRM'
        verbose_name_plural = 'مدارک CRM'
        ordering = ['-uploaded_at']


class CustomerActivity(models.Model):
    """فعالیت CRM."""
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='activities', verbose_name='مشتری',
    )
    activity_type = models.CharField(
        max_length=30, choices=[(a, a) for a in ACTIVITY_TYPES],
        verbose_name='نوع فعالیت',
    )
    title = models.CharField(max_length=200, blank=True, verbose_name='عنوان')
    content = models.TextField(blank=True, verbose_name='محتوا')
    token = models.CharField(max_length=100, blank=True, verbose_name='شناسه آگهی')
    property = models.ForeignKey(
        CRMProperty, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activities', verbose_name='ملک',
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, verbose_name='مدت (دقیقه)')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فعالیت'
        verbose_name_plural = 'فعالیت‌ها'
        ordering = ['-created_at']


class CustomerListing(models.Model):
    """پیوند مشتری به آگهی اسکرپ‌شده."""
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='linked_listings', verbose_name='مشتری',
    )
    crm_property = models.ForeignKey(
        CRMProperty, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='listing_links', verbose_name='ملک CRM',
    )
    token = models.CharField(max_length=100, verbose_name='شناسه')
    title = models.CharField(max_length=500, blank=True)
    price = models.CharField(max_length=100, blank=True)
    area = models.CharField(max_length=50, blank=True)
    link = models.URLField(max_length=500, blank=True)
    role = models.CharField(
        max_length=30, choices=[(r, r) for r in LISTING_ROLES],
        default='پیشنهادی', verbose_name='نقش',
    )
    deal_type = models.CharField(
        max_length=30, choices=[(d, d) for d in DEAL_TYPES],
        default='سایر', verbose_name='نوع معامله',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ملک مرتبط'
        verbose_name_plural = 'املاک مرتبط'
        ordering = ['-created_at']


class Reminder(models.Model):
    """یادآور."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reminders', verbose_name='کاربر',
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reminders',
    )
    title = models.CharField(max_length=200, verbose_name='عنوان')
    note = models.TextField(blank=True, verbose_name='یادداشت')
    due_at = models.DateTimeField(verbose_name='سررسید')
    token = models.CharField(max_length=100, blank=True, verbose_name='شناسه آگهی')
    is_done = models.BooleanField(default=False, verbose_name='انجام شده')
    recurrence = models.CharField(
        max_length=20, choices=REMINDER_RECURRENCE,
        blank=True, default='', verbose_name='تکرار',
    )
    series = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='occurrences', verbose_name='سری تکرار',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'یادآور'
        verbose_name_plural = 'یادآورها'
        ordering = ['due_at']

    def __str__(self):
        return self.title


class CRMMessageTemplate(models.Model):
    """قالب پیام واتساپ/پیامک."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_message_templates', verbose_name='کاربر',
    )
    name = models.CharField(max_length=120, verbose_name='نام قالب')
    category = models.CharField(
        max_length=30,
        choices=[(c, c) for c in MESSAGE_TEMPLATE_CATEGORIES],
        default='پیگیری', verbose_name='دسته',
    )
    channel = models.CharField(
        max_length=20,
        choices=[(c, c) for c in MESSAGE_CHANNELS],
        default='واتساپ', verbose_name='کانال',
    )
    body = models.TextField(verbose_name='متن قالب')
    is_system = models.BooleanField(default=False, verbose_name='پیش‌فرض سیستم')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قالب پیام CRM'
        verbose_name_plural = 'قالب‌های پیام CRM'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class CRMAutomationRule(models.Model):
    """قانون خودکار CRM."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_automation_rules', verbose_name='کاربر',
    )
    name = models.CharField(max_length=120, verbose_name='نام قانون')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    trigger = models.CharField(
        max_length=30,
        choices=AUTOMATION_TRIGGERS,
        default='inactive_days', verbose_name='شرط',
    )
    trigger_days = models.PositiveSmallIntegerField(default=3, verbose_name='تعداد روز')
    trigger_statuses = models.CharField(
        max_length=200, blank=True, default='جدید,در حال پیگیری',
        verbose_name='وضعیت‌های هدف',
    )
    action = models.CharField(
        max_length=30,
        choices=AUTOMATION_ACTIONS,
        default='create_reminder', verbose_name='عمل',
    )
    action_status = models.CharField(max_length=30, blank=True, verbose_name='وضعیت جدید')
    action_reminder_title = models.CharField(
        max_length=200, blank=True, default='پیگیری خودکار',
        verbose_name='عنوان یادآور',
    )
    action_reminder_days = models.PositiveSmallIntegerField(
        default=1, verbose_name='یادآور برای فردا (+روز)',
    )
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name='آخرین اجرا')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قانون اتوماسیون CRM'
        verbose_name_plural = 'قوانین اتوماسیون CRM'
        ordering = ['-is_active', 'name']

    def __str__(self):
        return self.name

    def status_list(self) -> list:
        return [s.strip() for s in (self.trigger_statuses or '').split(',') if s.strip()]


class CRMDeal(models.Model):
    """معامله CRM — ردیابی فروش/اجاره با کمیسیون."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_deals', verbose_name='کاربر',
    )
    agency = models.ForeignKey(
        'CRMAgency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deals', verbose_name='آژانس',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='crm_assigned_deals', verbose_name='مشاور مسئول',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='deals', verbose_name='مخاطب',
    )
    property = models.ForeignKey(
        'CRMProperty', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='deals', verbose_name='ملک',
    )
    listing_token = models.CharField(max_length=100, blank=True, verbose_name='شناسه آگهی')
    title = models.CharField(max_length=300, verbose_name='عنوان معامله')
    stage = models.CharField(
        max_length=60, default='سرنخ', verbose_name='مرحله',
    )
    checklist = models.JSONField(default=list, blank=True, verbose_name='چک‌لیست مدارک')
    value = models.BigIntegerField(null=True, blank=True, verbose_name='ارزش معامله')
    probability = models.PositiveSmallIntegerField(default=50, verbose_name='احتمال بستن (%)')
    expected_close_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تخمینی بستن')
    lost_reason = models.CharField(
        max_length=50, choices=[(r, r) for r in LOST_REASONS],
        blank=True, verbose_name='دلیل از دست دادن',
    )
    commission_rate = models.FloatField(default=1.0, verbose_name='نرخ کمیسیون (%)')
    commission_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ کمیسیون')
    contract_number = models.CharField(max_length=100, blank=True, verbose_name='شماره قرارداد')
    contract_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ قرارداد')
    contract_date = models.DateField(null=True, blank=True, verbose_name='تاریخ قرارداد')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بسته‌شدن')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'معامله'
        verbose_name_plural = 'معاملات'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'stage']),
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        return self.title


class PropertyVisit(models.Model):
    """ثبت نتیجه بازدید ملک."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='property_visits', verbose_name='کاربر',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='visits', verbose_name='مخاطب',
    )
    property = models.ForeignKey(
        'CRMProperty', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='visits', verbose_name='ملک',
    )
    listing_token = models.CharField(max_length=100, blank=True, verbose_name='شناسه آگهی')
    listing_title = models.CharField(max_length=500, blank=True, verbose_name='عنوان آگهی')
    visit_date = models.DateField(verbose_name='تاریخ بازدید')
    outcome = models.CharField(
        max_length=30, choices=[(o, o) for o in VISIT_OUTCOMES],
        default='در انتظار', verbose_name='نتیجه',
    )
    reject_reason = models.CharField(
        max_length=50, choices=[(r, r) for r in VISIT_REJECT_REASONS],
        blank=True, verbose_name='دلیل رد',
    )
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بازدید'
        verbose_name_plural = 'بازدیدها'
        ordering = ['-visit_date', '-created_at']


class CRMAgency(models.Model):
    """آژانس مشترک CRM — فاز ۴."""
    name = models.CharField(max_length=200, verbose_name='نام آژانس')
    slug = models.SlugField(max_length=80, unique=True, blank=True, verbose_name='شناسه')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='owned_crm_agencies', verbose_name='مالک',
    )
    api_key = models.CharField(max_length=64, unique=True, blank=True, verbose_name='کلید API')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'آژانس CRM'
        verbose_name_plural = 'آژانس‌های CRM'
        ordering = ['name']

    def __str__(self):
        return self.name


class CRMAgencyMember(models.Model):
    """عضو تیم آژانس."""
    agency = models.ForeignKey(
        CRMAgency, on_delete=models.CASCADE,
        related_name='members', verbose_name='آژانس',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_agency_memberships', verbose_name='کاربر',
    )
    role = models.CharField(
        max_length=20,
        choices=[(k, v) for k, v in [
            ('owner', 'مالک'), ('manager', 'مدیر'),
            ('advisor', 'مشاور'), ('secretary', 'منشی'),
        ]],
        default='advisor', verbose_name='نقش',
    )
    title = models.CharField(max_length=100, blank=True, verbose_name='عنوان شغلی')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'عضو آژانس'
        verbose_name_plural = 'اعضای آژانس'
        constraints = [
            models.UniqueConstraint(fields=['agency', 'user'], name='uniq_agency_member'),
        ]
        ordering = ['role', 'joined_at']

    def __str__(self):
        return f'{self.user} @ {self.agency}'


class CRMAgencyMembershipRequest(models.Model):
    """درخواست عضویت یا دعوت به تیم — نیازمند تأیید طرف مقابل."""
    TYPE_INVITE = 'invite'
    TYPE_JOIN = 'join'
    TYPE_CHOICES = [
        (TYPE_INVITE, 'دعوت'),
        (TYPE_JOIN, 'درخواست عضویت'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'در انتظار'),
        (STATUS_ACCEPTED, 'پذیرفته‌شده'),
        (STATUS_REJECTED, 'رد شده'),
        (STATUS_CANCELLED, 'لغو شده'),
    ]

    agency = models.ForeignKey(
        CRMAgency, on_delete=models.CASCADE,
        related_name='membership_requests', verbose_name='آژانس',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_membership_requests', verbose_name='کاربر',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_membership_requests_sent', verbose_name='درخواست‌دهنده',
    )
    request_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, verbose_name='نوع',
    )
    role = models.CharField(
        max_length=20,
        choices=[(k, v) for k, v in [
            ('manager', 'مدیر'), ('advisor', 'مشاور'), ('secretary', 'منشی'),
        ]],
        default='advisor', verbose_name='نقش پیشنهادی',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES,
        default=STATUS_PENDING, verbose_name='وضعیت',
    )
    message = models.TextField(blank=True, verbose_name='پیام')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='crm_membership_requests_responded', verbose_name='پاسخ‌دهنده',
    )

    class Meta:
        verbose_name = 'درخواست عضویت آژانس'
        verbose_name_plural = 'درخواست‌های عضویت آژانس'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_request_type_display()} — {self.user} @ {self.agency}'


class CRMAgencyWebhook(models.Model):
    """وب‌هوک خروجی آژانس."""
    agency = models.ForeignKey(
        CRMAgency, on_delete=models.CASCADE,
        related_name='webhooks', verbose_name='آژانس',
    )
    name = models.CharField(max_length=120, verbose_name='نام')
    url = models.URLField(max_length=500, verbose_name='آدرس')
    secret = models.CharField(max_length=64, blank=True, verbose_name='رمز امضا')
    events = models.JSONField(default=list, blank=True, verbose_name='رویدادها')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'وب‌هوک آژانس'
        verbose_name_plural = 'وب‌هوک‌های آژانس'
        ordering = ['name']


class CRMDealCommissionSplit(models.Model):
    """تقسیم کمیسیون بین مشاوران — E5."""
    deal = models.ForeignKey(
        'CRMDeal', on_delete=models.CASCADE,
        related_name='commission_splits', verbose_name='معامله',
    )
    member = models.ForeignKey(
        CRMAgencyMember, on_delete=models.CASCADE,
        related_name='commission_splits', verbose_name='عضو',
    )
    percent = models.FloatField(default=0, verbose_name='درصد')
    amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سهم کمیسیون'
        verbose_name_plural = 'سهم‌های کمیسیون'
        constraints = [
            models.UniqueConstraint(fields=['deal', 'member'], name='uniq_deal_commission_member'),
        ]


class CustomerTransferLog(models.Model):
    """لاگ انتقال پرونده — E6."""
    agency = models.ForeignKey(
        CRMAgency, on_delete=models.CASCADE,
        related_name='transfer_logs', verbose_name='آژانس',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='transfer_logs', verbose_name='مخاطب',
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='از',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='به',
    )
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+', verbose_name='توسط',
    )
    note = models.CharField(max_length=300, blank=True, verbose_name='یادداشت')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'انتقال پرونده'
        verbose_name_plural = 'انتقالات پرونده'
        ordering = ['-created_at']


class CRMResourceShare(models.Model):
    """اشتراک‌گذاری صریح مخاطب/ملک/معامله با عضو دیگر تیم."""
    SHARE_MODE_COLLABORATIVE = 'collaborative'
    SHARE_MODE_CONFIDENTIAL = 'confidential'
    SHARE_MODE_CHOICES = [
        (SHARE_MODE_COLLABORATIVE, 'اشتراک کامل'),
        (SHARE_MODE_CONFIDENTIAL, 'ارسال محرمانه'),
    ]

    agency = models.ForeignKey(
        'CRMAgency', on_delete=models.CASCADE,
        related_name='resource_shares', verbose_name='آژانس',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_shares_sent', verbose_name='مالک',
    )
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_shares_received', verbose_name='گیرنده',
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_shares_created', verbose_name='توسط',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shares', verbose_name='مخاطب',
    )
    property = models.ForeignKey(
        'CRMProperty', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shares', verbose_name='ملک',
    )
    deal = models.ForeignKey(
        'CRMDeal', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shares', verbose_name='معامله',
    )
    note = models.CharField(max_length=300, blank=True, verbose_name='یادداشت')
    share_mode = models.CharField(
        max_length=20,
        choices=SHARE_MODE_CHOICES,
        default=SHARE_MODE_CONFIDENTIAL,
        verbose_name='نوع اشتراک',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اشتراک CRM'
        verbose_name_plural = 'اشتراک‌های CRM'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'shared_with'],
                condition=models.Q(customer__isnull=False),
                name='uniq_crm_share_customer',
            ),
            models.UniqueConstraint(
                fields=['property', 'shared_with'],
                condition=models.Q(property__isnull=False),
                name='uniq_crm_share_property',
            ),
            models.UniqueConstraint(
                fields=['deal', 'shared_with'],
                condition=models.Q(deal__isnull=False),
                name='uniq_crm_share_deal',
            ),
        ]

    def __str__(self):
        return f'share #{self.pk}'


class CRMSavedFilter(models.Model):
    """فیلتر ذخیره‌شده CRM — A10."""
    SCOPE_CHOICES = [
        ('contacts', 'مخاطبین'),
        ('properties', 'املاک'),
        ('deals', 'معاملات'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crm_saved_filters', verbose_name='کاربر',
    )
    name = models.CharField(max_length=120, verbose_name='نام')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, verbose_name='بخش')
    params = models.JSONField(default=dict, verbose_name='پارامترها')
    is_pinned = models.BooleanField(default=False, verbose_name='سنجاق')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'فیلتر ذخیره CRM'
        verbose_name_plural = 'فیلترهای ذخیره CRM'
        ordering = ['-is_pinned', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'scope', 'name'],
                name='uniq_crm_saved_filter_name_scope',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.scope})'


class WorkspaceSettings(models.Model):
    """تنظیمات workspace کاربر."""
    THEME_CHOICES = [('light', 'روشن'), ('cheerful', 'شاد'), ('dark', 'تیره')]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='workspace_settings', verbose_name='کاربر',
    )
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    font_scale = models.FloatField(default=1.0)
    map_cluster = models.BooleanField(default=True, verbose_name='خوشه‌بندی نقشه')
    map_heatmap = models.BooleanField(default=False, verbose_name='نقشه حرارتی')
    map_kmeans = models.IntegerField(default=0, verbose_name='K-Means')
    agency_name = models.CharField(max_length=200, blank=True, verbose_name='نام آژانس')
    agency_logo = models.ImageField(
        upload_to='workspace/logos/', blank=True, null=True, verbose_name='لوگو',
    )
    crm_deal_stages = models.JSONField(
        default=list, blank=True,
        verbose_name='مراحل سفارشی pipeline معامله',
    )
    onboarding_completed = models.BooleanField(
        default=False,
        verbose_name='تور آموزشی میزکار',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تنظیمات workspace'
        verbose_name_plural = 'تنظیمات workspace'
