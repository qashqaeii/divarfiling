# Phase 2.1.1 — pending recovery automation (not deployed to production yet)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_planfunnelevent_idempotency'),
        ('accounts', '0005_marketing_campaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='marketing_sms_opt_out',
            field=models.BooleanField(
                default=False,
                verbose_name='عدم دریافت پیامک بازاریابی',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='marketing_sms_opt_out_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='زمان Opt-out',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='marketing_sms_opt_out_source',
            field=models.CharField(
                blank=True,
                max_length=64,
                verbose_name='منبع Opt-out',
            ),
        ),
        migrations.CreateModel(
            name='MarketingAutomationRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flow_key', models.CharField(db_index=True, max_length=64, verbose_name='کلید Flow')),
                ('mode', models.CharField(
                    choices=[('dry_run', 'Dry Run'), ('live', 'Live')],
                    default='dry_run',
                    max_length=16,
                    verbose_name='حالت',
                )),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='شروع')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='پایان')),
                ('examined_count', models.PositiveIntegerField(default=0, verbose_name='بررسی\u200cشده')),
                ('eligible_count', models.PositiveIntegerField(default=0, verbose_name='واجد شرایط')),
                ('suppressed_count', models.PositiveIntegerField(default=0, verbose_name='حذف\u200cشده')),
                ('would_send_count', models.PositiveIntegerField(default=0, verbose_name='would_send')),
                ('error_count', models.PositiveIntegerField(default=0, verbose_name='خطا')),
                ('status', models.CharField(
                    choices=[
                        ('running', 'در حال اجرا'),
                        ('completed', 'تکمیل\u200cشده'),
                        ('failed', 'ناموفق'),
                    ],
                    db_index=True,
                    default='running',
                    max_length=16,
                    verbose_name='وضعیت',
                )),
                ('config_snapshot', models.JSONField(blank=True, default=dict, verbose_name='تنظیمات')),
            ],
            options={
                'verbose_name': 'اجرای Automation بازاریابی',
                'verbose_name_plural': 'اجراهای Automation بازاریابی',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='MarketingAutomationActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flow_key', models.CharField(db_index=True, max_length=64, verbose_name='کلید Flow')),
                ('step_key', models.CharField(db_index=True, max_length=32, verbose_name='مرحله')),
                ('phone_hash', models.CharField(db_index=True, max_length=64, verbose_name='هش شماره')),
                ('masked_phone', models.CharField(blank=True, max_length=20, verbose_name='شماره Mask')),
                ('action', models.CharField(
                    choices=[
                        ('would_send', 'Would Send'),
                        ('sent', 'Sent'),
                        ('provider_accepted', 'Provider Accepted'),
                        ('failed', 'Failed'),
                        ('suppressed', 'Suppressed'),
                        ('cancelled', 'Cancelled'),
                    ],
                    db_index=True,
                    default='would_send',
                    max_length=20,
                    verbose_name='اقدام',
                )),
                ('reason', models.CharField(blank=True, max_length=200, verbose_name='دلیل')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='متادیتا')),
                ('decision_key', models.CharField(max_length=220, unique=True, verbose_name='کلید تصمیم (شبیه\u200cسازی)')),
                ('send_idempotency_key', models.CharField(
                    blank=True,
                    max_length=200,
                    null=True,
                    unique=True,
                    verbose_name='کلید Idempotency ارسال واقعی',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')),
                ('order', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='marketing_automation_actions',
                    to='shop.order',
                    verbose_name='سفارش',
                )),
                ('product', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='marketing_automation_actions',
                    to='shop.product',
                    verbose_name='محصول',
                )),
                ('run', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='actions',
                    to='accounts.marketingautomationrun',
                    verbose_name='اجرای Run',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='marketing_automation_actions',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'لاگ اقدام Automation',
                'verbose_name_plural': 'لاگ\u200cهای اقدام Automation',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='marketingautomationactionlog',
            index=models.Index(
                fields=['flow_key', 'step_key', 'phone_hash'],
                name='accounts_ma_flow_ke_8a1f2d_idx',
            ),
        ),
    ]
