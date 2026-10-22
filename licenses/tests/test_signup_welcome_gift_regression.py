"""Regression: هدیه خوش‌آمدگویی — OTP دیرهنگام، بدون هدیه تکراری، ثبت‌نام بدون تأیید."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.services.phone_verification import complete_phone_verification
from licenses.models import LicenseCampaignGrant
from licenses.services.signup_welcome_gift import campaign_key, offer_signup_welcome_gift
from licenses.tests.test_weekly_trial_campaign import _ensure_bot_monthly_plan

User = get_user_model()

GIFT_SETTINGS = {
    'SIGNUP_WELCOME_GIFT_ENABLED': True,
    'SIGNUP_WELCOME_GIFT_START_AT': '2020-01-01T00:00:00+03:30',
    'SIGNUP_WELCOME_GIFT_CAMPAIGN_KEY': 'signup_welcome_7d_v1_regression',
}


@override_settings(**GIFT_SETTINGS)
class SignupWelcomeGiftRegressionTests(TestCase):
    def setUp(self):
        _ensure_bot_monthly_plan()

    def test_password_register_no_gift_until_verify(self):
        phone = '09138880001'
        self.client.post(reverse('register_password'), {
            'phone': phone,
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        })
        user = User.objects.get(phone=phone)
        self.assertFalse(user.phone_verified)
        self.assertFalse(
            LicenseCampaignGrant.objects.filter(user=user, campaign_key=campaign_key()).exists()
        )

    def test_late_phone_verify_grants_once(self):
        user = User.objects.create_user(
            username='late_verify',
            password='ComplexPass123!',
            phone='09138880002',
            phone_verified=False,
        )
        result = complete_phone_verification(user, channel='web_phone_verify')
        self.assertEqual(result, 'granted')
        result2 = complete_phone_verification(user, channel='web_phone_verify_retry')
        self.assertEqual(result2, 'already_granted')
        self.assertEqual(
            LicenseCampaignGrant.objects.filter(user=user, campaign_key=campaign_key()).count(),
            1,
        )

    @patch('accounts.otp_views.verify_otp')
    def test_otp_login_unverified_user_gets_gift(self, mock_verify):
        user = User.objects.create_user(
            username='09138880003',
            password='unused',
            phone='09138880003',
            phone_verified=False,
        )
        session = self.client.session
        session['otp_phone'] = '09138880003'
        session['otp_purpose'] = 'login'
        session.save()
        mock_verify.return_value = None
        self.client.post(reverse('otp_login_verify'), {'code': '123456'})
        self.assertTrue(User.objects.get(pk=user.pk).phone_verified)
        self.assertTrue(
            LicenseCampaignGrant.objects.filter(
                user=user,
                campaign_key=campaign_key(),
                status=LicenseCampaignGrant.Status.GRANTED,
            ).exists()
        )

    def test_offer_logs_skipped_phone_not_verified(self):
        user = User.objects.create_user(
            username='no_verify',
            password='x',
            phone='09138880004',
            phone_verified=False,
        )
        with self.assertLogs('licenses.services.signup_welcome_gift', level='INFO') as logs:
            result = offer_signup_welcome_gift(user, channel='test')
        self.assertEqual(result, 'skipped:phone_not_verified')
        self.assertTrue(any('phone_not_verified' in m for m in logs.output))
