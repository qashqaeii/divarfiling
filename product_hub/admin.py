from django.contrib import admin

from product_hub.models import (
    BugReport,
    FeatureFollow,
    FeatureRequest,
    FeatureRequestStatusLog,
    FeatureVote,
    ProductFeature,
    ProductHubNotification,
    ProductRelease,
    ReleaseChange,
)


class ReleaseChangeInline(admin.TabularInline):
    model = ReleaseChange
    extra = 1


@admin.register(ProductFeature)
class ProductFeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'added_at', 'is_published', 'sort_order')
    list_filter = ('category', 'status', 'is_published')
    search_fields = ('title', 'summary', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('sort_order', 'title')


@admin.register(ProductRelease)
class ProductReleaseAdmin(admin.ModelAdmin):
    list_display = ('version', 'title', 'released_at', 'is_published', 'created_by')
    list_filter = ('is_published',)
    search_fields = ('version', 'title', 'summary')
    date_hierarchy = 'released_at'
    raw_id_fields = ('created_by',)
    inlines = [ReleaseChangeInline]


@admin.register(FeatureRequest)
class FeatureRequestAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'user', 'category', 'priority', 'status',
        'votes_count', 'follows_count', 'created_at',
    )
    list_filter = ('status', 'priority', 'category', 'is_public')
    search_fields = ('title', 'problem', 'user__username', 'user__phone')
    raw_id_fields = ('user', 'linked_feature', 'released_in')
    date_hierarchy = 'created_at'


@admin.register(FeatureVote)
class FeatureVoteAdmin(admin.ModelAdmin):
    list_display = ('request', 'user', 'created_at')
    raw_id_fields = ('request', 'user')


@admin.register(FeatureFollow)
class FeatureFollowAdmin(admin.ModelAdmin):
    list_display = ('request', 'user', 'created_at')
    raw_id_fields = ('request', 'user')


@admin.register(FeatureRequestStatusLog)
class FeatureRequestStatusLogAdmin(admin.ModelAdmin):
    list_display = ('request', 'from_status', 'to_status', 'actor', 'created_at')
    list_filter = ('to_status',)
    raw_id_fields = ('request', 'actor')
    readonly_fields = ('created_at',)


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'user', 'severity', 'status', 'resolved_at', 'created_at',
    )
    list_filter = ('status', 'severity', 'is_public')
    search_fields = ('title', 'description', 'user__username', 'user__phone')
    raw_id_fields = ('user', 'resolved_by')
    date_hierarchy = 'created_at'


@admin.register(ProductHubNotification)
class ProductHubNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'kind', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read')
    search_fields = ('title', 'body', 'user__username', 'user__phone')
    raw_id_fields = ('user', 'feature_request', 'bug_report')
