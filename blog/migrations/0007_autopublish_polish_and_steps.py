# Migration: AI polish metadata and step history for systematic autopublish

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0006_systematic_article_autopublish'),
    ]

    operations = [
        migrations.AddField(
            model_name='systematicarticleautopublishrun',
            name='step_history',
            field=models.JSONField(blank=True, default=list, verbose_name='تاریخچه مراحل'),
        ),
        migrations.AddField(
            model_name='systematicarticleautopublishrun',
            name='ai_polish_report',
            field=models.JSONField(blank=True, default=dict, verbose_name='گزارش پولیش AI'),
        ),
        migrations.AddField(
            model_name='systematicarticleautopublishrun',
            name='retry_count',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='تعداد تلاش مجدد'),
        ),
        migrations.AlterField(
            model_name='systematicarticleautopublishrun',
            name='status',
            field=models.CharField(
                choices=[
                    ('candidate', 'کاندید'),
                    ('queued', 'در صف'),
                    ('generating', 'در حال تولید'),
                    ('ai_polishing', 'پولیش AI'),
                    ('ai_polish_failed', 'شکست پولیش AI'),
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
            ),
        ),
    ]
