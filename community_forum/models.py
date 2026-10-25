"""مدل‌های تالار گفتگوی عمومی."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ForumMember(models.Model):
    """عضویت و هویت نمایشی در تالار — جدا از CRM."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_member',
        verbose_name='کاربر',
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    display_name = models.CharField(max_length=64, blank=True, verbose_name='نام نمایشی')
    display_name_approved = models.BooleanField(default=False, verbose_name='نام نمایشی تأیید‌شده')
    last_read_message_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='آخرین پیام خوانده‌شده',
    )
    welcome_seen_at = models.DateTimeField(null=True, blank=True, verbose_name='خوش‌آمد دیده شده')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عضو تالار'
        verbose_name_plural = 'اعضای تالار'

    def __str__(self):
        return f'ForumMember<{self.public_id}>'


class ForumMessage(models.Model):
    """پیام عمومی تالار."""

    sender = models.ForeignKey(
        ForumMember,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='فرستنده',
    )
    body = models.TextField(verbose_name='متن')
    reply_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replies',
        verbose_name='پاسخ به',
    )
    client_message_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reactions_updated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'پیام تالار'
        verbose_name_plural = 'پیام‌های تالار'
        permissions = [
            ('can_moderate_forum', 'مدیریت تالار گفتگو'),
        ]
        indexes = [
            models.Index(fields=['-created_at', '-id']),
            models.Index(fields=['sender', 'client_message_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['sender', 'client_message_id'],
                condition=models.Q(client_message_id__isnull=False),
                name='uniq_forum_client_message_per_sender',
            ),
        ]

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def __str__(self):
        return f'ForumMessage<{self.pk}>'


class ForumReaction(models.Model):
    message = models.ForeignKey(
        ForumMessage,
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    member = models.ForeignKey(
        ForumMember,
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    emoji = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'واکنش'
        verbose_name_plural = 'واکنش‌ها'
        constraints = [
            models.UniqueConstraint(fields=['message', 'member'], name='uniq_forum_reaction_per_member'),
        ]


class ForumReport(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        REVIEWED = 'reviewed', 'بررسی‌شده'
        DISMISSED = 'dismissed', 'رد شده'

    message = models.ForeignKey(ForumMessage, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(ForumMember, on_delete=models.CASCADE, related_name='reports_filed')
    reason = models.CharField(max_length=32)
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='forum_reports_reviewed',
    )

    class Meta:
        verbose_name = 'گزارش تخلف'
        verbose_name_plural = 'گزارش‌های تخلف'
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'reporter'],
                name='uniq_forum_report_per_reporter',
            ),
        ]


class ForumBan(models.Model):
    """محدودیت ارسال در تالار — مستقل از مسدودی حساب."""

    member = models.ForeignKey(ForumMember, on_delete=models.CASCADE, related_name='bans')
    reason = models.TextField(blank=True)
    can_read = models.BooleanField(default=True, verbose_name='اجازه مشاهده')
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='forum_bans_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'محدودیت تالار'
        verbose_name_plural = 'محدودیت‌های تالار'
        indexes = [
            models.Index(fields=['member', '-starts_at']),
        ]


class ForumPinnedNotice(models.Model):
    body = models.TextField(verbose_name='متن اطلاعیه')
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='forum_notices_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'اطلاعیه سنجاق‌شده'
        verbose_name_plural = 'اطلاعیه‌های سنجاق‌شده'
        ordering = ['-created_at']


class ForumModerationAudit(models.Model):
    action = models.CharField(max_length=64, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='forum_audit_actions',
    )
    target_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    target_member_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سابقه مدیریت تالار'
        verbose_name_plural = 'سوابق مدیریت تالار'
        ordering = ['-created_at']
