from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobile_api', '0006_mobile_sync_operation'),
    ]

    operations = [
        migrations.AddField(
            model_name='mobilesyncoperation',
            name='payload_fingerprint',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='mobilesyncoperation',
            name='status',
            field=models.CharField(
                choices=[
                    ('ok', 'موفق'),
                    ('conflict', 'تعارض'),
                    ('processing', 'در حال پردازش'),
                ],
                default='ok',
                max_length=16,
            ),
        ),
    ]
