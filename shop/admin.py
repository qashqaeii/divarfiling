"""
پنل مدیریت فروشگاه
"""
from django.contrib import admin
from django.contrib import messages as admin_messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from .models import (
    Product, ProductMedia, LicensePlan, Order, Transaction,
    PaymentWebhookLog, DownloadLog, DiscountCode,
    ProductRating, ProductReview, ReviewHelpful,
    Announcement, Banner, PaymentSettings, CardTransferSubmission,
)
from .services.order_fulfillment import approve_card_transfer, reject_card_transfer


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1


class LicensePlanInline(admin.TabularInline):
    model = LicensePlan
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'repeat_purchase_discount', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'description']
    # prepopulated_fields حذف شد چون Django نمی‌تواند فارسی را به اسلاگ تبدیل کند
    # اسلاگ به صورت خودکار در متد save() مدل تولید می‌شود
    inlines = [ProductMediaInline, LicensePlanInline]
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'slug', 'description', 'short_description', 'features')
        }),
        ('رسانه و فایل', {
            'fields': ('video_url', 'download_file')
        }),
        ('تخفیف‌ها', {
            'fields': ('repeat_purchase_discount',),
            'description': 'درصد تخفیف برای خریدهای دوم به بعد این محصول'
        }),
        ('تنظیمات', {
            'fields': ('is_active', 'order')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'product', 'plan', 'amount', 'payment_method', 'status', 'discount_code', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at', 'discount_code']
    search_fields = ['id', 'user__username', 'user__email', 'discount_code__code']
    readonly_fields = ['id', 'created_at', 'paid_at']


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'zibal_enabled', 'card_transfer_enabled', 'bank_name', 'updated_at']
    fieldsets = (
        ('روش‌های پرداخت', {
            'fields': ('zibal_enabled', 'card_transfer_enabled'),
        }),
        ('اطلاعات کارت به کارت', {
            'fields': (
                'card_number', 'card_holder_name', 'bank_name', 'iban',
                'instructions', 'support_contact',
            ),
            'description': 'برای فعال شدن کارت به کارت، گزینه بالا را فعال و شماره کارت را وارد کنید.',
        }),
        ('زمان', {
            'fields': ('updated_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = PaymentSettings.objects.first()
        if obj:
            url = reverse('admin:shop_paymentsettings_change', args=[obj.pk])
            return HttpResponseRedirect(url)
        return super().changelist_view(request, extra_context)


@admin.register(CardTransferSubmission)
class CardTransferSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'reference_number', 'payer_name', 'status',
        'order_amount', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['reference_number', 'payer_name', 'order__id', 'order__user__username']
    readonly_fields = [
        'order', 'reference_number', 'payer_name', 'transferred_at',
        'receipt_preview', 'user_note', 'reviewed_by', 'reviewed_at',
        'created_at', 'updated_at',
    ]
    fields = [
        'order', 'status', 'reference_number', 'payer_name', 'transferred_at',
        'receipt_preview', 'user_note', 'admin_note',
        'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
    ]
    actions = ['approve_selected', 'reject_selected']
    list_per_page = 30

    @admin.display(description='مبلغ سفارش')
    def order_amount(self, obj):
        return f'{int(obj.order.amount):,} تومان'

    @admin.display(description='تصویر رسید')
    def receipt_preview(self, obj):
        if obj.receipt_image:
            from django.utils.html import format_html
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:120px;border-radius:8px;" /></a>',
                obj.receipt_image.url,
                obj.receipt_image.url,
            )
        return '—'

    @admin.action(description='تایید پرداخت‌های انتخاب‌شده')
    def approve_selected(self, request, queryset):
        count = 0
        for submission in queryset.filter(status='pending'):
            approve_card_transfer(submission, request.user)
            count += 1
        admin_messages.success(request, f'{count} درخواست تایید شد.')

    @admin.action(description='رد پرداخت‌های انتخاب‌شده')
    def reject_selected(self, request, queryset):
        count = 0
        for submission in queryset.filter(status='pending'):
            reject_card_transfer(submission, request.user)
            count += 1
        admin_messages.warning(request, f'{count} درخواست رد شد.')

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            old = CardTransferSubmission.objects.get(pk=obj.pk)
            if old.status == 'pending' and obj.status == 'approved':
                approve_card_transfer(obj, request.user)
                return
            if old.status == 'pending' and obj.status == 'rejected':
                reject_card_transfer(obj, request.user, obj.admin_note)
                return
        super().save_model(request, obj, form, change)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'zibal_track_id', 'zibal_ref_number', 'amount',
        'status', 'gateway_result_code', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['zibal_track_id', 'zibal_ref_number', 'order__id']
    readonly_fields = [
        'order', 'zibal_track_id', 'zibal_ref_number', 'amount', 'status',
        'gateway_result_code', 'gateway_message', 'callback_payload',
        'verify_payload', 'paid_amount_rial', 'card_number_masked',
        'created_at', 'verified_at',
    ]


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'ip_address', 'created_at']
    readonly_fields = ['payload', 'headers', 'ip_address', 'created_at']


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'order', 'ip_address', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'order__id']


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'used_count', 'max_uses', 'is_active', 'valid_from', 'valid_until', 'created_at']
    list_filter = ['discount_type', 'is_active', 'created_at', 'valid_from', 'valid_until']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('code', 'discount_type', 'discount_value', 'description')
        }),
        ('محدودیت‌ها', {
            'fields': ('max_uses', 'min_purchase_amount', 'valid_from', 'valid_until')
        }),
        ('وضعیت', {
            'fields': ('is_active', 'used_count')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # در حالت ویرایش
            return self.readonly_fields
        return ['used_count', 'created_at', 'updated_at']


@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at', 'updated_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['product__title', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'title', 'is_approved', 'is_verified_purchase', 'helpful_count', 'created_at']
    list_filter = ['is_approved', 'is_verified_purchase', 'created_at']
    search_fields = ['product__title', 'user__username', 'title', 'content']
    readonly_fields = ['helpful_count', 'created_at', 'updated_at']
    list_editable = ['is_approved']
    list_per_page = 50
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('product', 'user', 'rating', 'title', 'content')
        }),
        ('وضعیت', {
            'fields': ('is_approved', 'is_verified_purchase', 'helpful_count')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'user__username']
    readonly_fields = ['created_at']
    list_per_page = 50


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'order', 'show_from', 'show_until', 'created_at']
    list_filter = ['is_active', 'created_at', 'show_from', 'show_until']
    search_fields = ['title', 'content']
    list_editable = ['is_active', 'order']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'content')
        }),
        ('لینک', {
            'fields': ('link', 'link_text'),
            'description': 'در صورت نیاز می‌توانید لینک و متن لینک را وارد کنید'
        }),
        ('تنظیمات نمایش', {
            'fields': ('is_active', 'order', 'show_from', 'show_until')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'banner_type', 'is_active', 'order', 'show_from', 'show_until', 'created_at']
    list_filter = ['banner_type', 'is_active', 'created_at', 'show_from', 'show_until']
    search_fields = ['title', 'text_content']
    list_editable = ['is_active', 'order']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'banner_type')
        }),
        ('محتوا', {
            'fields': ('image', 'text_content'),
            'description': 'برای بنر تصویری، تصویر را آپلود کنید. برای بنر متنی، متن را وارد کنید.'
        }),
        ('لینک', {
            'fields': ('link', 'link_text'),
            'description': 'در صورت نیاز می‌توانید لینک و متن لینک را وارد کنید'
        }),
        ('تنظیمات نمایش', {
            'fields': ('is_active', 'order', 'show_from', 'show_until')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

