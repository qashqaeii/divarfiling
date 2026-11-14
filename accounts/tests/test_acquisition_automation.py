"""Tests for acquisition automation layer."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import (
    AcquisitionAutomationCampaign,
    AcquisitionRun,
    LeadCampaign,
    MarketingLead,
)
from accounts.services.acquisition_automation import (
    ingest_acquisition_run,
    schedule_due_campaigns,
)
from accounts.services.acquisition_automation_ui import (
    AutomationUIError,
    automation_overview_stats,
    delete_automation_campaign,
)
from accounts.tests.test_lead_acquisition import SAMPLE_JSON


class AcquisitionAutomationTests(TestCase):
    def setUp(self):
        self.campaign = AcquisitionAutomationCampaign.objects.create(
            name='تهران · ونک · تست',
            city='تهران',
            districts=['ونک'],
            category='apartment-sell',
            limit_per_run=30,
            interval_hours=6,
            is_active=True,
            auto_create_campaign=True,
            auto_enroll_pilot=True,
        )

    @override_settings(ACQUISITION_AUTOMATION_ENABLED=True)
    def test_schedule_due_campaign_creates_run(self):
        self.campaign.next_run_at = timezone.now()
        self.campaign.save()
        created = schedule_due_campaigns(max_jobs=1)
        self.assertEqual(len(created), 1)
        run = created[0]
        self.assertEqual(run.status, AcquisitionRun.Status.QUEUED)
        self.assertEqual(run.district, 'ونک')
        self.campaign.refresh_from_db()
        self.assertIsNotNone(self.campaign.next_run_at)

    @override_settings(ACQUISITION_AUTOMATION_ENABLED=True)
    def test_schedule_skips_future_campaign(self):
        self.campaign.next_run_at = timezone.now() + timezone.timedelta(hours=2)
        self.campaign.save()
        created = schedule_due_campaigns(max_jobs=1)
        self.assertEqual(created, [])

    def test_ingest_acquisition_run_pipeline(self):
        run = AcquisitionRun.objects.create(
            campaign=self.campaign,
            status=AcquisitionRun.Status.COMPLETED,
            district='ونک',
            output_json=SAMPLE_JSON,
        )
        result = ingest_acquisition_run(run)
        self.assertFalse(result.get('skipped'))
        self.assertGreater(result.get('members_added', 0), 0)

        run.refresh_from_db()
        self.assertEqual(run.status, AcquisitionRun.Status.INGESTED)
        self.assertIsNotNone(run.import_batch_id)
        self.assertIsNotNone(run.lead_campaign_id)

        batch = run.import_batch
        self.assertEqual(batch.acquisition_run_id, run.pk)
        self.assertEqual(batch.status, 'committed')

        self.assertTrue(
            MarketingLead.objects.filter(phone_normalized='09121111111').exists(),
        )
        self.assertTrue(
            LeadCampaign.objects.filter(pk=run.lead_campaign_id).exists(),
        )

    @patch('accounts.services.acquisition_automation.enroll_pilot')
    @patch('accounts.services.acquisition_automation.auto_create_campaign_for_import')
    def test_ingest_respects_auto_flags(self, mock_auto_campaign, mock_enroll):
        self.campaign.auto_create_campaign = False
        self.campaign.auto_enroll_pilot = False
        self.campaign.save()

        run = AcquisitionRun.objects.create(
            campaign=self.campaign,
            status=AcquisitionRun.Status.COMPLETED,
            district='ونک',
            output_json=json.loads(json.dumps(SAMPLE_JSON)),
        )
        ingest_acquisition_run(run)
        mock_auto_campaign.assert_not_called()
        mock_enroll.assert_not_called()


class AcquisitionAutomationUITests(TestCase):
    def setUp(self):
        self.campaign = AcquisitionAutomationCampaign.objects.create(
            name='تهران · حذف',
            city='تهران',
            districts=['ونک'],
            category='apartment-sell',
        )

    def test_delete_automation_campaign_removes_runs(self):
        AcquisitionRun.objects.create(
            campaign=self.campaign,
            status=AcquisitionRun.Status.COMPLETED,
            district='ونک',
        )
        pk = self.campaign.pk
        result = delete_automation_campaign(pk)
        self.assertFalse(AcquisitionAutomationCampaign.objects.filter(pk=pk).exists())
        self.assertEqual(result['runs_removed'], 1)
        self.assertEqual(AcquisitionRun.objects.filter(campaign_id=pk).count(), 0)

    def test_delete_automation_campaign_blocks_busy_run(self):
        AcquisitionRun.objects.create(
            campaign=self.campaign,
            status=AcquisitionRun.Status.RUNNING,
            district='ونک',
        )
        with self.assertRaises(AutomationUIError):
            delete_automation_campaign(self.campaign.pk)
        self.assertTrue(AcquisitionAutomationCampaign.objects.filter(pk=self.campaign.pk).exists())

    def test_create_campaign_from_form(self):
        from accounts.services.acquisition_automation_ui import create_automation_campaign_from_form

        c = create_automation_campaign_from_form({
            'name': 'تهران · تست',
            'city': 'تهران',
            'districts': 'ونک\nآجودانیه',
            'category': 'apartment-sell',
            'limit_per_run': '25',
        })
        self.assertEqual(c.districts, ['ونک', 'آجودانیه'])
        self.assertEqual(c.limit_per_run, 25)
        self.assertTrue(c.is_active)


class DistrictRotationTests(TestCase):
    def setUp(self):
        self.campaign = AcquisitionAutomationCampaign.objects.create(
            name='تهران · چرخشی',
            city='تهران',
            districts=['ونک', 'آشتیانی', 'امانیه'],
            category='apartment-sell',
            limit_per_run=20,
            interval_hours=6,
            is_active=True,
        )

    def test_pick_district_uses_cursor(self):
        from accounts.services.acquisition_automation import pick_district

        self.assertEqual(pick_district(self.campaign), 'ونک')
        self.campaign.district_cursor = 1
        self.campaign.save(update_fields=['district_cursor'])
        self.assertEqual(pick_district(self.campaign), 'آشتیانی')

    def test_finalize_advances_cursor(self):
        from accounts.services.acquisition_automation import finalize_run_from_worker, pick_district

        run = AcquisitionRun.objects.create(
            campaign=self.campaign,
            status=AcquisitionRun.Status.RUNNING,
            district='ونک',
            output_json={'metadata': {}, 'consultants': []},
        )
        finalize_run_from_worker(
            run.pk,
            worker_status='completed',
            output_payload=run.output_json,
            auto_ingest=False,
        )
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.district_cursor, 1)
        self.assertEqual(pick_district(self.campaign), 'آشتیانی')

    def test_schedule_stores_rotation_metrics(self):
        from accounts.services.acquisition_automation import schedule_due_campaigns

        self.campaign.next_run_at = timezone.now()
        self.campaign.save()
        created = schedule_due_campaigns(max_jobs=1)
        self.assertEqual(len(created), 1)
        run = created[0]
        self.assertEqual(run.district, 'ونک')
        self.assertEqual(run.metrics.get('district_index'), 1)
        self.assertEqual(run.metrics.get('district_total'), 3)


class AutomationPartialIngestTests(TestCase):
    def test_rate_limited_with_phones_can_ingest(self):
        from accounts.services.acquisition_automation import finalize_run_from_worker

        campaign = AcquisitionAutomationCampaign.objects.create(
            name='تست',
            city='تهران',
            districts=['ونک'],
            interval_hours=6,
        )
        run = AcquisitionRun.objects.create(
            campaign=campaign,
            status=AcquisitionRun.Status.RUNNING,
            district='ونک',
            output_json={
                'metadata': {'city': 'تهران', 'district': 'ونک', 'category': 'apartment-sell'},
                'consultants': [
                    {'consultant_name': 'آژانس تست', 'phone': '09123334444', 'district': 'ونک'},
                ],
            },
            phones_extracted=1,
        )
        result = finalize_run_from_worker(
            run.pk,
            worker_status='rate_limited',
            output_payload=run.output_json,
            error_message='captcha',
            auto_ingest=True,
        )
        run.refresh_from_db()
        self.assertEqual(run.status, AcquisitionRun.Status.INGESTED)
        self.assertIsNotNone(run.import_batch_id)


class AutomationOverviewStatsTests(TestCase):
    def setUp(self):
        self.campaign = AcquisitionAutomationCampaign.objects.create(
            name='تهران · تست KPI',
            city='تهران',
            districts=['ونک', 'آشتیانی'],
            is_active=True,
            next_run_at=timezone.now(),
        )

    def test_overview_stats_focus_run_and_due(self):
        run = AcquisitionRun.objects.create(
            campaign=self.campaign,
            status=AcquisitionRun.Status.QUEUED,
            district='ونک',
        )
        stats = automation_overview_stats()
        self.assertEqual(stats['campaigns_active'], 1)
        self.assertGreaterEqual(stats['campaigns_due'], 1)
        self.assertEqual(stats['runs_queued'], 1)
        self.assertIsNotNone(stats['focus_run'])
        self.assertEqual(stats['focus_run']['id'], run.pk)
        self.assertEqual(stats['focus_run']['district'], 'ونک')
        self.assertIn('phones_ingested_24h', stats)
        self.assertIn('lines_total', stats)
