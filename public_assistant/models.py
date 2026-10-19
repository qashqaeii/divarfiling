"""مدل‌های پایگاه دانش و چت عمومی."""
from __future__ import annotations

import uuid

from django.db import models
class KnowledgeArticle(models.Model):
    """مقاله دانشنامه — منبع: فایل Markdown در ریپو."""

    article_id = models.CharField(max_length=80, unique=True, verbose_name='شناسه')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    category = models.CharField(max_length=80, verbose_name='دسته')
    summary = models.TextField(blank=True, verbose_name='خلاصه')
    body_markdown = models.TextField(verbose_name='متن کامل')
    prerequisites = models.TextField(blank=True, verbose_name='پیش‌نیازها')
    platforms = models.JSONField(default=list, blank=True, verbose_name='پلتفرم‌ها')
    subscription_note = models.CharField(max_length=200, blank=True, verbose_name='اشتراک/نقش')
    limitations = models.TextField(blank=True, verbose_name='محدودیت‌ها')
    synonyms = models.JSONField(default=list, blank=True, verbose_name='مترادف‌ها')
    related_links = models.JSONField(default=list, blank=True, verbose_name='لینک‌ها')
    technical_refs = models.JSONField(default=list, blank=True, verbose_name='مراجع فنی')
    reviewed_at = models.DateField(null=True, blank=True, verbose_name='آخرین بررسی')
    source_path = models.CharField(max_length=300, blank=True, verbose_name='مسیر فایل')
    content_hash = models.CharField(max_length=64, verbose_name='هش محتوا')
    is_public = models.BooleanField(default=True, verbose_name='عمومی')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مقاله دانشنامه'
        verbose_name_plural = 'مقالات دانشنامه'
        ordering = ['category', 'title']

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):
    """بخش قابل جست‌وجو از مقاله."""

    article = models.ForeignKey(
        KnowledgeArticle,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='مقاله',
    )
    chunk_index = models.PositiveSmallIntegerField(verbose_name='شماره بخش')
    heading = models.CharField(max_length=200, blank=True, verbose_name='عنوان بخش')
    body = models.TextField(verbose_name='متن بخش')
    search_blob = models.TextField(verbose_name='متن نرمال جست‌وجو', db_index=True)

    class Meta:
        verbose_name = 'بخش دانشنامه'
        verbose_name_plural = 'بخش‌های دانشنامه'
        ordering = ['article_id', 'chunk_index']
        constraints = [
            models.UniqueConstraint(
                fields=['article', 'chunk_index'],
                name='uniq_knowledge_chunk_article_index',
            ),
        ]

    def __str__(self):
        return f'{self.article.article_id}#{self.chunk_index}'


class PublicChatSession(models.Model):
    """نشست چت عمومی — بدون احراز هویت."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'نشست چت عمومی'
        verbose_name_plural = 'نشست‌های چت عمومی'


class PublicChatMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'

    session = models.ForeignKey(
        PublicChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='نشست',
    )
    role = models.CharField(max_length=16)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پیام چت عمومی'
        verbose_name_plural = 'پیام‌های چت عمومی'
        ordering = ['created_at']


class PublicAssistantFeedback(models.Model):
    session = models.ForeignKey(
        PublicChatSession,
        on_delete=models.CASCADE,
        related_name='feedback',
        verbose_name='نشست',
    )
    message = models.ForeignKey(
        PublicChatMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback',
        verbose_name='پیام',
    )
    is_helpful = models.BooleanField(verbose_name='مفید بود')
    comment = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'بازخورد دستیار'
        verbose_name_plural = 'بازخوردهای دستیار'


class PublicAssistantUsageLog(models.Model):
    """لاگ سبک مصرف — بدون ذخیره متن کامل مکالمه."""

    STATUS_OK = 'ok'
    STATUS_ERROR = 'error'
    STATUS_RATE_LIMIT = 'rate_limit'
    STATUS_FALLBACK = 'fallback'

    session = models.ForeignKey(
        PublicChatSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='نشست',
    )
    provider = models.CharField(max_length=30, blank=True)
    model = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20)
    latency_ms = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'لاگ مصرف دستیار عمومی'
        verbose_name_plural = 'لاگ‌های مصرف دستیار عمومی'
