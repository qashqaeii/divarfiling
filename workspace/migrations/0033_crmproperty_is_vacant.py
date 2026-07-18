# Generated manually for CRMProperty.is_vacant

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0032_crmproperty_next_follow_up'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='is_vacant',
            field=models.BooleanField(default=False, verbose_name='تخلیه'),
        ),
    ]
