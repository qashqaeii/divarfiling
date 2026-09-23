"""M2 Text-to-Action — create_contact."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from ai_workspace.constants import FEATURE_NL_COMMAND
from ai_workspace.models import AIUsageLog
from ai_workspace.providers.base import ProviderResult
from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from ai_workspace.services.nl_command.state import load_state
from workspace.models import Customer

User = get_user_model()


def _contact_json(**overrides):
    data = {
        'name': 'خانم احمدی',
        'phone': '09121234567',
        'customer_type': 'خریدار',
        'source': None,
        'preferences': {
            'areas': None,
            'property_type': None,
            'min_area': None,
            'max_area': None,
            'budget_min': None,
            'budget_max': None,
            'deposit_min': None,
            'deposit_max': None,
            'rent_min': None,
            'rent_max': None,
            'rooms': None,
        },
        'notes': None,
    }
    prefs = data['preferences']
    pref_keys = set(prefs.keys())
    for key, val in overrides.items():
        if key in pref_keys:
            prefs[key] = val
        else:
            data[key] = val
    return json.dumps({
        'intent': 'create_contact',
        'confidence': 0.92,
        'data': data,
        'missing_fields': [],
        'ambiguous_fields': [],
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
class NLCommandContactTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ct_u', password='x', is_staff=True)
        cache.clear()

    @_patch_chain_json(_contact_json())
    def test_a_parse_confirm_creates_customer(self, _chain):
        parsed = parse_command(self.user, text='خانم احمدی رو با شماره 09121234567 ذخیره کن')
        self.assertEqual(parsed['intent'], 'create_contact')
        self.assertTrue(parsed['can_confirm'])
        out = confirm_command(self.user, parsed['command_id'])
        self.assertTrue(out['ok'])
        self.assertEqual(out['entity_type'], 'contact')
        c = Customer.objects.get(pk=out['entity_id'])
        self.assertEqual(c.name, 'خانم احمدی')
        self.assertEqual(c.phone, '09121234567')

    @_patch_chain_json(_contact_json(name='حسینی', phone=None, areas='پونک'))
    def test_b_preferences_without_phone_blocks_confirm(self, _chain):
        parsed = parse_command(self.user, text='یه مشتری دارم حسینی دنبال پونکه')
        self.assertEqual(parsed['intent'], 'create_contact')
        self.assertFalse(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], ['phone'])
        self.assertEqual(parsed['hint'], 'شماره تماس مخاطب را هم وارد کنید.')
        self.assertFalse(parsed.get('duplicate_contact'))

    @_patch_chain_json(_contact_json(
        name='علی مرادی',
        phone=None,
        areas='مرزداران, پونک',
        min_area=90,
        max_area=110,
        budget_max=13_000_000_000,
    ))
    def test_c_ranges_and_budget(self, _chain):
        parsed = parse_command(
            self.user,
            text='علی مرادی دنبال مرزداران و پونکه، ۹۰ تا ۱۱۰ متر، بودجه تا ۱۳ میلیارد',
        )
        self.assertFalse(parsed['can_confirm'])
        self.assertEqual(parsed['missing_fields'], ['phone'])
        state = load_state(self.user.pk, parsed['command_id'])
        v = state['validated']
        self.assertEqual(v['min_area'], 90)
        self.assertEqual(v['max_area'], 110)
        self.assertEqual(v['budget_max'], 13_000_000_000)

    @_patch_chain_json(_contact_json())
    def test_d_duplicate_phone_blocks(self, _chain):
        Customer.objects.create(user=self.user, name='قبلی', phone='09121234567')
        parsed = parse_command(self.user, text='خانم احمدی 09121234567')
        self.assertFalse(parsed['can_confirm'])
        self.assertTrue(parsed['duplicate_contact'])
        self.assertIn('existing_contact', parsed)
        with self.assertRaises(NLCommandError):
            confirm_command(self.user, parsed['command_id'])
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    @_patch_chain_json(_contact_json())
    def test_e_double_confirm_idempotent(self, _chain):
        parsed = parse_command(self.user, text='ذخیره احمدی')
        self.assertTrue(parsed['can_confirm'])
        first = confirm_command(self.user, parsed['command_id'])
        second = confirm_command(self.user, parsed['command_id'])
        self.assertEqual(first['entity_id'], second['entity_id'])
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    @_patch_chain_json(_contact_json())
    def test_f_wrong_user_rejected(self, _chain):
        parsed = parse_command(self.user, text='ذخیره')
        other = User.objects.create_user(username='other2', password='x', phone='09129998877')
        with self.assertRaises(NLCommandError):
            confirm_command(other, parsed['command_id'])

    @_patch_chain_json(_contact_json(phone='123'))
    def test_g_invalid_phone_no_confirm(self, _chain):
        parsed = parse_command(self.user, text='شماره بد')
        self.assertFalse(parsed['can_confirm'])
        self.assertIn('phone', parsed['ambiguous_fields'])
        self.assertEqual(parsed['hint'], 'شماره تماس واردشده معتبر نیست.')

    @_patch_chain_json(_contact_json(budget_min=20_000_000_000, budget_max=10_000_000_000))
    def test_h_invalid_budget_range(self, _chain):
        parsed = parse_command(self.user, text='بودجه نامعتبر')
        self.assertFalse(parsed['can_confirm'])

    @_patch_chain_json(_contact_json())
    def test_k_confirm_no_llm(self, _chain):
        parsed = parse_command(self.user, text='ذخیره')
        before = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        confirm_command(self.user, parsed['command_id'])
        after = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        self.assertEqual(before, after)

    @_patch_chain_json(_contact_json())
    def test_m_no_raw_phone_in_usage_log_entity(self, _chain):
        parse_command(self.user, text='09121234567 ذخیره')
        log = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).first()
        self.assertIsNotNone(log)
        self.assertNotIn('09121234567', log.entity_id or '')

    @_patch_chain_json(_contact_json(name='حسینی', phone=None))
    def test_correction_merge_command_id(self, _chain):
        first = parse_command(self.user, text='حسینی رو ذخیره کن')
        self.assertFalse(first['can_confirm'])
        self.assertEqual(first['missing_fields'], ['phone'])
        cid = first['command_id']
        with _patch_chain_json(_contact_json(name='حسینی', phone='09125556677')):
            second = parse_command(
                self.user,
                text='09125556677',
                command_id=cid,
            )
        self.assertEqual(second['command_id'], cid)
        self.assertTrue(second['can_confirm'])
        state = load_state(self.user.pk, cid)
        self.assertEqual(state['validated']['phone'], '09125556677')
