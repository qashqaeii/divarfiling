from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0008_transaction_zibal_audit_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='licenseplan',
            name='plan_type',
            field=models.CharField(
                choices=[
                    ('single', 'یک\u200cسیستمی'),
                    ('multi', 'چندسیستمی'),
                    ('lifetime', 'مادام\u200cالعمر'),
                    ('daily', 'یک\u200cروزه'),
                    ('monthly', 'یک\u200cماهه'),
                    ('quarterly', 'سه\u200cماهه'),
                    ('yearly', 'یک\u200cساله'),
                ],
                max_length=20,
                verbose_name='نوع پلن',
            ),
        ),
    ]
