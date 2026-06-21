"""
پنل مدیریت لایسنس‌ها
"""
from django.contrib import admin
from .models import License, LicenseActivation, AuditLog


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ['license_key', 'order', 'plan', 'status', 'max_activations', 'created_at']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['license_key', 'order__id', 'order__user__username']
    readonly_fields = ['license_key', 'created_at']


@admin.register(LicenseActivation)
class LicenseActivationAdmin(admin.ModelAdmin):
    list_display = ['license', 'label', 'hardware_fingerprint', 'assigned_user', 'is_active', 'activated_at']
    list_filter = ['is_active', 'activated_at']
    search_fields = ['license__license_key', 'hardware_fingerprint', 'label', 'assigned_user__username']
    readonly_fields = ['activated_at', 'assigned_at']
    raw_id_fields = ['assigned_user', 'assigned_by']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['license', 'action_type', 'ip_address', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['license__license_key', 'ip_address']
    readonly_fields = ['created_at', 'details']

