from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0076_divar_account_sessions'),
    ]

    operations = [
        migrations.AddField(
            model_name='divaraccountsession',
            name='operation_lock_until',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name='DivarContactThrottle',
            fields=[
                ('throttle_key', models.CharField(max_length=128, primary_key=True, serialize=False)),
                ('expires_at', models.DateTimeField(db_index=True)),
            ],
            options={
                'verbose_name': 'Throttle دیوار',
                'verbose_name_plural': 'Throttleهای دیوار',
            },
        ),
    ]
