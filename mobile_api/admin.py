from django.contrib import admin

from mobile_api.models import MobileDevice


@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'user', 'device_model', 'app_version', 'last_seen_at')
    search_fields = ('device_id', 'user__phone', 'user__username')
    readonly_fields = ('registered_at', 'last_seen_at')
