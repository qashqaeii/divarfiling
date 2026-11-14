from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0079_agency_space_item_archived_orphan_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='divaraccountsession',
            name='extraction_auto_opt_out',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='مدیر همگام‌سازی خودکار این نشست با خطوط استخراج را قطع کرده است',
            ),
        ),
    ]