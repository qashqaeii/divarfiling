from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0076_divar_account_sessions'),
        ('accounts', '0027_phone_detector_extraction_line'),
    ]

    operations = [
        migrations.AddField(
            model_name='phonedetectorextractionline',
            name='divar_account_session',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='extraction_line',
                to='workspace.divaraccountsession',
                verbose_name='نشست مرکزی فایلینگ',
            ),
        ),
    ]
