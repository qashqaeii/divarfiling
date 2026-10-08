from django import forms
from django.contrib import admin
from django.utils.html import format_html

from workspace.academy.cta import django_validate_action_url

from workspace.academy.models import (
    AcademyBadge,
    AcademyEvent,
    AcademyMission,
    AcademyMissionStep,
    AcademyVideo,
    AcademyVideoViewDaily,
    CuratedPath,
    CuratedPathVideo,
    LearningPath,
    UserAcademyBadge,
    UserAcademySettings,
    UserMissionProgress,
    UserVideoProgress,
)


class AcademyVideoInline(admin.TabularInline):
    model = AcademyVideo
    extra = 0
    fields = ('order', 'slug', 'title', 'file_name', 'duration_seconds', 'is_launch', 'is_active')


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'phase', 'order', 'is_public', 'is_active')
    list_filter = ('phase', 'is_public', 'is_active')
    search_fields = ('title', 'slug')
    inlines = [AcademyVideoInline]


class AcademyVideoAdminForm(forms.ModelForm):
    class Meta:
        model = AcademyVideo
        fields = '__all__'

    def clean_action_url(self):
        value = (self.cleaned_data.get('action_url') or '').strip()
        if value:
            django_validate_action_url(value)
        return value


@admin.register(AcademyVideo)
class AcademyVideoAdmin(admin.ModelAdmin):
    form = AcademyVideoAdminForm
    list_display = (
        'title', 'slug', 'path', 'order', 'duration_seconds',
        'views_count', 'has_poster', 'is_launch', 'is_public', 'is_active',
    )
    list_filter = ('path', 'is_launch', 'is_public', 'is_active')
    search_fields = ('title', 'slug', 'file_name')
    raw_id_fields = ('path',)
    readonly_fields = ('poster_preview', 'views_count')
    fieldsets = (
        (None, {
            'fields': ('path', 'slug', 'title', 'subtitle', 'order', 'duration_seconds'),
        }),
        ('فایل ویدیو', {
            'fields': ('file_name', 'file_path', 'video_url'),
        }),
        ('پوستر', {
            'fields': ('poster_image', 'poster_preview', 'poster_path'),
            'description': 'تصویر JPG یا PNG — قبل از پخش ویدیو نمایش داده می‌شود.',
        }),
        ('CTA و ماموریت', {
            'fields': (
                'action_url', 'action_label', 'auto_confirm_event', 'mission_step',
            ),
        }),
        ('وضعیت', {
            'fields': ('is_public', 'is_launch', 'is_active', 'views_count'),
        }),
    )

    @admin.display(boolean=True, description='پوستر')
    def has_poster(self, obj):
        return bool(obj.poster_image or obj.poster_path)

    @admin.display(description='پیش‌نمایش پوستر')
    def poster_preview(self, obj):
        if obj.poster_image:
            return format_html(
                '<img src="{}" alt="" style="max-height:140px;max-width:100%;border-radius:10px;border:1px solid #ddd;">',
                obj.poster_image.url,
            )
        poster, kind = obj.get_poster_context()
        if not poster:
            return '—'
        if kind == 'static':
            return format_html(
                '<span style="color:#666;">مسیر static قدیمی:</span> <code>{}</code>',
                obj.poster_path,
            )
        return format_html(
            '<img src="{}" alt="" style="max-height:140px;max-width:100%;border-radius:10px;border:1px solid #ddd;">',
            poster,
        )


class AcademyMissionStepInline(admin.TabularInline):
    model = AcademyMissionStep
    extra = 0
    raw_id_fields = ('video',)


@admin.register(AcademyMission)
class AcademyMissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'badge_slug', 'is_active')
    inlines = [AcademyMissionStepInline]


@admin.register(AcademyBadge)
class AcademyBadgeAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'level', 'condition_key')


class CuratedPathVideoInline(admin.TabularInline):
    model = CuratedPathVideo
    extra = 0
    raw_id_fields = ('video',)


@admin.register(CuratedPath)
class CuratedPathAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug')
    inlines = [CuratedPathVideoInline]


@admin.register(UserVideoProgress)
class UserVideoProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'video', 'watched_seconds', 'completed', 'updated_at')
    list_filter = ('completed',)
    raw_id_fields = ('user', 'video')


@admin.register(UserMissionProgress)
class UserMissionProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'mission', 'current_step', 'completed', 'completed_at')
    list_filter = ('completed',)
    raw_id_fields = ('user', 'mission')


@admin.register(UserAcademyBadge)
class UserAcademyBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    raw_id_fields = ('user', 'badge')


@admin.register(UserAcademySettings)
class UserAcademySettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'learning_level', 'mission_started_at', 'first_file_at', 'ttlv_seconds')
    raw_id_fields = ('user',)


@admin.register(AcademyEvent)
class AcademyEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'video', 'created_at')
    list_filter = ('event_type',)
    raw_id_fields = ('user', 'video')


@admin.register(AcademyVideoViewDaily)
class AcademyVideoViewDailyAdmin(admin.ModelAdmin):
    list_display = ('video', 'date', 'views')
    list_filter = ('date',)
    date_hierarchy = 'date'
    raw_id_fields = ('video',)
    ordering = ('-date', '-views')
