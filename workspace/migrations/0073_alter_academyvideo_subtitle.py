from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0072_academyvideo_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='academyvideo',
            name='subtitle',
            field=models.TextField(blank=True, verbose_name='هدف درس'),
        ),
    ]
