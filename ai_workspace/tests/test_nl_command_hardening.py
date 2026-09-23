"""Command engine hardening — merge, errors, lock, timing."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from workspace.models import Customer, Reminder

from ai_workspace.tests.test_nl_command import (
    _patch_chain_json,
    _patch_chain_ok,
    _reminder_json,
)

User = get_user_model()


def _reminder_incomplete_contact_json():
    return json.dumps({
        'intent': 'create_reminder',
        'confidence': 0.9,
        'data': {
            'contact_name': 'احمدی',
            'title': 'تماس با احمدی',
            'note': '',
            'date_text': None,
            'time_text': None,
        },
        'missing_fields': ['date_text', 'time_text'],
        'ambiguous_fields': [],
        'requires_confirmation': True,
    }, ensure_ascii=False)


def _reminder_time_only_json():
    return json.dumps({
        'intent': 'create_reminder',
        'confidence': 0.9,
        'data': {
            'contact_name': None,
            'title': None,
            'note': '',
            'date_text': 'فردا',
            'time_text': 'ساعت ده',
        },
        'missing_fields': [],
        'ambiguous_fields': [],
        'requires_confirmation': True,
    }, ensure_ascii=False)


@override_settings(AI_ENABLED=True)
class ReminderMergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='hard_rm', password='x', is_staff=True)
        Customer.objects.create(user=self.user, name='علی احمدی', phone='09120001111')

    @_patch_chain_json(_reminder_incomplete_contact_json())
    def test_incomplete_then_time_merge_same_command_id(self, _chain):
        first = parse_command(self.user, text='یادم بنداز به احمدی زنگ بزنم')
        self.assertEqual(first['intent'], 'create_reminder')
        self.assertFalse(first['can_confirm'])
        cid = first['command_id']
        with _patch_chain_json(_reminder_time_only_json()):
            second = parse_command(self.user, text='فردا ساعت ۱۰', command_id=cid)
        self.assertEqual(second['command_id'], cid)
        self.assertTrue(second['can_confirm'])

    @_patch_chain_ok()
    def test_complete_preview_new_parse_new_command_id(self, _chain):
        first = parse_command(self.user, text='فردا ساعت ده یادم بنداز به احمدی زنگ بزنم')
        self.assertTrue(first['can_confirm'])
        cid1 = first['command_id']
        second = parse_command(self.user, text='پس‌فردا ساعت ۹', command_id=cid1)
        self.assertNotEqual(second['command_id'], cid1)

    @_patch_chain_ok()
    def test_edit_resume_correction_keeps_command_id(self, _chain):
        first = parse_command(self.user, text='فردا ساعت ده یادم بنداز به احمدی زنگ بزنم')
        cid = first['command_id']
        with _patch_chain_json(_reminder_json(title='تماس فوری')):
            second = parse_command(
                self.user,
                text='عنوانش تماس فوری باشه',
                command_id=cid,
                resume_correction=True,
            )
        self.assertEqual(second['command_id'], cid)


@override_settings(AI_ENABLED=True)
class ErrorContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='hard_err', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.user)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_parse_empty_error_contract(self, _lic):
        url = reverse('workspace:ai_workspace:nl_parse')
        resp = self.client.post(
            url,
            data=json.dumps({'text': '   '}),
            content_type='application/json',
        )
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['error_code'], 'invalid_input')
        self.assertEqual(data['code'], 'empty_text')
        self.assertIn('message', data)
        self.assertIn('retryable', data)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_confirm_expired_error_contract(self, _lic):
        url = reverse('workspace:ai_workspace:nl_confirm')
        resp = self.client.post(
            url,
            data=json.dumps({'command_id': '00000000-0000-0000-0000-000000000099'}),
            content_type='application/json',
        )
        data = resp.json()
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(data['error_code'], 'command_expired')


@override_settings(AI_ENABLED=True)
class ConfirmLockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='hard_lock', password='x', is_staff=True)
        Customer.objects.create(user=self.user, name='علی احمدی', phone='09120003333')

    def test_confirm_cache_lock_excludes_parallel(self):
        from ai_workspace.services.nl_command.state import (
            release_confirm_lock,
            try_acquire_confirm_lock,
        )

        cid = 'lock-test-cmd'
        self.assertTrue(try_acquire_confirm_lock(self.user.pk, cid))
        self.assertFalse(try_acquire_confirm_lock(self.user.pk, cid))
        release_confirm_lock(self.user.pk, cid)
        self.assertTrue(try_acquire_confirm_lock(self.user.pk, cid))
        release_confirm_lock(self.user.pk, cid)

    @_patch_chain_ok()
    def test_second_confirm_while_locked_gets_conflict(self, _chain):
        parsed = parse_command(self.user, text='فردا احمدی')
        cid = parsed['command_id']
        from ai_workspace.services.nl_command.state import try_acquire_confirm_lock, release_confirm_lock

        self.assertTrue(try_acquire_confirm_lock(self.user.pk, cid))
        try:
            with self.assertRaises(NLCommandError) as ctx:
                confirm_command(self.user, cid)
            self.assertEqual(ctx.exception.code, 'confirm_conflict')
        finally:
            release_confirm_lock(self.user.pk, cid)
        out = confirm_command(self.user, cid)
        self.assertTrue(out['ok'])
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 1)


@override_settings(AI_ENABLED=True)
class ReminderContactNotFoundFlagTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='hard_nf', password='x', is_staff=True)

    @_patch_chain_json(_reminder_json(contact_name='رضایی ناموجود'))
    def test_contact_not_found_flag(self, _chain):
        result = parse_command(self.user, text='فردا به رضایی')
        self.assertTrue(result.get('contact_not_found'))
