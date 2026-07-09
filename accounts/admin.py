"""
پنل مدیریت کاربران، OTP و پیامک
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import OtpRequest, SmsMessageLog, User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'username',
        'email',
        'phone',
        'phone_verified',
        'is_affiliate',
        'is_staff',
        'date_joined',
    ]
    list_filter = [
        'is_staff',
        'is_superuser',
        'is_affiliate',
        'phone_verified',
        'date_joined',
    ]
    search_fields = ['username', 'email', 'phone']
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'اطلاعات تکمیلی',
            {
                'fields': (
                    'phone',
                    'phone_verified',
                    'phone_verified_at',
                    'national_id',
                    'is_affiliate',
                ),
            },
        ),
    )
    readonly_fields = ['phone_verified_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city']
    search_fields = ['user__username', 'user__email', 'user__phone', 'city']


@admin.register(OtpRequest)
class OtpRequestAdmin(admin.ModelAdmin):
    list_display = [
        'phone',
        'purpose',
        'created_at',
        'expires_at',
        'attempts',
        'is_consumed',
        'ip_address',
    ]
    list_filter = ['purpose', 'is_consumed', 'created_at']
    search_fields = ['phone', 'ip_address']
    readonly_fields = [
        'phone',
        'purpose',
        'code_hash',
        'created_at',
        'expires_at',
        'attempts',
        'max_attempts',
        'is_consumed',
        'consumed_at',
        'ip_address',
        'user_agent',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SmsMessageLog)
class SmsMessageLogAdmin(admin.ModelAdmin):
    list_display = [
        'phone',
        'purpose',
        'channel',
        'provider',
        'status',
        'pattern_code',
        'provider_message_id',
        'created_at',
    ]
    list_filter = ['status', 'channel', 'provider', 'purpose', 'created_at']
    search_fields = ['phone', 'provider_message_id', 'pattern_code', 'error_message']
    readonly_fields = [
        'phone',
        'purpose',
        'channel',
        'provider',
        'pattern_code',
        'status',
        'provider_message_id',
        'error_message',
        'otp_request',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
