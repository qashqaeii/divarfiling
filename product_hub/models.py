"""مدل‌های مرکز توسعه فایلینگ دیوار (Product Hub)."""
from django.conf import settings
from django.db import models
from django.utils import timezone


FEATURE_CATEGORY_CHOICES = [
    ('filing', 'فایلینگ'),
    ('extraction', 'استخراج آگهی'),
    ('crm', 'CRM'),
    ('customers', 'مشتریان'),
    ('deals', 'معاملات'),
    ('reports', 'گزارشات'),
    ('tools', 'ابزارهای هوشمند'),
    ('mobile', 'اپلیکیشن موبایل'),
    ('desktop_bot', 'ربات دسکتاپ'),
]

FEATURE_STATUS_CHOICES = [
    ('active', 'فعال'),
    ('in_progress', 'در حال توسعه'),
    ('planned', 'برنامه آینده'),
    ('beta', 'آزمایشی'),
]

CHANGE_TYPE_CHOICES = [
    ('feature', 'Feature جدید'),
    ('fix', 'Bug Fix'),
    ('improvement', 'Improvement'),
    ('security', 'Security'),
    ('performance', 'Performance'),
]

REQUEST_PRIORITY_CHOICES = [
    ('low', 'کم'),
    ('medium', 'متوسط'),
    ('high', 'زیاد'),
]

REQUEST_STATUS_CHOICES = [
    ('submitted', 'ثبت شده'),
    ('reviewing', 'در حال بررسی'),
    ('approved', 'تایید شده'),
    ('in_development', 'در حال توسعه'),
    ('completed', 'تکمیل شده'),
    ('rejected', 'رد شده'),
]

BUG_SEVERITY_CHOICES = [
    ('critical', 'بحرانی'),
    ('high', 'زیاد'),
    ('medium', 'متوسط'),
    ('low', 'کم'),
]

BUG_STATUS_CHOICES = [
    ('reported', 'گزارش شده'),
    ('reviewing', 'بررسی'),
    ('fixing', 'در حال رفع'),
    ('resolved', 'رفع شده'),
]

NOTIFICATION_KIND_CHOICES = [
    ('feature_shipped', 'انتشار قابلیت'),
    ('request_status', 'تغییر وضعیت پیشنهاد'),
    ('bug_resolved', 'رفع مشکل'),
    ('release', 'نسخه جدید'),
]


class ProductFeature(models.Model):
    """کاتالوگ قابلیت‌های محصول."""

    title = models.CharField(max_length=200, verbose_name='نام قابلیت')
    slug = models.SlugField(max_length=220, unique=True, allow_unicode=True, verbose_name='اسلاگ')
    summary = models.TextField(verbose_name='توضیح کوتاه')
    category = models.CharField(
        max_length=30, choices=FEATURE_CATEGORY_CHOICES, verbose_name='دسته‌بندی',
    )
    status = models.CharField(
        max_length=20, choices=FEATURE_STATUS_CHOICES, default='active', verbose_name='وضعیت',
    )
    added_at = models.DateField(default=timezone.localdate, verbose_name='تاریخ اضافه شدن')
    last_changed_at = models.DateField(null=True, blank=True, verbose_name='آخرین تغییرات')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')
    is_published = models.BooleanField(default=True, verbose_name='منتشر شده')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'قابلیت محصول'
        verbose_name_plural = 'قابلیت‌های محصول'
        ordering = ['sort_order', 'title']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['is_published', 'sort_order']),
        ]

    def __str__(self):
        return self.title


class ProductRelease(models.Model):
    """نسخه منتشرشده محصول."""

    version = models.CharField(max_length=40, unique=True, verbose_name='شماره نسخه')
    title = models.CharField(max_length=200, verbose_name='عنوان بروزرسانی')
    summary = models.TextField(blank=True, verbose_name='خلاصه')
    released_at = models.DateTimeField(verbose_name='تاریخ انتشار')
    is_published = models.BooleanField(default=True, verbose_name='منتشر شده')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='product_releases', verbose_name='ایجادکننده',
    )

    class Meta:
        verbose_name = 'نسخه محصول'
        verbose_name_plural = 'نسخه‌های محصول'
        ordering = ['-released_at']
        indexes = [
            models.Index(fields=['is_published', '-released_at']),
        ]

    def __str__(self):
        return f'v{self.version} — {self.title}'


class ReleaseChange(models.Model):
    """آیتم تغییر در یک نسخه."""

    release = models.ForeignKey(
        ProductRelease, on_delete=models.CASCADE,
        related_name='changes', verbose_name='نسخه',
    )
    change_type = models.CharField(
        max_length=20, choices=CHANGE_TYPE_CHOICES, default='improvement', verbose_name='نوع تغییر',
    )
    text = models.CharField(max_length=500, verbose_name='متن تغییر')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')

    class Meta:
        verbose_name = 'آیتم تغییر'
        verbose_name_plural = 'آیتم‌های تغییر'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.text[:80]


class FeatureRequest(models.Model):
    """پیشنهاد قابلیت از کاربران."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='feature_requests', verbose_name='ثبت‌کننده',
    )
    title = models.CharField(max_length=200, verbose_name='عنوان پیشنهاد')
    category = models.CharField(
        max_length=30, choices=FEATURE_CATEGORY_CHOICES, verbose_name='دسته‌بندی',
    )
    problem = models.TextField(verbose_name='این قابلیت چه مشکلی را حل می‌کند؟')
    why_important = models.TextField(verbose_name='چرا برای شما مهم است؟')
    priority = models.CharField(
        max_length=10, choices=REQUEST_PRIORITY_CHOICES, default='medium', verbose_name='اولویت',
    )
    status = models.CharField(
        max_length=20, choices=REQUEST_STATUS_CHOICES, default='submitted', verbose_name='وضعیت',
    )
    votes_count = models.PositiveIntegerField(default=0, verbose_name='تعداد رای')
    follows_count = models.PositiveIntegerField(default=0, verbose_name='تعداد دنبال‌کننده')
    linked_feature = models.ForeignKey(
        ProductFeature, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='requests', verbose_name='قابلیت مرتبط',
    )
    released_in = models.ForeignKey(
        ProductRelease, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='shipped_requests', verbose_name='نسخه انتشار',
    )
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انتشار قابلیت')
    release_note = models.TextField(blank=True, verbose_name='توضیح انتشار')
    staff_note = models.TextField(blank=True, verbose_name='توضیح مدیر')
    is_public = models.BooleanField(default=True, verbose_name='نمایش عمومی')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پیشنهاد قابلیت'
        verbose_name_plural = 'پیشنهادهای قابلیت'
        ordering = ['-votes_count', '-created_at']
        indexes = [
            models.Index(fields=['status', '-votes_count']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['category', 'status']),
        ]

    def __str__(self):
        return self.title

    def get_status_display_fa(self):
        return dict(REQUEST_STATUS_CHOICES).get(self.status, self.status)

    def get_priority_display_fa(self):
        return dict(REQUEST_PRIORITY_CHOICES).get(self.priority, self.priority)

    def get_category_display_fa(self):
        return dict(FEATURE_CATEGORY_CHOICES).get(self.category, self.category)


class FeatureVote(models.Model):
    """رای کاربر به پیشنهاد قابلیت (حداکثر یک رای)."""

    request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE,
        related_name='votes', verbose_name='پیشنهاد',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='feature_votes', verbose_name='کاربر',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رای پیشنهاد'
        verbose_name_plural = 'رای‌های پیشنهاد'
        constraints = [
            models.UniqueConstraint(fields=['request', 'user'], name='uniq_feature_vote_user'),
        ]

    def __str__(self):
        return f'{self.user_id} → {self.request_id}'


class FeatureFollow(models.Model):
    """دنبال کردن پیشنهاد قابلیت."""

    request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE,
        related_name='follows', verbose_name='پیشنهاد',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='feature_follows', verbose_name='کاربر',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'دنبال‌کننده پیشنهاد'
        verbose_name_plural = 'دنبال‌کنندگان پیشنهاد'
        constraints = [
            models.UniqueConstraint(fields=['request', 'user'], name='uniq_feature_follow_user'),
        ]

    def __str__(self):
        return f'{self.user_id} follows {self.request_id}'


class FeatureRequestStatusLog(models.Model):
    """لاگ تغییر وضعیت پیشنهاد."""

    request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE,
        related_name='status_logs', verbose_name='پیشنهاد',
    )
    from_status = models.CharField(max_length=20, blank=True, verbose_name='از وضعیت')
    to_status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, verbose_name='به وضعیت')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='feature_request_status_logs', verbose_name='اقدام‌کننده',
    )
    note = models.TextField(blank=True, verbose_name='توضیح')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'لاگ وضعیت پیشنهاد'
        verbose_name_plural = 'لاگ‌های وضعیت پیشنهاد'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_id}: {self.from_status} → {self.to_status}'


class BugReport(models.Model):
    """گزارش مشکل کاربران."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bug_reports', verbose_name='گزارش‌دهنده',
    )
    title = models.CharField(max_length=200, verbose_name='عنوان مشکل')
    description = models.TextField(verbose_name='توضیح')
    severity = models.CharField(
        max_length=10, choices=BUG_SEVERITY_CHOICES, default='medium', verbose_name='شدت',
    )
    status = models.CharField(
        max_length=20, choices=BUG_STATUS_CHOICES, default='reported', verbose_name='وضعیت',
    )
    resolution_note = models.TextField(blank=True, verbose_name='توضیح رفع مشکل')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ رفع')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_bugs', verbose_name='رفع‌کننده',
    )
    staff_note = models.TextField(blank=True, verbose_name='توضیح مدیر')
    is_public = models.BooleanField(default=True, verbose_name='نمایش عمومی')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'گزارش باگ'
        verbose_name_plural = 'گزارش‌های باگ'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['severity', 'status']),
        ]

    def __str__(self):
        return self.title

    def get_status_display_fa(self):
        return dict(BUG_STATUS_CHOICES).get(self.status, self.status)

    def get_severity_display_fa(self):
        return dict(BUG_SEVERITY_CHOICES).get(self.severity, self.severity)


class ProductHubNotification(models.Model):
    """اعلان درون‌برنامه‌ای مرکز توسعه."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='product_hub_notifications', verbose_name='کاربر',
    )
    kind = models.CharField(max_length=30, choices=NOTIFICATION_KIND_CHOICES, verbose_name='نوع')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    body = models.TextField(blank=True, verbose_name='متن')
    link_path = models.CharField(max_length=300, blank=True, verbose_name='مسیر لینک')
    feature_request = models.ForeignKey(
        FeatureRequest, on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications', verbose_name='پیشنهاد مرتبط',
    )
    bug_report = models.ForeignKey(
        BugReport, on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications', verbose_name='باگ مرتبط',
    )
    is_read = models.BooleanField(default=False, verbose_name='خوانده شده')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اعلان مرکز توسعه'
        verbose_name_plural = 'اعلان‌های مرکز توسعه'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return self.title
