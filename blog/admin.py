"""
پنل مدیریت بلاگ
"""
from django.contrib import admin
from .models import (
    Category,
    MarketArticleLink,
    MarketArticleRun,
    Post,
    SystematicArticleAutoPublishConfig,
    SystematicArticleAutoPublishRun,
    Tag,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'is_published', 'views_count', 'created_at']
    list_filter = ['is_published', 'category', 'created_at']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['tags']
    readonly_fields = ['views_count', 'created_at', 'updated_at']


@admin.register(MarketArticleRun)
class MarketArticleRunAdmin(admin.ModelAdmin):
    list_display = ['market_key', 'status', 'dataset', 'confidence_score', 'valid_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['market_key']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MarketArticleLink)
class MarketArticleLinkAdmin(admin.ModelAdmin):
    list_display = ['market_key', 'post', 'primary_dataset', 'last_generated_at']
    search_fields = ['market_key']


@admin.register(SystematicArticleAutoPublishConfig)
class SystematicArticleAutoPublishConfigAdmin(admin.ModelAdmin):
    list_display = ['is_enabled', 'shadow_mode', 'max_daily_publish', 'quality_threshold', 'last_run_at']
    readonly_fields = ['updated_at', 'last_run_at']


@admin.register(SystematicArticleAutoPublishRun)
class SystematicArticleAutoPublishRunAdmin(admin.ModelAdmin):
    list_display = ['run_date', 'status', 'action', 'quality_score', 'dataset', 'published_at']
    list_filter = ['status', 'action', 'publish_mode', 'run_date']
    search_fields = ['dataset__name', 'failure_reasons']
    readonly_fields = ['created_at', 'updated_at']
