from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0010_crmproperty_deleted_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='pipeline_order',
            field=models.PositiveIntegerField(default=0, verbose_name='ترتیب کانبان'),
        ),
    ]
