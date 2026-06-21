from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0009_crm_resource_share_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان حذف'),
        ),
    ]
