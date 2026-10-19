"""تست هدیه خوش‌آمدگویی ۷روزه در ثبت‌نام."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.account_completion import create_user_from_verified_phone
from licenses.models import License, LicenseCampaignGrant
from licenses.services.signup_welcome_gift import (
    acknowledge_welcome_modal,
    campaign_key,
    offer_signup_welcome_gift,
    should_show_welcome_modal,
)
from licenses.tests.test_weekly_trial_campaign import _ensure_bot_monthly_plan
from shop.models import Order
from workspace.models import WorkspaceSettings

User = get_user_model()

GIFT_SETTINGS = {
    'SIGNUP_WELCOME_GIFT_ENABLED': True,
    'SIGNUP_WELCOME_GIFT_START_AT': '2020-01-01T00:00:00+03:30',
    'SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY': 'signup_welcome_7d_v1_test',
}


@override_settings(**GIFT_SETTINGS)
class SignupWelcomeGiftGrantTests(TestCase):
    def setUp(self):
        _ensure_bot_monthly_plan()
        self.user = User.objects.create_user(
            username='new_user',
            password='pass',
            phone='09123334455',
            phone_verified=True,
        )

    def test_grant_on_offer_creates_granted_order_and_license(self):
        result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'granted')
        grant = LicenseCampaignGrant.objects.get(user=self.user, campaign_key=campaign_key())
        self.assertEqual(grant.status, LicenseCampaignGrant.Status.GRANTED)
        self.assertIsNotNone(grant.license_id)
        self.assertEqual(grant.order.status, 'granted')
        self.assertEqual(grant.order.amount, 0)
        lic = grant.license
        self.assertEqual(lic.status, 'active')
        delta = lic.expires_at - timezone.now()
        self.assertGreaterEqual(delta, timedelta(days=6, hours=23))
        self.assertLessEqual(delta, timedelta(days=7, minutes=5))
        self.assertEqual(grant.sms_status, LicenseCampaignGrant.SmsStatus.SKIPPED)

    def test_idempotent_second_offer(self):
        offer_signup_welcome_gift(self.user, channel='test')
        result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'already_granted')
        self.assertEqual(
            LicenseCampaignGrant.objects.filter(user=self.user, campaign_key=campaign_key()).count(),
            1,
        )

    def test_skipped_when_feature_disabled(self):
        with override_settings(SIGNUP_WELCOME_GIFT_ENABLED=False):
            result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertTrue(result.startswith('skipped:'))
        self.assertEqual(LicenseCampaignGrant.objects.count(), 0)

    def test_fail_closed_when_start_at_missing(self):
        with override_settings(
            SIGNUP_WELCOME_GIFT_ENABLED=True,
            SIGNUP_WELCOME_GIFT_START_AT='',
            SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY=GIFT_SETTINGS['SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY'],
        ):
            result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'skipped:start_at_not_configured')
        self.assertEqual(LicenseCampaignGrant.objects.count(), 0)

    def test_fail_closed_when_start_at_invalid(self):
        with override_settings(
            SIGNUP_WELCOME_GIFT_ENABLED=True,
            SIGNUP_WELCOME_GIFT_START_AT='not-a-date',
            SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY=GIFT_SETTINGS['SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY'],
        ):
            result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'skipped:start_at_invalid')

    def test_fail_closed_when_start_at_has_no_timezone(self):
        with override_settings(
            SIGNUP_WELCOME_GIFT_ENABLED=True,
            SIGNUP_WELCOME_GIFT_START_AT='2030-06-01T00:00:00',
            SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY=GIFT_SETTINGS['SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY'],
        ):
            result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'skipped:start_at_missing_timezone')

    def test_user_joined_before_start_at_not_granted(self):
        with override_settings(
            SIGNUP_WELCOME_GIFT_ENABLED=True,
            SIGNUP_WELCOME_GIFT_START_AT='2030-01-01T00:00:00+03:30',
            SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY=GIFT_SETTINGS['SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY'],
        ):
            result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'skipped:campaign_not_started')

    def test_failed_record_does_not_clobber_successful_grant(self):
        offer_signup_welcome_gift(self.user, channel='test')
        from licenses.services.signup_welcome_gift import _record_failed_grant

        _record_failed_grant(self.user, channel='race', error='simulated')
        grant = LicenseCampaignGrant.objects.get(user=self.user, campaign_key=campaign_key())
        self.assertEqual(grant.status, LicenseCampaignGrant.Status.GRANTED)
        self.assertIsNotNone(grant.license_id)

    def test_skipped_when_phone_not_verified(self):
        self.user.phone_verified = False
        self.user.save(update_fields=['phone_verified'])
        result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertEqual(result, 'skipped:phone_not_verified')

    def test_not_eligible_after_paid_purchase(self):
        product, plan = _ensure_bot_monthly_plan()
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=plan.price,
            status='paid',
        )
        result = offer_signup_welcome_gift(self.user, channel='test')
        self.assertTrue(result.startswith('skipped:'))

    @patch('licenses.services.signup_welcome_gift.resolve_professional_gift_plan')
    def test_registration_not_broken_on_grant_failure(self, mock_plan):
        mock_plan.side_effect = RuntimeError('boom')
        user = create_user_from_verified_phone('09124445566', 'StrongPass123!')
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        grant = LicenseCampaignGrant.objects.filter(user=user, campaign_key=campaign_key()).first()
        self.assertIsNotNone(grant)
        self.assertEqual(grant.status, LicenseCampaignGrant.Status.FAILED)


@override_settings(**GIFT_SETTINGS)
class SignupWelcomeModalTests(TestCase):
    def setUp(self):
        _ensure_bot_monthly_plan()
        self.user = User.objects.create_user(
            username='modal_user',
            password='pass',
            phone='09125556677',
            phone_verified=True,
        )
        offer_signup_welcome_gift(self.user, channel='test')

    def test_should_show_until_acknowledged(self):
        self.assertTrue(should_show_welcome_modal(self.user))
        ok, _ = acknowledge_welcome_modal(self.user, start_tour=True)
        self.assertTrue(ok)
        self.assertFalse(should_show_welcome_modal(self.user))
        grant = LicenseCampaignGrant.objects.get(user=self.user, campaign_key=campaign_key())
        self.assertIsNotNone(grant.welcome_modal_seen_at)
        self.assertIsNotNone(grant.welcome_tour_started_at)

    def test_ack_api_requires_login(self):
        client = Client()
        url = reverse('workspace:signup_welcome_ack')
        resp = client.post(url)
        self.assertEqual(resp.status_code, 302)

    def test_ack_api_success(self):
        client = Client()
        client.force_login(self.user)
        url = reverse('workspace:signup_welcome_ack')
        resp = client.post(url, {'start_tour': '1'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])


@override_settings(**GIFT_SETTINGS)
class SignupWelcomeWorkspaceContextTests(TestCase):
    def setUp(self):
        _ensure_bot_monthly_plan()
        self.user = User.objects.create_user(
            username='ctx_user',
            password='pass',
            phone='09126667788',
            phone_verified=True,
        )
        offer_signup_welcome_gift(self.user, channel='test')
        WorkspaceSettings.objects.get_or_create(user=self.user, defaults={'onboarding_completed': False})

    def test_home_shows_gift_flag_in_context(self):
        client = Client()
        client.force_login(self.user)
        resp = client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['show_signup_welcome_gift'])
        self.assertTrue(resp.context['signup_welcome_blocks_tour'])
        self.assertTrue(resp.context['has_bot_license'])


@override_settings(**GIFT_SETTINGS)
class SignupWelcomeAndroidVerifyTests(TestCase):
    def setUp(self):
        _ensure_bot_monthly_plan()
        self.user = User.objects.create_user(
            username='android_verify',
            password='pass',
            phone='09127778899',
            phone_verified=False,
        )

    @patch('mobile_api.services.auth_otp_service.verify_otp')
    def test_complete_verify_phone_triggers_gift(self, _mock_verify):
        from mobile_api.services.auth_otp_service import complete_verify_phone

        complete_verify_phone(self.user, '123456')
        self.assertTrue(
            LicenseCampaignGrant.objects.filter(
                user=self.user,
                campaign_key=campaign_key(),
                status=LicenseCampaignGrant.Status.GRANTED,
            ).exists()
        )
