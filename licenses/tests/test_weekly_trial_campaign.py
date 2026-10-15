"""تست کمپین هدیه ۷ روز دسترسی حرفه‌ای."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ai_workspace.services.quota import is_ai_unlimited_user
from licenses.models import License, LicenseCampaignGrant
from licenses.services.weekly_trial_campaign import (
    CAMPAIGN_DURATION_DAYS,
    evaluate_user_eligibility,
    grant_weekly_trial_to_user,
    run_weekly_trial_campaign,
    send_campaign_sms_for_grant,
)
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product, Transaction
from shop.services.plan_funnel import is_bi_production_order
from workspace.services.access import has_active_bot_license, has_purchased_bot_license

User = get_user_model()
CAMPAIGN = 'test_weekly_gift'
TEST_HW = 'd' * 64


class WeeklyTrialCampaignEligibilityTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-weekly-campaign',
            description='t',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
            order=1,
        )
        self.eligible = User.objects.create_user(
            username='eligible_user',
            password='pass',
            phone='09121112233',
        )

    def test_eligible_user_without_purchase(self):
        result = evaluate_user_eligibility(self.eligible, CAMPAIGN)
        self.assertTrue(result.eligible)
        self.assertEqual(result.reason, '')

    def test_excluded_after_paid_order(self):
        Order.objects.create(
            user=self.eligible,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        result = evaluate_user_eligibility(self.eligible, CAMPAIGN)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, 'has_paid_purchase')

    def test_excluded_when_active_license(self):
        order = Order.objects.create(
            user=self.eligible,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        License.objects.create(
            order=order,
            license_key='PAID-TEST-KEY1',
            plan=self.plan,
            status='active',
            max_activations=2,
            expires_at=timezone.now() + timedelta(days=10),
        )
        result = evaluate_user_eligibility(self.eligible, CAMPAIGN)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, 'has_paid_purchase')

    def test_excluded_after_campaign_grant(self):
        grant_weekly_trial_to_user(
            self.eligible,
            campaign_key=CAMPAIGN,
            plan=self.plan,
            dry_run=False,
        )
        other = User.objects.create_user(username='other', password='p', phone='09123334455')
        result = evaluate_user_eligibility(self.eligible, CAMPAIGN)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason, 'already_granted_campaign')
        self.assertTrue(evaluate_user_eligibility(other, CAMPAIGN).eligible)


@override_settings(AI_LICENSED_UNLIMITED=True)
class WeeklyTrialCampaignGrantTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-weekly-grant',
            description='t',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
            order=1,
        )
        self.user = User.objects.create_user(
            username='gift_user',
            password='pass',
            phone='09124445566',
        )
        self.client = APIClient()

    def test_grant_creates_granted_order_and_active_license(self):
        grant, status = grant_weekly_trial_to_user(
            self.user,
            campaign_key=CAMPAIGN,
            plan=self.plan,
        )
        self.assertEqual(status, 'granted')
        self.assertIsNotNone(grant)
        self.assertFalse(has_purchased_bot_license(self.user))
        self.assertTrue(has_active_bot_license(self.user))
        self.assertTrue(is_ai_unlimited_user(self.user))

        order = Order.objects.get(pk=grant.order_id)
        self.assertEqual(order.status, 'granted')
        self.assertEqual(order.amount, Decimal('0'))
        self.assertFalse(Transaction.objects.filter(order=order).exists())
        self.assertFalse(
            PlanFunnelEvent.objects.filter(event_type='payment_success', order=order).exists()
        )
        self.assertFalse(is_bi_production_order(order))

        lic = grant.license
        self.assertEqual(lic.status, 'active')
        delta = lic.expires_at - timezone.now()
        self.assertGreater(delta, timedelta(days=CAMPAIGN_DURATION_DAYS - 1, hours=23))
        self.assertLessEqual(delta, timedelta(days=CAMPAIGN_DURATION_DAYS, minutes=5))

    def test_grant_idempotent(self):
        grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        grant2, status = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        self.assertEqual(status, 'already_granted')
        self.assertEqual(LicenseCampaignGrant.objects.filter(user=self.user, campaign_key=CAMPAIGN).count(), 1)
        self.assertEqual(License.objects.filter(order__user=self.user).count(), 1)

    def test_expired_gift_blocks_access(self):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        lic = grant.license
        lic.expires_at = timezone.now() - timedelta(minutes=1)
        lic.save(update_fields=['expires_at'])
        lic.sync_expiration_status(save=True)
        self.assertFalse(has_active_bot_license(self.user))

    def test_real_purchase_after_gift_expired(self):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        lic = grant.license
        lic.expires_at = timezone.now() - timedelta(minutes=1)
        lic.status = 'expired'
        lic.save(update_fields=['expires_at', 'status'])
        paid_order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
            paid_at=timezone.now(),
        )
        paid_lic = License.objects.create(
            order=paid_order,
            license_key='REAL-PAID-KEY1',
            plan=self.plan,
            status='active',
            max_activations=2,
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.assertTrue(has_purchased_bot_license(self.user))
        self.assertTrue(has_active_bot_license(self.user))
        self.assertEqual(paid_lic.pk, License.objects.filter(order=paid_order).first().pk)

    @override_settings(LICENSE_ALLOW_LOCAL_DEV=True)
    def test_license_validate_after_activation(self):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        lic = grant.license
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': lic.license_key,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        lic.refresh_from_db()
        self.assertEqual(lic.status, 'active')
        resp2 = self.client.post('/api/licenses/validate/', {
            'license_key': lic.license_key,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['valid'])


class WeeklyTrialCampaignSmsTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-weekly-sms',
            description='t',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
        )
        self.user = User.objects.create_user(
            username='sms_user',
            password='pass',
            phone='09125556677',
        )

    @patch('licenses.services.weekly_trial_campaign._send_templated_or_simple_sms', return_value=True)
    def test_sms_only_after_successful_grant(self, _mock_send):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        ok, reason = send_campaign_sms_for_grant(grant)
        self.assertTrue(ok)
        self.assertEqual(reason, 'sent')
        grant.refresh_from_db()
        self.assertIsNotNone(grant.sms_sent_at)

    @patch('licenses.services.weekly_trial_campaign._send_templated_or_simple_sms', return_value=True)
    def test_no_sms_when_grant_failed(self, _mock_send):
        grant = LicenseCampaignGrant.objects.create(
            user=self.user,
            campaign_key=CAMPAIGN,
            status=LicenseCampaignGrant.Status.FAILED,
        )
        ok, reason = send_campaign_sms_for_grant(grant)
        self.assertFalse(ok)
        self.assertEqual(reason, 'not_granted')

    @patch('licenses.services.weekly_trial_campaign._send_templated_or_simple_sms', return_value=True)
    def test_sms_skipped_on_opt_out(self, _mock_send):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        self.user.marketing_sms_opt_out = True
        self.user.save(update_fields=['marketing_sms_opt_out'])
        ok, reason = send_campaign_sms_for_grant(grant)
        self.assertFalse(ok)
        self.assertEqual(reason, 'marketing_opt_out')


class WeeklyTrialCampaignCommandTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-weekly-cmd',
            description='t',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
        )
        self.user = User.objects.create_user(username='cmd_user', password='p', phone='09126667788')

    def test_dry_run_does_not_create_grant(self):
        stats = run_weekly_trial_campaign(
            campaign_key=CAMPAIGN,
            dry_run=True,
        )
        self.assertTrue(stats.dry_run)
        self.assertGreaterEqual(stats.eligible_count, 1)
        self.assertEqual(LicenseCampaignGrant.objects.count(), 0)

    def test_apply_with_limit(self):
        stats = run_weekly_trial_campaign(
            campaign_key=CAMPAIGN,
            apply=True,
            limit=1,
        )
        self.assertEqual(stats.grants_created, 1)
        self.assertTrue(LicenseCampaignGrant.objects.filter(campaign_key=CAMPAIGN).exists())
