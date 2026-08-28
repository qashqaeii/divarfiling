# Generated manually for systematic article auto publish

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0005_marketarticlerun_building_failed'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystematicArticleAutoPublishConfig',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('is_enabled', models.BooleanField(default=False, verbose_name='انتشار خودکار فعال')),
                ('shadow_mode', models.BooleanField(default=True, verbose_name='حالت Shadow')),
                ('max_daily_publish', models.PositiveSmallIntegerField(default=1, verbose_name='حداکثر انتشار روزانه')),
                ('quality_threshold', models.PositiveSmallIntegerField(default=90, verbose_name='حداقل امتیاز انتشار')),
                ('publish_time', models.TimeField(blank=True, null=True, verbose_name='زمان ترجیحی اجرا')),
                ('min_records', models.PositiveIntegerField(default=150, verbose_name='حداقل رکورد')),
                ('min_valid_ratio', models.FloatField(default=0.85, verbose_name='حداقل نسبت داده معتبر')),
                ('max_dataset_age_days', models.PositiveIntegerField(default=90, verbose_name='حداکثر سن دیتاست (روز)')),
                ('min_insights', models.PositiveSmallIntegerField(default=2, verbose_name='حداقل Insight')),
                ('last_run_at', models.DateTimeField(blank=True, null=True, verbose_name='آخرین اجرا')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'تنظیمات انتشار خودکار',
                'verbose_name_plural': 'تنظیمات انتشار خودکار',
            },
        ),
        migrations.CreateModel(
            name='SystematicArticleAutoPublishRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('run_date', models.DateField(db_index=True, verbose_name='تاریخ اجرا (محلی)')),
                ('status', models.CharField(
                    choices=[
                        ('candidate', 'کاندید'),
                        ('queued', 'در صف'),
                        ('generating', 'در حال تولید'),
                        ('qa_running', 'کنترل کیفیت'),
                        ('qa_failed', 'رد QA'),
                        ('ready_to_publish', 'آماده انتشار'),
                        ('published', 'منتشرشده'),
                        ('updated', 'به‌روزرسانی‌شده'),
                        ('needs_review', 'نیازمند بررسی'),
                        ('skipped', 'رد شده'),
                    ],
                    db_index=True,
                    default='candidate',
                    max_length=24,
                    verbose_name='وضعیت',
                )),
                ('action', models.CharField(
                    choices=[
                        ('create_new', 'ساخت جدید'),
                        ('update_existing', 'به‌روزرسانی'),
                        ('skip', 'رد'),
                    ],
                    default='skip',
                    max_length=24,
                    verbose_name='اقدام',
                )),
                ('publish_mode', models.CharField(
                    choices=[
                        ('live', 'انتشار واقعی'),
                        ('shadow', 'Shadow'),
                        ('dry_run', 'Dry Run'),
                    ],
                    default='live',
                    max_length=16,
                    verbose_name='حالت اجرا',
                )),
                ('opportunity_score', models.FloatField(blank=True, null=True, verbose_name='امتیاز فرصت')),
                ('quality_score', models.FloatField(blank=True, null=True, verbose_name='امتیاز QA')),
                ('critical_errors_count', models.PositiveSmallIntegerField(default=0, verbose_name='خطاهای بحرانی')),
                ('qa_report', models.JSONField(blank=True, default=dict, verbose_name='گزارش QA')),
                ('failure_reasons', models.JSONField(blank=True, default=list, verbose_name='دلایل رد')),
                ('would_publish', models.BooleanField(default=False, verbose_name='در حالت واقعی منتشر می‌شد')),
                ('candidate_snapshot', models.JSONField(blank=True, default=dict, verbose_name='خلاصه کاندید')),
                ('published_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان انتشار')),
                ('post_publish_verified', models.BooleanField(default=False, verbose_name='تأیید پس از انتشار')),
                ('post_publish_report', models.JSONField(blank=True, default=dict, verbose_name='گزارش پس از انتشار')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('dataset', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='autopublish_runs',
                    to='workspace.dataset',
                    verbose_name='دیتاست',
                )),
                ('market_article_run', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='autopublish_runs',
                    to='blog.marketarticlerun',
                    verbose_name='اجرای مقاله',
                )),
                ('post', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='autopublish_runs',
                    to='blog.post',
                    verbose_name='مقاله',
                )),
            ],
            options={
                'verbose_name': 'اجرای انتشار خودکار',
                'verbose_name_plural': 'اجراهای انتشار خودکار',
                'ordering': ['-run_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='systematicarticleautopublishrun',
            index=models.Index(fields=['run_date', 'status'], name='blog_autopub_run_date_status_idx'),
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('blog', 'SystematicArticleAutoPublishConfig').objects.get_or_create(pk=1),
            reverse_code=migrations.RunPython.noop,
        ),
    ]
