from django.contrib import admin

from public_assistant.models import (
    KnowledgeArticle,
    KnowledgeChunk,
    PublicAssistantFeedback,
    PublicAssistantUsageLog,
    PublicChatMessage,
    PublicChatSession,
)


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    readonly_fields = ('chunk_index', 'heading', 'body', 'search_blob')
    can_delete = False


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('article_id', 'title', 'category', 'is_active', 'is_public', 'reviewed_at', 'updated_at')
    list_filter = ('category', 'is_active', 'is_public')
    search_fields = ('article_id', 'title', 'summary')
    inlines = [KnowledgeChunkInline]
    readonly_fields = ('content_hash', 'source_path', 'created_at', 'updated_at')


@admin.register(PublicChatSession)
class PublicChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message_count', 'created_at', 'updated_at')
    readonly_fields = ('id', 'ip_hash', 'created_at', 'updated_at', 'message_count')


@admin.register(PublicAssistantUsageLog)
class PublicAssistantUsageLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'provider', 'model', 'latency_ms', 'created_at')
    list_filter = ('status', 'provider')
