# Generated manually for CRMProperty tenant fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0033_crmproperty_is_vacant'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='tenant_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='نام مستاجر'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='tenant_phone',
            field=models.CharField(blank=True, max_length=20, verbose_name='شماره مستاجر'),
        ),
    ]
