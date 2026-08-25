"""تست سرویس تأیید هویت پیش از خروجی."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from accounts.services.export_verification import (
    ExportVerificationError,
    begin_export_verification,
    complete_export_verification,
    is_export_authorized,
    issue_export_token,
    mark_session_export_verified,
    validate_export_token,
    verify_password_for_export,
)
from accounts.services.otp import hash_otp_code
from accounts.models import OtpRequest

User = get_user_model()


@override_settings(SMS_PROVIDER='console', OTP_DEBUG_RETURN_CODE=True)
class ExportVerificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121234567',
            phone='09121234567',
            password='SecretPass123',
        )
        self.factory = RequestFactory()

    def test_verify_password_rejects_wrong_password(self):
        with self.assertRaises(ExportVerificationError) as ctx:
            verify_password_for_export(self.user, 'wrong-password')
        self.assertEqual(ctx.exception.code, 'invalid_password')

    def test_full_flow_session_and_token(self):
        request = self.factory.post('/')
        request.session = self.client.session

        challenge_token = verify_password_for_export(self.user, 'SecretPass123')
        self.assertTrue(challenge_token)

        begin_export_verification(self.user, 'SecretPass123', request=request)
        otp = OtpRequest.objects.filter(phone='09121234567', purpose='login').latest('created_at')
        code = '123456'
        otp.code_hash = hash_otp_code(code, '09121234567', 'login')
        otp.save(update_fields=['code_hash'])

        payload = complete_export_verification(self.user, challenge_token, code, request=request)
        self.assertIn('export_token', payload)
        self.assertTrue(is_export_authorized(request, self.user))

        token = payload['export_token']
        self.assertTrue(validate_export_token(token, self.user.pk))

        bare_request = self.factory.get('/')
        bare_request.session = self.client.session
        bare_request.META['HTTP_X_EXPORT_TOKEN'] = token
        self.assertTrue(is_export_authorized(bare_request, self.user))

    def test_issue_export_token_is_user_bound(self):
        token = issue_export_token(self.user.pk)
        other = User.objects.create_user(
            username='09129876543',
            phone='09129876543',
            password='SecretPass123',
        )
        self.assertTrue(validate_export_token(token, self.user.pk))
        self.assertFalse(validate_export_token(token, other.pk))

    def test_session_marking(self):
        request = self.factory.get('/')
        request.session = self.client.session
        mark_session_export_verified(request)
        self.assertTrue(is_export_authorized(request, self.user))
