"""رگرسیون: خطوط RUNNING متعلق به اجرای فعال باید در rotation بمانند."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import AcquisitionAutomationCampaign, AcquisitionRun, PhoneDetectorExtractionLine
from accounts.services.extraction_lines_reconcile import (
    _sync_rotation_index_from_db,
    reconcile_extraction_lines,
)
from accounts.services.phone_detector_line_ops import (
    active_acquisition_run_ids,
    excluded_phones_for_extraction,
    line_running_in_active_run,
    mark_lines_run_started,
)

User = get_user_model()

_PD_PATCHES = (
    'accounts.services.extraction_lines_reconcile.resolve_phone_detector_dir',
    'accounts.services.pd_sessions_file_lock.resolve_phone_detector_dir',
)


def _write_session_and_lines(root: Path, phones: list[str], *, run_id: int) -> AcquisitionRun:
    user = User.objects.create_user(username=f'run{run_id}', phone='09120000001', password='x')
    campaign = AcquisitionAutomationCampaign.objects.create(
        name=f'کمپین {run_id}',
        city='تهران',
        districts=['قاسم‌آباد'],
        is_active=True,
    )
    run = AcquisitionRun.objects.create(
        campaign=campaign,
        district='قاسم‌آباد',
        status=AcquisitionRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    for idx, phone in enumerate(phones, start=1):
        (root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        PhoneDetectorExtractionLine.objects.create(
            phone=phone,
            line_index=idx,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
    mark_lines_run_started(run_id=run.pk)
    return run


class RotationRunningActiveRunTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.sessions_root = Path(self._tmpdir.name) / 'sessions'
        self.sessions_root.mkdir(parents=True)
        self.pd_dir = Path(self._tmpdir.name)
        (self.pd_dir / 'engine.py').write_text('# stub', encoding='utf-8')

    def tearDown(self):
        self._tmpdir.cleanup()

    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    @patch('accounts.services.phone_detector_lines.session_file_exists', return_value=True)
    def test_ten_healthy_lines_stay_in_rotation_after_mark_started(
        self,
        _has_file,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phones = [f'091211100{i:02d}' for i in range(10)]
        run = _write_session_and_lines(self.sessions_root, phones, run_id=319)

        _sync_rotation_index_from_db()
        data = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        rotation = set(data.get('phones') or [])
        paused = set(data.get('paused_phones') or [])

        self.assertEqual(len(rotation), 10)
        self.assertEqual(len(paused), 0)
        self.assertTrue(rotation.isdisjoint(paused))
        for line in PhoneDetectorExtractionLine.objects.filter(phone__in=phones):
            self.assertTrue(line_running_in_active_run(line))
            self.assertEqual(line.last_run_id, run.pk)
        self.assertIn(run.pk, active_acquisition_run_ids())

    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    @patch('accounts.services.phone_detector_lines.session_file_exists', return_value=True)
    def test_reconcile_during_active_run_keeps_rotation(
        self,
        _has_file,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phones = [f'091222200{i:02d}' for i in range(10)]
        run = _write_session_and_lines(self.sessions_root, phones, run_id=320)

        with patch(
            'accounts.services.extraction_lines_reconcile.sync_lines_from_sessions',
            return_value=0,
        ):
            stats = reconcile_extraction_lines(wait_seconds=5.0)
        self.assertTrue(stats.get('ok'))

        data = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data.get('phones') or []), 10)
        self.assertEqual(len(data.get('paused_phones') or []), 0)
        self.assertEqual(run.pk, run.pk)

    @patch('accounts.services.phone_detector_lines.session_file_exists', return_value=True)
    def test_excluded_phones_allows_current_run_running_lines(self, _has_file):
        campaign = AcquisitionAutomationCampaign.objects.create(
            name='excluded',
            city='تهران',
            districts=['ونک'],
        )
        run_a = AcquisitionRun.objects.create(
            campaign=campaign,
            district='ونک',
            status=AcquisitionRun.Status.RUNNING,
        )
        run_b = AcquisitionRun.objects.create(
            campaign=campaign,
            district='ونک',
            status=AcquisitionRun.Status.RUNNING,
        )
        PhoneDetectorExtractionLine.objects.create(
            phone='09123334444',
            line_index=1,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.RUNNING,
            last_run_id=run_a.pk,
        )
        PhoneDetectorExtractionLine.objects.create(
            phone='09124445555',
            line_index=2,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.RUNNING,
            last_run_id=run_b.pk,
        )
        excluded = excluded_phones_for_extraction(current_run_id=run_a.pk)
        self.assertNotIn('09123334444', excluded)
        self.assertIn('09124445555', excluded)

    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    @patch('accounts.services.phone_detector_lines.session_file_exists', return_value=True)
    def test_stale_running_without_active_run_goes_paused(
        self,
        _has_file,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09125556666'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        PhoneDetectorExtractionLine.objects.create(
            phone=phone,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.RUNNING,
            last_run_id=12345,
        )
        _sync_rotation_index_from_db()
        data = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        self.assertNotIn(phone, data.get('phones') or [])
        self.assertIn(phone, data.get('paused_phones') or [])

    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    @patch('accounts.services.phone_detector_lines.session_file_exists', return_value=True)
    def test_captcha_line_removed_from_rotation(
        self,
        _has_file,
        mock_pd,
        mock_pd2,
    ):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phones = ['09126667777', '09127778888']
        for p in phones:
            (self.sessions_root / f'{p}.json').write_text('{"cookies":[]}', encoding='utf-8')
        run = AcquisitionRun.objects.create(
            campaign=AcquisitionAutomationCampaign.objects.create(
                name='captcha',
                city='تهران',
                districts=['ونک'],
            ),
            district='ونک',
            status=AcquisitionRun.Status.RUNNING,
        )
        for idx, phone in enumerate(phones, start=1):
            st = PhoneDetectorExtractionLine.OperationalStatus
            status = st.BLOCKED_CAPTCHA if phone.endswith('7777') else st.ACTIVE
            PhoneDetectorExtractionLine.objects.create(phone=phone, line_index=idx, operational_status=status)
        mark_lines_run_started(run_id=run.pk)

        _sync_rotation_index_from_db()
        data = json.loads((self.sessions_root / 'index.json').read_text(encoding='utf-8'))
        rotation = set(data.get('phones') or [])
        paused = set(data.get('paused_phones') or [])
        self.assertIn('09127778888', rotation)
        self.assertNotIn('09126667777', rotation)
        self.assertIn('09126667777', paused)

    @patch(_PD_PATCHES[1])
    @patch(_PD_PATCHES[0])
    def test_sync_rotation_idempotent_when_unchanged(self, mock_pd, mock_pd2):
        mock_pd.return_value = self.pd_dir
        mock_pd2.return_value = self.pd_dir
        phone = '09128889999'
        (self.sessions_root / f'{phone}.json').write_text('{"cookies":[]}', encoding='utf-8')
        PhoneDetectorExtractionLine.objects.create(
            phone=phone,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        self.assertGreaterEqual(_sync_rotation_index_from_db(), 0)
        self.assertEqual(_sync_rotation_index_from_db(), 0)