from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import OtpRequest, SmsMessageLog
from accounts.services.otp import (
    OtpError,
    OtpRateLimitError,
    hash_otp_code,
    request_otp,
    verify_otp,
)

User = get_user_model()


@override_settings(
    SMS_PROVIDER='console',
    SMS_ENABLED=True,
    OTP_EXPIRY_SECONDS=120,
    OTP_RESEND_SECONDS=60,
    OTP_MAX_ATTEMPTS=3,
    OTP_MAX_SENDS_PER_HOUR=5,
    OTP_LENGTH=6,
    OTP_DEBUG_RETURN_CODE=True,
    FARAZSMS_PATTERN_OTP='TESTPAT',
)
class OtpServiceTests(TestCase):
    def test_request_stores_hash_not_raw(self):
        challenge = request_otp('09121111111', 'register')
        self.assertTrue(challenge.debug_code)
        otp = OtpRequest.objects.get(phone='09121111111', purpose='register')
        self.assertNotEqual(otp.code_hash, challenge.debug_code)
        self.assertEqual(
            otp.code_hash,
            hash_otp_code(challenge.debug_code, '09121111111', 'register'),
        )
        self.assertFalse(
            SmsMessageLog.objects.filter(error_message__contains=challenge.debug_code).exists()
        )

    def test_verify_success_consumes(self):
        challenge = request_otp('09121111112', 'login')
        self.assertTrue(verify_otp('09121111112', 'login', challenge.debug_code))
        otp = OtpRequest.objects.filter(phone='09121111112', purpose='login').latest('created_at')
        self.assertTrue(otp.is_consumed)
        with self.assertRaises(OtpError):
            verify_otp('09121111112', 'login', challenge.debug_code)

    def test_wrong_code_increments_attempts(self):
        request_otp('09121111113', 'login')
        with self.assertRaises(OtpError) as ctx:
            verify_otp('09121111113', 'login', '000000')
        self.assertEqual(ctx.exception.code, 'otp_mismatch')
        otp = OtpRequest.objects.filter(phone='09121111113').latest('created_at')
        self.assertEqual(otp.attempts, 1)

    def test_lock_after_max_attempts(self):
        request_otp('09121111114', 'login')
        for _ in range(3):
            with self.assertRaises(OtpError):
                verify_otp('09121111114', 'login', '000000')
        otp = OtpRequest.objects.filter(phone='09121111114').latest('created_at')
        self.assertTrue(otp.is_consumed)

    def test_resend_rate_limit(self):
        request_otp('09121111115', 'register')
        with self.assertRaises(OtpRateLimitError):
            request_otp('09121111115', 'register')

    def test_expired_code(self):
        challenge = request_otp('09121111116', 'login')
        otp = OtpRequest.objects.filter(phone='09121111116').latest('created_at')
        otp.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        otp.save(update_fields=['expires_at'])
        with self.assertRaises(OtpError) as ctx:
            verify_otp('09121111116', 'login', challenge.debug_code)
        self.assertEqual(ctx.exception.code, 'otp_expired')


@override_settings(
    SMS_PROVIDER='console',
    SMS_ENABLED=True,
    OTP_DEBUG_RETURN_CODE=True,
    OTP_RESEND_SECONDS=0,
    OTP_MAX_SENDS_PER_HOUR=20,
    FARAZSMS_PATTERN_OTP='TESTPAT',
)
class OtpAuthFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='u9122222222',
            phone='09122222222',
            password='ComplexPass123!',
        )

    @patch('accounts.services.otp.generate_otp_code', return_value='123456')
    def test_otp_login_flow(self, _mock_code):
        response = self.client.post(reverse('otp_login'), {'phone': '09122222222'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('otp_login_verify'))

        response = self.client.post(reverse('otp_login_verify'), {'code': '123456'})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(phone='09122222222')
        self.assertTrue(user.phone_verified)

    @patch('accounts.services.otp.generate_otp_code', return_value='654321')
    def test_otp_register_flow(self, _mock_code):
        phone = '09123333333'
        response = self.client.post(reverse('register'), {'phone': phone})
        self.assertEqual(response.status_code, 302)

        response = self.client.post(reverse('otp_register_verify'), {'code': '654321'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('otp_register_password'))

        response = self.client.post(
            reverse('otp_register_password'),
            {
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(phone=phone)
        self.assertTrue(user.phone_verified)
        self.assertTrue(user.check_password('ComplexPass123!'))

    def test_register_rejects_existing_phone(self):
        response = self.client.post(reverse('register'), {'phone': '09122222222'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'قبلاً ثبت‌نام')

    def test_password_login_still_works(self):
        logged_in = self.client.login(username='09122222222', password='ComplexPass123!')
        self.assertTrue(logged_in)
