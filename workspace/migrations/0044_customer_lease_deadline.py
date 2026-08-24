# Generated manually — مهلت اجاره برای متقاضی اجاره

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0043_crmsavedfilter_listings_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='lease_deadline',
            field=models.DateField(blank=True, null=True, verbose_name='مهلت اجاره'),
        ),
    ]
