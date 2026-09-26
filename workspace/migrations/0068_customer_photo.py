from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0067_align_agency_space_copy_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='crm/customer_photos/',
                verbose_name='تصویر مخاطب',
            ),
        ),
    ]
