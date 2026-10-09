"""تست مدیریت عملیاتی خطوط استخراج و scheduler."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import (
    AcquisitionAutomationCampaign,
    AcquisitionRun,
    PhoneDetectorExtractionLine,
)
from accounts.services.acquisition_automation import finalize_run_from_worker, schedule_due_campaigns
from accounts.services.phone_detector_lines import PhoneDetectorLineError
from accounts.services.phone_detector_line_ops import (
    apply_run_outcome_from_engine,
    build_run_summary_message,
    count_schedulable_lines,
    excluded_phones_for_extraction,
    probe_and_reactivate_line,
    recover_stale_running_lines,
    set_line_paused,
    sync_lines_from_sessions,
)


class PhoneDetectorLineOpsTests(TestCase):
    def setUp(self):
        self._no_pd = patch(
            'accounts.services.phone_detector_line_ops.resolve_phone_detector_dir',
            return_value=None,
        )
        self._no_pd.start()
        self.line1 = PhoneDetectorExtractionLine.objects.create(
            phone='09111111111',
            line_index=1,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        self.line2 = PhoneDetectorExtractionLine.objects.create(
            phone='09222222222',
            line_index=2,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        self.line3 = PhoneDetectorExtractionLine.objects.create(
            phone='09333333333',
            line_index=3,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )

    def tearDown(self):
        self._no_pd.stop()

    def test_excluded_phones_includes_blocked_and_paused(self):
        self.line2.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
        self.line2.save()
        self.line3.operational_status = PhoneDetectorExtractionLine.OperationalStatus.PAUSED
        self.line3.save()
        excluded = excluded_phones_for_extraction()
        self.assertIn('09222222222', excluded)
        self.assertIn('09333333333', excluded)
        self.assertNotIn('09111111111', excluded)
        self.assertEqual(count_schedulable_lines(), 1)

    def test_captcha_on_one_line_only_blocks_that_line(self):
        outcome = apply_run_outcome_from_engine(
            run_id=99,
            accounts=[
                {'phone': '09111111111', 'ok': True, 'hip_blocked': False},
                {'phone': '09222222222', 'ok': True, 'hip_blocked': True},
                {'phone': '09333333333', 'ok': True, 'hip_blocked': False},
            ],
            hip={'captcha_triggered': 1},
            phones_extracted=5,
            worker_status='completed',
        )
        self.line2.refresh_from_db()
        self.assertEqual(
            self.line2.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )
        self.line1.refresh_from_db()
        self.assertEqual(
            self.line1.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        self.assertEqual(outcome['blocked_lines'], ['09222222222'])
        self.assertGreater(outcome['healthy_lines_remaining'], 0)
        msg = build_run_summary_message(
            outcome=outcome,
            phones_extracted=5,
            worker_status='completed',
        )
        self.assertIn('خط استخراج شماره 2', msg)
        self.assertIn('5', msg)

    def test_blocked_line_excluded_from_extraction_set(self):
        self.line2.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
        self.line2.save()
        self.assertIn('09222222222', excluded_phones_for_extraction())

    def test_blocked_stays_blocked_when_engine_shows_healthy(self):
        self.line2.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
        self.line2.save()
        apply_run_outcome_from_engine(
            run_id=101,
            accounts=[
                {'phone': '09111111111', 'ok': True, 'hip_blocked': False},
                {'phone': '09222222222', 'ok': True, 'hip_blocked': False},
            ],
            hip={},
            phones_extracted=3,
            worker_status='completed',
        )
        self.line2.refresh_from_db()
        self.assertEqual(
            self.line2.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )

    def test_success_count_only_for_lines_with_via_session(self):
        apply_run_outcome_from_engine(
            run_id=102,
            accounts=[
                {'phone': '09111111111', 'ok': True, 'hip_blocked': False},
                {'phone': '09222222222', 'ok': True, 'hip_blocked': False},
            ],
            hip={},
            phones_extracted=2,
            worker_status='completed',
            lines_phone_counts={'09111111111': 2},
        )
        self.line1.refresh_from_db()
        self.line2.refresh_from_db()
        self.assertEqual(self.line1.success_extract_count, 2)
        self.assertEqual(self.line2.success_extract_count, 0)

    def test_unpause_does_not_clear_blocked_captcha(self):
        self.line2.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
        self.line2.save()
        with self.assertRaises(PhoneDetectorLineError):
            set_line_paused('09222222222', paused=False)
        self.line2.refresh_from_db()
        self.assertEqual(
            self.line2.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )

    @patch('accounts.services.phone_detector_lines._get_engine')
    def test_probe_failure_does_not_activate_line(self, mock_engine):
        self.line2.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
        self.line2.save()
        engine = mock_engine.return_value
        engine.probe_line_reactivation.return_value = {
            'ok': False,
            'code': 'still_blocked',
            'message': 'هنوز محدود',
        }
        with self.assertRaises(PhoneDetectorLineError):
            probe_and_reactivate_line('09222222222')
        self.line2.refresh_from_db()
        self.assertEqual(
            self.line2.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
        )

    def test_all_lines_blocked_message(self):
        for line in (self.line1, self.line2, self.line3):
            line.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
            line.save()
        outcome = apply_run_outcome_from_engine(
            run_id=100,
            accounts=[
                {'phone': '09111111111', 'ok': False, 'hip_blocked': True},
                {'phone': '09222222222', 'ok': False, 'hip_blocked': True},
                {'phone': '09333333333', 'ok': False, 'hip_blocked': True},
            ],
            hip={'captcha_triggered': 3},
            phones_extracted=0,
            worker_status='rate_limited',
        )
        self.assertTrue(outcome['all_lines_blocked'])
        msg = build_run_summary_message(
            outcome=outcome,
            phones_extracted=0,
            worker_status='rate_limited',
        )
        self.assertIn('تمام خطوط استخراج', msg)

    def test_recover_stale_running_without_active_run(self):
        self.line1.operational_status = PhoneDetectorExtractionLine.OperationalStatus.RUNNING
        self.line1.save()
        n = recover_stale_running_lines()
        self.assertEqual(n, 1)
        self.line1.refresh_from_db()
        self.assertEqual(
            self.line1.operational_status,
            PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )

    def test_schedule_skips_when_no_schedulable_lines(self):
        for line in (self.line1, self.line2, self.line3):
            line.operational_status = PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA
            line.save()
        campaign = AcquisitionAutomationCampaign.objects.create(
            name='تست بدون خط',
            city='تهران',
            districts=['ونک'],
            is_active=True,
            next_run_at=timezone.now(),
        )
        with override_settings(ACQUISITION_AUTOMATION_ENABLED=True):
            created = schedule_due_campaigns(max_jobs=1)
        self.assertEqual(created, [])
        campaign.refresh_from_db()
        self.assertIsNotNone(campaign.next_run_at)

    def test_finalize_partial_captcha_does_not_use_generic_message(self):
        campaign = AcquisitionAutomationCampaign.objects.create(
            name='تست',
            city='تهران',
            districts=['ونک'],
        )
        run = AcquisitionRun.objects.create(
            campaign=campaign,
            status=AcquisitionRun.Status.RUNNING,
            district='ونک',
            output_json={'metadata': {}, 'consultants': []},
        )
        outcome = {
            'blocked_lines': ['09222222222'],
            'blocked_labels': ['خط استخراج شماره 2'],
            'healthy_lines_remaining': 2,
            'all_lines_blocked': False,
        }
        finalize_run_from_worker(
            run.pk,
            worker_status='completed',
            output_payload=run.output_json,
            metrics={
                'line_outcome': outcome,
                'summary_message': build_run_summary_message(
                    outcome=outcome,
                    phones_extracted=3,
                    worker_status='completed',
                ),
            },
            auto_ingest=False,
        )
        run.refresh_from_db()
        self.assertIn('خط استخراج شماره 2', run.error_message)
        self.assertNotIn('تا زمان‌بندی بعدی', run.error_message)


class RunnerStopLogicTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import sys
        from pathlib import Path

        pd_root = Path(__file__).resolve().parents[3] / 'phone-detector'
        if pd_root.is_dir() and str(pd_root) not in sys.path:
            sys.path.insert(0, str(pd_root))

    def test_evaluate_does_not_stop_when_healthy_remain(self):
        from automation.runner import evaluate_extraction_stop

        state = {
            'auto_liking': True,
            'accounts': [
                {'phone': '09111111111', 'ok': True, 'hip_blocked': False},
                {'phone': '09222222222', 'ok': True, 'hip_blocked': True},
            ],
            'hip': {'captcha_triggered': 1},
        }
        self.assertIsNone(evaluate_extraction_stop(state))

    def test_evaluate_stops_when_all_blocked(self):
        from automation.runner import evaluate_extraction_stop

        state = {
            'auto_liking': True,
            'accounts': [
                {'phone': '09111111111', 'ok': True, 'hip_blocked': True},
                {'phone': '09222222222', 'ok': True, 'hip_blocked': True},
            ],
        }
        stop = evaluate_extraction_stop(state)
        self.assertEqual(stop, ('rate_limited', 'all_lines_captcha'))
