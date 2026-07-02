from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0018_property_match_alert'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='builder_buy_areas',
            field=models.TextField(blank=True, verbose_name='محله‌های هدف خرید (سازنده)'),
        ),
        migrations.AddField(
            model_name='customer',
            name='builder_buy_budget_max',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='بودجه خرید تا (سازنده)'),
        ),
        migrations.AddField(
            model_name='customer',
            name='builder_buy_budget_min',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='بودجه خرید از (سازنده)'),
        ),
        migrations.AddField(
            model_name='customer',
            name='builder_buy_max_area',
            field=models.IntegerField(blank=True, null=True, verbose_name='متراژ خرید تا (سازنده)'),
        ),
        migrations.AddField(
            model_name='customer',
            name='builder_buy_min_area',
            field=models.IntegerField(blank=True, null=True, verbose_name='متراژ خرید از (سازنده)'),
        ),
        migrations.AddField(
            model_name='customer',
            name='builder_buy_property_types',
            field=models.CharField(blank=True, max_length=120, verbose_name='انواع ملک هدف خرید (سازنده)'),
        ),
    ]
