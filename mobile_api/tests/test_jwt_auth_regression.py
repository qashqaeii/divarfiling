"""Regression tests for MobileJWTAuthentication across auth flows."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()

_REST = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'mobile_api.authentication.MobileJWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


@override_settings(REST_FRAMEWORK=_REST)
class MobileJWTAuthFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09127778899',
            phone='09127778899',
            password='testpass123',
        )
        self.client = APIClient()

    def _login(self):
        resp = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09127778899',
            'password': 'testpass123',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        return resp.data['data']

    def test_login_refresh_logout_flow(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        dash = self.client.get('/api/mobile/v1/dashboard')
        self.assertEqual(dash.status_code, 200)

        refresh = self.client.post('/api/mobile/v1/auth/refresh', {
            'refresh': tokens['refresh'],
        }, format='json')
        self.assertEqual(refresh.status_code, 200)
        new_access = refresh.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')

        logout = self.client.post('/api/mobile/v1/auth/logout', {
            'refresh': tokens['refresh'],
        }, format='json')
        self.assertEqual(logout.status_code, 200)

    def test_anonymous_app_version_allowed(self):
        resp = self.client.get('/api/mobile/v1/app/version')
        self.assertEqual(resp.status_code, 200)

    def test_session_auth_still_works_for_drf(self):
        session_client = APIClient()
        session_client.force_authenticate(user=self.user)
        resp = session_client.get('/api/mobile/v1/dashboard')
        self.assertEqual(resp.status_code, 200)

    def test_expired_token_reports_auth_failure_attribute(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid.jwt.token')
        resp = self.client.get('/api/mobile/v1/dashboard')
        self.assertEqual(resp.status_code, 401)
