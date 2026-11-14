from django.db import migrations, models


def backfill_line_source(apps, schema_editor):
    Line = apps.get_model('accounts', 'PhoneDetectorExtractionLine')
    Line.objects.filter(divar_account_session_id__isnull=False).update(line_source='filing')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0031_userprofile_advisor_professional_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='phonedetectorextractionline',
            name='operational_status',
            field=models.CharField(
                choices=[
                    ('active', 'فعال'),
                    ('running', 'در حال استخراج'),
                    ('blocked_captcha', 'محدودیت کپچا'),
                    ('cooldown', 'استراحت'),
                    ('paused', 'متوقف توسط مدیر'),
                    ('error', 'خطای فنی'),
                    ('evicted', 'خارج از چرخه'),
                ],
                db_index=True,
                default='active',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='phonedetectorextractionline',
            name='line_source',
            field=models.CharField(
                choices=[('manual', 'OTP دستی مدیر'), ('filing', 'نشست فایلینگ')],
                db_index=True,
                default='manual',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='phonedetectorextractionline',
            name='admin_hold',
            field=models.BooleanField(db_index=True, default=False, help_text='توقف عمدی مدیر — همگام‌سازی خودکار فعال نمی‌کند'),
        ),
        migrations.RunPython(backfill_line_source, migrations.RunPython.noop),
    ]