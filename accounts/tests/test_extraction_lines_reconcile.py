"""تست reconcile خودکار نشست فایلینگ ↔ خطوط استخراج."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import PhoneDetectorExtractionLine
from accounts.services.extraction_lines_reconcile import (
    _ensure_consent_for_connected,
    reconcile_extraction_lines,
)
from workspace.divar_session_models import DivarAccountSession

User = get_user_model()

_PD_PATCHES = (
    'accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir',
    'accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir',
)


class ExtractionLinesReconcileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='recon1', phone='09120001111', password='x')
        self._tmpdir = tempfile.TemporaryDirectory()
        self.pd_dir = Path(self._tmpdir.name)
        (self.pd_dir / 'engine.py').write_text('# stub', encoding='utf-8')
        (self.pd_dir / 'sessions').mkdir(parents=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    @patch('accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir', return_value=None)
    def test_reconcile_without_pd_configured(self, _mock):
        stats = reconcile_extraction_lines(force=True)
        self.assertFalse(stats.get('ok'))

    def test_auto_consent_for_connected(self):
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121112222',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
        )
        count = _ensure_consent_for_connected()
        self.assertEqual(count, 1)
        row = DivarAccountSession.objects.get(divar_phone='09121112222')
        self.assertTrue(row.phone_detector_consent)

    def test_opt_out_skips_consent_grant(self):
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09123334444',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
            extraction_auto_opt_out=True,
        )
        self.assertEqual(_ensure_consent_for_connected(), 0)

    @patch('accounts.services.extraction_lines_reconcile._provision_filing_session')
    @patch('accounts.services.extraction_lines_reconcile.sync_lines_from_sessions', return_value=0)
    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    def test_reconcile_provisions_connected(self, mock_pd, mock_pd2, _sync, mock_provision):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        session = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09124445555',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
        )
        mock_provision.return_value = PhoneDetectorExtractionLine(
            phone=session.divar_phone,
            line_source=PhoneDetectorExtractionLine.LineSource.FILING,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        stats = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats.get('ok'))
        self.assertGreaterEqual(stats.get('provisioned', 0), 1)
        mock_provision.assert_called()

    @patch('accounts.services.extraction_lines_reconcile._evict_filing_line')
    @patch('accounts.services.extraction_lines_reconcile.sync_lines_from_sessions', return_value=0)
    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    def test_reconcile_evicts_expired_filing_line(self, mock_pd, mock_pd2, _sync, mock_evict):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        session = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09125556666',
            auth_status=DivarAccountSession.AuthStatus.EXPIRED,
            encrypted_session='enc',
        )
        PhoneDetectorExtractionLine.objects.create(
            phone=session.divar_phone,
            divar_account_session=session,
            line_source=PhoneDetectorExtractionLine.LineSource.FILING,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        stats = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats.get('ok'))
        self.assertGreaterEqual(stats.get('evicted', 0), 1)
        mock_evict.assert_called()