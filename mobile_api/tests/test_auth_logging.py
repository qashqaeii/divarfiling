"""Tests for mobile auth instrumentation."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'mobile_api.authentication.MobileJWTAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
    },
)
class MobileAuthLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09124445566',
            phone='09124445566',
            password='testpass123',
        )
        self.client = APIClient()

    def test_missing_token_sets_auth_failure_missing(self):
        resp = self.client.get(
            '/api/mobile/v1/dashboard',
            HTTP_X_DEVICE_ID='dev-1',
            HTTP_X_APP_VERSION='2.5.0',
        )
        self.assertEqual(resp.status_code, 401)

    def test_invalid_token_sets_auth_failure_invalid(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-valid-jwt')
        resp = self.client.get('/api/mobile/v1/dashboard')
        self.assertEqual(resp.status_code, 401)
