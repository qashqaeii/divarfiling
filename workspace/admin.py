from django.contrib import admin
from django.utils.html import format_html

from workspace.models import (
    CRMProperty, Customer, CustomerActivity, CustomerDocument, CustomerListing,
    CRMPropertyPublicShare, PropertyMatchAlert,
    Dataset, Listing, ListingMeta, ListingPublicShare, PriceHistory,
    PropertyContact, Reminder, Ticket, TicketAttachment, TicketMessage, WorkspaceSettings,
)
from workspace.services.support_tickets import close_ticket, reopen_ticket

from workspace.academy import admin as academy_admin  # noqa: F401


@admin.register(PropertyMatchAlert)
class PropertyMatchAlertAdmin(admin.ModelAdmin):
    list_display = ('customer', 'source', 'match_key', 'score', 'status', 'user', 'created_at')
    list_filter = ('source', 'status')
    search_fields = ('customer__name', 'match_key', 'listing_token')
    raw_id_fields = ('user', 'customer', 'crm_property')


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'row_count', 'transaction_type', 'created_at')
    list_filter = ('transaction_type', 'file_format')
    search_fields = ('name', 'user__username')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('token', 'title', 'price', 'neighborhood', 'dataset')
    search_fields = ('token', 'title')
    raw_id_fields = ('dataset',)


@admin.register(ListingMeta)
class ListingMetaAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'tag', 'is_favorite')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'customer_type', 'status', 'user')
    list_filter = ('status', 'customer_type')
    search_fields = ('name', 'phone', 'email')


@admin.register(CRMProperty)
class CRMPropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'deal_mode', 'transaction_status', 'city', 'user')
    list_filter = ('deal_mode', 'transaction_status', 'property_type')
    search_fields = ('title', 'city', 'neighborhood', 'token')


@admin.register(ListingPublicShare)
class ListingPublicShareAdmin(admin.ModelAdmin):
    list_display = ('share_token', 'listing', 'created_by', 'view_count', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('share_token', 'listing__title', 'created_by__phone')
    raw_id_fields = ('listing', 'created_by')


@admin.register(CRMPropertyPublicShare)
class CRMPropertyPublicShareAdmin(admin.ModelAdmin):
    list_display = (
        'share_token', 'property', 'created_by', 'view_count', 'is_active', 'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('share_token', 'property__title', 'created_by__phone')
    raw_id_fields = ('property', 'created_by')


admin.site.register(CustomerActivity)
admin.site.register(CustomerListing)
admin.site.register(PropertyContact)
admin.site.register(CustomerDocument)
admin.site.register(PriceHistory)
admin.site.register(Reminder)
admin.site.register(WorkspaceSettings)


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = ('author', 'body', 'is_staff_reply', 'is_internal', 'is_read', 'created_at')
    readonly_fields = ('created_at',)
    raw_id_fields = ('author',)


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0
    fields = ('original_filename', 'file', 'file_size', 'uploaded_by', 'message', 'created_at')
    readonly_fields = ('original_filename', 'file_size', 'created_at')
    raw_id_fields = ('uploaded_by', 'message')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_number', 'subject', 'user', 'category', 'priority',
        'status_badge', 'assigned_to', 'user_has_unread', 'staff_has_unread',
        'last_message_at', 'created_at',
    )
    list_filter = ('status', 'priority', 'category', 'user_has_unread', 'staff_has_unread', 'created_at')
    search_fields = ('ticket_number', 'subject', 'description', 'user__phone', 'user__username')
    raw_id_fields = ('user', 'assigned_to')
    readonly_fields = (
        'ticket_number', 'created_at', 'updated_at', 'closed_at', 'last_message_at',
    )
    inlines = [TicketMessageInline, TicketAttachmentInline]
    date_hierarchy = 'created_at'
    list_select_related = ('user', 'assigned_to')
    actions = ['mark_in_review', 'mark_waiting_user', 'close_selected', 'reopen_selected']

    fieldsets = (
        (None, {
            'fields': (
                'ticket_number', 'user', 'subject', 'description',
                'category', 'priority', 'status', 'assigned_to',
            ),
        }),
        ('وضعیت خوانده‌شدن', {
            'fields': ('user_has_unread', 'staff_has_unread'),
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at', 'last_message_at', 'closed_at'),
        }),
    )

    @admin.display(description='وضعیت')
    def status_badge(self, obj):
        colors = {
            'open': '#2563eb',
            'in_review': '#7c3aed',
            'answered': '#059669',
            'waiting_user': '#d97706',
            'closed': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        label = obj.get_status_display()
        return format_html(
            '<span style="background:{}20;color:{};padding:2px 8px;border-radius:999px;font-size:11px">{}</span>',
            color, color, label,
        )

    @admin.action(description='علامت‌گذاری: در حال بررسی')
    def mark_in_review(self, request, queryset):
        updated = queryset.exclude(status='closed').update(status='in_review')
        self.message_user(request, f'{updated} تیکت به «در حال بررسی» تغییر کرد.')

    @admin.action(description='علامت‌گذاری: منتظر پاسخ کاربر')
    def mark_waiting_user(self, request, queryset):
        updated = queryset.exclude(status='closed').update(status='waiting_user', user_has_unread=False)
        self.message_user(request, f'{updated} تیکت به «منتظر پاسخ کاربر» تغییر کرد.')

    @admin.action(description='بستن تیکت‌های انتخاب‌شده')
    def close_selected(self, request, queryset):
        count = 0
        for ticket in queryset.exclude(status='closed'):
            close_ticket(ticket=ticket, by_user=request.user, staff=True)
            count += 1
        self.message_user(request, f'{count} تیکت بسته شد.')

    @admin.action(description='باز کردن مجدد تیکت‌های انتخاب‌شده')
    def reopen_selected(self, request, queryset):
        count = 0
        for ticket in queryset.filter(status='closed'):
            reopen_ticket(ticket=ticket)
            count += 1
        self.message_user(request, f'{count} تیکت باز شد.')

    def save_model(self, request, obj, form, change):
        if not obj.ticket_number:
            from workspace.services.support_tickets import generate_ticket_number
            obj.ticket_number = generate_ticket_number()
        super().save_model(request, obj, form, change)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'author', 'is_staff_reply', 'is_internal', 'is_read', 'created_at')
    list_filter = ('is_staff_reply', 'is_internal', 'is_read')
    search_fields = ('ticket__ticket_number', 'body', 'author__phone')
    raw_id_fields = ('ticket', 'author')
    readonly_fields = ('created_at',)


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'ticket', 'file_size', 'uploaded_by', 'created_at')
    search_fields = ('original_filename', 'ticket__ticket_number')
    raw_id_fields = ('ticket', 'message', 'uploaded_by')
    readonly_fields = ('created_at',)
