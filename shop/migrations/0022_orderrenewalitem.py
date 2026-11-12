from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0009_licensecampaigngrant_welcome_tracking'),
        ('shop', '0021_order_granted_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderRenewalItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'unit_original_price',
                    models.DecimalField(decimal_places=0, max_digits=12, verbose_name='قیمت واحد (قبل تخفیف)'),
                ),
                (
                    'unit_discount_amount',
                    models.DecimalField(decimal_places=0, default=0, max_digits=12, verbose_name='تخفیف واحد'),
                ),
                (
                    'unit_final_price',
                    models.DecimalField(decimal_places=0, max_digits=12, verbose_name='مبلغ نهایی واحد'),
                ),
                ('previous_expires_at', models.DateTimeField(blank=True, null=True, verbose_name='انقضای قبلی')),
                ('new_expires_at', models.DateTimeField(blank=True, null=True, verbose_name='انقضای پیش‌بینی‌شده')),
                ('applied_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان اعمال')),
                (
                    'apply_status',
                    models.CharField(
                        choices=[('pending', 'در انتظار'), ('applied', 'اعمال‌شده'), ('failed', 'ناموفق')],
                        db_index=True,
                        default='pending',
                        max_length=16,
                        verbose_name='وضعیت اعمال',
                    ),
                ),
                ('apply_error', models.CharField(blank=True, max_length=500, verbose_name='خطای اعمال')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')),
                (
                    'license',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='renewal_items',
                        to='licenses.license',
                        verbose_name='لایسنس',
                    ),
                ),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='renewal_items',
                        to='shop.order',
                        verbose_name='سفارش تمدید',
                    ),
                ),
            ],
            options={
                'verbose_name': 'آیتم تمدید سفارش',
                'verbose_name_plural': 'آیتم‌های تمدید سفارش',
                'ordering': ['license_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='orderrenewalitem',
            constraint=models.UniqueConstraint(
                fields=('order', 'license'),
                name='uniq_order_renewal_item_license',
            ),
        ),
    ]
