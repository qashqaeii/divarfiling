from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_acquisition_district_cursor'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagementAutomationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='کلید')),
                ('name', models.CharField(max_length=200, verbose_name='نام')),
                ('is_active', models.BooleanField(db_index=True, default=False, verbose_name='فعال')),
                ('cooldown_days', models.PositiveIntegerField(default=7, verbose_name='Cooldown (روز)')),
                ('message_template', models.TextField(blank=True, verbose_name='قالب پیام')),
                ('conditions', models.JSONField(blank=True, default=dict, verbose_name='شرایط')),
                ('last_run_at', models.DateTimeField(blank=True, null=True, verbose_name='آخرین اجرا')),
                ('activated_at', models.DateTimeField(blank=True, null=True, verbose_name='فعال\u200cسازی')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='به\u200cروزرسانی')),
                (
                    'activated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='management_automation_rules',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='فعال\u200cکننده',
                    ),
                ),
            ],
            options={
                'verbose_name': 'قانون خودکارسازی مدیریت',
                'verbose_name_plural': 'قوانین خودکارسازی مدیریت',
                'ordering': ['name'],
            },
        ),
    ]
