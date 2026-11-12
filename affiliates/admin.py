"""
پنل مدیریت افیلیت
"""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from .models import Affiliate, AffiliateSale, AffiliatePayout, Wallet, WalletTransaction, Withdrawal


@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'commission_rate', 'discount_percentage', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'code']
    readonly_fields = ['code', 'created_at']
    fields = ['user', 'code', 'commission_rate', 'discount_percentage', 'is_active', 'bank_account', 'bank_name', 'created_at']


class FinancialOwnerOnlyAdminMixin:
    """Keep financial changes outside generic delegated staff privileges."""

    @staticmethod
    def _is_owner(request):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
            and request.user.is_superuser
        )

    def has_add_permission(self, request):
        return self._is_owner(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._is_owner(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._is_owner(request) and super().has_delete_permission(request, obj)


@admin.register(AffiliateSale)
class AffiliateSaleAdmin(FinancialOwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['affiliate', 'order', 'commission_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['affiliate__code', 'order__id']


@admin.register(AffiliatePayout)
class AffiliatePayoutAdmin(FinancialOwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['affiliate', 'amount', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'created_at']
    search_fields = ['affiliate__code']
    filter_horizontal = ['sales']


@admin.register(Wallet)
class WalletAdmin(FinancialOwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['user', 'balance', 'total_earned', 'total_withdrawn', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(FinancialOwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['wallet', 'amount', 'transaction_type', 'description', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['wallet__user__username', 'description']
    readonly_fields = ['created_at']


@admin.register(Withdrawal)
class WithdrawalAdmin(FinancialOwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['wallet', 'amount', 'status', 'bank_name', 'created_at', 'processed_at']
    list_filter = ['status', 'created_at', 'bank_name']
    search_fields = ['wallet__user__username', 'bank_account']
    readonly_fields = [
        'wallet', 'amount', 'status', 'bank_account', 'bank_name',
        'account_holder', 'created_at', 'processed_at',
    ]
    actions = ['approve_withdrawals', 'complete_withdrawals', 'reject_withdrawals']

    def has_add_permission(self, request):
        # Withdrawal requests must be initiated by the account owner.
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep an auditable financial history.
        return False

    def _require_owner(self, request):
        if not self._is_owner(request):
            raise PermissionDenied('پردازش درخواست برداشت فقط برای مدیر ارشد مجاز است.')
    
    def approve_withdrawals(self, request, queryset):
        self._require_owner(request)
        count = 0
        for withdrawal in queryset.filter(status='pending'):
            if withdrawal.approve():
                self.log_change(request, withdrawal, 'withdrawal approved via admin action')
                count += 1
        self.message_user(request, f'{count} درخواست تایید شد.')
    approve_withdrawals.short_description = 'تایید درخواست‌های انتخاب شده'
    
    def complete_withdrawals(self, request, queryset):
        self._require_owner(request)
        count = 0
        for withdrawal in queryset.filter(status__in=['approved', 'processing']):
            if withdrawal.complete():
                self.log_change(request, withdrawal, 'withdrawal completed via admin action')
                count += 1
        self.message_user(request, f'{count} درخواست تکمیل شد.')
    complete_withdrawals.short_description = 'تکمیل پرداخت درخواست‌های انتخاب شده'
    
    def reject_withdrawals(self, request, queryset):
        self._require_owner(request)
        count = 0
        for withdrawal in queryset.filter(status='pending'):
            if withdrawal.reject('رد شده توسط ادمین'):
                self.log_change(request, withdrawal, 'withdrawal rejected via admin action')
                count += 1
        self.message_user(request, f'{count} درخواست رد شد.')
    reject_withdrawals.short_description = 'رد درخواست‌های انتخاب شده'

