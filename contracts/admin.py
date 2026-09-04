"""ادمین قرارداد."""
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone

from contracts.models import (
    Contract,
    ContractAcceptance,
    ContractAuditEvent,
    ContractClause,
    ContractClauseDefinition,
    ContractInvitation,
    ContractLegalRule,
    ContractLegalSource,
    ContractParty,
    ContractVersion,
    ContractWitness,
)


@admin.register(ContractLegalSource)
class ContractLegalSourceAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'article', 'is_active')
    search_fields = ('code', 'title')
    list_filter = ('is_active',)


@admin.register(ContractClauseDefinition)
class ContractClauseDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'title', 'category', 'contract_type', 'version',
        'review_status', 'is_required', 'is_active',
    )
    list_filter = ('contract_type', 'category', 'review_status', 'is_active')
    search_fields = ('code', 'title', 'body_template')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ContractLegalRule)
class ContractLegalRuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'contract_type', 'status', 'warning_level', 'effective_from', 'effective_to')
    list_filter = ('contract_type', 'status', 'warning_level')
    search_fields = ('code', 'name')

    def save_model(self, request, obj, form, change):
        ef = obj.effective_from
        et = obj.effective_to
        if ef and et and ef > et:
            raise ValidationError('تاریخ «اعتبار از» نمی‌تواند بعد از «اعتبار تا» باشد.')
        overlap = ContractLegalRule.objects.filter(
            contract_type=obj.contract_type,
            rule_type=obj.rule_type,
            status='active',
        ).exclude(pk=obj.pk)
        for other in overlap:
            if not _date_ranges_overlap(ef, et, other.effective_from, other.effective_to):
                continue
            raise ValidationError(
                f'بازه زمانی با قاعده «{other.code}» هم‌پوشانی دارد.',
            )
        super().save_model(request, obj, form, change)


def _date_ranges_overlap(start_a, end_a, start_b, end_b):
    """None = open-ended boundary."""
    ref_start = start_a or timezone.localdate().replace(year=1900)
    ref_end = end_a or timezone.localdate().replace(year=2999)
    other_start = start_b or timezone.localdate().replace(year=1900)
    other_end = end_b or timezone.localdate().replace(year=2999)
    return ref_start <= other_end and other_start <= ref_end


class ContractPartyInline(admin.TabularInline):
    model = ContractParty
    extra = 0
    readonly_fields = ('mobile_verified', 'national_id_claimed')


class ContractVersionInline(admin.TabularInline):
    model = ContractVersion
    extra = 0
    readonly_fields = ('content_hash', 'published_at', 'is_published')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('internal_number', 'contract_type', 'status', 'deal', 'user', 'updated_at')
    list_filter = ('contract_type', 'status')
    search_fields = ('internal_number', 'title')
    readonly_fields = ('internal_number', 'verification_token_hash', 'created_at', 'updated_at')
    inlines = [ContractVersionInline]


@admin.register(ContractAuditEvent)
class ContractAuditEventAdmin(admin.ModelAdmin):
    list_display = ('contract', 'event_type', 'created_at', 'ip_address')
    list_filter = ('event_type',)
    readonly_fields = (
        'contract', 'version', 'event_type', 'actor_user', 'party',
        'metadata', 'ip_address', 'user_agent', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ContractInvitation)
class ContractInvitationAdmin(admin.ModelAdmin):
    list_display = ('contract', 'mobile', 'sms_status', 'opened_at', 'created_at')
    list_filter = ('sms_status', 'is_revoked')
    readonly_fields = ('token_hash',)
