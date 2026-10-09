from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0026_admin_management_ai_analysis'),
    ]

    operations = [
        migrations.CreateModel(
            name='PhoneDetectorExtractionLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(db_index=True, max_length=20, unique=True)),
                ('line_index', models.PositiveSmallIntegerField(default=0, help_text='ترتیب نمایش در پنل (۱، ۲، …)')),
                (
                    'operational_status',
                    models.CharField(
                        choices=[
                            ('active', 'فعال'),
                            ('running', 'در حال استخراج'),
                            ('blocked_captcha', 'محدودیت کپچا'),
                            ('cooldown', 'استراحت'),
                            ('paused', 'متوقف توسط مدیر'),
                            ('error', 'خطای فنی'),
                        ],
                        db_index=True,
                        default='active',
                        max_length=32,
                    ),
                ),
                (
                    'block_scope',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('line', 'خط'),
                            ('shared_session', 'نشست مشترک'),
                            ('shared_ip', 'IP مشترک'),
                        ],
                        default='',
                        max_length=32,
                    ),
                ),
                ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('last_error_at', models.DateTimeField(blank=True, null=True)),
                ('last_error_reason', models.TextField(blank=True)),
                ('error_count', models.PositiveIntegerField(default=0)),
                ('success_extract_count', models.PositiveIntegerField(default=0)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('status_detail', models.TextField(blank=True)),
                ('blocked_until', models.DateTimeField(blank=True, null=True)),
                ('last_run_id', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'خط استخراج phone-detector',
                'verbose_name_plural': 'خطوط استخراج phone-detector',
                'ordering': ['line_index', 'phone'],
            },
        ),
    ]
