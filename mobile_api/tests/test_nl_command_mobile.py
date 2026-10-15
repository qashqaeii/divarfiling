"""Mobile NL Command API tests."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from ai_workspace.constants import FEATURE_NL_COMMAND
from ai_workspace.providers.base import ProviderResult
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from ai_workspace.services.nl_command.state import load_state
from licenses.models import License, LicenseActivation
from shop.models import LicensePlan, Order, Product
from workspace.models import CRMProperty, Customer

User = get_user_model()

_CONTACT_JSON = json.dumps({
    'intent': 'create_contact',
    'confidence': 0.9,
    'data': {
        'name': 'رضا اکبری',
        'phone': '09121234567',
        'customer_type': 'خریدار',
        'notes': '',
    },
    'missing_fields': [],
    'ambiguous_fields': [],
    'requires_confirmation': True,
}, ensure_ascii=False)

_PROPERTY_JSON = json.dumps({
    'intent': 'create_personal_property',
    'confidence': 0.9,
    'data': {
        'property_type': 'آپارتمان',
        'deal_mode': 'فروش',
        'neighborhood': 'پونک',
        'area': 90,
        'sale_price': 12_000_000_000,
        'rooms': '2',
    },
    'missing_fields': [],
    'ambiguous_fields': [],
    'requires_confirmation': True,
}, ensure_ascii=False)

_UNKNOWN_JSON = json.dumps({
    'intent': 'unknown',
    'confidence': 0.2,
    'data': {},
    'missing_fields': [],
    'ambiguous_fields': [],
}, ensure_ascii=False)


def _patch_chain(payload: str):
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(
        text=payload,
        provider='arvan',
        model='test',
        input_tokens=5,
        output_tokens=10,
        latency_ms=20,
        is_fallback=False,
    )
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])


class MobileNLCommandApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09127770001', phone='09127770001', password='x')
        self._grant_license(self.user)
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    @staticmethod
    def _grant_license(user):
        product = Product.objects.create(title='Bot', slug='bot-nl-mob', description='t', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='Pro', plan_type='yearly', price=1, duration_days=365, max_activations=1,
        )
        order = Order.objects.create(user=user, product=product, plan=plan, amount=1, status='paid')
        lic = License.objects.create(
            order=order, license_key='NL-MOB-1', plan=plan, status='active', max_activations=1,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        LicenseActivation.objects.create(license=lic, hardware_fingerprint='c' * 64, is_active=True)

    @override_settings(AI_ENABLED=True)
    def test_capabilities_authenticated(self):
        resp = self.client.get('/api/mobile/v1/ai/capabilities')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['can_use_smart_command'])
        self.assertTrue(data['is_unlimited'])
        self.assertTrue(data['has_license'])
        self.assertIn('smart_command_profiles', data)
        self.assertIsNone(data.get('nl_command'))
        overall = data.get('quota') or {}
        self.assertTrue(overall.get('is_unlimited'))

    @override_settings(AI_ENABLED=True)
    def test_capabilities_superuser_without_license_unlimited(self):
        admin = User.objects.create_superuser(
            username='09129990000',
            phone='09129990000',
            password='x',
        )
        client = APIClient()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.get('/api/mobile/v1/ai/capabilities')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['is_unlimited'])
        self.assertFalse(data['has_license'])
        self.assertTrue(data['can_use_smart_command'])
        self.assertTrue(data['can_use_crm_message'])

    @override_settings(AI_ENABLED=True)
    def test_parse_superuser_without_license(self):
        admin = User.objects.create_superuser(
            username='09129990001',
            phone='09129990001',
            password='x',
        )
        client = APIClient()
        token = RefreshToken.for_user(admin)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        with _patch_chain(_UNKNOWN_JSON):
            resp = client.post('/api/mobile/v1/ai/nl/parse', {'text': 'چیزی نامربوط'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['intent'], 'unknown')

    def test_parse_requires_auth(self):
        client = APIClient()
        resp = client.post('/api/mobile/v1/ai/nl/parse', {'text': 'test'}, format='json')
        self.assertEqual(resp.status_code, 401)

    @override_settings(AI_ENABLED=True)
    @_patch_chain(_UNKNOWN_JSON)
    def test_parse_unknown(self, _mock):
        resp = self.client.post('/api/mobile/v1/ai/nl/parse', {'text': 'چیزی نامربوط'}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['intent'], 'unknown')
        self.assertFalse(data['can_confirm'])

    @override_settings(AI_ENABLED=True)
    @_patch_chain(_CONTACT_JSON)
    def test_parse_and_confirm_contact(self, _mock):
        parse = self.client.post(
            '/api/mobile/v1/ai/nl/parse',
            {'text': 'مخاطب رضا اکبری 09121234567'},
            format='json',
        )
        self.assertEqual(parse.status_code, 200)
        body = parse.json()['data']
        self.assertEqual(body['intent'], 'create_contact')
        self.assertTrue(body.get('can_confirm'))
        cid = body['command_id']
        confirm = self.client.post('/api/mobile/v1/ai/nl/confirm', {'command_id': cid}, format='json')
        self.assertEqual(confirm.status_code, 200)
        result = confirm.json()['data']
        self.assertEqual(result['entity_type'], 'contact')
        self.assertTrue(Customer.objects.filter(user=self.user).exists())

    @override_settings(AI_ENABLED=True)
    @_patch_chain(_PROPERTY_JSON)
    def test_parse_and_confirm_property(self, _mock):
        parse = self.client.post(
            '/api/mobile/v1/ai/nl/parse',
            {'text': 'آپارتمان ۹۰ متری پونک فروش ۱۲ میلیارد'},
            format='json',
        )
        self.assertEqual(parse.status_code, 200)
        cid = parse.json()['data']['command_id']
        confirm = self.client.post('/api/mobile/v1/ai/nl/confirm', {'command_id': cid}, format='json')
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(confirm.json()['data']['entity_type'], 'property')
        self.assertTrue(CRMProperty.objects.filter(user=self.user).exists())

    @override_settings(AI_ENABLED=False)
    def test_ai_disabled(self):
        resp = self.client.post('/api/mobile/v1/ai/nl/parse', {'text': 'test'}, format='json')
        self.assertEqual(resp.status_code, 503)

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True)
    @_patch_chain(_UNKNOWN_JSON)
    def test_free_user_without_license_can_parse(self, _mock):
        user = User.objects.create_user(username='09127770002', phone='09127770002', password='x')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        resp = client.post('/api/mobile/v1/ai/nl/parse', {'text': 'چیزی نامربوط'}, format='json')
        self.assertEqual(resp.status_code, 200)

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=False)
    def test_legacy_no_license_forbidden(self):
        user = User.objects.create_user(username='09127770003', phone='09127770003', password='x')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        resp = client.post('/api/mobile/v1/ai/nl/parse', {'text': 'test'}, format='json')
        self.assertEqual(resp.status_code, 403)

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True)
    def test_free_user_capabilities(self):
        user = User.objects.create_user(username='09127770004', phone='09127770004', password='x')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        resp = client.get('/api/mobile/v1/ai/capabilities')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertFalse(data['has_license'])
        self.assertFalse(data['is_unlimited'])
        self.assertTrue(data['can_use_smart_command'])

    @override_settings(AI_ENABLED=True)
    def test_empty_text_validation(self):
        resp = self.client.post('/api/mobile/v1/ai/nl/parse', {'text': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)

    @override_settings(AI_ENABLED=True)
    @_patch_chain(_CONTACT_JSON)
    def test_confirm_expired_state(self, _mock):
        resp = self.client.post('/api/mobile/v1/ai/nl/confirm', {'command_id': 'missing-id'}, format='json')
        self.assertEqual(resp.status_code, 404)

    @override_settings(AI_ENABLED=True)
    @_patch_chain(_CONTACT_JSON)
    def test_double_confirm_idempotent(self, _mock):
        parsed = parse_command(self.user, text='مخاطب تست 09121112233')
        cid = parsed['command_id']
        first = confirm_command(self.user, cid)
        second = confirm_command(self.user, cid)
        self.assertTrue(first.get('ok'))
        self.assertTrue(second.get('ok'))
        self.assertTrue(second.get('duplicate'))

    @override_settings(AI_ENABLED=True)
    @_patch_chain(_CONTACT_JSON)
    def test_resolve_contact_wrong_intent(self, _mock):
        parsed = parse_command(self.user, text='مخاطب تست 09121112233')
        cid = parsed['command_id']
        resp = self.client.post(
            '/api/mobile/v1/ai/nl/resolve-contact',
            {'command_id': cid, 'contact_id': 1},
            format='json',
        )
        self.assertIn(resp.status_code, (400, 404))
