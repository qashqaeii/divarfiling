"""تست کمپین بازاریابی پیامکی."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    MarketingAutomationActionLog,
    MarketingAutomationRun,
    MarketingCampaign,
    MarketingCampaignRecipient,
    SmsMessageLog,
)
from accounts.services.admin_marketing import (
    RECOVERY_SUPPRESS_SKIP_REASON,
    create_shared_discount,
    create_unique_discount,
    get_marketing_dashboard_stats,
    get_recovery_suppressed_phones,
    preview_segment,
    recently_marketed_phones,
    render_message,
)
from accounts.services.admin_marketing_send import create_campaign_draft, run_campaign_send
from accounts.services.pending_recovery import FLOW_KEY, live_send_idempotency_key
from shop.models import DiscountCode, LicensePlan, Order, Product
from shop.services.checkout_abandon import ensure_checkout_abandon_event

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
        self.assertIn('users_with_active_license', stats['segment_sizes'])

    def test_active_license_segment_preview(self):
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
            license_key='LIC-MKT-ACTIVE-1',
            plan=self.plan,
            status='active',
        )
        preview = preview_segment('users_with_active_license')
        phones = [r['phone'] for r in preview['recipients']]
        self.assertIn('09121111111', phones)

    def test_active_license_segment_excludes_without_license(self):
        preview = preview_segment('users_with_active_license')
        phones = [r['phone'] for r in preview['recipients']]
        self.assertNotIn('09121111111', phones)

    def test_active_license_campaign_send(self):
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
            license_key='LIC-MKT-SEND-1',
            plan=self.plan,
            status='active',
        )
        staff = User.objects.create_user(
            username='stafflic', password='pass1234', phone='09120000001', is_staff=True,
        )
        campaign = create_campaign_draft(
            name='تست لایسنس فعال',
            segment_key='users_with_active_license',
            message_template='سلام{name_part} — {product}: {link}',
            discount_mode='none',
            created_by=staff,
            dedupe_days=0,
        )
        run_campaign_send(campaign)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, MarketingCampaign.Status.COMPLETED)
        self.assertGreaterEqual(campaign.sent_count, 1)
        self.assertTrue(
            MarketingCampaignRecipient.objects.filter(
                campaign=campaign, phone='09121111111', status='sent',
            ).exists()
        )

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


@override_settings(
    SMS_ENABLED=True,
    SMS_PROVIDER='console',
    SITE_URL='https://divarfiling.ir',
    PENDING_RECOVERY_FLOW_ENABLED=True,
    RECOVERY_STEP_1_MIN_HOURS=2,
    RECOVERY_STEP_2_MIN_HOURS=24,
    RECOVERY_MAX_AGE_HOURS=72,
    RECOVERY_LOOKBACK_DAYS=7,
    RECOVERY_FREQUENCY_CAP_HOURS=24,
)
class MarketingRecoveryOverlapTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan()
        self.staff = User.objects.create_user(
            username='staffoverlap', password='pass1234', phone='09120001111', is_staff=True,
        )
        self.user = User.objects.create_user(
            username='overlap1', password='pass1234', phone='09121112222', first_name='رضا',
        )
        self.now = timezone.now()
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
            payment_method='zibal',
        )
        Order.objects.filter(pk=self.order.pk).update(
            created_at=self.now - timedelta(hours=5),
        )
        self.order.refresh_from_db()
        ensure_checkout_abandon_event(self.order)

    def test_pending_segment_excludes_active_recovery_phone(self):
        suppressed = get_recovery_suppressed_phones()
        self.assertIn('09121112222', suppressed)

        preview = preview_segment('pending_orders')
        phones = [r['phone'] for r in preview['recipients']]
        self.assertNotIn('09121112222', phones)

    @patch('accounts.services.admin_marketing.get_recovery_suppressed_phones', return_value=frozenset())
    def test_run_campaign_skips_active_recovery_at_send_time(self, _mock_suppress):
        run = MarketingAutomationRun.objects.create(
            flow_key=FLOW_KEY,
            mode=MarketingAutomationRun.Mode.LIVE,
            status=MarketingAutomationRun.Status.COMPLETED,
        )
        send_key = live_send_idempotency_key(
            order_id=self.order.pk,
            step_key='recovery_step_1',
            phone_hash='abc123',
            product_id=self.product.pk,
        )
        MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key='recovery_step_1',
            user=self.user,
            phone_hash='abc123',
            masked_phone='0912***22',
            order=self.order,
            product=self.product,
            action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            decision_key=f'live:decision:{send_key}',
            send_idempotency_key=send_key,
        )

        with patch(
            'accounts.services.admin_marketing_send.get_recovery_suppressed_phones',
            return_value=frozenset({'09121112222'}),
        ):
            campaign = create_campaign_draft(
                name='تست recovery overlap',
                segment_key='pending_orders',
                message_template='سلام {name_part}',
                discount_mode='none',
                created_by=self.staff,
                dedupe_days=0,
            )
            run_campaign_send(campaign, selected_phones=['09121112222'])

        campaign.refresh_from_db()
        self.assertEqual(campaign.skipped_count, 1)
        recipient = MarketingCampaignRecipient.objects.get(campaign=campaign, phone='09121112222')
        self.assertEqual(recipient.status, MarketingCampaignRecipient.Status.SKIPPED)
        self.assertEqual(recipient.skip_reason, RECOVERY_SUPPRESS_SKIP_REASON)

    def test_dashboard_stats_include_recovery_revenue_fields(self):
        stats = get_marketing_dashboard_stats()
        self.assertIn('campaign_revenue', stats)
        self.assertIn('recovery_revenue', stats)
        self.assertIn('total_assisted_revenue', stats)
        self.assertEqual(
            stats['total_assisted_revenue'],
            stats['campaign_revenue'] + stats['recovery_revenue'],
        )


@override_settings(SMS_ENABLED=True, SMS_PROVIDER='console')
class MarketingRecoveryBridgeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='staffbridge', password='pass1234', phone='09123334444', is_staff=True,
        )

    def test_marketing_page_shows_recovery_bridge(self):
        self.client.login(username='staffbridge', password='pass1234')
        resp = self.client.get(reverse('admin_panel_marketing'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مشاهده Recovery Center')
        self.assertContains(resp, 'Total Assisted Revenue')
