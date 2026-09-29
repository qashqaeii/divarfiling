from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0071_merge_crmproperty_area_and_customer_gender'),
    ]

    operations = [
        migrations.AddField(
            model_name='academyvideo',
            name='description',
            field=models.TextField(blank=True, verbose_name='شرح آموزش'),
        ),
    ]
