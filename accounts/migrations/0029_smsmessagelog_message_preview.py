from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0028_phone_detector_line_divar_session'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsmessagelog',
            name='message_preview',
            field=models.CharField(
                blank=True,
                max_length=500,
                verbose_name='پیش‌نمایش متن (بدون کد حساس)',
            ),
        ),
    ]
