from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_planfunnelevent_idempotency'),
    ]

    operations = [
        migrations.AddField(
            model_name='licenseplan',
            name='compare_at_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                help_text='برای نمایش آفر ویژه — اگر بیشتر از قیمت فروش باشد، خط‌خورده نمایش داده می‌شود.',
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='قیمت قبل از تخفیف (تومان)',
            ),
        ),
        migrations.AddField(
            model_name='licenseplan',
            name='is_featured',
            field=models.BooleanField(
                default=False,
                help_text='برچسب «پیشنهادی» روی کارت قیمت‌گذاری',
                verbose_name='پلن پیشنهادی',
            ),
        ),
        migrations.AddField(
            model_name='licenseplan',
            name='offer_badge',
            field=models.CharField(
                blank=True,
                help_text='مثلاً «آفر ویژه» — اگر خالی باشد و پلن پیشنهادی باشد، «پیشنهادی» نمایش داده می‌شود.',
                max_length=50,
                verbose_name='برچسب آفر',
            ),
        ),
        migrations.AddField(
            model_name='licenseplan',
            name='allow_bulk_purchase',
            field=models.BooleanField(
                default=False,
                help_text='امکان خرید چند لایسنس مستقل در یک سفارش — هر لایسنس یک کلید جدا',
                verbose_name='خرید چندتایی (آژانس)',
            ),
        ),
        migrations.AddField(
            model_name='licenseplan',
            name='min_quantity',
            field=models.PositiveIntegerField(
                default=1,
                help_text='فقط برای خرید چندتایی آژانس',
                verbose_name='حداقل تعداد',
            ),
        ),
        migrations.AddField(
            model_name='licenseplan',
            name='max_quantity',
            field=models.PositiveIntegerField(
                default=20,
                help_text='فقط برای خرید چندتایی آژانس',
                verbose_name='حداکثر تعداد',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='quantity',
            field=models.PositiveIntegerField(default=1, verbose_name='تعداد لایسنس'),
        ),
    ]
