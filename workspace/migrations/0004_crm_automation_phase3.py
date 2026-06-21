from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workspace', '0003_crm_deals_visits'),
    ]

    operations = [
        migrations.AddField(
            model_name='reminder',
            name='recurrence',
            field=models.CharField(
                blank=True, choices=[
                    ('', 'یک\u200cبار'), ('weekly', 'هفتگی'),
                    ('biweekly', 'دو هفته\u200cای'), ('monthly', 'ماهانه'),
                ], default='', max_length=20, verbose_name='تکرار',
            ),
        ),
        migrations.AddField(
            model_name='reminder',
            name='series',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='occurrences', to='workspace.reminder', verbose_name='سری تکرار',
            ),
        ),
        migrations.CreateModel(
            name='CRMMessageTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='نام قالب')),
                ('category', models.CharField(
                    choices=[
                        ('پیگیری', 'پیگیری'), ('بازدید', 'بازدید'), ('پیشنهاد', 'پیشنهاد'),
                        ('خوش\u200cآمد', 'خوش\u200cآمد'), ('سفارشی', 'سفارشی'),
                    ], default='پیگیری', max_length=30, verbose_name='دسته',
                )),
                ('channel', models.CharField(
                    choices=[('واتساپ', 'واتساپ'), ('پیامک', 'پیامک')],
                    default='واتساپ', max_length=20, verbose_name='کانال',
                )),
                ('body', models.TextField(verbose_name='متن قالب')),
                ('is_system', models.BooleanField(default=False, verbose_name='پیش\u200cفرض سیستم')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='crm_message_templates', to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'قالب پیام CRM',
                'verbose_name_plural': 'قالب\u200cهای پیام CRM',
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CRMAutomationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='نام قانون')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('trigger', models.CharField(
                    choices=[('inactive_days', 'بدون فعالیت (روز)')],
                    default='inactive_days', max_length=30, verbose_name='شرط',
                )),
                ('trigger_days', models.PositiveSmallIntegerField(default=3, verbose_name='تعداد روز')),
                ('trigger_statuses', models.CharField(
                    blank=True, default='جدید,در حال پیگیری', max_length=200,
                    verbose_name='وضعیت\u200cهای هدف',
                )),
                ('action', models.CharField(
                    choices=[
                        ('set_status', 'تغییر وضعیت'),
                        ('create_reminder', 'ایجاد یادآور'),
                    ], default='create_reminder', max_length=30, verbose_name='عمل',
                )),
                ('action_status', models.CharField(blank=True, max_length=30, verbose_name='وضعیت جدید')),
                ('action_reminder_title', models.CharField(
                    blank=True, default='پیگیری خودکار', max_length=200, verbose_name='عنوان یادآور',
                )),
                ('action_reminder_days', models.PositiveSmallIntegerField(
                    default=1, verbose_name='یادآور برای فردا (+روز)',
                )),
                ('last_run_at', models.DateTimeField(blank=True, null=True, verbose_name='آخرین اجرا')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='crm_automation_rules', to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'قانون اتوماسیون CRM',
                'verbose_name_plural': 'قوانین اتوماسیون CRM',
                'ordering': ['-is_active', 'name'],
            },
        ),
    ]
