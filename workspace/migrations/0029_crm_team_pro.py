"""CRM team pro — inbox, audit, sync log, goals."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0028_customer_social_channels'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان تخصیص'),
        ),
        migrations.AddField(
            model_name='customer',
            name='assigned_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_assignments_made', to=settings.AUTH_USER_MODEL,
                verbose_name='تخصیص‌دهنده',
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='team_visibility',
            field=models.CharField(
                choices=[
                    ('private', 'خصوصی'),
                    ('team_inbox', 'صندوق تیم'),
                    ('assigned', 'تخصیص‌یافته'),
                ],
                default='private', max_length=20, verbose_name='نمایش تیمی',
            ),
        ),
        migrations.AddField(
            model_name='crmagency',
            name='lead_routing_policy',
            field=models.CharField(
                choices=[
                    ('owner', 'مالک آژانس'),
                    ('inbox', 'صندوق سرنخ تیم'),
                    ('round_robin', 'چرخشی بین مشاوران'),
                ],
                default='inbox', max_length=20, verbose_name='سیاست تخصیص سرنخ API',
            ),
        ),
        migrations.AddField(
            model_name='crmagency',
            name='round_robin_cursor',
            field=models.PositiveIntegerField(default=0, verbose_name='شاخص چرخش'),
        ),
        migrations.CreateModel(
            name='CRMSyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sync_type', models.CharField(
                    choices=[('export', 'خروجی'), ('import', 'ورودی'), ('dry_run', 'پیش‌نمایش')],
                    max_length=12, verbose_name='نوع',
                )),
                ('stats', models.JSONField(blank=True, default=dict, verbose_name='آمار')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sync_logs', to='workspace.crmagency', verbose_name='آژانس',
                )),
                ('user', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_sync_logs', to=settings.AUTH_USER_MODEL, verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'لاگ همگام‌سازی',
                'verbose_name_plural': 'لاگ‌های همگام‌سازی',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CRMAgencyAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(max_length=40, verbose_name='رویداد')),
                ('payload', models.JSONField(blank=True, default=dict, verbose_name='جزئیات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_audit_actions', to=settings.AUTH_USER_MODEL, verbose_name='کاربر',
                )),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs', to='workspace.crmagency', verbose_name='آژانس',
                )),
            ],
            options={
                'verbose_name': 'ممیزی تیم',
                'verbose_name_plural': 'ممیزی‌های تیم',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CRMAgencyWebhookDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(max_length=40, verbose_name='رویداد')),
                ('status_code', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='کد HTTP')),
                ('success', models.BooleanField(default=False, verbose_name='موفق')),
                ('error', models.CharField(blank=True, max_length=300, verbose_name='خطا')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('webhook', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='deliveries', to='workspace.crmagencywebhook', verbose_name='وب‌هوک',
                )),
            ],
            options={
                'verbose_name': 'ارسال وب‌هوک',
                'verbose_name_plural': 'ارسال‌های وب‌هوک',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CRMAgencyTeamGoal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric', models.CharField(
                    choices=[
                        ('calls', 'تماس'), ('visits', 'بازدید'), ('deals_closed', 'معامله بسته'),
                    ],
                    max_length=20, verbose_name='شاخص',
                )),
                ('target_value', models.PositiveIntegerField(default=0, verbose_name='هدف')),
                ('period_start', models.DateField(verbose_name='شروع دوره')),
                ('period_end', models.DateField(verbose_name='پایان دوره')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team_goals', to='workspace.crmagency', verbose_name='آژانس',
                )),
                ('member', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='goals', to='workspace.crmagencymember', verbose_name='عضو',
                )),
            ],
            options={
                'verbose_name': 'هدف تیم',
                'verbose_name_plural': 'اهداف تیم',
                'ordering': ['-period_start'],
            },
        ),
    ]
