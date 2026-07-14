"""تست کمپین بازاریابی پیامکی."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import MarketingCampaign, MarketingCampaignRecipient, SmsMessageLog
from accounts.services.admin_marketing import (
    create_shared_discount,
    create_unique_discount,
    get_marketing_dashboard_stats,
    preview_segment,
    recently_marketed_phones,
    render_message,
)
from accounts.services.admin_marketing_send import create_campaign_draft, run_campaign_send
from shop.models import DiscountCode, LicensePlan, Order, Product

User = get_user_model()


def _product_plan():
    product = Product.objects.create(
        title='میزکار تست',
        slug='mizkar-mkt-test',
        description='test',
        is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product,
        name='ماهانه',
        plan_type='monthly',
        price=200000,
        duration_days=30,
        is_active=True,
    )
    return product, plan


@override_settings(SMS_ENABLED=True, SMS_PROVIDER='console', SITE_URL='https://divarfiling.ir')
class MarketingSegmentTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan()
        self.user = User.objects.create_user(
            username='mkt1', password='pass1234', phone='09121111111', first_name='علی',
        )
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )

    def test_pending_segment_preview(self):
        preview = preview_segment('pending_orders')
        self.assertGreaterEqual(preview['count'], 1)
        phones = [r['phone'] for r in preview['sample']]
        self.assertIn('09121111111', phones)

    def test_pending_segment_excludes_paid_order_user(self):
        """کاربری که بعداً سفارش پرداخت‌شده گرفته نباید در سگمنت باشد."""
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        preview = preview_segment('pending_orders')
        phones = [r['phone'] for r in preview['recipients']]
        self.assertNotIn('09121111111', phones)

    def test_pending_segment_excludes_active_license_user(self):
        """کاربری با لایسنس فعال نباید در سگمنت سفارش معلق باشد."""
        from licenses.models import License

        paid = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        License.objects.create(
            order=paid,
            license_key='LIC-MKT-TEST-1',
            plan=self.plan,
            status='active',
        )
        preview = preview_segment('pending_orders')
        phones = [r['phone'] for r in preview['recipients']]
        self.assertNotIn('09121111111', phones)

    def test_marketing_dashboard_stats(self):
        stats = get_marketing_dashboard_stats()
        self.assertIn('campaigns_total', stats)
        self.assertIn('segment_sizes', stats)
        self.assertIn('pending_orders', stats['segment_sizes'])

    def test_render_message_placeholders(self):
        text = render_message(
            'سلام{name_part} کد {code} برای {product}',
            {'name_part': ' علی', 'code': 'ABC', 'product': 'میزکار'},
        )
        self.assertEqual(text, 'سلام علی کد ABC برای میزکار')

    def test_shared_and_unique_codes(self):
        shared = create_shared_discount(
            code='RECOVER15',
            discount_type='percentage',
            discount_value=15,
            max_uses=50,
            valid_days=7,
        )
        self.assertEqual(shared.code, 'RECOVER15')
        unique = create_unique_discount(
            discount_type='percentage',
            discount_value=10,
            valid_days=5,
        )
        self.assertTrue(unique.code.startswith('MK-'))
        self.assertEqual(unique.max_uses, 1)


@override_settings(SMS_ENABLED=True, SMS_PROVIDER='console', SITE_URL='https://divarfiling.ir')
class MarketingSendTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan()
        self.staff = User.objects.create_user(
            username='staffmkt', password='pass1234', phone='09120000000', is_staff=True,
        )
        self.user = User.objects.create_user(
            username='mkt2', password='pass1234', phone='09123333333',
        )
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )

    def test_run_campaign_shared_discount(self):
        campaign = create_campaign_draft(
            name='تست بازیابی',
            segment_key='pending_orders',
            message_template='کد {code} برای {product}: {link}',
            discount_mode='shared',
            created_by=self.staff,
            discount_type='percentage',
            discount_value=Decimal('15'),
            discount_valid_days=7,
            shared_code='TESTMKT15',
            dedupe_days=0,
        )
        run_campaign_send(campaign)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, MarketingCampaign.Status.COMPLETED)
        self.assertGreaterEqual(campaign.sent_count, 1)
        self.assertTrue(DiscountCode.objects.filter(code='TESTMKT15').exists())
        self.assertTrue(
            MarketingCampaignRecipient.objects.filter(
                campaign=campaign, phone='09123333333', status='sent',
            ).exists()
        )
        self.assertTrue(
            SmsMessageLog.objects.filter(phone='09123333333', purpose='marketing').exists()
        )

    def test_selected_phones_only(self):
        other = User.objects.create_user(
            username='mkt3', password='pass1234', phone='09126666666',
        )
        Order.objects.create(
            user=other,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )
        campaign = create_campaign_draft(
            name='تست انتخاب',
            segment_key='pending_orders',
            message_template='سلام',
            discount_mode='none',
            created_by=self.staff,
            dedupe_days=0,
        )
        run_campaign_send(campaign, selected_phones=['09123333333'])
        campaign.refresh_from_db()
        self.assertEqual(campaign.recipients_total, 1)
        self.assertEqual(campaign.sent_count, 1)
        self.assertFalse(
            MarketingCampaignRecipient.objects.filter(
                campaign=campaign, phone='09126666666',
            ).exists()
        )

    def test_dedupe_skips_recent_marketing(self):
        SmsMessageLog.objects.create(
            phone='09123333333',
            purpose='marketing',
            status=SmsMessageLog.Status.SENT,
            channel=SmsMessageLog.Channel.SIMPLE,
        )
        recently = recently_marketed_phones(['09123333333'], days=7)
        self.assertIn('09123333333', recently)

        campaign = create_campaign_draft(
            name='تست تکرار',
            segment_key='pending_orders',
            message_template='پیام تست',
            discount_mode='none',
            created_by=self.staff,
            dedupe_days=7,
        )
        run_campaign_send(campaign)
        campaign.refresh_from_db()
        self.assertGreaterEqual(campaign.skipped_count, 1)


@override_settings(SMS_ENABLED=True, SMS_PROVIDER='console')
class MarketingViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='staffview', password='pass1234', phone='09124444444', is_staff=True,
        )
        self.user = User.objects.create_user(
            username='normal', password='pass1234', phone='09125555555',
        )

    def test_staff_only(self):
        url = reverse('admin_panel_marketing')
        self.client.login(username='normal', password='pass1234')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))

        self.client.login(username='staffview', password='pass1234')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرکز اتوماسیون بازاریابی')
        self.assertContains(resp, 'سگمنت‌های هوشمند')

    def test_preview_json(self):
        self.client.login(username='staffview', password='pass1234')
        resp = self.client.get(reverse('admin_panel_marketing_preview'), {'segment': 'pending_orders'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('count', data)
