# Generated manually for public_assistant

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='KnowledgeArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('article_id', models.CharField(max_length=80, unique=True, verbose_name='شناسه')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان')),
                ('category', models.CharField(max_length=80, verbose_name='دسته')),
                ('summary', models.TextField(blank=True, verbose_name='خلاصه')),
                ('body_markdown', models.TextField(verbose_name='متن کامل')),
                ('prerequisites', models.TextField(blank=True, verbose_name='پیش\u200cنیازها')),
                ('platforms', models.JSONField(blank=True, default=list, verbose_name='پلتفرم\u200cها')),
                ('subscription_note', models.CharField(blank=True, max_length=200, verbose_name='اشتراک/نقش')),
                ('limitations', models.TextField(blank=True, verbose_name='محدودیت\u200cها')),
                ('synonyms', models.JSONField(blank=True, default=list, verbose_name='مترادف\u200cها')),
                ('related_links', models.JSONField(blank=True, default=list, verbose_name='لینک\u200cها')),
                ('technical_refs', models.JSONField(blank=True, default=list, verbose_name='مراجع فنی')),
                ('reviewed_at', models.DateField(blank=True, null=True, verbose_name='آخرین بررسی')),
                ('source_path', models.CharField(blank=True, max_length=300, verbose_name='مسیر فایل')),
                ('content_hash', models.CharField(max_length=64, verbose_name='هش محتوا')),
                ('is_public', models.BooleanField(default=True, verbose_name='عمومی')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'مقاله دانشنامه',
                'verbose_name_plural': 'مقالات دانشنامه',
                'ordering': ['category', 'title'],
            },
        ),
        migrations.CreateModel(
            name='PublicChatSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ip_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message_count', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'نشست چت عمومی',
                'verbose_name_plural': 'نشست\u200cهای چت عمومی',
            },
        ),
        migrations.CreateModel(
            name='PublicAssistantUsageLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(blank=True, max_length=30)),
                ('model', models.CharField(blank=True, max_length=120)),
                ('status', models.CharField(max_length=20)),
                ('latency_ms', models.PositiveIntegerField(default=0)),
                ('input_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('output_tokens', models.PositiveIntegerField(blank=True, null=True)),
                ('error_code', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'session',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to='public_assistant.publicchatsession',
                        verbose_name='نشست',
                    ),
                ),
            ],
            options={
                'verbose_name': 'لاگ مصرف دستیار عمومی',
                'verbose_name_plural': 'لاگ\u200cهای مصرف دستیار عمومی',
            },
        ),
        migrations.CreateModel(
            name='PublicChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(max_length=16)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'session',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='messages',
                        to='public_assistant.publicchatsession',
                        verbose_name='نشست',
                    ),
                ),
            ],
            options={
                'verbose_name': 'پیام چت عمومی',
                'verbose_name_plural': 'پیام\u200cهای چت عمومی',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='KnowledgeChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_index', models.PositiveSmallIntegerField(verbose_name='شماره بخش')),
                ('heading', models.CharField(blank=True, max_length=200, verbose_name='عنوان بخش')),
                ('body', models.TextField(verbose_name='متن بخش')),
                ('search_blob', models.TextField(db_index=True, verbose_name='متن نرمال جست\u200cوجو')),
                (
                    'article',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='chunks',
                        to='public_assistant.knowledgearticle',
                        verbose_name='مقاله',
                    ),
                ),
            ],
            options={
                'verbose_name': 'بخش دانشنامه',
                'verbose_name_plural': 'بخش\u200cهای دانشنامه',
                'ordering': ['article_id', 'chunk_index'],
            },
        ),
        migrations.CreateModel(
            name='PublicAssistantFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_helpful', models.BooleanField(verbose_name='مفید بود')),
                ('comment', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'message',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='feedback',
                        to='public_assistant.publicchatmessage',
                        verbose_name='پیام',
                    ),
                ),
                (
                    'session',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='feedback',
                        to='public_assistant.publicchatsession',
                        verbose_name='نشست',
                    ),
                ),
            ],
            options={
                'verbose_name': 'بازخورد دستیار',
                'verbose_name_plural': 'بازخوردهای دستیار',
            },
        ),
        migrations.AddConstraint(
            model_name='knowledgechunk',
            constraint=models.UniqueConstraint(
                fields=('article', 'chunk_index'),
                name='uniq_knowledge_chunk_article_index',
            ),
        ),
    ]
