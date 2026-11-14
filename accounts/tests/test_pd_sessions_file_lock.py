"""تست قفل فایل بین‌پردازه‌ای sessions phone-detector."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from accounts.services.pd_sessions_file_lock import PdSessionsFileLock


class PdSessionsFileLockTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.pd_dir = Path(self._tmpdir.name)
        (self.pd_dir / 'engine.py').write_text('# stub', encoding='utf-8')
        (self.pd_dir / 'sessions').mkdir(parents=True)

    def tearDown(self):
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