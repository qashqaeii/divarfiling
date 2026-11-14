"""تست یکپارچه reconcile با sessions/index.json موقت."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import PhoneDetectorExtractionLine
from accounts.services.extraction_lines_reconcile import (
    _register_phone_in_pd_index,
    _register_phone_in_pd_index_explicit,
    _remove_phone_from_index_only,
    _sync_rotation_index_from_db,
    reconcile_extraction_lines,
)
from accounts.services.pd_sessions_file_lock import PdSessionsFileLock
from workspace.divar_session_models import DivarAccountSession

User = get_user_model()
PD_ROOT = Path(__file__).resolve().parents[3] / 'phone-detector'


class ExtractionLinesPdIndexIntegrationTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.sessions_root = Path(self._tmpdir.name) / 'sessions'
        self.sessions_root.mkdir(parents=True)
        self.pd_dir = Path(self._tmpdir.name)
        (self.pd_dir / 'engine.py').write_text('# stub', encoding='utf-8')
        if str(PD_ROOT) not in sys.path:
            sys.path.insert(0, str(PD_ROOT))

    def tearDown(self):
        self._tmpdir.cleanup()

    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    def test_cross_process_file_lock_blocks_reconcile(self, mock_pd2, mock_pd):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        held = PdSessionsFileLock()
        self.assertTrue(held.acquire(wait_seconds=0))
        stats = reconcile_extraction_lines(wait_seconds=0)
        self.assertTrue(stats.get('skipped_concurrent'))
        self.assertFalse(stats.get('ok'))
        held.release()

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_force_true_still_waits_on_lock_not_bypass(self, mock_pd, mock_pd2):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        held = PdSessionsFileLock()
        self.assertTrue(held.acquire(wait_seconds=0))
        stats = reconcile_extraction_lines(wait_seconds=0.25, force=True)
        self.assertFalse(stats.get('ok'))
        self.assertTrue(stats.get('skipped_concurrent'))
        held.release()

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_explicit_index_register_adds_phone(self, mock_pd, mock_pd2):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09121234567'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        self.assertTrue(_register_phone_in_pd_index_explicit(phone))
        index = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertIn(phone, index.get('phones') or [])

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_remove_index_keeps_session_file(self, mock_pd, mock_pd2):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09129876543'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        _register_phone_in_pd_index_explicit(phone)
        self.assertTrue(_remove_phone_from_index_only(phone))
        index = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertNotIn(phone, index.get('phones') or [])
        self.assertTrue((self.sessions_root / f'{phone}.json').is_file())

    @patch('accounts.services.phone_detector_lines._get_engine')
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_register_via_engine_registry(self, mock_pd, mock_pd2, mock_engine):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09121111111'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        from main import SessionRegistry

        reg = SessionRegistry(self.sessions_root)
        engine = type('E', (), {'registry': reg})()
        mock_engine.return_value = engine
        self.assertTrue(_register_phone_in_pd_index(phone))

    @patch('workspace.services.divar_session.phone_detector_bridge._write_refreshed_session_file')
    @patch('accounts.services.extraction_lines_reconcile._register_phone_in_pd_index', return_value=True)
    @patch('accounts.services.extraction_lines_reconcile.sync_lines_from_sessions', return_value=0)
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_blocked_captcha_not_auto_activated(
        self,
        mock_pd,
        mock_pd2,
        _sync,
        _reg,
        mock_write,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        user = User.objects.create_user(username='cap1', phone='09120009999', password='x')
        session = DivarAccountSession.objects.create(
            user=user,
            divar_phone='09122223333',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
        )
        PhoneDetectorExtractionLine.objects.create(
            phone=session.divar_phone,
            divar_account_session=session,
            line_source=PhoneDetectorExtractionLine.LineSource.FILING,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )
        stats = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats.get('ok'))
        line = PhoneDetectorExtractionLine.objects.get(phone=session.divar_phone)
        self.assertEqual(
            line.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )
        self.assertGreaterEqual(stats.get('skipped_provision', 0), 1)
        mock_write.assert_not_called()

    @patch('workspace.services.divar_session.phone_detector_bridge._write_refreshed_session_file')
    @patch('accounts.services.extraction_lines_reconcile.sync_lines_from_sessions', return_value=0)
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_manual_line_blocks_session_file_write(self, mock_pd, mock_pd2, _sync, mock_write):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        user = User.objects.create_user(username='man1', phone='09120008888', password='x')
        session = DivarAccountSession.objects.create(
            user=user,
            divar_phone='09124445555',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
        )
        PhoneDetectorExtractionLine.objects.create(
            phone=session.divar_phone,
            line_source=PhoneDetectorExtractionLine.LineSource.MANUAL,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        stats = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats.get('ok'))
        mock_write.assert_not_called()

    @patch('workspace.services.divar_session.phone_detector_bridge._write_refreshed_session_file')
    @patch('accounts.services.extraction_lines_reconcile._register_phone_in_pd_index', return_value=True)
    @patch('accounts.services.extraction_lines_reconcile.sync_lines_from_sessions', return_value=0)
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_idempotent_reconcile_twice(self, mock_pd, mock_pd2, _sync, _reg, mock_write):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        user = User.objects.create_user(username='idm1', phone='09120007777', password='x')
        session = DivarAccountSession.objects.create(
            user=user,
            divar_phone='09126667777',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
        )
        stats1 = reconcile_extraction_lines(wait_seconds=5.0)
        stats2 = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats1.get('ok'))
        self.assertTrue(stats2.get('ok'))
        self.assertEqual(
            PhoneDetectorExtractionLine.objects.filter(phone=session.divar_phone).count(),
            1,
        )

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_manual_captcha_stays_paused_after_reconcile_and_save_index(
        self,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        if str(PD_ROOT) not in sys.path:
            sys.path.insert(0, str(PD_ROOT))
        phone = '09127778899'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        index = {
            'active_phone': phone,
            'rotate': True,
            'phones': [phone],
            'paused_phones': [],
        }
        (self.sessions_root / 'index.json').write_text(
            json.dumps(index, ensure_ascii=False),
            encoding='utf-8',
        )
        PhoneDetectorExtractionLine.objects.create(
            phone=phone,
            line_source=PhoneDetectorExtractionLine.LineSource.MANUAL,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )
        self.assertGreaterEqual(_sync_rotation_index_from_db(), 0)
        stats = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats.get('ok'))
        data = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertNotIn(phone, data.get('phones') or [])
        self.assertIn(phone, data.get('paused_phones') or [])
        from main import SessionRegistry

        reg = SessionRegistry(self.sessions_root)
        reg.save_index()
        data2 = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertNotIn(phone, data2.get('phones') or [])
        self.assertIn(phone, data2.get('paused_phones') or [])
        stats2 = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats2.get('ok'))
        data3 = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertNotIn(phone, data3.get('phones') or [])

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_sync_rotation_index_idempotent_when_unchanged(
        self,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09127770001'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        PhoneDetectorExtractionLine.objects.create(
            phone=phone,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        first = _sync_rotation_index_from_db()
        self.assertGreaterEqual(first, 0)
        second = _sync_rotation_index_from_db()
        self.assertEqual(second, 0)

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_orphan_session_file_stays_paused_not_rotation(
        self,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        orphan = '09128887777'
        (self.sessions_root / f'{orphan}.json').write_text('{"cookies":[]}', encoding='utf-8')
        _sync_rotation_index_from_db()
        data = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertNotIn(orphan, data.get('phones') or [])
        self.assertIn(orphan, data.get('paused_phones') or [])