"""
پنل مدیریت کاربران، OTP و پیامک
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    AcquisitionAutomationCampaign,
    AcquisitionRun,
    CampaignEnrollment,
    CampaignMessage,
    CampaignStep,
    CampaignVariant,
    GrowthJourney,
    GrowthJourneyEvent,
    LeadAttribution,
    LeadCampaign,
    LeadImportBatch,
    LeadList,
    LeadListMember,
    LeadTouchpoint,
    MarketingAutomationActionLog,
    MarketingAutomationRun,
    MarketingCampaign,
    MarketingCampaignRecipient,
    ManagementAutomationRule,
    ManagementAutomationExecution,
    ManagementAutomationRecipient,
    MarketingLead,
    OtpRequest,
    SmsMessageLog,
    SuppressionEntry,
    User,
    UserProfile,
)

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

@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'segment_key', 'status', 'discount_mode',
        'sent_count', 'failed_count', 'skipped_count', 'created_at',
    ]
    list_filter = ['status', 'segment_key', 'discount_mode']
    search_fields = ['name', 'message_template']
    readonly_fields = [
        'recipients_total', 'sent_count', 'failed_count', 'skipped_count',
        'created_at', 'completed_at',
    ]


@admin.register(MarketingCampaignRecipient)
class MarketingCampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'phone', 'status', 'discount_code', 'created_at']
    list_filter = ['status']
    search_fields = ['phone']
    raw_id_fields = ['campaign', 'user', 'discount_code', 'sms_log']


@admin.register(MarketingAutomationRun)
class MarketingAutomationRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'flow_key', 'mode', 'status', 'would_send_count',
        'examined_count', 'started_at',
    ]
    list_filter = ['flow_key', 'mode', 'status']
    readonly_fields = [
        'flow_key', 'mode', 'started_at', 'finished_at', 'examined_count',
        'eligible_count', 'suppressed_count', 'would_send_count', 'error_count',
        'status', 'config_snapshot',
    ]


@admin.register(MarketingAutomationActionLog)
class MarketingAutomationActionLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'flow_key', 'step_key', 'masked_phone', 'action', 'created_at',
    ]
    list_filter = ['flow_key', 'step_key', 'action']
    search_fields = ['masked_phone', 'decision_key', 'send_idempotency_key', 'reason']
    readonly_fields = [
        'run', 'flow_key', 'step_key', 'user', 'phone_hash', 'masked_phone',
        'order', 'product', 'action', 'reason', 'metadata', 'decision_key',
        'send_idempotency_key', 'created_at',
    ]


@admin.register(LeadImportBatch)
class LeadImportBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_filename', 'city', 'district', 'status', 'created_at']
    list_filter = ['status', 'source']
    search_fields = ['file_hash', 'original_filename', 'city', 'district']
    readonly_fields = ['file_hash', 'preview_stats', 'created_at', 'committed_at']


@admin.register(MarketingLead)
class MarketingLeadAdmin(admin.ModelAdmin):
    list_display = [
        'phone_normalized', 'display_name', 'lead_type', 'status', 'city', 'district',
    ]
    list_filter = ['status', 'lead_type', 'source']
    search_fields = ['phone_normalized', 'display_name', 'public_token']


@admin.register(LeadList)
class LeadListAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'slug', 'city', 'district', 'created_at']
    search_fields = ['name', 'slug']


@admin.register(LeadCampaign)
class LeadCampaignAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'kind', 'status', 'is_pilot', 'created_at']
    list_filter = ['kind', 'status', 'is_pilot']


@admin.register(CampaignMessage)
class CampaignMessageAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'campaign', 'lead', 'variant', 'step', 'status', 'sms_cost_snapshot', 'requested_at',
    ]
    list_filter = ['status']
    search_fields = ['click_token', 'idempotency_key', 'lead__phone_normalized']
    readonly_fields = ['click_token', 'idempotency_key', 'requested_at']


@admin.register(LeadAttribution)
class LeadAttributionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'axis', 'attribution_kind', 'touch_model', 'lead', 'user', 'campaign', 'created_at',
    ]
    list_filter = ['axis', 'attribution_kind', 'touch_model']


@admin.register(SuppressionEntry)
class SuppressionEntryAdmin(admin.ModelAdmin):
    list_display = ['phone_normalized', 'reason', 'created_at']
    list_filter = ['reason']
    search_fields = ['phone_normalized'    ]


@admin.register(ManagementAutomationRule)
class ManagementAutomationRuleAdmin(admin.ModelAdmin):
    list_display = ['key', 'name', 'is_active', 'is_paused', 'cadence', 'action_type', 'cooldown_days', 'last_run_at', 'updated_at']
    list_filter = ['is_active', 'is_paused', 'cadence', 'action_type']
    search_fields = ['key', 'name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ManagementAutomationExecution)
class ManagementAutomationExecutionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'rule', 'status', 'dry_run', 'matched_count', 'success_count',
        'failed_count', 'skipped_count', 'started_at',
    ]
    list_filter = ['status', 'dry_run']
    readonly_fields = [
        'rule', 'started_at', 'finished_at', 'status', 'dry_run',
        'matched_count', 'processed_count', 'success_count', 'failed_count',
        'skipped_count', 'error_summary',
    ]


@admin.register(ManagementAutomationRecipient)
class ManagementAutomationRecipientAdmin(admin.ModelAdmin):
    list_display = ['id', 'rule', 'trigger_key', 'status', 'sent_at', 'skipped_reason']
    list_filter = ['status', 'rule']
    search_fields = ['trigger_key', 'skipped_reason']
    readonly_fields = [
        'execution', 'rule', 'user', 'trigger_key', 'status', 'skipped_reason',
        'sent_at', 'converted_at', 'conversion_type', 'metadata', 'created_at',
    ]


@admin.register(GrowthJourney)
class GrowthJourneyAdmin(admin.ModelAdmin):
    list_display = [
        'phone_normalized', 'stage', 'source', 'user', 'lead',
        'nurture_paused', 'suppressed', 'stage_entered_at', 'updated_at',
    ]
    list_filter = ['stage', 'source', 'suppressed', 'nurture_paused']
    search_fields = ['phone_normalized']
    raw_id_fields = ['user', 'lead']


@admin.register(GrowthJourneyEvent)
class GrowthJourneyEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'journey', 'event_type', 'stage_from', 'stage_to', 'created_at']
    list_filter = ['event_type', 'stage_to']
    raw_id_fields = ['journey']


admin.site.register(LeadListMember)
admin.site.register(CampaignVariant)
admin.site.register(CampaignStep)
admin.site.register(CampaignEnrollment)
admin.site.register(LeadTouchpoint)


@admin.register(AcquisitionAutomationCampaign)
class AcquisitionAutomationCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'name', 'is_active', 'city', 'next_run_at', 'last_run_at', 'created_at',
    ]
    list_filter = ['is_active', 'city']
    search_fields = ['name', 'city']
    readonly_fields = ['last_run_at', 'created_at']


@admin.register(AcquisitionRun)
class AcquisitionRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'campaign', 'status', 'district', 'phones_extracted', 'created_at', 'error_message',
    ]
    list_filter = ['status', 'campaign']
    readonly_fields = [
        'campaign', 'started_at', 'finished_at', 'scanned_posts', 'consultants_found',
        'phones_extracted', 'output_path', 'import_batch', 'lead_campaign', 'metrics', 'created_at',
    ]
    search_fields = ['district', 'error_message']
