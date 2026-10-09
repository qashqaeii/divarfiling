"""تست مدیریت خطوط phone-detector در LAC."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.services.phone_detector_lines import (
    PhoneDetectorLineError,
    _clear_otp_pending,
    _get_engine,
    _load_otp_pending,
    _restore_otp_pending,
    _save_otp_pending,
    handle_line_action,
    list_lines,
    phone_detector_available,
    resolve_phone_detector_dir,
)

User = get_user_model()


def _fake_session(phone: str) -> dict:
    # JWT with far-future exp (year 2099)
    token = (
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
        'eyJleHAiOjQwOTI0MDAwMDAsInBob25lIjoi' + phone + 'In0.'
        'sig'
    )
    return {
        'saved_at': '2026-08-08T06:25:36+00:00',
        'phone': phone,
        'cookies': [
            {'name': 'sAccessToken', 'value': token, 'domain': '.divar.ir', 'path': '/'},
            {'name': 'sRefreshToken', 'value': 'refresh', 'domain': '.divar.ir', 'path': '/'},
        ],
    }


class PhoneDetectorLinesServiceTests(TestCase):
    def setUp(self):
        self.tmp = Path(self._temp_dir())
        self.pd = self.tmp / 'phone-detector'
        self.sessions = self.pd / 'sessions'
        self.sessions.mkdir(parents=True)
        (self.pd / 'engine.py').write_text('# stub', encoding='utf-8')
        (self.sessions / '09111111111.json').write_text(
            json.dumps(_fake_session('09111111111'), ensure_ascii=False),
            encoding='utf-8',
        )
        (self.sessions / '09222222222.json').write_text(
            json.dumps(_fake_session('09222222222'), ensure_ascii=False),
            encoding='utf-8',
        )
        (self.sessions / 'index.json').write_text(
            json.dumps({
                'active_phone': '09111111111',
                'rotate': True,
                'phones': ['09111111111', '09222222222'],
            }, ensure_ascii=False),
            encoding='utf-8',
        )

    def _temp_dir(self):
        import tempfile

        return tempfile.mkdtemp()

    @override_settings(PHONE_DETECTOR_DIR='')
    def test_resolve_from_repo_fallback(self):
        with patch('accounts.services.phone_detector_lines.Path') as mock_path:
            mock_path.return_value.expanduser.return_value.resolve.return_value = self.pd
        # With explicit override we get our temp dir
        with override_settings(PHONE_DETECTOR_DIR=str(self.pd)):
            self.assertTrue(phone_detector_available())
            self.assertEqual(resolve_phone_detector_dir(), self.pd.resolve())

    @override_settings(PHONE_DETECTOR_DIR='')
    def test_list_lines_from_filesystem(self):
        with override_settings(PHONE_DETECTOR_DIR=str(self.pd)):
            payload = list_lines(probe=False)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['total'], 2)
        self.assertEqual(payload['active_phone'], '09111111111')
        self.assertTrue(payload['rotate'])
        phones = {row['phone'] for row in payload['lines']}
        self.assertEqual(phones, {'09111111111', '09222222222'})
        active_row = next(r for r in payload['lines'] if r['phone'] == '09111111111')
        self.assertTrue(active_row['is_active'])

    @override_settings(PHONE_DETECTOR_DIR='')
    def test_handle_invalid_action(self):
        with override_settings(PHONE_DETECTOR_DIR=str(self.pd)):
            with self.assertRaises(PhoneDetectorLineError):
                handle_line_action('unknown', {})

    @override_settings(PHONE_DETECTOR_DIR='')
    @patch('accounts.services.phone_detector_lines._save_otp_pending')
    @patch('accounts.services.phone_detector_lines._get_engine')
    def test_send_otp_delegates_to_engine(self, mock_get_engine, _save_pending):
        import accounts.services.phone_detector_lines as lines_mod

        lines_mod._engine = None
        engine = MagicMock()
        engine.send_otp.return_value = {'ok': True, 'phone': '09133333333'}
        engine.state.phone = '09133333333'
        engine.state.pre_auth_session_id = 'pre-auth-test'
        engine.auth.get_session_phone.return_value = '09133333333'
        engine.session.cookies = []
        mock_get_engine.return_value = engine
        with override_settings(PHONE_DETECTOR_DIR=str(self.pd)):
            result = handle_line_action('send_otp', {'phone': '09133333333'})
        self.assertEqual(result['phone'], '09133333333')
        engine.send_otp.assert_called_once_with('09133333333')
        _save_pending.assert_called_once()

    @override_settings(PHONE_DETECTOR_DIR='')
    def test_restore_otp_pending_applies_cookies(self):
        real_pd = Path(__file__).resolve().parents[3] / 'phone-detector'
        if not (real_pd / 'engine.py').is_file():
            self.skipTest('phone-detector checkout not available')
        import accounts.services.phone_detector_lines as lines_mod

        lines_mod._engine = None
        with override_settings(PHONE_DETECTOR_DIR=str(real_pd)):
            engine = _get_engine()
            _restore_otp_pending(engine, {
                'phone': '09166666666',
                'pre_auth_session_id': 'test-pre-auth',
                'device_id': 'dev-id',
                'cookies': [
                    {'name': 'did', 'value': 'abc', 'domain': '.divar.ir', 'path': '/'},
                ],
            })
        self.assertEqual(engine.state.pre_auth_session_id, 'test-pre-auth')
        self.assertEqual(engine.state.phone, '09166666666')
        lines_mod._engine = None


class PhoneDetectorLinesApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='stafflines',
            password='test-pass',
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)
        self.url = reverse('admin_panel_lead_automation_lines_json')

        self.tmp = Path(self._temp_dir())
        self.pd = self.tmp / 'phone-detector'
        self.sessions = self.pd / 'sessions'
        self.sessions.mkdir(parents=True)
        (self.pd / 'engine.py').write_text('# stub', encoding='utf-8')
        (self.sessions / '09111111111.json').write_text(
            json.dumps(_fake_session('09111111111'), ensure_ascii=False),
            encoding='utf-8',
        )
        (self.sessions / 'index.json').write_text(
            json.dumps({'active_phone': '09111111111', 'rotate': True, 'phones': ['09111111111']}),
            encoding='utf-8',
        )

    def _temp_dir(self):
        import tempfile

        return tempfile.mkdtemp()

    @override_settings(PHONE_DETECTOR_DIR='')
    def test_get_lines_requires_staff_and_returns_json(self):
        with override_settings(PHONE_DETECTOR_DIR=str(self.pd)):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)

    @override_settings(PHONE_DETECTOR_DIR='')
    def test_anonymous_denied(self):
        anon = Client()
        with override_settings(PHONE_DETECTOR_DIR=str(self.pd)):
            resp = anon.get(self.url)
        self.assertIn(resp.status_code, (302, 403))
