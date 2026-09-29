from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0069_crmproperty_extended_specs'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crmproperty',
            name='area',
            field=models.FloatField(blank=True, null=True, verbose_name='متراژ بنا'),
        ),
    ]
