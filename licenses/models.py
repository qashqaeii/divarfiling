"""
مدل‌های لایسنس
"""
import uuid
import hashlib
import hmac
from django.db import models
from django.conf import settings
from django.utils import timezone
from shop.models import Order, LicensePlan


class License(models.Model):
    """لایسنس محصول — یک کلید برای چند سیستم (طبق max_activations پلن)."""
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
        ('suspended', 'مسدود'),
        ('expired', 'منقضی شده'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='licenses', verbose_name='سفارش')
    sequence = models.PositiveSmallIntegerField(default=1, verbose_name='شماره در سفارش')
    license_key = models.CharField(max_length=100, unique=True, verbose_name='کلید لایسنس')
    plan = models.ForeignKey(LicensePlan, on_delete=models.PROTECT, verbose_name='پلن')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', verbose_name='وضعیت')
    max_activations = models.IntegerField(default=1, verbose_name='حداکثر فعال‌سازی')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انقضا')
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocated_licenses',
        verbose_name='تخصیص به عضو',
        help_text='عضو تیم که این کلید لایسنس به او اختصاص داده شده است.',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='licenses_assigned_by_me',
        verbose_name='تخصیص توسط',
    )
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تخصیص کلید')
    agency_subscription = models.ForeignKey(
        'workspace.AgencySubscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seat_licenses',
        verbose_name='اشتراک آژانس',
        help_text='Seat متعلق به کدام اشتراک آژانس است.',
    )

    class Meta:
        verbose_name = 'لایسنس'
        verbose_name_plural = 'لایسنس‌ها'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'sequence'],
                name='uniq_license_order_sequence',
            ),
        ]
    
    def __str__(self):
        return f'{self.license_key} - {self.order.user.username}'
    
    def is_valid(self):
        """بررسی اعتبار لایسنس (فعال و منقضی نشده)."""
        self.sync_expiration_status(save=True)
        if self.status != 'active':
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def can_be_activated(self):
        """آیا لایسنس قابل فعال‌سازی در نرم‌افزار است؟"""
        self.sync_expiration_status(save=True)
        if self.status in ('suspended', 'expired'):
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def sync_expiration_status(self, *, save: bool = True) -> bool:
        """اگر تاریخ انقضا گذشته باشد status را expired می‌کند."""
        if self.expires_at and self.expires_at < timezone.now():
            if self.status not in ('expired', 'suspended'):
                self.status = 'expired'
                if save:
                    self.save(update_fields=['status'])
                return True
        return False

    def plan_payload(self):
        if not self.plan_id:
            return {}
        return {
            'plan_id': self.plan_id,
            'plan_name': self.plan.name,
            'max_activations': self.max_activations,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    @property
    def slots_used(self) -> int:
        return self.activations.count()

    @property
    def slots_available(self) -> int:
        return max(0, self.max_activations - self.slots_used)

    def active_slot_count(self) -> int:
        return self.activations.filter(is_active=True).count()


class LicenseActivation(models.Model):
    """اسلات سیستم — هر رکورد یک دستگاه/سیستم روی لایسنس."""
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='activations', verbose_name='لایسنس')
    hardware_fingerprint = models.CharField(max_length=200, db_index=True, verbose_name='شناسه سخت‌افزاری')
    label = models.CharField(max_length=80, blank=True, verbose_name='نام سیستم')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='آدرس IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    activated_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    is_active = models.BooleanField(default=False, verbose_name='فعال در ربات')
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='license_seat_assignments',
        verbose_name='عضو تیم',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='license_seats_assigned',
        verbose_name='تخصیص توسط',
    )
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تخصیص')
    notes = models.CharField(max_length=300, blank=True, verbose_name='یادداشت')

    class Meta:
        verbose_name = 'اسلات لایسنس'
        verbose_name_plural = 'اسلات‌های لایسنس'
        unique_together = ['license', 'hardware_fingerprint']
        ordering = ['activated_at', 'pk']

    def __str__(self):
        name = self.label or self.hardware_fingerprint[:20]
        return f'{self.license.license_key} — {name}'

    @property
    def display_name(self) -> str:
        return self.label.strip() or f'سیستم {self.pk}'

    @property
    def masked_fingerprint(self) -> str:
        fp = self.hardware_fingerprint
        if len(fp) <= 12:
            return fp
        return f'{fp[:6]}…{fp[-4:]}'

    @property
    def seat_status(self) -> str:
        if self.is_active:
            return 'active'
        return 'pending'


class AuditLog(models.Model):
    """لاگ امنیتی و لایسنس"""
    ACTION_TYPES = [
        ('activation', 'فعال‌سازی'),
        ('deactivation', 'غیرفعال‌سازی'),
        ('validation', 'اعتبارسنجی'),
        ('revoke', 'لغو'),
        ('transfer', 'انتقال'),
        ('suspicious', 'فعالیت مشکوک'),
    ]
    
    license = models.ForeignKey(License, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='لایسنس')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name='نوع عملیات')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='آدرس IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    details = models.JSONField(default=dict, verbose_name='جزئیات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'لاگ امنیتی'
        verbose_name_plural = 'لاگ‌های امنیتی'
        ordering = ['-created_at']


class ClientAppEvent(models.Model):
    """رویدادهای گزارش‌شده از اپ کلاینت (ویندوز) — نصب/اجرای واقعی."""

    class EventType(models.TextChoices):
        FIRST_LAUNCH = 'first_launch', 'اولین اجرا'
        APP_LAUNCH = 'app_launch', 'اجرای برنامه'

    class Platform(models.TextChoices):
        WINDOWS = 'windows', 'ویندوز'

    license = models.ForeignKey(
        License,
        on_delete=models.CASCADE,
        related_name='client_events',
        verbose_name='لایسنس',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_app_events',
        verbose_name='کاربر',
    )
    activation = models.ForeignKey(
        LicenseActivation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_events',
        verbose_name='اسلات دستگاه',
    )
    hardware_fingerprint = models.CharField(max_length=200, db_index=True, verbose_name='شناسه سخت‌افزاری')
    event_type = models.CharField(max_length=32, choices=EventType.choices, verbose_name='نوع رویداد')
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.WINDOWS,
        verbose_name='پلتفرم',
    )
    app_version = models.CharField(max_length=40, blank=True, verbose_name='نسخه اپ')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='آدرس IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ رویداد')

    class Meta:
        verbose_name = 'رویداد اپ کلاینت'
        verbose_name_plural = 'رویدادهای اپ کلاینت'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['license', 'hardware_fingerprint', 'event_type'],
                name='uniq_client_event_per_device',
            ),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.user_id}'

