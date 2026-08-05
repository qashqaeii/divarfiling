"""تست‌های API دسکتاپ — auth، eligible، bind، validate."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License, LicenseActivation
from licenses.services.management import assign_license_to_member
from shop.models import LicensePlan, Order, Product
from workspace.models import CRMAgency, CRMAgencyMember

User = get_user_model()

TEST_HW = 'a' * 64
TEST_HW_B = 'b' * 64
TEST_HW_C = 'c' * 64
TEST_KEY = 'ABCD-1234-5678-9ABC'
TEST_KEY_2 = 'BCDE-2345-6789-ABCD'


def _paid_license(user, key=TEST_KEY, max_act=1, plan_name='ماهانه'):
    product = Product.objects.create(
        title='ربات',
        slug=f'bot-{key[:4]}-{user.pk}',
        description='test',
        is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product,
        name=plan_name,
        plan_type='monthly',
        price=100000,
        duration_days=30,
        max_activations=max_act,
        is_active=True,
    )
    order = Order.objects.create(
        user=user,
        product=product,
        plan=plan,
        amount=plan.price,
        status='paid',
    )
    lic = License.objects.create(
        order=order,
        plan=plan,
        license_key=key,
        status='inactive',
        max_activations=max_act,
        expires_at=timezone.now() + timedelta(days=30),
    )
    return lic


@override_settings(
    DESKTOP_ACCOUNT_LOGIN_ENABLED=True,
    LICENSE_ALLOW_LOCAL_DEV=True,
)
class DesktopAuthAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='owner1',
            password='pass1234',
            phone='09121111111',
        )
        self.license = _paid_license(self.owner)

    def test_login_with_phone(self):
        resp = self.client.post('/api/desktop/v1/auth/login', {
            'phone': '09121111111',
            'password': 'pass1234',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('access', data['data'])
        self.assertIn('refresh', data['data'])

    def test_login_invalid(self):
        resp = self.client.post('/api/desktop/v1/auth/login', {
            'phone': '09121111111',
            'password': 'wrong',
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_refresh_token(self):
        login = self.client.post('/api/desktop/v1/auth/login', {
            'username': 'owner1',
            'password': 'pass1234',
        }, format='json').json()['data']
        resp = self.client.post('/api/desktop/v1/auth/refresh', {
            'refresh': login['refresh'],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.json()['data'])

    def test_feature_flag_disabled(self):
        with override_settings(DESKTOP_ACCOUNT_LOGIN_ENABLED=False):
            resp = self.client.post('/api/desktop/v1/auth/login', {
                'username': 'owner1',
                'password': 'pass1234',
            }, format='json')
            self.assertEqual(resp.status_code, 503)


@override_settings(
    DESKTOP_ACCOUNT_LOGIN_ENABLED=True,
    LICENSE_ALLOW_LOCAL_DEV=True,
)
class DesktopLicensingAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='owner1',
            password='pass1234',
            phone='09121111111',
        )
        self.member = User.objects.create_user(
            username='member1',
            password='pass1234',
            phone='09122222222',
        )
        self.license = _paid_license(self.owner)
        self._login(self.owner)

    def _login(self, user):
        user_map = {
            self.owner: ('owner1', 'pass1234'),
            self.member: ('member1', 'pass1234'),
        }
        username, password = user_map[user]
        resp = self.client.post('/api/desktop/v1/auth/login', {
            'username': username,
            'password': password,
        }, format='json')
        tokens = resp.json()['data']
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return tokens

    def test_single_license_auto_bind(self):
        resp = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['success'])
        self.assertEqual(data['license_key'], TEST_KEY)
        act = LicenseActivation.objects.get(license=self.license, hardware_fingerprint=TEST_HW)
        self.assertTrue(act.is_active)
        self.assertIn('device_type=desktop', act.notes)

    def test_eligible_does_not_expose_full_key(self):
        resp = self.client.get(
            f'/api/desktop/v1/licenses/eligible?hardware_fingerprint={TEST_HW}',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertEqual(body['auto_bind_license_id'], self.license.pk)
        lic = body['licenses'][0]
        self.assertNotIn('license_key', lic)
        self.assertEqual(lic['key_short'], TEST_KEY[-8:])

    def test_legacy_key_activate_still_works(self):
        anon = APIClient()
        resp = anon.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW_B,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_multi_license_requires_selection(self):
        lic2 = _paid_license(self.owner, key=TEST_KEY_2, plan_name='طلایی')
        resp = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['code'], 'LICENSE_SELECTION_REQUIRED')
        self.assertEqual(len(resp.json()['fields']['licenses']), 2)

        resp2 = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
            'license_id': lic2.pk,
        }, format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['data']['license_key'], TEST_KEY_2)

    def test_member_assigned_license(self):
        agency = CRMAgency.objects.create(name='آژانس', slug='agency-1', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner')
        CRMAgencyMember.objects.create(agency=agency, user=self.member, role='advisor')
        assign_license_to_member(self.owner, self.license.pk, self.member.pk)
        tokens = self._login(self.member)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['license_key'], TEST_KEY)

    def test_member_seat_assignment(self):
        agency = CRMAgency.objects.create(name='آژانس۲', slug='agency-2', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner')
        CRMAgencyMember.objects.create(agency=agency, user=self.member, role='advisor')
        self.license.max_activations = 2
        self.license.save()
        act = LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint='d' * 64,
            is_active=True,
            assigned_user=self.member,
        )
        self.assertEqual(act.assigned_user_id, self.member.pk)
        tokens = self._login(self.member)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = self.client.get(
            f'/api/desktop/v1/licenses/eligible?hardware_fingerprint={TEST_HW}',
        )
        ids = [x['license_id'] for x in resp.json()['data']['licenses']]
        self.assertIn(self.license.pk, ids)

    def test_revoked_member_cannot_bind(self):
        agency = CRMAgency.objects.create(name='آژانس۳', slug='agency-3', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner')
        CRMAgencyMember.objects.create(agency=agency, user=self.member, role='advisor')
        assign_license_to_member(self.owner, self.license.pk, self.member.pk)
        self.license.assigned_user = None
        self.license.save(update_fields=['assigned_user'])
        tokens = self._login(self.member)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_expired_license_not_eligible(self):
        self.license.expires_at = timezone.now() - timedelta(days=1)
        self.license.status = 'expired'
        self.license.save()
        resp = self.client.get(
            f'/api/desktop/v1/licenses/eligible?hardware_fingerprint={TEST_HW}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['licenses'], [])

    def test_full_license_cannot_bind(self):
        self.license.max_activations = 1
        self.license.save()
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint=TEST_HW_B,
            is_active=True,
        )
        resp = self.client.get(
            f'/api/desktop/v1/licenses/eligible?hardware_fingerprint={TEST_HW}',
        )
        lic = resp.json()['data']['licenses'][0]
        self.assertEqual(lic['eligibility_state'], 'full')
        self.assertFalse(lic['can_bind'])

    def test_validate_session_after_bind(self):
        self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        resp = self.client.post('/api/desktop/v1/licenses/validate-session', {
            'hardware_fingerprint': TEST_HW,
            'license_key': TEST_KEY,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['data']['valid'])

    def test_logout_does_not_deactivate(self):
        self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        tokens = self.client.post('/api/desktop/v1/auth/login', {
            'username': 'owner1',
            'password': 'pass1234',
        }, format='json').json()['data']
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.client.post('/api/desktop/v1/auth/logout', {
            'refresh': tokens['refresh'],
        }, format='json')
        act = LicenseActivation.objects.get(license=self.license, hardware_fingerprint=TEST_HW)
        self.assertTrue(act.is_active)

    def test_existing_device_rebinds_same_license(self):
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint=TEST_HW,
            is_active=True,
        )
        resp = self.client.get(
            f'/api/desktop/v1/licenses/eligible?hardware_fingerprint={TEST_HW}',
        )
        self.assertEqual(
            resp.json()['data']['auto_bind_license_id'],
            self.license.pk,
        )

    def test_last_slot_blocks_extra_bind(self):
        multi = _paid_license(
            self.owner, key='CDEF-3456-7890-BCDE', max_act=2, plan_name='دو دستگاه',
        )
        r1 = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW_B,
            'license_id': multi.pk,
        }, format='json')
        r2 = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW_C,
            'license_id': multi.pk,
        }, format='json')
        r3 = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': 'e' * 64,
            'license_id': multi.pk,
        }, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(
            LicenseActivation.objects.filter(license=multi, is_active=True).count(),
            2,
        )

    def test_change_license_on_system(self):
        lic2 = _paid_license(self.owner, key=TEST_KEY_2, plan_name='طلایی')
        self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
            'license_id': self.license.pk,
        }, format='json')
        resp = self.client.post('/api/desktop/v1/licenses/bind', {
            'hardware_fingerprint': TEST_HW,
            'license_id': lic2.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['license_key'], TEST_KEY_2)
