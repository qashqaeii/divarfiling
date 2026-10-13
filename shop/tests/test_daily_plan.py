"""تست پلن آزمایشی یک‌هفته‌ای."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License
from licenses.services.claim import issue_license_for_paid_order
from shop.bot_catalog import bot_license_plans
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from shop.services.plan_guards import user_meets_plan_requirements
from workspace.services.access import has_active_bot_license

User = get_user_model()

TEST_HW = 'c' * 64
TEST_KEY = 'DAIL-1234-5678-9ABC'


class DailyPlanCatalogTests(TestCase):
    def test_bot_license_plans_includes_daily_plan(self):
        daily = next(p for p in bot_license_plans() if p['plan_type'] == 'daily')
        self.assertEqual(daily['name'], 'پلن آزمایشی ۱ هفته‌ای')
        self.assertEqual(daily['duration_days'], 7)
        self.assertEqual(daily['order'], 0)


@override_settings(LICENSE_ALLOW_LOCAL_DEV=True)
class DailyPlanLicenseFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='daily_user',
            password='pass1234',
            phone='09128888888',
        )
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-daily-test',
            description='test',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس آزمایشی یک‌هفته‌ای',
            plan_type='daily',
            price=50_000,
            duration_days=7,
            max_activations=2,
            is_active=True,
            order=0,
        )
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )
        self.client = APIClient()

    def test_fulfill_issues_license_with_one_week_expiry(self):
        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        license_obj = issue_license_for_paid_order(self.order)
        self.assertIsNotNone(license_obj)
        self.assertIsNotNone(license_obj.expires_at)
        delta = license_obj.expires_at - timezone.now()
        self.assertGreater(delta, timedelta(days=6, hours=23))
        self.assertLessEqual(delta, timedelta(days=7, minutes=5))

    def test_activate_and_access_until_expiry(self):
        license_obj = fulfill_order_after_payment(self.order)
        self.assertIsNotNone(license_obj)
        license_obj.license_key = TEST_KEY
        license_obj.save(update_fields=['license_key'])

        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        license_obj.refresh_from_db()
        self.assertEqual(license_obj.status, 'active')
        self.assertTrue(has_active_bot_license(self.user))

    def test_expired_daily_license_blocks_access(self):
        license_obj = fulfill_order_after_payment(self.order)
        self.assertIsNotNone(license_obj)
        license_obj.license_key = TEST_KEY
        license_obj.status = 'active'
        license_obj.expires_at = timezone.now() - timedelta(minutes=1)
        license_obj.save()

        LicenseActivation = license_obj.activations.model
        LicenseActivation.objects.create(
            license=license_obj,
            hardware_fingerprint=TEST_HW,
            is_active=True,
        )

        resp = self.client.post('/api/licenses/validate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['valid'])
        self.assertFalse(has_active_bot_license(self.user))


class DailyPlanPhoneVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='unverified_user',
            password='pass1234',
            phone='09129999999',
            phone_verified=False,
        )
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-daily-verify-test',
            description='test',
            is_active=True,
        )
        self.daily_plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس آزمایشی یک‌هفته‌ای',
            plan_type='daily',
            price=50_000,
            duration_days=7,
            max_activations=2,
            is_active=True,
            order=0,
        )
        self.monthly_plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=1_000_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
            order=1,
        )

    def test_daily_plan_allowed_without_phone_verification(self):
        ok, _ = user_meets_plan_requirements(self.user, self.daily_plan)
        self.assertTrue(ok)
        ok, _ = user_meets_plan_requirements(self.user, self.monthly_plan)
        self.assertTrue(ok)

    def test_buy_daily_allowed_without_phone_verification(self):
        self.client.force_login(self.user)
        url = reverse('buy', kwargs={'slug': self.product.slug})
        response = self.client.get(f'{url}?plan={self.daily_plan.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.daily_plan.name)

    def test_buy_monthly_allowed_without_phone_verification(self):
        self.client.force_login(self.user)
        url = reverse('buy', kwargs={'slug': self.product.slug})
        response = self.client.get(f'{url}?plan={self.monthly_plan.pk}')
        self.assertEqual(response.status_code, 200)

    @override_settings(
        OTP_DEBUG_RETURN_CODE=True,
        OTP_RESEND_SECONDS=0,
        OTP_MAX_SENDS_PER_HOUR=20,
        FARAZSMS_PATTERN_OTP='TESTPAT',
    )
    @patch('accounts.services.otp.generate_otp_code', return_value='123456')
    def test_verify_phone_allows_daily_purchase(self, _mock_code):
        self.client.force_login(self.user)
        verify_url = reverse('otp_verify_phone')
        buy_url = reverse('buy', kwargs={'slug': self.product.slug})
        next_url = f'{buy_url}?plan={self.daily_plan.pk}'

        response = self.client.get(f'{verify_url}?next={next_url}')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(verify_url, {'code': '123456', 'next': next_url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)

        self.user.refresh_from_db()
        self.assertTrue(self.user.phone_verified)

        response = self.client.get(next_url)
        self.assertEqual(response.status_code, 200)


class DailyPlanRepeatPurchaseTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='repeat_daily_user',
            password='pass1234',
            phone='09127777777',
            phone_verified=True,
        )
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-daily-repeat-test',
            description='test',
            is_active=True,
        )
        self.daily_plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس آزمایشی یک‌هفته‌ای',
            plan_type='daily',
            price=50_000,
            duration_days=7,
            max_activations=2,
            is_active=True,
            order=0,
        )
        self.monthly_plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=1_000_000,
            duration_days=30,
            max_activations=2,
            is_active=True,
            order=1,
        )

    def _create_expired_daily_order(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.daily_plan,
            amount=self.daily_plan.price,
            status='paid',
        )
        license_obj = fulfill_order_after_payment(order)
        license_obj.status = 'active'
        license_obj.expires_at = timezone.now() - timedelta(minutes=5)
        license_obj.save(update_fields=['status', 'expires_at'])
        return order

    def test_repeat_daily_purchase_blocked_on_buy_page(self):
        self._create_expired_daily_order()
        self.client.force_login(self.user)
        buy_url = reverse('buy', kwargs={'slug': self.product.slug})
        response = self.client.get(f'{buy_url}?plan={self.daily_plan.pk}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, buy_url)
        response = self.client.get(buy_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.daily_plan.name)
        self.assertNotContains(response, 'plan_' + str(self.daily_plan.pk))

    def test_repeat_daily_purchase_blocked_on_post(self):
        self._create_expired_daily_order()
        self.client.force_login(self.user)
        buy_url = reverse('buy', kwargs={'slug': self.product.slug})
        response = self.client.post(buy_url, {'plan': self.daily_plan.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, buy_url)

    def test_monthly_purchase_still_allowed_after_daily_expired(self):
        self._create_expired_daily_order()
        self.client.force_login(self.user)
        buy_url = reverse('buy', kwargs={'slug': self.product.slug})
        response = self.client.get(f'{buy_url}?plan={self.monthly_plan.pk}')
        self.assertEqual(response.status_code, 200)
