"""تست جریان OTP و فروشگاه موبایل."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from shop.bot_catalog import BOT_PRODUCT_SLUG
from shop.models import LicensePlan, Product

User = get_user_model()


from copy import deepcopy

from django.conf import settings as django_settings

_REST = deepcopy(django_settings.REST_FRAMEWORK)
_REST['DEFAULT_THROTTLE_RATES']['mobile_login'] = '10000/minute'
_REST['DEFAULT_THROTTLE_RATES']['mobile_user'] = '10000/minute'
_REST['DEFAULT_THROTTLE_RATES']['mobile_refresh'] = '10000/minute'


@override_settings(
    SMS_PROVIDER='console',
    SMS_ENABLED=True,
    OTP_EXPIRY_SECONDS=120,
    OTP_RESEND_SECONDS=0,
    OTP_MAX_ATTEMPTS=5,
    OTP_MAX_SENDS_PER_HOUR=10,
    OTP_LENGTH=6,
    OTP_DEBUG_RETURN_CODE=True,
    REST_FRAMEWORK=_REST,
)
class MobileAuthOtpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='09120001111',
            phone='09120001111',
            password='oldpass123',
        )

    def test_otp_login_flow(self):
        start = self.client.post('/api/mobile/v1/auth/otp/request', {
            'phone': '09120001111',
            'purpose': 'login',
        }, format='json')
        self.assertTrue(start.data.get('ok'), start.data)
        code = start.data['data']['debug_code']
        self.assertTrue(code)
        verify = self.client.post('/api/mobile/v1/auth/otp/verify', {
            'phone': '09120001111',
            'purpose': 'login',
            'code': code,
        }, format='json')
        self.assertTrue(verify.data.get('ok'), verify.data)
        self.assertIn('access', verify.data['data'])
        self.assertEqual(verify.data['data']['user']['phone'], '09120001111')

    def test_otp_login_unknown_phone(self):
        resp = self.client.post('/api/mobile/v1/auth/otp/request', {
            'phone': '09129990000',
            'purpose': 'login',
        }, format='json')
        self.assertFalse(resp.data.get('ok'))
        self.assertEqual(resp.data.get('code'), 'USER_NOT_FOUND')

    def test_register_duplicate_phone(self):
        resp = self.client.post('/api/mobile/v1/auth/otp/request', {
            'phone': '09120001111',
            'purpose': 'register',
        }, format='json')
        self.assertFalse(resp.data.get('ok'))
        self.assertEqual(resp.data.get('code'), 'PHONE_TAKEN')

    def test_register_and_password_reset(self):
        start = self.client.post('/api/mobile/v1/auth/otp/request', {
            'phone': '09123334455',
            'purpose': 'register',
        }, format='json')
        self.assertTrue(start.data.get('ok'), start.data)
        code = start.data['data']['debug_code']
        verify = self.client.post('/api/mobile/v1/auth/otp/verify', {
            'phone': '09123334455',
            'purpose': 'register',
            'code': code,
        }, format='json')
        self.assertTrue(verify.data.get('ok'), verify.data)
        token = verify.data['data']['challenge_token']
        complete = self.client.post('/api/mobile/v1/auth/register', {
            'phone': '09123334455',
            'challenge_token': token,
            'password': 'newpass123',
            'password_confirm': 'newpass123',
        }, format='json')
        self.assertTrue(complete.data.get('ok'), complete.data)
        self.assertIn('access', complete.data['data'])

        reset = self.client.post('/api/mobile/v1/auth/otp/request', {
            'phone': '09123334455',
            'purpose': 'password_reset',
        }, format='json')
        self.assertTrue(reset.data.get('ok'), reset.data)
        rcode = reset.data['data']['debug_code']
        rverify = self.client.post('/api/mobile/v1/auth/otp/verify', {
            'phone': '09123334455',
            'purpose': 'password_reset',
            'code': rcode,
        }, format='json')
        self.assertTrue(rverify.data.get('ok'), rverify.data)
        done = self.client.post('/api/mobile/v1/auth/password-reset', {
            'phone': '09123334455',
            'challenge_token': rverify.data['data']['challenge_token'],
            'password': 'resetpass9',
            'password_confirm': 'resetpass9',
        }, format='json')
        self.assertTrue(done.data.get('ok'), done.data)
        login = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09123334455',
            'password': 'resetpass9',
        }, format='json')
        self.assertTrue(login.data.get('ok'), login.data)

    def test_wrong_otp(self):
        User.objects.create_user(username='09121112222', phone='09121112222', password='x')
        self.client.post('/api/mobile/v1/auth/otp/request', {
            'phone': '09121112222',
            'purpose': 'login',
        }, format='json')
        resp = self.client.post('/api/mobile/v1/auth/otp/verify', {
            'phone': '09121112222',
            'purpose': 'login',
            'code': '000000',
        }, format='json')
        self.assertFalse(resp.data.get('ok'))
        self.assertEqual(resp.data.get('code'), 'OTP_INVALID')


@override_settings(REST_FRAMEWORK=_REST)
class MobileShopPlansTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='09125556666',
            phone='09125556666',
            password='testpass123',
            phone_verified=True,
        )
        self.product = Product.objects.create(
            title='ربات',
            slug=BOT_PRODUCT_SLUG,
            description='تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='سالانه',
            plan_type='yearly',
            price=1000000,
            duration_days=365,
            is_active=True,
            is_featured=True,
            tagline='مناسب آژانس',
        )
        self.client = APIClient()
        resp = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09125556666',
            'password': 'testpass123',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['data']['access']}")

    def test_plans_from_backend(self):
        resp = self.client.get('/api/mobile/v1/shop/plans')
        self.assertTrue(resp.data.get('ok'), resp.data)
        plans = resp.data['data']['plans']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['final_price'], 1000000)
        self.assertTrue(plans[0]['is_featured'])

    @patch('mobile_api.services.shop_checkout_service.zibal_service.request_payment')
    @patch('mobile_api.services.shop_checkout_service.zibal_service.get_start_pay_url', return_value='https://gateway.example/pay')
    @patch('mobile_api.services.shop_checkout_service.zibal_service.build_callback_url', return_value='https://divarfiling.ir/payment/callback/')
    def test_checkout_reuses_pending_order(self, _cb, _url, mock_pay):
        mock_pay.return_value = MagicMock(track_id='t1', result_code=100, message='ok', raw={})
        with patch('shop.models.PaymentSettings.load') as pay_load:
            settings = MagicMock()
            settings.zibal_enabled = True
            settings.available_methods.return_value = ['zibal']
            pay_load.return_value = settings
            first = self.client.post('/api/mobile/v1/shop/checkout', {'plan_id': self.plan.pk}, format='json')
            self.assertTrue(first.data.get('ok'), first.data)
            second = self.client.post('/api/mobile/v1/shop/checkout', {'plan_id': self.plan.pk}, format='json')
            self.assertTrue(second.data.get('ok'), second.data)
            self.assertEqual(first.data['data']['order_id'], second.data['data']['order_id'])
            self.assertTrue(second.data['data'].get('reused'))
            status = self.client.get(f"/api/mobile/v1/shop/orders/{first.data['data']['order_id']}")
            self.assertTrue(status.data.get('ok'))
            self.assertEqual(status.data['data']['status'], 'pending')
