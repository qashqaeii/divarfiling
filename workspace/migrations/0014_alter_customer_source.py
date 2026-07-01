from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0013_workspacesettings_onboarding_completed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='source',
            field=models.CharField(
                blank=True,
                choices=[
                    ('دیوار', 'دیوار'),
                    ('معرف', 'معرف'),
                    ('ورود به املاک', 'ورود به املاک'),
                    ('تماس ورودی', 'تماس ورودی'),
                    ('اینستاگرام', 'اینستاگرام'),
                    ('سایت', 'سایت'),
                    ('تلگرام', 'تلگرام'),
                    ('موبایل', 'موبایل'),
                    ('سایر', 'سایر'),
                ],
                max_length=30,
                verbose_name='منبع',
            ),
        ),
    ]
