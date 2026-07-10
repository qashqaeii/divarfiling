import re

from django.db import migrations, models


def forwards_copy_rooms(apps, schema_editor):
    Customer = apps.get_model('workspace', 'Customer')
    for customer in Customer.objects.exclude(rooms='').iterator():
        digits = re.sub(r'\D', '', customer.rooms or '')
        if not digits:
            continue
        try:
            value = int(digits)
        except ValueError:
            continue
        customer.rooms_min = value
        customer.save(update_fields=['rooms_min'])


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0023_crmproperty_owner_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='rooms_min',
            field=models.IntegerField(blank=True, null=True, verbose_name='اتاق از'),
        ),
        migrations.AddField(
            model_name='customer',
            name='rooms_max',
            field=models.IntegerField(blank=True, null=True, verbose_name='اتاق تا'),
        ),
        migrations.AddField(
            model_name='customer',
            name='year_min',
            field=models.IntegerField(blank=True, null=True, verbose_name='سال ساخت از'),
        ),
        migrations.AddField(
            model_name='customer',
            name='year_max',
            field=models.IntegerField(blank=True, null=True, verbose_name='سال ساخت تا'),
        ),
        migrations.AddField(
            model_name='customer',
            name='floor_min',
            field=models.IntegerField(blank=True, null=True, verbose_name='طبقه از'),
        ),
        migrations.AddField(
            model_name='customer',
            name='floor_max',
            field=models.IntegerField(blank=True, null=True, verbose_name='طبقه تا'),
        ),
        migrations.AddField(
            model_name='customer',
            name='want_parking',
            field=models.BooleanField(default=False, verbose_name='پارکینگ'),
        ),
        migrations.AddField(
            model_name='customer',
            name='want_storage',
            field=models.BooleanField(default=False, verbose_name='انباری'),
        ),
        migrations.AddField(
            model_name='customer',
            name='want_elevator',
            field=models.BooleanField(default=False, verbose_name='آسانسور'),
        ),
        migrations.RunPython(forwards_copy_rooms, migrations.RunPython.noop),
    ]
