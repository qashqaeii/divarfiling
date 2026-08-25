from django.db import migrations, models


def backfill_deal_finance(apps, schema_editor):
    CRMDeal = apps.get_model('workspace', 'CRMDeal')
    fields = [
        'deal_kind', 'commission_mode',
        'buyer_commission_rate', 'seller_commission_rate',
        'buyer_commission_amount', 'seller_commission_amount',
        'advisor_share_percent', 'agency_share_percent',
        'advisor_commission', 'agency_commission',
        'commission_amount', 'deal_costs', 'received_amount', 'payout_status',
    ]
    batch = []
    for deal in CRMDeal.objects.all().iterator():
        total_rate = float(deal.commission_rate or 0) or 1.0
        deal.deal_kind = deal.deal_kind or 'sale'
        deal.commission_mode = deal.commission_mode or 'percent'
        deal.buyer_commission_rate = total_rate / 2.0
        deal.seller_commission_rate = total_rate / 2.0
        deal.advisor_share_percent = 70.0
        deal.agency_share_percent = 30.0
        basis = int(deal.contract_amount or deal.value or 0)
        total = int(deal.commission_amount or 0)
        if not total and basis:
            total = int(round(basis * total_rate / 100.0))
            deal.commission_amount = total
        if total:
            deal.buyer_commission_amount = total // 2
            deal.seller_commission_amount = total - deal.buyer_commission_amount
            deal.advisor_commission = int(round(total * 0.7))
            deal.agency_commission = total - deal.advisor_commission
        else:
            deal.buyer_commission_amount = 0
            deal.seller_commission_amount = 0
            deal.advisor_commission = 0
            deal.agency_commission = 0
        if deal.deal_costs is None:
            deal.deal_costs = 0
        if deal.received_amount is None:
            deal.received_amount = 0
        if not deal.payout_status:
            deal.payout_status = 'unpaid'
        batch.append(deal)
        if len(batch) >= 200:
            CRMDeal.objects.bulk_update(batch, fields)
            batch = []
    if batch:
        CRMDeal.objects.bulk_update(batch, fields)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0047_crmdeal_stage_changed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmdeal',
            name='deal_kind',
            field=models.CharField(
                choices=[('sale', 'فروش'), ('rent', 'اجاره')],
                default='sale',
                max_length=12,
                verbose_name='نوع معامله',
            ),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='commission_mode',
            field=models.CharField(
                choices=[('percent', 'درصد از ارزش'), ('fixed', 'مبلغ ثابت')],
                default='percent',
                max_length=12,
                verbose_name='نحوه محاسبه کمیسیون',
            ),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='buyer_commission_rate',
            field=models.FloatField(default=0.5, verbose_name='نرخ کمیسیون خریدار (%)'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='seller_commission_rate',
            field=models.FloatField(default=0.5, verbose_name='نرخ کمیسیون فروشنده (%)'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='buyer_commission_amount',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='کمیسیون خریدار'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='seller_commission_amount',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='کمیسیون فروشنده'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='advisor_share_percent',
            field=models.FloatField(default=70.0, verbose_name='سهم مشاور (%)'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='agency_share_percent',
            field=models.FloatField(default=30.0, verbose_name='سهم املاک (%)'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='advisor_commission',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='کمیسیون مشاور'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='agency_commission',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='کمیسیون املاک'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='deal_costs',
            field=models.BigIntegerField(default=0, verbose_name='هزینه‌های معامله'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='received_amount',
            field=models.BigIntegerField(default=0, verbose_name='مبلغ وصول‌شده'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='payout_status',
            field=models.CharField(
                choices=[
                    ('unpaid', 'وصول نشده'),
                    ('partial', 'نیمه‌وصول'),
                    ('paid', 'وصول شده'),
                    ('waived', 'بخشوده'),
                ],
                default='unpaid',
                max_length=12,
                verbose_name='وضعیت وصول',
            ),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='payout_notes',
            field=models.TextField(blank=True, verbose_name='یادداشت مالی'),
        ),
        migrations.AddField(
            model_name='workspacesettings',
            name='crm_finance_defaults',
            field=models.JSONField(blank=True, default=dict, verbose_name='پیش‌فرض کمیسیون و تقسیم مالی معاملات'),
        ),
        migrations.RunPython(backfill_deal_finance, noop_reverse),
    ]
