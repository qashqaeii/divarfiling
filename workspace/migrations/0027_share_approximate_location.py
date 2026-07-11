# Generated manually for public share approximate location

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0026_agency_share_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="listingpublicshare",
            name="approximate_location",
            field=models.BooleanField(
                default=False,
                help_text="حتی اگر مختصات دقیق باشد، در صفحه عمومی به\u200cصورت تقریبی نمایش داده شود.",
                verbose_name="نمایش موقعیت تقریبی",
            ),
        ),
        migrations.AddField(
            model_name="crmpropertypublicshare",
            name="approximate_location",
            field=models.BooleanField(
                default=False,
                help_text="حتی اگر مختصات دقیق باشد، در صفحه عمومی به\u200cصورت تقریبی نمایش داده شود.",
                verbose_name="نمایش موقعیت تقریبی",
            ),
        ),
    ]
