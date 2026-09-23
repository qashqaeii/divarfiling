"""Gate context فایل شخصی — بدون LLM برای ملک ناقص."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ai_workspace.services.property_context_gate import (
    assess_property_context,
    has_meaningful_property_context,
)
from ai_workspace.services.property_summary import generate_property_summary
from ai_workspace.services.property_summary_skip import PropertySummaryInsufficientContext
from ai_workspace.services.quota import get_or_create_quota
from workspace.models import CRMProperty


def _prop(user, **kwargs) -> CRMProperty:
    defaults = {
        'user': user,
        'title': 'ملک تست',
        'deal_mode': 'فروش',
        'property_type': 'آپارتمان',
    }
    defaults.update(kwargs)
    return CRMProperty.objects.create(**defaults)


@override_settings(AI_ENABLED=True)
class PropertyContextGateTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='gate_user', password='x', phone='09120001111',
        )

    def test_title_only_not_meaningful(self):
        prop = _prop(self.user, title='فقط عنوان')
        self.assertFalse(has_meaningful_property_context(prop))

    def test_title_and_price_not_meaningful(self):
        prop = _prop(self.user, title='ویلا', sale_price=10_000_000_000)
        self.assertFalse(has_meaningful_property_context(prop))

    def test_title_and_area_only_not_meaningful(self):
        prop = _prop(self.user, title='ویلا', area=120)
        self.assertFalse(has_meaningful_property_context(prop))

    def test_price_area_neighborhood_rooms_meaningful(self):
        prop = _prop(
            self.user,
            sale_price=12_000_000_000,
            area=90,
            neighborhood='پونک',
            rooms='۳',
        )
        self.assertTrue(has_meaningful_property_context(prop))

    def test_features_raise_detail_score(self):
        prop = _prop(
            self.user,
            sale_price=8_000_000_000,
            area=100,
            neighborhood='سعادت‌آباد',
            has_parking=True,
            has_elevator=True,
        )
        self.assertTrue(has_meaningful_property_context(prop))

    def test_notes_phone_only_not_meaningful(self):
        prop = _prop(
            self.user,
            sale_price=5_000_000_000,
            area=80,
            notes='تماس 09123456789',
        )
        self.assertFalse(has_meaningful_property_context(prop))

    def test_meaningful_notes_with_core_fields(self):
        prop = _prop(
            self.user,
            sale_price=6_000_000_000,
            area=75,
            neighborhood='ونک',
            notes='ملک نورگیر جنوبی، بازسازی کامل سال گذشته انجام شده است.',
        )
        self.assertTrue(has_meaningful_property_context(prop))


@override_settings(AI_ENABLED=True)
class PropertySummaryGateIntegrationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='gate_int', password='x', phone='09120002222',
        )
        self.url = reverse(
            'workspace:ai_workspace:property_summary',
            kwargs={'property_id': 0},
        )

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @patch('ai_workspace.services.gateway.run')
    def test_skip_does_not_call_gateway(self, mocked_run, _license):
        prop = _prop(self.user, title='خالی')
        with self.assertRaises(PropertySummaryInsufficientContext):
            generate_property_summary(self.user, prop)
        mocked_run.assert_not_called()

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @patch('ai_workspace.services.property_summary.run')
    def test_meaningful_property_calls_gateway(self, mocked_run, _license):
        from ai_workspace.services.gateway import GatewayResult

        prop = _prop(
            self.user,
            sale_price=12_000_000_000,
            area=100,
            neighborhood='پونک',
            rooms='۲',
        )
        mocked_run.return_value = GatewayResult(
            feature='listing_summary',
            provider='arvan',
            model='test',
            text='{}',
            data={'summary': 'x', 'highlights': ['a']},
            is_fallback=False,
            from_cache=False,
            latency_ms=1,
            input_tokens=1,
            output_tokens=1,
            status='ok',
        )
        generate_property_summary(self.user, prop)
        mocked_run.assert_called_once()

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @patch('ai_workspace.services.gateway.run')
    def test_skip_does_not_consume_quota(self, mocked_run, _license):
        prop = _prop(self.user, title='فقط عنوان')
        quota = get_or_create_quota(self.user)
        quota.listing_summary_used = 2
        quota.used_today = 2
        quota.save()
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('workspace:ai_workspace:property_summary', kwargs={'property_id': prop.id}),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('skipped'))
        mocked_run.assert_not_called()
        quota.refresh_from_db()
        self.assertEqual(quota.listing_summary_used, 2)
        self.assertEqual(quota.used_today, 2)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_web_skipped_json_contract(self, _license):
        prop = _prop(self.user, sale_price=9_000_000_000)
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('workspace:ai_workspace:property_summary', kwargs={'property_id': prop.id}),
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get('ok'))
        self.assertTrue(body.get('skipped'))
        self.assertEqual(body.get('skip_reason'), 'insufficient_context')
        self.assertIn('اطلاعات بیشتری', body.get('message', ''))
