"""تست‌های مرکز جذب سرنخ."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import (
    CampaignEnrollment,
    CampaignMessage,
    LeadAttribution,
    LeadCampaign,
    LeadTouchpoint,
    MarketingLead,
    SuppressionEntry,
)
from accounts.services.lead_attribution import attribute_purchase, attribute_signup
from accounts.services.lead_campaign_send import (
    create_acquisition_campaign,
    enroll_pilot,
    send_campaign_step,
    send_step_message,
)
from accounts.services.lead_funnel import campaign_funnel
from accounts.services.lead_import import commit_import_batch, preview_phone_detector_json, create_preview_batch
from accounts.services.lead_sequence import run_acquisition_sequence
from accounts.services.user_activation import get_or_create_default_activation_campaign

User = get_user_model()


SAMPLE_JSON = {
    'metadata': {
        'city': 'تهران',
        'district': 'آجودانیه',
        'category': 'apartment-sell',
        'scraped_at': '2026-07-21T15:32:02.261616+00:00',
    },
    'consultants': [
        {
            'consultant_name': 'آژانس مسکن نمونه',
            'district': 'ajoodanieh',
            'phone': '09121111111',
        },
        {
            'consultant_name': 'مشاور تست',
            'district': 'ajoodanieh',
            'phone': '09122222222',
        },
        {
            'consultant_name': 'تکراری',
            'district': 'ajoodanieh',
            'phone': '09121111111',
        },
        {
            'consultant_name': 'نامعتبر',
            'phone': '12345',
        },
    ],
}


class LeadImportTests(TestCase):
    def test_preview_and_commit(self):
        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='t.json')
        self.assertEqual(preview.stats['valid'], 3)
        self.assertEqual(preview.stats['duplicate_in_file'], 1)
        self.assertEqual(preview.stats['invalid'], 1)
        self.assertGreaterEqual(preview.stats['eligible'], 2)

        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        self.assertEqual(MarketingLead.objects.count(), 2)
        self.assertTrue(result['list_id'])

        lead = MarketingLead.objects.get(phone_normalized='09121111111')
        self.assertEqual(lead.lead_type, MarketingLead.LeadType.AGENCY)

    def test_existing_user_not_suppressed(self):
        User.objects.create_user(username='eu1', password='x', phone='09123333333')
        payload = {
            'metadata': {'city': 'تهران', 'district': 'آجودانیه', 'category': 'apartment-sell'},
            'consultants': [{'consultant_name': 'کاربر موجود', 'phone': '09123333333'}],
        }
        raw = json.dumps(payload).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='u.json')
        self.assertEqual(preview.stats['existing_user'], 1)
        batch = create_preview_batch(preview)
        commit_import_batch(batch.pk, preview_rows=preview.rows)
        lead = MarketingLead.objects.get(phone_normalized='09123333333')
        self.assertEqual(lead.status, MarketingLead.Status.EXISTING_USER)
        self.assertFalse(SuppressionEntry.objects.filter(phone_normalized='09123333333').exists())

    def test_duplicate_file_hash_rejected_after_commit(self):
        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='t.json')
        batch = create_preview_batch(preview)
        commit_import_batch(batch.pk, preview_rows=preview.rows)
        again = preview_phone_detector_json(raw, filename='t2.json')
        self.assertTrue(again.duplicate_file)


class LeadCampaignTrackingTests(TestCase):
    def setUp(self):
        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='c.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        from accounts.models import LeadList
        self.lead_list = LeadList.objects.get(pk=result['list_id'])
        self.campaign = create_acquisition_campaign(
            name='Pilot Ajoodanieh',
            lead_list=self.lead_list,
            is_pilot=True,
            pilot_per_variant=10,
        )
        enroll_pilot(self.campaign)

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_send_creates_click_token_and_idempotent(self, mock_notify):
        from accounts.models import SmsMessageLog

        def _fake(phone, text='', attributes=None):
            log = SmsMessageLog.objects.create(
                phone=phone, purpose='lead_acquisition', status=SmsMessageLog.Status.FAKE,
            )
            return True, log

        mock_notify.side_effect = _fake
        stats = send_campaign_step(self.campaign, 1)
        self.assertGreaterEqual(stats['accepted'], 1)
        msg = CampaignMessage.objects.filter(campaign=self.campaign).first()
        self.assertTrue(msg.click_token)
        self.assertEqual(msg.sms_cost_snapshot, 300)

        stats2 = send_campaign_step(self.campaign, 1)
        self.assertGreaterEqual(stats2['idempotent'], 1)
        self.assertEqual(
            CampaignMessage.objects.filter(campaign=self.campaign, step__step_number=1).count(),
            CampaignEnrollment.objects.filter(campaign=self.campaign).count(),
        )

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_click_redirect_sets_cookie_and_touchpoints(self, mock_notify):
        from accounts.models import SmsMessageLog

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        send_campaign_step(self.campaign, 1)
        msg = CampaignMessage.objects.filter(
            campaign=self.campaign,
            status=CampaignMessage.Status.PROVIDER_ACCEPTED,
        ).first()
        client = Client()
        resp = client.get(reverse('lead_click_redirect_root', kwargs={'click_token': msg.click_token}))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('df_lead_msg', resp.cookies)
        self.assertTrue(
            LeadTouchpoint.objects.filter(
                message=msg, event_type=LeadTouchpoint.EventType.CLICK,
            ).exists()
        )

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_signup_direct_attribution_and_activation_enroll(self, mock_notify):
        from accounts.models import SmsMessageLog

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        send_campaign_step(self.campaign, 1)
        msg = CampaignMessage.objects.filter(
            status=CampaignMessage.Status.PROVIDER_ACCEPTED,
        ).select_related('lead').first()

        class Req:
            COOKIES = {'df_lead_msg': msg.click_token}

        user = User.objects.create_user(
            username='newu', password='x', phone=msg.lead.phone_normalized,
        )
        attr = attribute_signup(user=user, request=Req())
        self.assertIsNotNone(attr)
        self.assertEqual(attr.axis, LeadAttribution.Axis.ACQUISITION)
        self.assertEqual(attr.attribution_kind, LeadAttribution.Kind.DIRECT)
        msg.lead.refresh_from_db()
        self.assertEqual(msg.lead.status, MarketingLead.Status.REGISTERED)
        self.assertFalse(
            CampaignEnrollment.objects.filter(
                lead=msg.lead,
                campaign=self.campaign,
                status=CampaignEnrollment.Status.ACTIVE,
            ).exists()
        )
        act = get_or_create_default_activation_campaign()
        self.assertTrue(
            CampaignEnrollment.objects.filter(
                lead=msg.lead,
                campaign=act,
                status=CampaignEnrollment.Status.ACTIVE,
            ).exists()
        )

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_funnel_pilot_label(self, mock_notify):
        from accounts.models import SmsMessageLog

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        send_campaign_step(self.campaign, 1)
        data = campaign_funnel(self.campaign)
        self.assertEqual(data['pilot_label'], 'Pilot Result')
        self.assertIn('accepted', data['funnel'])
        self.assertEqual(data['funnel']['estimated_reach'], data['funnel']['accepted'])

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_sequence_step2_without_click(self, mock_notify):
        from accounts.models import SmsMessageLog
        from django.utils import timezone
        from datetime import timedelta

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        send_campaign_step(self.campaign, 1)
        CampaignEnrollment.objects.filter(campaign=self.campaign).update(
            last_message_at=timezone.now() - timedelta(days=3),
            current_step_number=1,
        )
        report = run_acquisition_sequence(campaign_id=self.campaign.pk)
        step2 = report['campaigns'][0]['steps'].get(2) or report['campaigns'][0]['steps'].get('2')
        # keys may be int
        if step2 is None:
            step2 = list(report['campaigns'][0]['steps'].values())[1]
        self.assertGreaterEqual(step2['accepted'] + step2['skipped'] + step2['failed'], 1)


class LeadAdminViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff1', password='pass1234', phone='09120000001', is_staff=True,
        )
        self.client = Client()
        self.client.login(username='staff1', password='pass1234')

    def test_lead_acquisition_page(self):
        resp = self.client.get(reverse('admin_panel_lead_acquisition'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرکز جذب سرنخ')
