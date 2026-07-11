# Generated manually for agency share profile fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0025_share_defaults_and_social_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_address",
            field=models.TextField(blank=True, verbose_name="آدرس دفتر"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_city",
            field=models.CharField(blank=True, max_length=100, verbose_name="شهر دفتر"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_landline",
            field=models.CharField(blank=True, max_length=32, verbose_name="تلفن ثابت"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_landline_alt",
            field=models.CharField(blank=True, max_length=32, verbose_name="تلفن ثابت دوم"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_latitude",
            field=models.FloatField(blank=True, null=True, verbose_name="عرض جغرافیایی دفتر"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_longitude",
            field=models.FloatField(blank=True, null=True, verbose_name="طول جغرافیایی دفتر"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_social_links",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="لینک شبکه\u200cهای اجتماعی دفتر"
            ),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="agency_website",
            field=models.URLField(blank=True, verbose_name="وبسایت آژانس"),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="business_card_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="workspace/business_cards/",
                verbose_name="کارت ویزیت",
            ),
        ),
        migrations.AddField(
            model_name="workspacesettings",
            name="consultant_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="workspace/consultant_photos/",
                verbose_name="عکس مشاور",
            ),
        ),
        migrations.AlterField(
            model_name="workspacesettings",
            name="social_links",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="لینک شبکه\u200cهای اجتماعی مشاور"
            ),
        ),
    ]
