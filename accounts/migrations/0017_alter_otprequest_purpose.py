# Adds password_reset to OtpRequest.purpose choices (was missing from 0004 state on some DBs).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0016_lead_acquisition_step23_templates"),
    ]

    operations = [
        migrations.AlterField(
            model_name="otprequest",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("login", "ورود"),
                    ("register", "ثبت\u200cنام"),
                    ("verify_phone", "تأیید موبایل"),
                    ("password_reset", "بازیابی رمز"),
                    ("license_renewal", "تمدید لایسنس"),
                    ("system", "سیستمی"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="هدف",
            ),
        ),
    ]
