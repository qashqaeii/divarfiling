from django.contrib import admin

from workspace.models import (
    CRMProperty, Customer, CustomerActivity, CustomerDocument, CustomerListing,
    CRMPropertyPublicShare, PropertyMatchAlert,
    Dataset, Listing, ListingMeta, ListingPublicShare, PriceHistory,
    PropertyContact, Reminder, WorkspaceSettings,
)


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
