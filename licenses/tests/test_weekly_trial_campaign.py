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
from licenses.services.management import _license_expiry_meta
from licenses.services.weekly_trial_campaign import (
    CAMPAIGN_DURATION_DAYS,
    WORKSPACE_CAMPAIGN_URL,
    build_campaign_sms_attributes,
    evaluate_user_eligibility,
    grant_weekly_trial_to_user,
    resolve_professional_gift_plan,
    run_campaign_sms_batch,
    run_weekly_trial_campaign,
    send_campaign_sms_for_grant,
    WeeklyTrialCampaignError,
)
from shop.bot_catalog import BOT_PRODUCT_SLUG
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product, Transaction
from shop.services.plan_funnel import is_bi_production_order
from workspace.services.access import has_active_bot_license, has_purchased_bot_license

User = get_user_model()
CAMPAIGN = 'test_weekly_gift'
TEST_HW = 'd' * 64


def _ensure_bot_monthly_plan():
    product, _ = Product.objects.get_or_create(
        slug=BOT_PRODUCT_SLUG,
        defaults={
            'title': 'ربات استخراج',
            'description': 'test',
            'is_active': True,
        },
    )
    if not product.is_active:
        product.is_active = True
        product.save(update_fields=['is_active'])
    plan = LicensePlan.objects.filter(
        product=product,
        plan_type='monthly',
        allow_bulk_purchase=False,
        is_active=True,
    ).first()
    if not plan:
        plan = LicensePlan.objects.create(
            product=product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
            order=1,
        )
    return product, plan


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
        self.assertEqual(grant.sms_status, LicenseCampaignGrant.SmsStatus.SENT)

    @patch('licenses.services.weekly_trial_campaign._send_templated_or_simple_sms', return_value=True)
    def test_sms_attributes_include_workspace_link(self, mock_send):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        send_campaign_sms_for_grant(grant)
        mock_send.assert_called_once()
        attrs = mock_send.call_args.kwargs.get('attributes') or {}
        self.assertEqual(attrs.get('link'), 'workspace/')
        self.assertIn(WORKSPACE_CAMPAIGN_URL, mock_send.call_args.kwargs.get('text', ''))

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
        grant.refresh_from_db()
        self.assertEqual(grant.sms_status, LicenseCampaignGrant.SmsStatus.SKIPPED)


class WeeklyTrialCampaignCommandTests(TestCase):
    def setUp(self):
        self.product, self.plan = _ensure_bot_monthly_plan()
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


class WeeklyTrialCampaignPlanResolutionTests(TestCase):
    def test_resolve_requires_bot_product_slug(self):
        with self.assertRaises(WeeklyTrialCampaignError):
            resolve_professional_gift_plan()

    def test_resolve_requires_monthly_individual_plan(self):
        Product.objects.create(
            title='ربات',
            slug=BOT_PRODUCT_SLUG,
            description='t',
            is_active=True,
        )
        with self.assertRaises(WeeklyTrialCampaignError):
            resolve_professional_gift_plan()

    def test_resolve_returns_monthly_individual_plan(self):
        _product, plan = _ensure_bot_monthly_plan()
        resolved = resolve_professional_gift_plan()
        self.assertEqual(resolved.pk, plan.pk)
        self.assertEqual(resolved.plan_type, 'monthly')
        self.assertFalse(resolved.allow_bulk_purchase)


class WeeklyTrialGiftDashboardExpiryTests(TestCase):
    def setUp(self):
        self.product, self.plan = _ensure_bot_monthly_plan()
        self.user = User.objects.create_user(username='dash_user', password='p', phone='09128889900')

    def test_health_percent_based_on_seven_day_gift_not_plan_duration(self):
        grant, _ = grant_weekly_trial_to_user(self.user, campaign_key=CAMPAIGN, plan=self.plan)
        lic = grant.license
        lic.expires_at = timezone.now() + timedelta(days=4)
        lic.save(update_fields=['expires_at'])
        meta = _license_expiry_meta(lic)
        self.assertEqual(meta['days_remaining'], 4)
        self.assertGreaterEqual(meta['health_pct'], 55)
        self.assertLessEqual(meta['health_pct'], 60)


class WeeklyTrialCampaignSmsQueueTests(TestCase):
    def setUp(self):
        self.product, self.plan = _ensure_bot_monthly_plan()

    @override_settings(WEEKLY_TRIAL_CAMPAIGN_SMS_BATCH_SIZE=3)
    @patch('licenses.services.weekly_trial_campaign._send_templated_or_simple_sms', return_value=True)
    def test_batch_skips_invalid_and_reaches_valid_user(self, _mock_send):
        u_invalid = User.objects.create_user(username='no_phone', password='p', phone='')
        u_optout = User.objects.create_user(
            username='optout_user',
            password='p',
            phone='09127778899',
            marketing_sms_opt_out=True,
        )
        u_valid = User.objects.create_user(username='valid_user', password='p', phone='09129998877')
        for user in (u_invalid, u_optout, u_valid):
            grant_weekly_trial_to_user(user, campaign_key=CAMPAIGN, plan=self.plan)
        attempted, sent, skipped, _failed = run_campaign_sms_batch(CAMPAIGN, limit=1)
        self.assertEqual(sent, 1)
        self.assertGreaterEqual(skipped, 2)
        self.assertGreaterEqual(attempted, 3)
        skipped_grants = LicenseCampaignGrant.objects.filter(
            campaign_key=CAMPAIGN,
            sms_status=LicenseCampaignGrant.SmsStatus.SKIPPED,
        )
        self.assertGreaterEqual(skipped_grants.count(), 2)
        valid_grant = LicenseCampaignGrant.objects.get(user=u_valid, campaign_key=CAMPAIGN)
        self.assertEqual(valid_grant.sms_status, LicenseCampaignGrant.SmsStatus.SENT)


class WeeklyTrialCampaignSmsAttributesTests(TestCase):
    def test_build_attributes_for_faraz_pattern(self):
        attrs = build_campaign_sms_attributes('my_campaign')
        self.assertEqual(attrs['days'], '7')
        self.assertEqual(attrs['link'], 'workspace/')
        self.assertEqual(attrs['url'], 'workspace/')
