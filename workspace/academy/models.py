"""مدل‌های آکادمی فایلینگ دیوار."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import models


def academy_poster_upload_to(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower() or '.jpg'
    return f'academy/posters/{instance.slug}{ext}'


class LearningPath(models.Model):
    slug = models.SlugField(unique=True, verbose_name='شناسه')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    icon = models.CharField(max_length=50, default='fa-graduation-cap', verbose_name='آیکون')
    description = models.TextField(blank=True, verbose_name='توضیح')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب')
    is_public = models.BooleanField(default=False, verbose_name='عمومی')
    requires_role = models.CharField(max_length=32, blank=True, verbose_name='نقش لازم')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    phase = models.CharField(max_length=16, default='launch', verbose_name='فاز')

    class Meta:
        verbose_name = 'مسیر یادگیری'
        verbose_name_plural = 'مسیرهای یادگیری'
        ordering = ['order', 'id']

    def __str__(self):
        return self.title


class AcademyVideo(models.Model):
    path = models.ForeignKey(
        LearningPath, on_delete=models.CASCADE, related_name='videos',
        verbose_name='مسیر',
    )
    slug = models.SlugField(unique=True, verbose_name='شناسه')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    subtitle = models.TextField(blank=True, verbose_name='هدف درس')
    description = models.TextField(blank=True, verbose_name='شرح آموزش')
    file_name = models.CharField(max_length=255, verbose_name='نام فایل')
    file_path = models.CharField(max_length=512, verbose_name='مسیر فایل')
    poster_path = models.CharField(
        max_length=512, blank=True,
        verbose_name='مسیر پوستر (قدیمی)',
        help_text='فقط برای مسیر static قدیمی — ترجیحاً از «تصویر پوستر» استفاده کنید.',
    )
    poster_image = models.ImageField(
        upload_to=academy_poster_upload_to,
        blank=True,
        null=True,
        verbose_name='تصویر پوستر',
    )
    video_url = models.URLField(blank=True, verbose_name='URL CDN')
    duration_seconds = models.PositiveIntegerField(verbose_name='مدت (ثانیه)')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب')
    is_public = models.BooleanField(default=False, verbose_name='عمومی')
    is_launch = models.BooleanField(default=False, verbose_name='لانچ')
    action_url = models.CharField(max_length=512, blank=True, verbose_name='لینک CTA')
    action_label = models.CharField(max_length=100, blank=True, verbose_name='برچسب CTA')
    auto_confirm_event = models.CharField(max_length=64, blank=True, verbose_name='رویداد تأیید')
    mission_step = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='قدم ماموریت')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    views_count = models.PositiveIntegerField(default=0, verbose_name='تعداد بازدید')

    class Meta:
        verbose_name = 'ویدیوی آکادمی'
        verbose_name_plural = 'ویدیوهای آکادمی'
        ordering = ['path__order', 'order', 'id']

    def __str__(self):
        return self.title

    @property
    def duration_display(self) -> str:
        mins, secs = divmod(self.duration_seconds, 60)
        if mins and secs:
            return f'{mins} دقیقه و {secs} ثانیه'
        if mins:
            return f'{mins} دقیقه'
        return f'{secs} ثانیه'

    def file_exists(self) -> bool:
        if self.video_url:
            return True
        return (Path(settings.MEDIA_ROOT) / self.file_path / self.file_name).is_file()

    def get_stream_url(self) -> str:
        if self.video_url:
            return self.video_url
        if not self.file_exists():
            return ''
        rel = f'{self.file_path.strip("/")}/{self.file_name}'.replace('\\', '/')
        return f'{settings.MEDIA_URL.rstrip("/")}/{rel}'

    def get_poster_context(self) -> tuple[str, str]:
        if self.poster_image:
            return self.poster_image.url, 'media'
        if not self.poster_path:
            return '', ''
        if self.poster_path.startswith(('http://', 'https://', '/')):
            return self.poster_path, 'media'
        media_file = Path(settings.MEDIA_ROOT) / self.poster_path.lstrip('/')
        if media_file.is_file():
            rel = self.poster_path.lstrip('/').replace('\\', '/')
            return f'{settings.MEDIA_URL.rstrip("/")}/{rel}', 'media'
        return self.poster_path, 'static'

    def resolved_action_url(self) -> str:
        from workspace.academy.cta import resolve_academy_action_url
        return resolve_academy_action_url(self.action_url)

    def to_player_context(self) -> dict:
        url = self.get_stream_url()
        poster, poster_kind = self.get_poster_context()
        return {
            'available': bool(url),
            'mode': 'file' if url and not self.video_url else ('cdn' if url else 'none'),
            'src': url,
            'title': self.title,
            'subtitle': self.subtitle,
            'duration': self.duration_display,
            'poster': poster,
            'poster_kind': poster_kind,
            'slug': self.slug,
        }


class AcademyMission(models.Model):
    slug = models.SlugField(unique=True, default='day-one', verbose_name='شناسه')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    description = models.TextField(blank=True, verbose_name='توضیح')
    badge_slug = models.CharField(max_length=64, verbose_name='نشان')
    is_active = models.BooleanField(default=True, verbose_name='فعال')

    class Meta:
        verbose_name = 'ماموریت'
        verbose_name_plural = 'ماموریت‌ها'

    def __str__(self):
        return self.title


class AcademyMissionStep(models.Model):
    CONFIRM_VIDEO = 'video'
    CONFIRM_ACTION = 'action'
    CONFIRM_BOTH = 'both'
    CONFIRM_CHOICES = [
        (CONFIRM_VIDEO, 'فقط ویدیو'),
        (CONFIRM_ACTION, 'فقط عمل'),
        (CONFIRM_BOTH, 'ویدیو + عمل'),
    ]

    mission = models.ForeignKey(
        AcademyMission, on_delete=models.CASCADE, related_name='steps',
        verbose_name='ماموریت',
    )
    video = models.ForeignKey(AcademyVideo, on_delete=models.PROTECT, verbose_name='ویدیو')
    order = models.PositiveSmallIntegerField(verbose_name='ترتیب')
    action_url = models.CharField(max_length=512, verbose_name='لینک عمل')
    action_label = models.CharField(max_length=100, verbose_name='برچسب عمل')
    confirm_type = models.CharField(
        max_length=32, choices=CONFIRM_CHOICES, default=CONFIRM_BOTH,
        verbose_name='نوع تأیید',
    )
    auto_confirm_key = models.CharField(max_length=64, blank=True, verbose_name='کلید تأیید خودکار')

    class Meta:
        verbose_name = 'قدم ماموریت'
        verbose_name_plural = 'قدم‌های ماموریت'
        ordering = ['order']
        unique_together = [('mission', 'order')]

    def __str__(self):
        return f'{self.mission.title} — قدم {self.order}'


class AcademyBadge(models.Model):
    slug = models.SlugField(unique=True, verbose_name='شناسه')
    title = models.CharField(max_length=100, verbose_name='عنوان')
    description = models.TextField(verbose_name='توضیح')
    icon = models.CharField(max_length=50, default='fa-trophy', verbose_name='آیکون')
    level = models.PositiveSmallIntegerField(verbose_name='سطح')
    condition_key = models.CharField(max_length=64, verbose_name='شرط')

    class Meta:
        verbose_name = 'نشان'
        verbose_name_plural = 'نشان‌ها'
        ordering = ['level']

    def __str__(self):
        return self.title


class UserVideoProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='academy_video_progress', verbose_name='کاربر',
    )
    video = models.ForeignKey(
        AcademyVideo, on_delete=models.CASCADE,
        related_name='user_progress', verbose_name='ویدیو',
    )
    watched_seconds = models.PositiveIntegerField(default=0, verbose_name='ثانیه تماشا')
    completed = models.BooleanField(default=False, verbose_name='تکمیل')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان تکمیل')
    last_position = models.PositiveIntegerField(default=0, verbose_name='آخرین موقعیت')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پیشرفت ویدیو'
        verbose_name_plural = 'پیشرفت ویدیوها'
        unique_together = [('user', 'video')]

    def __str__(self):
        return f'{self.user_id} — {self.video.slug}'


class UserMissionProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='academy_mission_progress', verbose_name='کاربر',
    )
    mission = models.ForeignKey(
        AcademyMission, on_delete=models.CASCADE,
        related_name='user_progress', verbose_name='ماموریت',
    )
    current_step = models.PositiveSmallIntegerField(default=1, verbose_name='قدم فعلی')
    completed = models.BooleanField(default=False, verbose_name='تکمیل')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان تکمیل')
    step_states = models.JSONField(default=dict, blank=True, verbose_name='وضعیت قدم‌ها')

    class Meta:
        verbose_name = 'پیشرفت ماموریت'
        verbose_name_plural = 'پیشرفت ماموریت‌ها'
        unique_together = [('user', 'mission')]

    def __str__(self):
        return f'{self.user_id} — {self.mission.slug}'


class UserAcademyBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='academy_badges', verbose_name='کاربر',
    )
    badge = models.ForeignKey(
        AcademyBadge, on_delete=models.CASCADE,
        related_name='earned_by', verbose_name='نشان',
    )
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نشان کاربر'
        verbose_name_plural = 'نشان‌های کاربر'
        unique_together = [('user', 'badge')]

    def __str__(self):
        return f'{self.user_id} — {self.badge.slug}'


class UserAcademySettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='academy_settings', verbose_name='کاربر',
    )
    learning_level = models.PositiveSmallIntegerField(default=1, verbose_name='سطح UI')
    dismissed_contextual = models.JSONField(default=list, blank=True, verbose_name='بنرهای رد شده')
    mission_started_at = models.DateTimeField(null=True, blank=True, verbose_name='شروع ماموریت')
    first_file_at = models.DateTimeField(null=True, blank=True, verbose_name='اولین فایل')
    ttlv_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name='TTLV')
    tools_first_visit = models.BooleanField(default=True, verbose_name='اولین ورود ابزارها')

    class Meta:
        verbose_name = 'تنظیمات آکادمی'
        verbose_name_plural = 'تنظیمات آکادمی'

    def __str__(self):
        return f'Academy settings — {self.user_id}'


class CuratedPath(models.Model):
    slug = models.SlugField(unique=True, verbose_name='شناسه')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    description = models.TextField(verbose_name='توضیح')
    videos = models.ManyToManyField(
        AcademyVideo, through='CuratedPathVideo', related_name='curated_paths',
        verbose_name='ویدیوها',
    )

    class Meta:
        verbose_name = 'مسیر انتخابی'
        verbose_name_plural = 'مسیرهای انتخابی'

    def __str__(self):
        return self.title


class CuratedPathVideo(models.Model):
    path = models.ForeignKey(CuratedPath, on_delete=models.CASCADE, verbose_name='مسیر')
    video = models.ForeignKey(AcademyVideo, on_delete=models.CASCADE, verbose_name='ویدیو')
    order = models.PositiveSmallIntegerField(verbose_name='ترتیب')

    class Meta:
        verbose_name = 'ویدیوی مسیر انتخابی'
        verbose_name_plural = 'ویدیوهای مسیر انتخابی'
        ordering = ['order']
        unique_together = [('path', 'order'), ('path', 'video')]

    def __str__(self):
        return f'{self.path.slug} — {self.video.slug}'


class AcademyEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='academy_events', verbose_name='کاربر',
    )
    event_type = models.CharField(max_length=64, verbose_name='نوع رویداد')
    video = models.ForeignKey(
        AcademyVideo, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='events', verbose_name='ویدیو',
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رویداد آکادمی'
        verbose_name_plural = 'رویدادهای آکادمی'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type', '-created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} — {self.user_id}'


class AcademyVideoViewDaily(models.Model):
    """بازدید روزانه هر ویدیو — پایه Analytics پنل مدیریت."""

    video = models.ForeignKey(
        AcademyVideo,
        on_delete=models.CASCADE,
        related_name='daily_views',
        verbose_name='ویدیو',
    )
    date = models.DateField(verbose_name='تاریخ', db_index=True)
    views = models.PositiveIntegerField(default=0, verbose_name='بازدید')

    class Meta:
        verbose_name = 'بازدید روزانه ویدیو'
        verbose_name_plural = 'بازدیدهای روزانه ویدیو'
        ordering = ['-date', '-views']
        constraints = [
            models.UniqueConstraint(
                fields=['video', 'date'],
                name='workspace_academyvideoviewdaily_video_date_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['date', 'views']),
        ]

    def __str__(self):
        return f'{self.video_id} — {self.date}: {self.views}'
