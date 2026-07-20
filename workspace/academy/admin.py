from django.contrib import admin

from workspace.academy.models import (
    AcademyBadge,
    AcademyEvent,
    AcademyMission,
    AcademyMissionStep,
    AcademyVideo,
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


@admin.register(AcademyVideo)
class AcademyVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'path', 'order', 'duration_seconds', 'is_launch', 'is_public', 'is_active')
    list_filter = ('path', 'is_launch', 'is_public', 'is_active')
    search_fields = ('title', 'slug', 'file_name')
    raw_id_fields = ('path',)


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
