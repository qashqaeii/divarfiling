"""
پنل مدیریت کاربران
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'phone', 'is_affiliate', 'is_staff', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_affiliate', 'date_joined']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('اطلاعات تکمیلی', {'fields': ('phone', 'national_id', 'is_affiliate')}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city']
    search_fields = ['user__username', 'user__email', 'city']

