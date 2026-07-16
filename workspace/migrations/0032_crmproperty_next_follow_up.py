from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0031_crm_agency_announcements'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='next_follow_up',
            field=models.DateField(blank=True, null=True, verbose_name='پیگیری بعدی'),
        ),
    ]
