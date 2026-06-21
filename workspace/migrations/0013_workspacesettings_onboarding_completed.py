from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0012_crm_agency_membership_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspacesettings',
            name='onboarding_completed',
            field=models.BooleanField(default=False, verbose_name='تور آموزشی میزکار'),
        ),
    ]
