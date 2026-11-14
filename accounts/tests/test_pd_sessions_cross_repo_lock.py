"""Cross-repo: Django reconcile lock + phone-detector save_index/remove (no self-deadlock)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from accounts.services.pd_sessions_file_lock import PdSessionsFileLock
from accounts.services.extraction_lines_reconcile import (
    _register_phone_in_pd_index,
    _evict_phone_from_pd_index,
)

PD_ROOT = Path(__file__).resolve().parents[3] / 'phone-detector'


class PdSessionsCrossRepoLockTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.pd_dir = Path(self._tmpdir.name)
        (self.pd_dir / 'engine.py').write_text('# stub', encoding='utf-8')
        self.sessions = self.pd_dir / 'sessions'
        self.sessions.mkdir(parents=True)
        if str(PD_ROOT) not in sys.path:
            sys.path.insert(0, str(PD_ROOT))

    def tearDown(self):
        try:
            import lac_sessions_lock

            while lac_sessions_lock.mutation_depth() > 0:
                lac_sessions_lock.bump_mutation_depth(-1)
        except ImportError:
            pass
        self._tmpdir.cleanup()

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_save_index_under_django_reconcile_lock(self, mock_pd2, mock_pd):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09121234567'
        (self.sessions / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')

        from main import SessionRegistry

        holder = PdSessionsFileLock()
        self.assertTrue(holder.acquire(wait_seconds=0.5))
        reg = SessionRegistry(self.sessions)
        data = reg.save_index(active_phone=phone)
        self.assertIn(phone, data.get('phones') or [])
        holder.release()

    @patch('accounts.services.phone_detector_lines._get_engine')
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_register_phone_in_pd_index_while_lock_held(
        self,
        mock_pd2,
        mock_pd,
        mock_get_engine,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09129876543'
        (self.sessions / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        from main import SessionRegistry

        reg = SessionRegistry(self.sessions)
        mock_get_engine.return_value = type('E', (), {'registry': reg})()
        holder = PdSessionsFileLock()
        self.assertTrue(holder.acquire(wait_seconds=0.5))
        self.assertTrue(_register_phone_in_pd_index(phone))
        index = json.loads((self.sessions / 'index.json').read_text(encoding='utf-8'))
        self.assertIn(phone, index.get('phones') or [])
        holder.release()

    @patch('accounts.services.phone_detector_lines._get_engine')
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir')
    def test_remove_account_under_reconcile_lock(
        self,
        mock_pd2,
        mock_pd,
        mock_get_engine,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09121112222'
        (self.sessions / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        from main import SessionRegistry

        reg = SessionRegistry(self.sessions)
        reg.save_index(active_phone=phone)

        import threading

        class StubEngine:
            def __init__(self):
                self.registry = reg
                self.accounts = {}
                self.active_phone = None
                self._lock = threading.Lock()

            def remove_account(self, ph: str):
                with self._lock:
                    key = ph.strip()
                    self.registry.delete_phone(key)
                    self.accounts.pop(key, None)
                return {'ok': True}

        mock_get_engine.return_value = StubEngine()

        holder = PdSessionsFileLock()
        self.assertTrue(holder.acquire(wait_seconds=0.5))
        ok = _evict_phone_from_pd_index(phone, delete_session_file=True)
        self.assertTrue(ok)
        self.assertFalse((self.sessions / f'{phone}.json').is_file())
        holder.release()