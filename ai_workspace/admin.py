from django.contrib import admin

from ai_workspace.models import AICache, AIQuota, AIUsageLog


@admin.register(AIQuota)
class AIQuotaAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'daily_limit', 'used_today', 'listing_summary_used',
        'crm_message_used', 'upload_brief_used', 'reset_date', 'is_unlimited',
    )
    search_fields = ('user__username', 'user__phone')
    raw_id_fields = ('user',)


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'user', 'feature_code', 'provider', 'model',
        'provider_attempt', 'status', 'cache_hit', 'latency_ms',
        'total_tokens', 'input_tokens', 'output_tokens',
    )
    list_filter = ('feature_code', 'provider', 'status', 'cache_hit')
    search_fields = ('user__username', 'entity_id')
    date_hierarchy = 'created_at'
    raw_id_fields = ('user',)


@admin.register(AICache)
class AICacheAdmin(admin.ModelAdmin):
    list_display = ('cache_key', 'feature_code', 'created_at', 'expires_at')
    list_filter = ('feature_code',)
    search_fields = ('cache_key',)
