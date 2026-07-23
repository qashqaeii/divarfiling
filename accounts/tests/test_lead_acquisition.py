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
    auto_create_campaign_for_import,
    batches_pending_campaign,
    bulk_update_variant_templates,
    create_acquisition_campaign,
    enroll_all_eligible,
    enroll_pilot,
    ensure_campaign_for_batch,
    estimate_sms_cost_rial,
    generate_acquisition_campaign_name,
    pilot_per_variant_for_count,
    reset_campaign_for_retry,
    send_campaign_step,
    send_step_message,
    unicode_sms_parts,
    update_acquisition_campaign,
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

    def test_sms_cost_matches_provider_parts(self):
        sample = (
            'هنوز برای پیدا کردن فایل مناسب بین آگهی‌ها زمان زیادی می‌گذارید؟ '
            'فایلینگ دیوار برای سریع‌تر شدن کار مشاوران املاک ساخته شده. ببینید چطور: '
            'https://divarfiling.ir/s/t/2lp8ZE5pH_XftLE6/\nلغو۱۱'
        )
        # پنل واقعی: ۱۸۸ کاراکتر ≈ ۳ بخش × ۲۴۸۰ = ۷۴۴۰ ریال
        self.assertEqual(len(sample), 188)
        self.assertEqual(unicode_sms_parts(sample), 3)
        self.assertEqual(estimate_sms_cost_rial(sample), 7440)
        from accounts.models import LeadList, LeadListMember

        payload_a = {
            'metadata': {'city': 'تهران', 'district': 'اقدسیه', 'category': 'apartment-sell'},
            'consultants': [
                {'consultant_name': 'آژانس یک', 'phone': '09121110001'},
                {'consultant_name': 'مشاور دو', 'phone': '09121110002'},
            ],
        }
        payload_b = {
            'metadata': {'city': 'تهران', 'district': 'اقدسیه', 'category': 'apartment-sell'},
            'consultants': [
                {'consultant_name': 'آژانس یک', 'phone': '09121110001'},  # تکراری بین فایل
                {'consultant_name': 'مشاور سه', 'phone': '09121110003'},
            ],
        }
        raw_a = json.dumps(payload_a).encode('utf-8')
        raw_b = json.dumps(payload_b).encode('utf-8')
        prev_a = preview_phone_detector_json(raw_a, filename='aq1.json')
        batch_a = create_preview_batch(prev_a)
        r1 = commit_import_batch(batch_a.pk, preview_rows=prev_a.rows)

        prev_b = preview_phone_detector_json(raw_b, filename='aq2.json')
        batch_b = create_preview_batch(prev_b)
        r2 = commit_import_batch(batch_b.pk, preview_rows=prev_b.rows)

        self.assertEqual(r1['list_id'], r2['list_id'])
        self.assertEqual(
            LeadList.objects.filter(city='تهران', district='اقدسیه').count(),
            1,
        )
        self.assertEqual(LeadListMember.objects.filter(lead_list_id=r1['list_id']).count(), 3)
        self.assertFalse(r2['list_created'])

    def test_auto_campaign_after_import(self):
        from accounts.models import LeadList

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='auto.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        lead_list = LeadList.objects.get(pk=result['list_id'])
        eligible = preview.stats.get('eligible', 0)
        campaign = auto_create_campaign_for_import(
            lead_list=lead_list,
            batch_id=batch.pk,
            eligible_count=eligible,
        )
        self.assertIsNotNone(campaign)
        self.assertIn('جذب', campaign.name)
        self.assertIn('پایلوت A/B', campaign.name)
        self.assertEqual(campaign.pilot_per_variant, pilot_per_variant_for_count(eligible))
        # دومین بار برای همان بچ نباید کمپین تکراری بسازد
        again = auto_create_campaign_for_import(
            lead_list=lead_list,
            batch_id=batch.pk,
            eligible_count=eligible,
        )
        self.assertEqual(again.pk, campaign.pk)

    def test_ensure_campaign_for_committed_batch_without_campaign(self):
        from accounts.models import LeadImportBatch, LeadList

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='backfill.json')
        batch = create_preview_batch(preview)
        commit_import_batch(batch.pk, preview_rows=preview.rows)
        batch.refresh_from_db()
        self.assertEqual(batch.status, LeadImportBatch.Status.COMMITTED)
        self.assertFalse((batch.preview_stats or {}).get('campaign_id'))

        pending = batches_pending_campaign(limit=10)
        self.assertTrue(any(r['batch'].pk == batch.pk for r in pending))

        campaign = ensure_campaign_for_batch(batch.pk)
        self.assertIsNotNone(campaign)
        batch.refresh_from_db()
        self.assertEqual(batch.preview_stats.get('campaign_id'), campaign.pk)
        self.assertFalse(batches_pending_campaign(limit=10))

    def test_two_batches_same_list_each_get_campaign(self):
        from accounts.models import LeadList

        payload_a = {
            'metadata': {'city': 'تهران', 'district': 'اقدسیه', 'category': 'apartment-sell'},
            'consultants': [{'consultant_name': 'آژانس', 'phone': '09121110001'}],
        }
        payload_b = {
            'metadata': {'city': 'تهران', 'district': 'اقدسیه', 'category': 'apartment-sell'},
            'consultants': [{'consultant_name': 'مشاور', 'phone': '09121110002'}],
        }
        prev_a = preview_phone_detector_json(json.dumps(payload_a).encode(), filename='a.json')
        batch_a = create_preview_batch(prev_a)
        r_a = commit_import_batch(batch_a.pk, preview_rows=prev_a.rows)

        prev_b = preview_phone_detector_json(json.dumps(payload_b).encode(), filename='b.json')
        batch_b = create_preview_batch(prev_b)
        r_b = commit_import_batch(batch_b.pk, preview_rows=prev_b.rows)

        self.assertEqual(r_a['list_id'], r_b['list_id'])
        lead_list = LeadList.objects.get(pk=r_a['list_id'])

        c_a = auto_create_campaign_for_import(
            lead_list=lead_list, batch_id=batch_a.pk, eligible_count=1,
        )
        c_b = auto_create_campaign_for_import(
            lead_list=lead_list, batch_id=batch_b.pk, eligible_count=1,
        )
        self.assertIsNotNone(c_a)
        self.assertIsNotNone(c_b)
        self.assertNotEqual(c_a.pk, c_b.pk)

    def test_update_campaign_variants(self):
        from accounts.models import LeadList

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='u.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        lead_list = LeadList.objects.get(pk=result['list_id'])
        campaign = create_acquisition_campaign(name='Test', lead_list=lead_list)
        updated = update_acquisition_campaign(
            campaign.pk,
            name='جذب · تست',
            variant_a_template='نسخه A تست {link}',
            variant_b_template='نسخه B تست {link}',
        )
        self.assertEqual(updated.name, 'جذب · تست')
        step = updated.steps.get(step_number=1)
        self.assertIn('نسخه A تست', step.message_template)
        self.assertIn('نسخه B تست', step.message_template)


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
        self.assertEqual(msg.sms_cost_snapshot, estimate_sms_cost_rial(msg.body_rendered))
        self.assertGreaterEqual(unicode_sms_parts(msg.body_rendered), 1)

        stats2 = send_campaign_step(self.campaign, 1)
        self.assertEqual(stats2['accepted'], 0)
        self.assertEqual(stats2['remaining'], 0)
        self.assertEqual(stats2['pending_before'], 0)
        self.assertEqual(
            CampaignMessage.objects.filter(campaign=self.campaign, step__step_number=1).count(),
            CampaignEnrollment.objects.filter(
                campaign=self.campaign,
                status=CampaignEnrollment.Status.ACTIVE,
            ).count(),
        )

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_send_respects_batch_size_and_reports_remaining(self, mock_notify):
        from accounts.models import LeadListMember, SmsMessageLog

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        for idx, phone in enumerate(('09121110010', '09121110011', '09121110012'), start=1):
            lead = MarketingLead.objects.create(
                phone_normalized=phone,
                display_name=f'Lead {idx}',
                status=MarketingLead.Status.COLD,
            )
            LeadListMember.objects.create(lead_list=self.lead_list, lead=lead)
        enroll_pilot(self.campaign, per_variant=5)

        with self.settings(LEAD_CAMPAIGN_SEND_BATCH_SIZE=2):
            stats = send_campaign_step(self.campaign, 1)
        self.assertLessEqual(stats['accepted'], 2)
        self.assertEqual(stats['batch_limit'], 2)
        self.assertEqual(stats['remaining'], stats['pending_before'] - stats['processed'])

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

    def test_delete_campaign_allows_fresh_start(self):
        from accounts.models import LeadCampaign
        from accounts.services.lead_campaign_send import delete_lead_campaign

        cid = self.campaign.pk
        result = delete_lead_campaign(cid, confirm=True)
        self.assertEqual(result['deleted_campaign_id'], cid)
        self.assertFalse(LeadCampaign.objects.filter(pk=cid).exists())
        # لیست سرنخ باقی است
        self.assertTrue(self.lead_list.members.exists())

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_failed_message_can_be_retried(self, mock_notify):
        from accounts.models import SmsMessageLog

        calls = {'n': 0}

        def _fake(phone, text='', attributes=None):
            calls['n'] += 1
            log = SmsMessageLog.objects.create(
                phone=phone, purpose='x', status=SmsMessageLog.Status.FAILED,
            )
            if calls['n'] == 1:
                log.mark_failed('اختلال اپراتور شاتل')
                return False, log
            log.mark_sent(provider='console', message_id='ok', status=SmsMessageLog.Status.FAKE)
            return True, log

        mock_notify.side_effect = _fake
        send_campaign_step(self.campaign, 1)
        failed = CampaignMessage.objects.filter(
            campaign=self.campaign, status=CampaignMessage.Status.FAILED,
        ).count()
        self.assertGreaterEqual(failed, 1)
        reset_campaign_for_retry(self.campaign.pk)
        stats = send_campaign_step(self.campaign, 1)
        self.assertGreaterEqual(stats.get('retried', 0) + stats.get('accepted', 0), 1)
        self.assertGreaterEqual(
            CampaignMessage.objects.filter(
                campaign=self.campaign,
                status=CampaignMessage.Status.PROVIDER_ACCEPTED,
            ).count(),
            1,
        )
        from accounts.models import SmsMessageLog

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        send_campaign_step(self.campaign, 1)
        data = campaign_funnel(self.campaign)
        self.assertEqual(data['pilot_label'], 'نتیجه پایلوت')
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
        self.assertContains(resp, 'lac-campaigns-bulk-form')
        self.assertContains(resp, 'lac-select-all')
        self.assertContains(resp, 'کلیک لندینگ')
        self.assertContains(resp, 'lac-chart-conversion')
        self.assertContains(resp, 'lac-campaign-table')
        self.assertContains(resp, 'lac-charts-data')

    @patch('accounts.lead_acquisition_views.enroll_pilot')
    def test_bulk_enroll_pilot(self, mock_enroll):
        from accounts.models import LeadList

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='bulk.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        lead_list = LeadList.objects.get(pk=result['list_id'])
        c1 = create_acquisition_campaign(name='C1', lead_list=lead_list)
        c2 = create_acquisition_campaign(name='C2', lead_list=lead_list)
        mock_enroll.return_value = {'enrolled': 2, 'held': 0, 'per_variant': {'A': 1, 'B': 1}}

        resp = self.client.post(
            reverse('admin_panel_lead_acquisition'),
            {
                'action': 'bulk_campaigns',
                'bulk_op': 'enroll_pilot',
                'campaign_ids': [str(c1.pk), str(c2.pk)],
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(mock_enroll.call_count, 2)

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_send_progress_api_chunks_until_done(self, mock_notify):
        from accounts.models import LeadList, SmsMessageLog

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='prog.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        lead_list = LeadList.objects.get(pk=result['list_id'])
        campaign = create_acquisition_campaign(
            name='Progress test',
            lead_list=lead_list,
            is_pilot=True,
            pilot_per_variant=10,
        )
        enroll_pilot(campaign)
        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )

        start = self.client.post(
            reverse('admin_panel_lead_send_progress_start'),
            data=json.dumps({'campaign_ids': [campaign.pk], 'step_number': 1}),
            content_type='application/json',
        )
        self.assertEqual(start.status_code, 200)
        start_data = start.json()
        self.assertTrue(start_data['ok'])
        self.assertGreaterEqual(start_data['total_pending'], 1)

        total_accepted = 0
        for _ in range(20):
            tick = self.client.post(
                reverse('admin_panel_lead_send_progress_tick'),
                data=json.dumps({'campaign_ids': [campaign.pk], 'step_number': 1}),
                content_type='application/json',
            )
            self.assertEqual(tick.status_code, 200)
            tick_data = tick.json()
            self.assertTrue(tick_data['ok'])
            total_accepted += tick_data.get('accepted', 0)
            if tick_data.get('done'):
                break
        self.assertTrue(tick_data.get('done'))
        self.assertGreaterEqual(total_accepted, 1)

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_send_step_post_returns_redirect_not_500(self, mock_notify):
        from accounts.models import LeadList, SmsMessageLog

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='post.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        lead_list = LeadList.objects.get(pk=result['list_id'])
        campaign = create_acquisition_campaign(
            name='POST test',
            lead_list=lead_list,
            is_pilot=True,
            pilot_per_variant=10,
        )
        enroll_pilot(campaign)
        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        resp = self.client.post(
            reverse('admin_panel_lead_acquisition'),
            {
                'action': 'send_step',
                'campaign_id': campaign.pk,
                'step_number': 1,
            },
        )
        self.assertEqual(resp.status_code, 302)


class LeadCampaignFullSendTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff_full',
            password='x',
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)
        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='full.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        from accounts.models import LeadList

        self.lead_list = LeadList.objects.get(pk=result['list_id'])
        self.campaign = create_acquisition_campaign(
            name='Full send test',
            lead_list=self.lead_list,
            is_pilot=True,
            pilot_per_variant=1,
        )
        enroll_pilot(self.campaign)

    def test_enroll_all_eligible_activates_held_leads(self):
        from accounts.models import LeadListMember

        CampaignEnrollment.objects.filter(campaign=self.campaign).delete()
        extra = MarketingLead.objects.create(
            phone_normalized='09123333333',
            display_name='Extra lead',
            status=MarketingLead.Status.COLD,
        )
        LeadListMember.objects.create(lead_list=self.lead_list, lead=extra)
        enroll_pilot(self.campaign, per_variant=1)
        held = CampaignEnrollment.objects.filter(
            campaign=self.campaign,
            status=CampaignEnrollment.Status.HOLD,
        ).count()
        self.assertGreaterEqual(held, 1)
        result = enroll_all_eligible(self.campaign)
        self.assertGreaterEqual(result['activated'] + result['enrolled'], 1)
        self.assertEqual(
            CampaignEnrollment.objects.filter(
                campaign=self.campaign,
                status=CampaignEnrollment.Status.ACTIVE,
            ).count(),
            result['total_active'],
        )
        self.assertEqual(
            CampaignEnrollment.objects.filter(
                campaign=self.campaign,
                status=CampaignEnrollment.Status.HOLD,
            ).count(),
            0,
        )

    def test_bulk_update_variant_templates(self):
        campaign2 = create_acquisition_campaign(
            name='Bulk tpl 2',
            lead_list=self.lead_list,
            is_pilot=False,
        )
        result = bulk_update_variant_templates(
            [self.campaign.pk, campaign2.pk],
            variant_a='قالب A یکسان {link}',
            variant_b='قالب B یکسان {link}',
        )
        self.assertEqual(result['updated_count'], 2)
        for cid in (self.campaign.pk, campaign2.pk):
            step = LeadCampaign.objects.get(pk=cid).steps.get(step_number=1)
            self.assertIn('قالب A یکسان', step.message_template)
            self.assertIn('قالب B یکسان', step.message_template)

    @patch('accounts.services.lead_campaign_send.notify_marketing')
    def test_send_progress_start_enrolls_all_before_count(self, mock_notify):
        from accounts.models import SmsMessageLog

        mock_notify.side_effect = lambda phone, text='', attributes=None: (
            True,
            SmsMessageLog.objects.create(phone=phone, purpose='x', status=SmsMessageLog.Status.FAKE),
        )
        start = self.client.post(
            reverse('admin_panel_lead_send_progress_start'),
            data=json.dumps({'campaign_ids': [self.campaign.pk], 'step_number': 1}),
            content_type='application/json',
        )
        self.assertEqual(start.status_code, 200)
        data = start.json()
        self.assertTrue(data['ok'])
        self.assertIn('enroll', data)
        self.assertEqual(
            CampaignEnrollment.objects.filter(
                campaign=self.campaign,
                status=CampaignEnrollment.Status.HOLD,
            ).count(),
            0,
        )
        self.assertGreaterEqual(data['total_pending'], 2)

    def test_bulk_templates_api_apply_all(self):
        resp = self.client.post(
            reverse('admin_panel_lead_bulk_templates'),
            data=json.dumps({
                'apply_all': True,
                'variant_a': 'API A {link}',
                'variant_b': 'API B {link}',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertGreaterEqual(payload['updated_count'], 1)
        step = self.campaign.steps.get(step_number=1)
        self.assertIn('API A', step.message_template)
        self.assertIn('API B', step.message_template)


class LeadOverviewDashboardTests(TestCase):
    def test_overview_stats_includes_clicks_and_purchases(self):
        from accounts.services.lead_funnel import acquisition_dashboard_charts, overview_stats

        stats = overview_stats()
        self.assertIn('total_clicks', stats)
        self.assertIn('total_purchases', stats)
        self.assertIn('accepted_sms', stats)
        self.assertGreaterEqual(stats['leads_total'], 0)

    def test_acquisition_dashboard_charts_structure(self):
        from accounts.services.lead_funnel import acquisition_dashboard_charts, campaign_funnel

        raw = json.dumps(SAMPLE_JSON).encode('utf-8')
        preview = preview_phone_detector_json(raw, filename='chart.json')
        batch = create_preview_batch(preview)
        result = commit_import_batch(batch.pk, preview_rows=preview.rows)
        from accounts.models import LeadList

        lead_list = LeadList.objects.get(pk=result['list_id'])
        campaign = create_acquisition_campaign(
            name='Chart test campaign',
            lead_list=lead_list,
            is_pilot=True,
        )
        funnels = [campaign_funnel(campaign)]
        charts = acquisition_dashboard_charts([campaign], funnels)
        self.assertIn('funnel', charts)
        self.assertIn('rates', charts)
        self.assertIn('status', charts)
        self.assertIn('campaigns', charts)
        self.assertEqual(len(charts['campaigns']), 1)
        self.assertEqual(len(charts['funnel_steps']), 6)
        self.assertIn('summary', charts)
        self.assertIn('campaign_table', charts)
        self.assertIn('conversion_series', charts)
