"""M3 Text-to-Action — create_personal_property."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from ai_workspace.constants import FEATURE_NL_COMMAND, NL_COMMAND_INTENT_CREATE_REMINDER
from ai_workspace.models import AIUsageLog
from ai_workspace.providers.base import ProviderResult
from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from ai_workspace.services.nl_command.state import load_state
from ai_workspace.services.nl_command.preview import build_property_preview
from ai_workspace.services.nl_command.validators_property import build_nl_property_title, validate_property_parse
from workspace.models import CRMProperty, Customer, Reminder

User = get_user_model()


def _property_json(**overrides):
    data = {
        'title': None,
        'property_type': 'آپارتمان',
        'deal_mode': 'فروش',
        'location': {
            'city': None,
            'district': None,
            'neighborhood': 'پونک',
            'address': None,
        },
        'area': 120,
        'rooms': 2,
        'floor': 3,
        'total_floors': None,
        'build_year': None,
        'has_parking': True,
        'has_storage': None,
        'has_elevator': None,
        'sale_price': 12_000_000_000,
        'deposit': None,
        'monthly_rent': None,
        'amenities': [],
        'notes': None,
    }
    data.update(overrides)
    return json.dumps({
        'intent': 'create_personal_property',
        'confidence': 0.9,
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
class NLCommandPropertyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prop_nl', password='x', is_staff=True)
        cache.clear()

    @_patch_chain_json(_property_json())
    def test_a_sale_parse_confirm(self, _chain):
        parsed = parse_command(
            self.user,
            text='یه فایل شخصی ثبت کن پونک ۱۲۰ متر دو خواب طبقه سوم پارکینگ داره قیمت ۱۲ میلیارد',
        )
        self.assertEqual(parsed['intent'], 'create_personal_property')
        self.assertTrue(parsed['can_confirm'])
        state = load_state(self.user.pk, parsed['command_id'])
        self.assertIsNone(state['validated']['has_elevator'])
        out = confirm_command(self.user, parsed['command_id'])
        self.assertEqual(out['entity_type'], 'property')
        prop = CRMProperty.objects.get(pk=out['entity_id'])
        self.assertEqual(prop.area, 120)
        self.assertEqual(prop.sale_price, 12_000_000_000)
        self.assertTrue(prop.has_parking)
        self.assertFalse(prop.has_elevator)

    @_patch_chain_json(_property_json(
        deal_mode='اجاره',
        sale_price=None,
        deposit=500_000_000,
        monthly_rent=25_000_000,
        neighborhood='صادقیه',
        area=80,
        has_parking=None,
        floor=None,
        rooms=2,
    ))
    def test_b_rent_parse_confirm(self, _chain):
        parsed = parse_command(self.user, text='صادقیه ۸۰ متر ۵۰۰ میلیون ودیعه ۲۵ میلیون اجاره')
        self.assertTrue(parsed['can_confirm'])
        confirm_command(self.user, parsed['command_id'])
        prop = CRMProperty.objects.get(user=self.user)
        self.assertEqual(prop.deal_mode, 'اجاره')
        self.assertEqual(prop.deposit, 500_000_000)
        self.assertEqual(prop.monthly_rent, 25_000_000)

    @_patch_chain_json(_property_json(has_parking=None))
    def test_c_unmentioned_parking_null(self, _chain):
        parsed = parse_command(self.user, text='۱۲۰ متر دو خواب')
        state = load_state(self.user.pk, parsed['command_id'])
        self.assertIsNone(state['validated']['has_parking'])

    @_patch_chain_json(_property_json(has_parking=False))
    def test_d_explicit_no_parking_false(self, _chain):
        parsed = parse_command(self.user, text='پارکینگ نداره')
        state = load_state(self.user.pk, parsed['command_id'])
        self.assertFalse(state['validated']['has_parking'])

    def test_e_price_normalization_validator(self):
        validated, missing, ambiguous, _ = validate_property_parse(
            {
                'property_type': 'آپارتمان',
                'deal_mode': 'فروش',
                'location': {'neighborhood': 'پونک'},
                'area': 120,
                'sale_price': 12_000_000_000,
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertEqual(validated['sale_price'], 12_000_000_000)
        self.assertFalse(missing)
        self.assertFalse(ambiguous)

    @_patch_chain_json(_property_json(sale_price=-1))
    def test_f_negative_price_no_confirm(self, _chain):
        parsed = parse_command(self.user, text='قیمت منفی')
        self.assertFalse(parsed['can_confirm'])
        self.assertIn('sale_price', parsed['ambiguous_fields'])
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 0)

    @_patch_chain_json(_property_json(floor=5, total_floors=3))
    def test_g_floor_gt_total_no_confirm(self, _chain):
        parsed = parse_command(self.user, text='طبقه بالاتر از ساختمان')
        self.assertFalse(parsed['can_confirm'])
        self.assertIn('floor', parsed['ambiguous_fields'])

    @_patch_chain_json(_property_json(area=None, deal_mode=None, sale_price=None, neighborhood='پونک'))
    def test_h_missing_context_no_confirm(self, _chain):
        parsed = parse_command(self.user, text='یه فایل پونک ثبت کن')
        self.assertFalse(parsed['can_confirm'])
        self.assertIn('hint', parsed)

    @_patch_chain_json(_property_json())
    def test_i_double_confirm_idempotent(self, _chain):
        parsed = parse_command(self.user, text='ثبت فایل')
        first = confirm_command(self.user, parsed['command_id'])
        second = confirm_command(self.user, parsed['command_id'])
        self.assertEqual(first['entity_id'], second['entity_id'])
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 1)

    @_patch_chain_json(_property_json())
    def test_j_wrong_user_rejected(self, _chain):
        parsed = parse_command(self.user, text='ثبت')
        other = User.objects.create_user(username='other_p', password='x', phone='09128887766')
        with self.assertRaises(NLCommandError):
            confirm_command(other, parsed['command_id'])

    @_patch_chain_json(_property_json())
    def test_k_confirm_no_llm(self, _chain):
        parsed = parse_command(self.user, text='ثبت')
        before = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        confirm_command(self.user, parsed['command_id'])
        after = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        self.assertEqual(before, after)

    @_patch_chain_json(_property_json())
    def test_l_quota_only_parse(self, _chain):
        before = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        parse_command(self.user, text='ثبت فایل')
        after = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        self.assertEqual(after, before + 1)

    @_patch_chain_json(json.dumps({
        'intent': 'create_reminder',
        'confidence': 0.9,
        'data': {
            'contact_name': None,
            'title': 'یادآوری',
            'note': '',
            'date_text': 'فردا',
            'time_text': '۱۰',
        },
        'missing_fields': [],
        'ambiguous_fields': [],
        'requires_confirmation': True,
    }, ensure_ascii=False))
    def test_m_reminder_regression(self, _chain):
        parsed = parse_command(self.user, text='فردا ساعت ۱۰ یادم بنداز')
        self.assertEqual(parsed['intent'], NL_COMMAND_INTENT_CREATE_REMINDER)
        self.assertEqual(Reminder.objects.count(), 0)

    @_patch_chain_json(json.dumps({
        'intent': 'create_contact',
        'confidence': 0.9,
        'data': {
            'name': 'حسینی',
            'phone': '09121234567',
            'customer_type': 'خریدار',
            'source': None,
            'preferences': {'areas': 'پونک'},
            'notes': None,
        },
        'missing_fields': [],
        'ambiguous_fields': [],
        'requires_confirmation': True,
    }, ensure_ascii=False))
    def test_n_contact_regression(self, _chain):
        parsed = parse_command(self.user, text='حسینی پونک')
        self.assertEqual(parsed['intent'], 'create_contact')
        self.assertTrue(parsed['can_confirm'])
        confirm_command(self.user, parsed['command_id'])
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    @_patch_chain_json(_property_json(neighborhood='یادداشت محرمانه آدرس خیابان'))
    def test_p_no_raw_in_usage_log_entity(self, _chain):
        parse_command(self.user, text='ثبت فایل با یادداشت محرمانه')
        log = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).first()
        self.assertIsNotNone(log)
        self.assertNotIn('محرمانه', log.entity_id or '')

    @_patch_chain_json(_property_json(area=None, deal_mode=None, sale_price=None, neighborhood='پونک'))
    def test_correction_merge_command_id(self, _chain):
        first = parse_command(self.user, text='یه فایل پونک ثبت کن')
        cid = first['command_id']
        with _patch_chain_json(_property_json(area=120, deal_mode='فروش', sale_price=12_000_000_000)):
            second = parse_command(
                self.user,
                text='۱۲۰ متر فروش ۱۲ میلیارد',
                command_id=cid,
            )
        self.assertEqual(second['command_id'], cid)
        self.assertTrue(second['can_confirm'])

    def test_build_year_short_form(self):
        validated, missing, ambiguous, _ = validate_property_parse(
            {
                'specs': {'build_year': 98},
                'area': 100,
                'deal_mode': 'فروش',
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertEqual(validated['build_year'], 1398)
        self.assertFalse(ambiguous)

    def test_default_apartment_not_explicit_preview(self):
        validated, _, _, _ = validate_property_parse(
            {
                'property_type': 'آپارتمان',
                'deal_mode': 'فروش',
                'location': {'neighborhood': 'پونک'},
                'area': 120,
                'financial': {'sale_price': 1_000_000_000},
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertNotIn('property_type', validated.get('_explicit_fields') or [])

    def test_sale_rent_conflict(self):
        validated, missing, ambiguous, _ = validate_property_parse(
            {
                'area': 100,
                'financial': {'sale_price': 1_000_000_000, 'deposit': 100_000_000},
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertIn('deal_mode', ambiguous)
        self.assertFalse(validated.get('deal_mode'))

    def test_title_auto_without_hallucinated_type(self):
        validated = {
            'area': 120.0,
            'neighborhood': 'پونک',
            'property_type': '',
            '_explicit_fields': ['area', 'neighborhood'],
        }
        title = build_nl_property_title(validated)
        self.assertIn('متری', title)
        self.assertIn('پونک', title)
        self.assertNotIn('آپارتمان', title)

    @_patch_chain_json(_property_json(area=120))
    def test_correction_override_area(self, _chain):
        first = parse_command(self.user, text='۱۲۰ متر فروش')
        cid = first['command_id']
        with _patch_chain_json(_property_json(area=130, deal_mode='فروش', sale_price=12_000_000_000)):
            second = parse_command(
                self.user,
                text='نه ۱۳۰ متر',
                command_id=cid,
                resume_correction=True,
            )
        self.assertEqual(second['command_id'], cid)
        state = load_state(self.user.pk, cid)
        self.assertEqual(state['validated']['area'], 130)

    @_patch_chain_json(_property_json(rooms=2, notes='معرف گفت سریع بفروشیم'))
    def test_complete_then_new_command_clears_stale_state(self, _chain):
        first = parse_command(
            self.user,
            text='یه فایل پونک ثبت کن، ۱۲۰ متر، دو خواب، فروش ۱۲ میلیارد، معرف گفت سریع بفروشیم',
        )
        self.assertTrue(first['can_confirm'])
        cid1 = first['command_id']
        second_payload = _property_json(
            rooms=None,
            floor=None,
            has_parking=None,
            notes=None,
            owner={'owner_name': 'آقای رضایی', 'phone': '09121234567'},
        )
        with _patch_chain_json(second_payload):
            second = parse_command(
                self.user,
                text='یه فایل ۱۲۰ متری پونک ثبت کن، مالک آقای رضایی شماره 09121234567، فروش ۱۲ میلیارد',
                command_id=cid1,
            )
        self.assertNotEqual(second['command_id'], cid1)
        state = load_state(self.user.pk, second['command_id'])
        v = state['validated']
        self.assertFalse((v.get('rooms') or '').strip())
        self.assertFalse((v.get('notes') or '').strip())
        self.assertEqual(v.get('owner_name'), 'آقای رضایی')
        self.assertEqual(v.get('phone'), '09121234567')

    @_patch_chain_json(_property_json())
    def test_complete_then_different_property_no_inherit(self, _chain):
        first = parse_command(self.user, text='پونک ۱۲۰ متر دو خواب فروش ۱۲ میلیارد')
        self.assertTrue(first['can_confirm'])
        rent_payload = _property_json(
            location={
                'city': None,
                'district': None,
                'neighborhood': 'صادقیه',
                'address': None,
            },
            deal_mode='اجاره',
            sale_price=None,
            deposit=500_000_000,
            monthly_rent=25_000_000,
            neighborhood='صادقیه',
            area=80,
            rooms=2,
            floor=None,
            has_parking=None,
            notes=None,
        )
        with _patch_chain_json(rent_payload):
            second = parse_command(
                self.user,
                text='صادقیه ۸۰ متر ۵۰۰ میلیون ودیعه ۲۵ میلیون اجاره',
            )
        v = load_state(self.user.pk, second['command_id'])['validated']
        self.assertEqual(v.get('neighborhood'), 'صادقیه')
        self.assertEqual(v.get('area'), 80)
        self.assertNotEqual(v.get('neighborhood'), 'پونک')
        self.assertEqual(v.get('sale_price'), None)

    def test_owner_phone_explicit(self):
        validated, missing, ambiguous, _ = validate_property_parse(
            {
                'area': 90,
                'deal_mode': 'فروش',
                'owner': {'phone': '09121234567', 'owner_name': 'رضایی'},
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertEqual(validated['phone'], '09121234567')
        self.assertIn('phone', validated['_explicit_fields'])
        self.assertFalse(missing)
        preview = build_property_preview(validated)
        owner_sec = next((s for s in preview['sections'] if 'مالک' in (s.get('title') or '')), None)
        self.assertIsNotNone(owner_sec)
        joined = ' '.join(owner_sec['lines'])
        self.assertIn('نام مالک:', joined)
        self.assertIn('شماره مالک:', joined)
        self.assertNotIn('مخاطب', joined)

    def test_crm_source_ignored_not_in_preview(self):
        validated, _, ambiguous, _ = validate_property_parse(
            {
                'area': 100,
                'deal_mode': 'فروش',
                'crm': {'source': 'معرف'},
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertFalse(ambiguous)
        self.assertNotIn('source', validated)
        preview = build_property_preview(validated)
        blob = str(preview.get('sections'))
        self.assertNotIn('منبع', blob)
        self.assertNotIn('معرف', blob)

    def test_notes_for_unstructured_descriptor(self):
        validated, _, ambiguous, _ = validate_property_parse(
            {
                'area': 100,
                'deal_mode': 'فروش',
                'notes': 'خیلی خوش‌نقشه و نورگیر',
            },
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertIn('خوش', validated['notes'])
        self.assertFalse(ambiguous)
