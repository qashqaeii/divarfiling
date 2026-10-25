from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0081_crmproperty_archive_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='rental_contract_end_date',
            field=models.DateField(blank=True, null=True, verbose_name='تاریخ پایان قرارداد اجاره'),
        ),
        migrations.AddField(
            model_name='reminder',
            name='property',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reminders',
                to='workspace.crmproperty',
                verbose_name='ملک',
            ),
        ),
        migrations.AddField(
            model_name='reminder',
            name='reminder_kind',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='نوع یادآور'),
        ),
    ]
