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
    'overdue_followup': True,
    'digest_hour': 8,
}
