"""M2.1 — Full Contact Intelligence."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from ai_workspace.services.nl_command.contact_areas import map_area_names
from ai_workspace.services.nl_command.contact_validators import validate_contact_parse
from ai_workspace.services.nl_command.preview import build_contact_preview
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from ai_workspace.services.nl_command.state import load_state
from ai_workspace.providers.base import ProviderResult
from workspace.models import Customer

User = get_user_model()


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


def _nested_contact_payload(**overrides):
    data = {
        'name': 'احمدی',
        'customer_type': 'خریدار',
        'contact': {'phone': None, 'phone_alt': None, 'email': None},
        'location': {'city': None, 'district': None},
        'profile': {'job': None, 'is_legal_entity': None, 'company_name': None},
        'financial': {
            'budget_min': None, 'budget_max': None,
            'deposit_min': None, 'deposit_max': None,
            'rent_min': None, 'rent_max': None,
        },
        'preferences': {
            'property_type': None, 'rooms_min': None, 'rooms_max': None,
            'min_area': None, 'max_area': None,
            'year_min': None, 'year_max': None,
            'floor_min': None, 'floor_max': None,
            'areas': None, 'required_amenities': None,
        },
        'crm': {
            'status': None, 'priority': None, 'source': None,
            'next_followup_date_text': None, 'tags': None,
        },
        'notes': None,
    }
    for key, val in overrides.items():
        if '__' in key:
            grp, sub = key.split('__', 1)
            block = data.setdefault(grp, {})
            if isinstance(block, dict):
                block[sub] = val
        else:
            data[key] = val
    return json.dumps({
        'intent': 'create_contact',
        'confidence': 0.9,
        'data': data,
        'missing_fields': [],
        'ambiguous_fields': [],
        'requires_confirmation': True,
    }, ensure_ascii=False)


class ContactAreasTests(TestCase):
    def test_map_exact_normalized(self):
        mapped = map_area_names(['سعادت آباد', 'پونک'], ['سعادت‌آباد', 'ونک'])
        self.assertEqual(mapped[0], 'سعادت‌آباد')
        self.assertEqual(mapped[1], 'پونک')

    def test_custom_area_preserved(self):
        mapped = map_area_names(['محله ناشناخته'], ['پونک'])
        self.assertEqual(mapped, ['محله ناشناخته'])


class ContactValidatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='m21_u', password='x')

    def test_name_only(self):
        v, missing, amb, _ = validate_contact_parse(
            {'name': 'علی'},
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertEqual(v['name'], 'علی')
        self.assertFalse(missing)
        self.assertEqual(v['customer_type'], '')

    def test_invalid_budget_range(self):
        data = {
            'name': 'علی',
            'financial': {'budget_min': 20_000_000_000, 'budget_max': 10_000_000_000},
        }
        v, missing, amb, _ = validate_contact_parse(data, llm_missing=[], llm_ambiguous=[])
        self.assertIn('budget_min', amb)

    def test_tenant_deposit_rent(self):
        data = {
            'name': 'رضایی',
            'customer_type': 'مستاجر',
            'preferences': {'areas': ['پونک']},
            'financial': {'deposit_max': 500_000_000, 'rent_max': 30_000_000},
        }
        v, missing, amb, _ = validate_contact_parse(data, llm_missing=[], llm_ambiguous=[], user=self.user)
        self.assertEqual(v['deposit_max'], 500_000_000)
        self.assertEqual(v['rent_max'], 30_000_000)
        self.assertIn('areas', v['_explicit_fields'])

    def test_required_amenities(self):
        data = {
            'name': 'محمدی',
            'preferences': {
                'min_area': 90,
                'required_amenities': ['parking', 'elevator'],
                'floor_min': 1,
                'floor_max': 3,
            },
        }
        v, _, amb, _ = validate_contact_parse(data, llm_missing=[], llm_ambiguous=[])
        self.assertTrue(v['want_parking'])
        self.assertTrue(v['want_elevator'])
        self.assertFalse(amb)

    def test_explicit_priority_source(self):
        data = {
            'name': 'کریمی',
            'crm': {'priority': 'بالا', 'source': 'اینستاگرام'},
            'contact': {'phone_alt': '09121112233'},
            'profile': {'job': 'پزشک'},
        }
        v, _, amb, _ = validate_contact_parse(data, llm_missing=[], llm_ambiguous=[])
        self.assertEqual(v['priority'], 'بالا')
        self.assertEqual(v['source'], 'اینستاگرام')
        self.assertEqual(v['job'], 'پزشک')

    def test_invalid_enum_priority(self):
        data = {'name': 'x', 'crm': {'priority': 'فوری'}}
        v, _, amb, _ = validate_contact_parse(data, llm_missing=[], llm_ambiguous=[])
        self.assertIn('priority', amb)

    def test_followup_date(self):
        data = {'name': 'احمدی', 'crm': {'next_followup_date_text': 'پس فردا'}}
        v, _, amb, _ = validate_contact_parse(
            data, llm_missing=[], llm_ambiguous=[], tz_name='Asia/Tehran',
        )
        self.assertIsNotNone(v['next_follow_up'])
        self.assertNotIn('next_follow_up', amb)

    def test_preview_skips_defaults(self):
        v, _, _, _ = validate_contact_parse({'name': 'احمدی'}, llm_missing=[], llm_ambiguous=[])
        preview = build_contact_preview(v)
        self.assertEqual(len(preview['sections']), 1)
        self.assertNotIn('customer_type', preview['sections'][0].get('lines', [])[0])


@override_settings(AI_ENABLED=True)
class ContactM21IntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='m21_int', password='x', is_staff=True)
        cache.clear()

    @_patch_chain_json(_nested_contact_payload(
        name='احمدی',
        customer_type='خریدار',
        preferences__property_type='آپارتمان',
        preferences__areas=['سعادت آباد', 'شهرک غرب'],
        preferences__min_area=100,
        preferences__max_area=130,
        preferences__rooms_min=2,
        preferences__rooms_max=3,
        financial__budget_min=15_000_000_000,
        financial__budget_max=20_000_000_000,
    ))
    def test_full_buyer_confirm(self, _chain):
        parsed = parse_command(self.user, text='احمدی خریدار آپارتمان')
        self.assertTrue(parsed['can_confirm'])
        out = confirm_command(self.user, parsed['command_id'])
        c = Customer.objects.get(pk=out['entity_id'])
        self.assertEqual(c.min_area, 100)
        self.assertEqual(c.budget_max, 20_000_000_000)
        self.assertEqual(c.rooms_min, 2)

    @_patch_chain_json(_nested_contact_payload(name='حسینی', preferences__areas='پونک'))
    def test_backward_compat_areas_string(self, _chain):
        parsed = parse_command(self.user, text='حسینی پونک')
        self.assertTrue(parsed['can_confirm'])
        state = load_state(self.user.pk, parsed['command_id'])
        self.assertIn('پونک', state['validated']['areas'])

    @_patch_chain_json(_nested_contact_payload())
    def test_duplicate_phone(self, _chain):
        data = json.loads(_nested_contact_payload())
        data['data']['contact']['phone'] = '09121234567'
        Customer.objects.create(user=self.user, name='قبلی', phone='09121234567')
        with _patch_chain_json(json.dumps(data, ensure_ascii=False)):
            parsed = parse_command(self.user, text='duplicate')
        self.assertTrue(parsed['duplicate_contact'])
