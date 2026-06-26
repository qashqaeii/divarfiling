from django.contrib import admin

from mobile_api.models import MobileDevice, MobileNotification


@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'user', 'device_model', 'app_version', 'last_seen_at')
    search_fields = ('device_id', 'user__phone', 'user__username')
    readonly_fields = ('registered_at', 'last_seen_at')


@admin.register(MobileNotification)
class MobileNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('title', 'user__phone')
    readonly_fields = ('created_at', 'read_at')
