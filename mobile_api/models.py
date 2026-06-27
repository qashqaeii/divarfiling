"""مدل‌های API موبایل."""
from django.conf import settings
from django.db import models


class MobileDevice(models.Model):
    """دستگاه اندروید ثبت‌شده."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mobile_devices',
    )
    device_id = models.CharField(max_length=128, unique=True, db_index=True)
    device_model = models.CharField(max_length=120, blank=True)
    os_version = models.CharField(max_length=40, blank=True)
    app_version = models.CharField(max_length=40, blank=True)
    fcm_token = models.CharField(max_length=512, blank=True)
    notification_prefs = models.JSONField(default=dict, blank=True)
    license_activation = models.ForeignKey(
        'licenses.LicenseActivation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mobile_devices',
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دستگاه موبایل'
        verbose_name_plural = 'دستگاه‌های موبایل'
        ordering = ['-last_seen_at']

    def __str__(self):
        return f'{self.user_id} — {self.device_id[:12]}'


DEFAULT_NOTIFICATION_PREFS = {
    'crm_reminders': True,
    'today_digest': True,
    'new_dataset': True,
    'price_drop': True,
    'customer_match': True,
    'extract_complete': True,
    'extract_schedule_due': True,
    'overdue_followup': True,
    'license_alerts': True,
    'digest_hour': 8,
}


class MobileNotification(models.Model):
    """اعلان in-app برای اپ موبایل."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mobile_notifications',
    )
    notification_type = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    deep_link = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'اعلان موبایل'
        verbose_name_plural = 'اعلان‌های موبایل'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_id} — {self.title[:40]}'


class MobileExtractionSchedule(models.Model):
    """زمان‌بندی استخراج سبک موبایل — اجرا روی دستگاه کاربر."""
    RUN_STATUS_IDLE = 'idle'
    RUN_STATUS_QUEUED = 'queued'
    RUN_STATUS_RUNNING = 'running'
    RUN_STATUS_SUCCESS = 'success'
    RUN_STATUS_FAILED = 'failed'
    RUN_STATUS_SKIPPED_LIMIT = 'skipped_limit'
    RUN_STATUS_CHOICES = [
        (RUN_STATUS_IDLE, 'آماده'),
        (RUN_STATUS_QUEUED, 'در صف'),
        (RUN_STATUS_RUNNING, 'در حال اجرا'),
        (RUN_STATUS_SUCCESS, 'موفق'),
        (RUN_STATUS_FAILED, 'ناموفق'),
        (RUN_STATUS_SKIPPED_LIMIT, 'محدودیت روزانه'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mobile_extraction_schedules',
    )
    title = models.CharField(max_length=200)
    is_enabled = models.BooleanField(default=True, db_index=True)
    interval_hours = models.FloatField(default=6.0)
    filters = models.JSONField(default=dict, blank=True)
    max_items = models.PositiveSmallIntegerField(default=50)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(
        max_length=20,
        choices=RUN_STATUS_CHOICES,
        default=RUN_STATUS_IDLE,
    )
    last_error = models.TextField(blank=True)
    last_dataset_id = models.UUIDField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    primary_device_id = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'زمان‌بندی استخراج موبایل'
        verbose_name_plural = 'زمان‌بندی‌های استخراج موبایل'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user_id} — {self.title}'


class MobileExtractionRun(models.Model):
    """لاگ اجرای استخراج زمان‌بندی‌شده."""
    TRIGGER_SCHEDULED = 'scheduled'
    TRIGGER_MANUAL = 'manual'
    TRIGGER_FCM = 'fcm'
    TRIGGER_DEVICE = 'device'
    TRIGGER_CHOICES = [
        (TRIGGER_SCHEDULED, 'زمان‌بندی'),
        (TRIGGER_MANUAL, 'دستی'),
        (TRIGGER_FCM, 'اعلان'),
        (TRIGGER_DEVICE, 'دستگاه'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mobile_extraction_runs',
    )
    schedule = models.ForeignKey(
        MobileExtractionSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='runs',
    )
    status = models.CharField(
        max_length=20,
        choices=MobileExtractionSchedule.RUN_STATUS_CHOICES,
        default=MobileExtractionSchedule.RUN_STATUS_RUNNING,
        db_index=True,
    )
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_SCHEDULED)
    filters_snapshot = models.JSONField(default=dict, blank=True)
    dataset_id = models.UUIDField(null=True, blank=True)
    ingested_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'اجرای استخراج موبایل'
        verbose_name_plural = 'اجراهای استخراج موبایل'
        ordering = ['-started_at']

    def __str__(self):
        return f'run#{self.pk} — {self.status}'
