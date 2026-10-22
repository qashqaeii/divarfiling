from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0079_agency_space_item_archived_orphan_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='property_types',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='لیست خالی یعنی بدون محدودیت نوع ملک (مگر property_type legacy)',
                verbose_name='انواع ملک (ترجیح جستجو)',
            ),
        ),
    ]
