from django.contrib import admin

from community_forum.models import (
    ForumBan,
    ForumMember,
    ForumMessage,
    ForumModerationAudit,
    ForumPinnedNotice,
    ForumReport,
)


@admin.register(ForumMember)
class ForumMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'public_id', 'display_name', 'display_name_approved')
    search_fields = ('display_name', 'user__phone', 'user__first_name')
    raw_id_fields = ('user',)


@admin.register(ForumMessage)
class ForumMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'created_at', 'deleted_at')
    list_filter = ('deleted_at',)
    raw_id_fields = ('sender', 'reply_to')
    search_fields = ('body',)


@admin.register(ForumReport)
class ForumReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason')


@admin.register(ForumBan)
class ForumBanAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'starts_at', 'expires_at', 'revoked_at', 'can_read')
    raw_id_fields = ('member', 'created_by')


@admin.register(ForumPinnedNotice)
class ForumPinnedNoticeAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'created_at', 'expires_at')


@admin.register(ForumModerationAudit)
class ForumModerationAuditAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'actor', 'created_at')
    list_filter = ('action',)
