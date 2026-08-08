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
