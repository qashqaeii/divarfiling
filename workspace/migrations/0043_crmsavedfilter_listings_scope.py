# Generated manually for Sprint 2 — listings saved filters scope

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0042_customer_matching_tolerance_percent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crmsavedfilter',
            name='scope',
            field=models.CharField(
                choices=[
                    ('contacts', 'مخاطبین'),
                    ('properties', 'املاک'),
                    ('deals', 'معاملات'),
                    ('listings', 'فایلینگ'),
                ],
                max_length=20,
                verbose_name='بخش',
            ),
        ),
    ]
