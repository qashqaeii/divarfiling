from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0084_property_content_studio'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='streets',
            field=models.TextField(blank=True, verbose_name='خیابان‌های مورد نظر'),
        ),
    ]
