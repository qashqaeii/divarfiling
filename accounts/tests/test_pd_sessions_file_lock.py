"""تست قفل فایل بین‌پردازه‌ای sessions phone-detector."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from accounts.services.pd_sessions_file_lock import PdSessionsFileLock, try_reclaim_stale_lock


class PdSessionsFileLockTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.pd_dir = Path(self._tmpdir.name)
        (self.pd_dir / 'engine.py').write_text('# stub', encoding='utf-8')
        (self.pd_dir / 'sessions').mkdir(parents=True)

    def tearDown(self):
        try:
            from accounts.services.pd_sessions_file_lock import _import_pd_lock_sync

            mod = _import_pd_lock_sync()
            if mod is not None:
                while mod.mutation_depth() > 0:
                    mod.bump_mutation_depth(-1)
        except Exception:
            pass
        self._tmpdir.cleanup()

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    def test_exclusive_lock_blocks_second_holder(self, mock_pd):
        mock_pd.return_value = self.pd_dir
        first = PdSessionsFileLock()
        second = PdSessionsFileLock()
        self.assertTrue(first.acquire(wait_seconds=0))
        self.assertFalse(second.acquire(wait_seconds=0))
        first.release()
        self.assertTrue(second.acquire(wait_seconds=0))
        second.release()

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    def test_subprocess_waits_for_lock(self, mock_pd):
        mock_pd.return_value = self.pd_dir
        holder = PdSessionsFileLock()
        self.assertTrue(holder.acquire(wait_seconds=0))
        manage = Path(__file__).resolve().parents[2] / 'manage.py'
        code = (
            "import os,django;os.environ['PHONE_DETECTOR_DIR']=%r;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE','divar_shop.settings_test');"
            "django.setup();"
            "from accounts.services.pd_sessions_file_lock import PdSessionsFileLock;"
            "lock=PdSessionsFileLock();"
            "print('ok' if lock.acquire(wait_seconds=0.5) else 'busy')"
        ) % (str(self.pd_dir),)
        proc = subprocess.run(
            [sys.executable, '-c', code],
            cwd=str(manage.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn('busy', (proc.stdout or '').strip())
        holder.release()

    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    def test_stale_lock_reclaimed_when_pid_dead(self, mock_pd):
        mock_pd.return_value = self.pd_dir
        lock_path = self.pd_dir / 'sessions' / '.lac_pd_sessions.lock'
        lock_path.write_text('999999999\n', encoding='ascii')
        self.assertTrue(try_reclaim_stale_lock(lock_path))
        self.assertFalse(lock_path.is_file())
        second = PdSessionsFileLock()
        self.assertTrue(second.acquire(wait_seconds=0))
        second.release()

    @patch('accounts.services.pd_sessions_file_lock._pid_alive', return_value=True)
    @patch('accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir')
    def test_live_pid_lock_not_reclaimed(self, mock_pd, _alive):
        mock_pd.return_value = self.pd_dir
        lock_path = self.pd_dir / 'sessions' / '.lac_pd_sessions.lock'
        lock_path.write_text('12345\n', encoding='ascii')
        self.assertFalse(try_reclaim_stale_lock(lock_path))
        second = PdSessionsFileLock()
        self.assertFalse(second.acquire(wait_seconds=0))