from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0008_crm_resource_share'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmresourceshare',
            name='share_mode',
            field=models.CharField(
                choices=[('collaborative', 'اشتراک کامل'), ('confidential', 'ارسال محرمانه')],
                default='confidential',
                max_length=20,
                verbose_name='نوع اشتراک',
            ),
        ),
    ]
