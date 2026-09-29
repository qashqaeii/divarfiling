from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0069_crmproperty_extended_specs'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='gender',
            field=models.CharField(
                blank=True,
                choices=[('male', 'مرد'), ('female', 'زن')],
                max_length=10,
                null=True,
                verbose_name='جنسیت',
            ),
        ),
    ]
