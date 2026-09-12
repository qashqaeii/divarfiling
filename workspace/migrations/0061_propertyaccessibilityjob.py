# Generated manually for property accessibility jobs hardening.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0060_merge_20260910_1610'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PropertyAccessibilityJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('generation_id', models.CharField(db_index=True, max_length=36, verbose_name='شناسه نسل')),
                ('status', models.CharField(
                    choices=[
                        ('queued', 'در صف'),
                        ('running', 'در حال اجرا'),
                        ('done', 'انجام شد'),
                        ('failed', 'ناموفق'),
                        ('cancelled', 'لغو شده'),
                    ],
                    db_index=True,
                    default='queued',
                    max_length=20,
                    verbose_name='وضعیت',
                )),
                ('attempts', models.PositiveSmallIntegerField(default=0, verbose_name='تلاش')),
                ('max_attempts', models.PositiveSmallIntegerField(default=3, verbose_name='حداکثر تلاش')),
                ('run_after', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='اجرای بعد از')),
                ('locked_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان قفل')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان پایان')),
                ('last_error', models.CharField(blank=True, max_length=500, verbose_name='آخرین خطا')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='accessibility_jobs',
                    to='workspace.crmproperty',
                    verbose_name='ملک',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='property_accessibility_jobs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'کار دسترسی ملک',
                'verbose_name_plural': 'کارهای دسترسی ملک',
            },
        ),
        migrations.AddIndex(
            model_name='propertyaccessibilityjob',
            index=models.Index(fields=['status', 'run_after'], name='workspace_p_status_4a8b2d_idx'),
        ),
        migrations.AddConstraint(
            model_name='propertyaccessibilityjob',
            constraint=models.UniqueConstraint(
                fields=('property', 'generation_id'),
                name='uniq_property_accessibility_generation',
            ),
        ),
    ]
