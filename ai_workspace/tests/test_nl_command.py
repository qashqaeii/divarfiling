"""M1 Text-to-Action — create_reminder only."""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ai_workspace.constants import FEATURE_CRM_MESSAGE, FEATURE_LISTING_SUMMARY, FEATURE_NL_COMMAND
from ai_workspace.models import AIQuota, AIUsageLog
from ai_workspace.providers.base import ProviderError, ProviderResult
from ai_workspace.services.generation import get_feature_generation
from ai_workspace.services.gateway import run as gateway_run
from ai_workspace.services.nl_command.datetime_parser import parse_due_datetime
from ai_workspace.services.nl_command.service import (
    NLCommandError,
    confirm_command,
    parse_command,
    resolve_contact,
)
from ai_workspace.services.nl_command.state import load_state, save_state
from ai_workspace.services.quota import get_or_create_quota
from workspace.models import Customer, Reminder

User = get_user_model()

_MOCK_REMINDER_JSON = json.dumps({
    'intent': 'create_reminder',
    'confidence': 0.9,
    'data': {
        'contact_name': 'احمدی',
        'title': 'تماس با احمدی',
        'note': '',
        'date_text': 'فردا',
        'time_text': 'ساعت ده',
    },
    'missing_fields': [],
    'ambiguous_fields': [],
    'requires_confirmation': True,
}, ensure_ascii=False)


def _reminder_json(**data_overrides):
    data = {
        'contact_name': 'احمدی',
        'title': 'تماس با احمدی',
        'note': '',
        'date_text': 'فردا',
        'time_text': 'ساعت ده',
    }
    data.update(data_overrides)
    return json.dumps({
        'intent': 'create_reminder',
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
        output_tokens=10,
        latency_ms=50,
        is_fallback=False,
    )
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])


def _patch_chain_ok():
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(
        text=_MOCK_REMINDER_JSON,
        provider='arvan',
        model='test',
        input_tokens=5,
        output_tokens=10,
        latency_ms=50,
        is_fallback=False,
    )
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])


def _patch_chain_unknown():
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(
        text=json.dumps({
            'intent': 'unknown',
            'confidence': 0.5,
            'data': {
                'contact_name': None,
                'title': None,
                'note': None,
                'date_text': None,
                'time_text': None,
            },
            'missing_fields': [],
            'ambiguous_fields': [],
            'requires_confirmation': False,
        }, ensure_ascii=False),
        provider='arvan',
        model='test',
        input_tokens=5,
        output_tokens=10,
        latency_ms=50,
        is_fallback=False,
    )
    return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])


@override_settings(AI_ENABLED=True)
class NLCommandGenerationTests(TestCase):
    def test_feature_generation_overrides(self):
        nl = get_feature_generation(FEATURE_NL_COMMAND)
        self.assertAlmostEqual(nl['temperature'], 0.1)
        self.assertEqual(nl['max_tokens'], 700)
        listing = get_feature_generation(FEATURE_LISTING_SUMMARY)
        self.assertAlmostEqual(listing['temperature'], 0.4)
        crm = get_feature_generation(FEATURE_CRM_MESSAGE)
        self.assertAlmostEqual(crm['temperature'], 0.4)

    @_patch_chain_ok()
    def test_provider_receives_low_temperature(self, _chain):
        provider = _chain.return_value[0]
        user = User.objects.create_user(username='gen_u', password='x', is_staff=True)
        gateway_run(
            FEATURE_NL_COMMAND,
            user,
            context={'user_text': 'test', 'timezone': 'Asia/Tehran', 'now_local_display': 'x', 'content_version': 'v1'},
            entity_type='nl_parse',
            entity_id='e1',
        )
        kwargs = provider.complete.call_args.kwargs
        self.assertAlmostEqual(kwargs['generation']['temperature'], 0.1)


@override_settings(AI_ENABLED=True)
class NLCommandDatetimeTests(TestCase):
    def test_tomorrow_ten(self):
        tz = 'Asia/Tehran'
        now = timezone.now()
        due, err = parse_due_datetime(date_text='فردا', time_text='ساعت ده', tz_name=tz, now=now)
        self.assertEqual(err, '')
        self.assertIsNotNone(due)
        self.assertGreater(due, now)

    def test_day_after_noon(self):
        now = timezone.now()
        due, err = parse_due_datetime(date_text='پس‌فردا', time_text='ظهر', tz_name='Asia/Tehran', now=now)
        self.assertEqual(err, '')
        self.assertEqual(due.hour, 12)


@override_settings(AI_ENABLED=True)
class NLCommandParseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='nl_u', password='x', is_staff=True)
        self.customer = Customer.objects.create(user=self.user, name='علی احمدی', phone='09120001111')

    @_patch_chain_ok()
    def test_parse_create_reminder(self, _chain):
        result = parse_command(self.user, text='فردا ساعت ده یادم بنداز به احمدی زنگ بزنم')
        self.assertTrue(result['ok'])
        self.assertEqual(result['intent'], 'create_reminder')
        self.assertIn('command_id', result)
        self.assertIn('ai', result)
        self.assertTrue(result['ai'].get('model_label'))

    def test_parse_save_contact_without_phone(self):
        payload = json.dumps({
            'intent': 'create_contact',
            'confidence': 0.9,
            'data': {
                'name': 'حسینی',
                'phone': None,
                'customer_type': 'خریدار',
                'source': None,
                'preferences': {'areas': 'پونک'},
                'notes': None,
            },
            'missing_fields': [],
            'ambiguous_fields': [],
            'requires_confirmation': True,
        }, ensure_ascii=False)
        with _patch_chain_json(payload):
            result = parse_command(self.user, text='یه مشتری دارم حسینی دنبال پونکه')
        self.assertEqual(result['intent'], 'create_contact')
        self.assertTrue(result['can_confirm'])

    def test_contact_single_match(self):
        with _patch_chain_ok():
            result = parse_command(self.user, text='فردا به احمدی زنگ بزنم')
        self.assertTrue(result.get('can_confirm'))

    def test_contact_multiple_match(self):
        Customer.objects.create(user=self.user, name='مریم احمدی', phone='09120002222')
        with _patch_chain_ok():
            result = parse_command(self.user, text='فردا به احمدی زنگ بزنم')
        self.assertFalse(result['can_confirm'])
        self.assertTrue(result.get('contact_candidates'))

    @_patch_chain_json(_reminder_json(contact_name=None, title='یادآوری'))
    def test_confirm_creates_reminder(self, _chain):
        parsed = parse_command(self.user, text='فردا ساعت ده')
        if not parsed.get('can_confirm'):
            state = load_state(self.user.pk, parsed['command_id'])
            state['validated']['contact_id'] = None
            state['validated']['contact_name'] = None
            state['ambiguous_fields'] = []
            save_state(self.user.pk, parsed['command_id'], state)
        out = confirm_command(self.user, parsed['command_id'])
        self.assertTrue(out['ok'])
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 1)

    @_patch_chain_json(_reminder_json(contact_name=None, title='یادآوری'))
    def test_double_confirm_idempotent(self, _chain):
        parsed = parse_command(self.user, text='فردا ساعت ده')
        state = load_state(self.user.pk, parsed['command_id'])
        state['ambiguous_fields'] = []
        state['validated']['contact_id'] = None
        state['validated']['contact_name'] = None
        save_state(self.user.pk, parsed['command_id'], state)
        first = confirm_command(self.user, parsed['command_id'])
        second = confirm_command(self.user, parsed['command_id'])
        self.assertEqual(first['entity_id'], second['entity_id'])
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 1)

    def test_wrong_user_command(self):
        other = User.objects.create_user(username='other', password='x', phone='09129999999')
        save_state(self.user.pk, 'cmd-1', {'validated': {}, 'created_reminder_id': None})
        with self.assertRaises(NLCommandError):
            confirm_command(other, 'cmd-1')

    @_patch_chain_json(_reminder_json(contact_name=None, title='یادآوری'))
    def test_confirm_no_extra_llm_quota(self, _chain):
        parsed = parse_command(self.user, text='فردا ساعت ده')
        before = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        state = load_state(self.user.pk, parsed['command_id'])
        state['ambiguous_fields'] = []
        state['validated']['contact_name'] = None
        save_state(self.user.pk, parsed['command_id'], state)
        confirm_command(self.user, parsed['command_id'])
        after = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        self.assertEqual(before, after)

    @patch('ai_workspace.constants.has_active_bot_license', return_value=True)
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    @_patch_chain_ok()
    def test_parse_quota_consumed(self, _chain, _lic, _lic2):
        user = User.objects.create_user(username='quota_nl', password='x', phone='09128887777')
        quota = get_or_create_quota(user)
        used_before = quota.nl_command_used
        parse_command(user, text='فردا ساعت ده')
        quota.refresh_from_db()
        self.assertEqual(quota.nl_command_used, used_before + 1)


@override_settings(AI_ENABLED=True)
class NLCommandViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='view_u', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.user)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @_patch_chain_ok()
    def test_parse_endpoint(self, _chain, _lic):
        url = reverse('workspace:ai_workspace:nl_parse')
        resp = self.client.post(
            url,
            data=json.dumps({'text': 'فردا ساعت ده', 'locale': 'fa-IR', 'timezone': 'Asia/Tehran'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_provider_failure(self, _lic):
        with patch(
            'ai_workspace.services.nl_command.service.gateway_run',
            side_effect=NLCommandError('درک فرمان ممکن نشد.', code='parse_failed', status=503),
        ):
            url = reverse('workspace:ai_workspace:nl_parse')
            resp = self.client.post(
                url,
                data=json.dumps({'text': 'فردا'}),
                content_type='application/json',
            )
        data = resp.json()
        self.assertFalse(data.get('ok'))
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(data.get('code'), 'parse_failed')


@override_settings(AI_ENABLED=True)
class NLCommandConfirmBehaviorTests(TestCase):
    """A–F: standalone vs contact-linked reminder."""

    def setUp(self):
        self.user = User.objects.create_user(username='cfm_u', password='x', is_staff=True)
        self.customer = Customer.objects.create(user=self.user, name='علی احمدی', phone='09120003333')

    @_patch_chain_json(_reminder_json(contact_name=None, title='بررسی فایل پونک', note='فایل‌های پونک'))
    def test_a_standalone_without_contact_name(self, _chain):
        parsed = parse_command(self.user, text='فردا فایل پونک')
        self.assertTrue(parsed['can_confirm'])
        out = confirm_command(self.user, parsed['command_id'])
        reminder = Reminder.objects.get(pk=out['entity_id'])
        self.assertIsNone(reminder.customer)

    @_patch_chain_ok()
    def test_b_single_match_links_customer(self, _chain):
        parsed = parse_command(self.user, text='فردا به احمدی')
        self.assertTrue(parsed['can_confirm'])
        out = confirm_command(self.user, parsed['command_id'])
        reminder = Reminder.objects.get(pk=out['entity_id'])
        self.assertEqual(reminder.customer_id, self.customer.pk)

    @_patch_chain_json(_reminder_json(contact_name='رضایی ناموجود'))
    def test_c_zero_match_no_confirm_no_reminder(self, _chain):
        parsed = parse_command(self.user, text='فردا به رضایی')
        self.assertFalse(parsed['can_confirm'])
        self.assertIn('پیدا نشد', parsed.get('message', ''))
        with self.assertRaises(NLCommandError):
            confirm_command(self.user, parsed['command_id'])
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 0)

    @_patch_chain_ok()
    def test_d_multiple_resolve_then_linked(self, _chain):
        other = Customer.objects.create(user=self.user, name='مریم احمدی', phone='09120004444')
        parsed = parse_command(self.user, text='فردا احمدی')
        self.assertFalse(parsed['can_confirm'])
        resolved = resolve_contact(self.user, parsed['command_id'], other.pk)
        self.assertTrue(resolved['can_confirm'])
        out = confirm_command(self.user, parsed['command_id'])
        reminder = Reminder.objects.get(pk=out['entity_id'])
        self.assertEqual(reminder.customer_id, other.pk)

    @_patch_chain_ok()
    def test_e_contact_removed_before_confirm(self, _chain):
        parsed = parse_command(self.user, text='فردا احمدی')
        self.assertTrue(parsed['can_confirm'])
        self.customer.delete()
        with self.assertRaises(NLCommandError) as ctx:
            confirm_command(self.user, parsed['command_id'])
        self.assertEqual(ctx.exception.code, 'contact_scope')
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 0)

    @_patch_chain_ok()
    def test_f_double_confirm_linked_one_reminder(self, _chain):
        parsed = parse_command(self.user, text='فردا احمدی')
        first = confirm_command(self.user, parsed['command_id'])
        second = confirm_command(self.user, parsed['command_id'])
        self.assertEqual(first['entity_id'], second['entity_id'])
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Reminder.objects.get(pk=first['entity_id']).customer_id, self.customer.pk)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @_patch_chain_ok()
    def test_resolve_contact_no_llm_quota(self, _chain, _lic):
        Customer.objects.create(user=self.user, name='مریم احمدی', phone='09120005555')
        parsed = parse_command(self.user, text='فردا')
        before = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        with patch('ai_workspace.services.nl_command.service.gateway_run') as gw:
            resolve_contact(self.user, parsed['command_id'], self.customer.pk)
            gw.assert_not_called()
        after = AIUsageLog.objects.filter(user=self.user, feature_code=FEATURE_NL_COMMAND).count()
        self.assertEqual(before, after)


@override_settings(AI_ENABLED=True)
class NLCommandLoggingTests(TestCase):
    @_patch_chain_ok()
    def test_no_raw_text_in_usage_log_entity(self, _chain):
        user = User.objects.create_user(username='log_u', password='x', is_staff=True)
        secret = '09121234567 فردا ساعت ده'
        parse_command(user, text=secret)
        log = AIUsageLog.objects.filter(user=user, feature_code=FEATURE_NL_COMMAND).first()
        self.assertIsNotNone(log)
        self.assertNotIn(secret, log.entity_id or '')
        self.assertNotIn('09121234567', log.entity_id or '')
