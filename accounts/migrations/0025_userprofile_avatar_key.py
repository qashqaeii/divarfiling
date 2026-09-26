from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0024_discount_policy_and_issuance'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar_key',
            field=models.CharField(
                blank=True,
                max_length=32,
                null=True,
                verbose_name='کلید آواتار پیش‌فرض',
            ),
        ),
    ]
