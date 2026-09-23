"""create_contact — name + phone required for confirm."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from ai_workspace.providers.base import ProviderResult
from ai_workspace.services.nl_command.preview import build_contact_preview
from ai_workspace.services.nl_command.contact_validators import validate_contact_parse
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from ai_workspace.services.nl_command.state import load_state
from workspace.models import Customer

User = get_user_model()


def _payload(data: dict, *, missing=None, ambiguous=None) -> str:
    return json.dumps({
        'intent': 'create_contact',
        'confidence': 0.9,
        'data': data,
        'missing_fields': missing or [],
        'ambiguous_fields': ambiguous or [],
        'requires_confirmation': True,
    }, ensure_ascii=False)


def _patch_chain_json(payload: str):
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(
        text=payload,
        provider='arvan',
        model='test',
        input_tokens=5,
        output_tokens=20,
        latency_ms=50,
        is_fallback=False,
    )
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])


@override_settings(AI_ENABLED=True)
class NLCommandContactRequiredTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ct_req', password='x', is_staff=True)
        cache.clear()

    @_patch_chain_json(_payload({'name': 'احمدی', 'phone': None}))
    def test_a_name_only(self, _chain):
        parsed = parse_command(self.user, text='احمدی رو ذخیره کن')
        self.assertFalse(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], ['phone'])
        self.assertEqual(parsed['hint'], 'شماره تماس مخاطب را هم وارد کنید.')

    @_patch_chain_json(_payload({'name': None, 'phone': '09121234567'}))
    def test_b_phone_only(self, _chain):
        parsed = parse_command(self.user, text='09121234567 رو ذخیره کن')
        self.assertFalse(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], ['name'])
        self.assertEqual(parsed['hint'], 'نام مخاطب را هم وارد کنید.')

    @_patch_chain_json(_payload({'name': 'احمدی', 'phone': '09121234567'}))
    def test_c_name_and_phone_confirm(self, _chain):
        parsed = parse_command(self.user, text='احمدی رو با شماره 09121234567 ذخیره کن')
        self.assertTrue(parsed['can_confirm'])
        out = confirm_command(self.user, parsed['command_id'])
        c = Customer.objects.get(pk=out['entity_id'])
        self.assertEqual(c.name, 'احمدی')
        self.assertEqual(c.phone, '09121234567')

    @_patch_chain_json(_payload({
        'name': 'حسینی',
        'phone': None,
        'customer_type': 'خریدار',
        'preferences': {'property_type': 'آپارتمان', 'areas': ['پونک']},
    }))
    def test_d_preferences_kept_phone_missing(self, _chain):
        parsed = parse_command(
            self.user,
            text='یه مشتری دارم حسینی، خریدار آپارتمانه و دنبال پونکه',
        )
        self.assertFalse(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], ['phone'])
        v = load_state(self.user.pk, parsed['command_id'])['validated']
        self.assertEqual(v['name'], 'حسینی')
        self.assertIn('پونک', v['areas'])
        self.assertEqual(v['property_type'], 'آپارتمان')

    @_patch_chain_json(_payload({
        'name': 'علی مرادی',
        'phone': None,
        'preferences': {
            'areas': ['سعادت آباد', 'شهرک غرب'],
            'min_area': 90,
            'max_area': 120,
        },
    }))
    def test_e_preferences_kept_phone_missing(self, _chain):
        parsed = parse_command(
            self.user,
            text='علی مرادی دنبال سعادت‌آباد و شهرک غربه، ۹۰ تا ۱۲۰ متر',
        )
        self.assertFalse(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], ['phone'])
        v = load_state(self.user.pk, parsed['command_id'])['validated']
        self.assertEqual(v['min_area'], 90)
        self.assertEqual(v['max_area'], 120)

    @_patch_chain_json(_payload({'name': 'علی', 'phone': '123'}))
    def test_f_invalid_phone(self, _chain):
        parsed = parse_command(self.user, text='علی 123')
        self.assertFalse(parsed['can_confirm'])
        self.assertIn('phone', parsed['ambiguous_fields'])
        self.assertEqual(parsed['hint'], 'شماره تماس واردشده معتبر نیست.')
        self.assertNotIn('phone', parsed['missing_fields'])

    @_patch_chain_json(_payload(
        {'name': 'سارا', 'phone': '09121112233'},
        missing=['customer_type', 'property_type'],
    ))
    def test_g_llm_wrong_missing_ignored(self, _chain):
        parsed = parse_command(self.user, text='سارا 09121112233')
        self.assertTrue(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], [])

    def test_preview_no_implicit_crm_defaults(self):
        v, _, _, _ = validate_contact_parse(
            {
                'name': 'سارا',
                'contact': {'phone': '09121234000'},
                'crm': {
                    'status': 'جدید',
                    'priority': 'بالا',
                    'source': 'اینستاگرام',
                },
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        preview = build_contact_preview(v)
        blob = str(preview.get('sections'))
        self.assertNotIn('وضعیت', blob)
        self.assertIn('بالا', blob)
        self.assertIn('اینستاگرام', blob)

    def test_preview_name_phone_only_no_status_priority(self):
        v, _, _, _ = validate_contact_parse(
            {'name': 'علی', 'contact': {'phone': '09121234567'}},
            llm_missing=[],
            llm_ambiguous=[],
        )
        preview = build_contact_preview(v)
        blob = str(preview.get('sections'))
        self.assertNotIn('وضعیت', blob)
        self.assertNotIn('اولویت', blob)
        self.assertNotIn('جدید', blob)

    @_patch_chain_json(_payload({'name': None, 'phone': '09125556677'}))
    def test_merge_phone_then_name(self, _chain):
        first = parse_command(self.user, text='09125556677')
        cid = first['command_id']
        self.assertEqual(first['missing_fields'], ['name'])
        with _patch_chain_json(_payload({'name': 'حسینی', 'phone': None})):
            second = parse_command(self.user, text='حسینی', command_id=cid)
        self.assertTrue(second['can_confirm'])
        v = load_state(self.user.pk, cid)['validated']
        self.assertEqual(v['name'], 'حسینی')
        self.assertEqual(v['phone'], '09125556677')
