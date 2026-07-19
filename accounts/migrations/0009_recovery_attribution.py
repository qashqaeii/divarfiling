# Generated manually for Week 2 Recovery Attribution

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_planfunnelevent_idempotency'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0008_test_provider_accepted_action'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecoveryAttribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'attribution_model',
                    models.CharField(
                        blank=True,
                        choices=[('strict', 'Strict'), ('assisted', 'Assisted')],
                        max_length=16,
                        verbose_name='مدل نسبت‌دهی',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'در انتظار'),
                            ('matched', 'منطبق'),
                            ('no_match', 'بدون انطباق'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=16,
                        verbose_name='وضعیت',
                    ),
                ),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان پرداخت')),
                (
                    'lag_hours',
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=8,
                        null=True,
                        verbose_name='فاصله تا پرداخت (ساعت)',
                    ),
                ),
                (
                    'revenue_amount',
                    models.PositiveIntegerField(blank=True, null=True, verbose_name='درآمد (تومان)'),
                ),
                (
                    'matched_at',
                    models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='زمان انطباق'),
                ),
                (
                    'rule_version',
                    models.CharField(default='strict_v1', max_length=32, verbose_name='نسخه قانون'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='به‌روزرسانی')),
                (
                    'abandon_order',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='recovery_attributions_as_abandon',
                        to='shop.order',
                        verbose_name='سفارش رها شده',
                    ),
                ),
                (
                    'action_log',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='recovery_attribution',
                        to='accounts.marketingautomationactionlog',
                        verbose_name='لاگ اقدام',
                    ),
                ),
                (
                    'paid_order',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='recovery_attributions_as_paid',
                        to='shop.order',
                        verbose_name='سفارش پرداخت‌شده',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='recovery_attributions',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'نسبت‌دهی بازیابی',
                'verbose_name_plural': 'نسبت‌دهی‌های بازیابی',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'attribution_model'], name='accounts_re_status_8d4f2a_idx'),
                    models.Index(fields=['user', 'status'], name='accounts_re_user_id_5c91bb_idx'),
                    models.Index(fields=['abandon_order', 'status'], name='accounts_re_abandon_2e8c11_idx'),
                ],
            },
        ),
    ]
