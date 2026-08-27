from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0020_management_automation_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='managementautomationrule',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('send_sms', 'ارسال SMS'),
                    ('management_alert', 'هشدار مدیریت'),
                    ('manual_review', 'بررسی دستی'),
                ],
                default='send_sms',
                max_length=24,
                verbose_name='نوع اقدام',
            ),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='cadence',
            field=models.CharField(
                choices=[('hourly', 'ساعتی'), ('daily', 'روزانه')],
                db_index=True,
                default='daily',
                max_length=16,
                verbose_name='Cadence',
            ),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='insight_key',
            field=models.CharField(blank=True, max_length=64, verbose_name='کلید Insight'),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='is_paused',
            field=models.BooleanField(db_index=True, default=False, verbose_name='متوقف موقت'),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='max_recipients_per_run',
            field=models.PositiveIntegerField(default=50, verbose_name='حداکثر گیرنده در هر اجرا'),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='max_sends_per_user',
            field=models.PositiveIntegerField(default=1, verbose_name='حداکثر ارسال به کاربر'),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='quiet_hours_end',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name='پایان ساعات سکوت (ساعت محلی)',
            ),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='quiet_hours_start',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name='شروع ساعات سکوت (ساعت محلی)',
            ),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='segment_key',
            field=models.CharField(blank=True, max_length=64, verbose_name='کلید سگمنت'),
        ),
        migrations.CreateModel(
            name='ManagementAutomationExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='شروع')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='پایان')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('running', 'در حال اجرا'),
                            ('completed', 'تکمیل\u200cشده'),
                            ('failed', 'ناموفق'),
                            ('skipped', 'رد شده'),
                        ],
                        db_index=True,
                        default='running',
                        max_length=16,
                        verbose_name='وضعیت',
                    ),
                ),
                ('dry_run', models.BooleanField(default=False, verbose_name='Dry Run')),
                ('matched_count', models.PositiveIntegerField(default=0, verbose_name='Match شده')),
                ('processed_count', models.PositiveIntegerField(default=0, verbose_name='پردازش\u200cشده')),
                ('success_count', models.PositiveIntegerField(default=0, verbose_name='موفق')),
                ('failed_count', models.PositiveIntegerField(default=0, verbose_name='ناموفق')),
                ('skipped_count', models.PositiveIntegerField(default=0, verbose_name='رد شده')),
                ('error_summary', models.TextField(blank=True, verbose_name='خلاصه خطا')),
                (
                    'rule',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='executions',
                        to='accounts.managementautomationrule',
                        verbose_name='قانون',
                    ),
                ),
            ],
            options={
                'verbose_name': 'اجرای Automation مدیریت',
                'verbose_name_plural': 'اجراهای Automation مدیریت',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='ManagementAutomationRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trigger_key', models.CharField(db_index=True, max_length=220, verbose_name='Trigger Key')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'در انتظار'),
                            ('sent', 'ارسال\u200cشده'),
                            ('skipped', 'رد شده'),
                            ('failed', 'ناموفق'),
                            ('dry_run', 'Dry Run'),
                            ('alert', 'هشدار'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=16,
                        verbose_name='وضعیت',
                    ),
                ),
                ('skipped_reason', models.CharField(blank=True, max_length=200, verbose_name='دلیل رد')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان ارسال')),
                ('converted_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان تبدیل')),
                ('conversion_type', models.CharField(blank=True, max_length=64, verbose_name='نوع تبدیل')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='متادیتا')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')),
                (
                    'execution',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='recipients',
                        to='accounts.managementautomationexecution',
                        verbose_name='اجرای Run',
                    ),
                ),
                (
                    'rule',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='recipient_logs',
                        to='accounts.managementautomationrule',
                        verbose_name='قانون',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='management_automation_recipients',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'گیرنده Automation مدیریت',
                'verbose_name_plural': 'گیرندگان Automation مدیریت',
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='managementautomationrecipient',
            constraint=models.UniqueConstraint(
                fields=('rule', 'trigger_key'),
                name='uniq_mgmt_auto_rule_trigger',
            ),
        ),
    ]
