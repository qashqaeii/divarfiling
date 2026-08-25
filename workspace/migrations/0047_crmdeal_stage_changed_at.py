from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0046_merge_20260824_workspace'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmdeal',
            name='stage_changed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان ورود به مرحله'),
        ),
    ]
