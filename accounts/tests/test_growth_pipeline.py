"""Tests for unified growth pipeline orchestrator."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import GrowthJourney, MarketingLead
from accounts.services.growth_journey import journey_display_name, on_click_landing, on_signup, transition
from accounts.services.growth_suppression import (
    PURPOSE_ACQUISITION,
    PURPOSE_ACTIVATION,
    PURPOSE_RECOVERY,
    is_send_allowed,
)
from accounts.services.user_activation import get_or_create_default_activation_campaign

User = get_user_model()


class GrowthJourneyTransitionTests(TestCase):
    def setUp(self):
        self.lead = MarketingLead.objects.create(
            phone_normalized='09121234567',
            status=MarketingLead.Status.COLD,
            source='test',
        )

    def test_import_to_engaged_to_registered(self):
        j = transition(
            phone=self.lead.phone_normalized,
            lead=self.lead,
            event_type='lead_imported',
        )
        self.assertEqual(j.stage, GrowthJourney.Stage.COLD_LEAD)

        on_click_landing(lead=self.lead)
        j.refresh_from_db()
        self.assertEqual(j.stage, GrowthJourney.Stage.ENGAGED)

        user = User.objects.create_user(
            username='u9121234567',
            phone='09121234567',
            password='x',
        )
        on_signup(user=user, lead=self.lead)
        j.refresh_from_db()
        self.assertEqual(j.stage, GrowthJourney.Stage.REGISTERED)
        self.assertEqual(j.user_id, user.pk)

    def test_pending_checkout_blocks_activation_allows_recovery(self):
        user = User.objects.create_user(
            username='u9121234568',
            phone='09121234568',
            password='x',
        )
        MarketingLead.objects.create(
            phone_normalized='09121234568',
            status=MarketingLead.Status.REGISTERED,
            matched_user=user,
        )
        transition(
            phone='09121234568',
            user=user,
            event_type='signup',
            stage=GrowthJourney.Stage.REGISTERED,
            allow_regress=True,
        )
        self.assertTrue(is_send_allowed('09121234568', purpose=PURPOSE_ACTIVATION, user=user))
        self.assertFalse(is_send_allowed('09121234568', purpose=PURPOSE_ACQUISITION, user=user))

        transition(
            phone='09121234568',
            user=user,
            event_type='checkout_start',
            allow_regress=True,
        )
        self.assertTrue(is_send_allowed('09121234568', purpose=PURPOSE_RECOVERY, user=user))
        self.assertFalse(is_send_allowed('09121234568', purpose=PURPOSE_ACTIVATION, user=user))


class ActivationCampaignStepsTests(TestCase):
    def test_activation_has_three_steps(self):
        campaign = get_or_create_default_activation_campaign()
        steps = list(campaign.steps.order_by('step_number'))
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].delay_days, 0)
        self.assertEqual(steps[1].delay_days, 2)
        self.assertEqual(steps[2].delay_days, 5)

    @patch('accounts.services.user_activation.send_activation_step1_now')
    def test_enroll_triggers_welcome(self, mock_send):
        from accounts.services.user_activation import enroll_user_in_activation_campaign

        user = User.objects.create_user(
            username='u91219999999',
            phone='09129999999',
            password='x',
        )
        lead = MarketingLead.objects.create(
            phone_normalized='09129999999',
            status=MarketingLead.Status.REGISTERED,
            matched_user=user,
        )
        enroll = enroll_user_in_activation_campaign(user=user, lead=lead, send_welcome=True)
        self.assertIsNotNone(enroll)
        mock_send.assert_called_once()


@override_settings(ROOT_URLCONF='divar_shop.urls')
class GrowthPipelineAdminViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffgp',
            phone='09121110000',
            password='x',
            is_staff=True,
        )

    def test_pipeline_page_ok(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/accounts/admin-panel/marketing/growth/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'پایپلاین رشد')
        self.assertContains(resp, 'خروجی Excel')

    def test_growth_journeys_export_xlsx(self):
        MarketingLead.objects.create(
            phone_normalized='09123334444',
            display_name='آژانس نمونه',
            status=MarketingLead.Status.COLD,
            source='test',
        )
        transition(phone='09123334444', event_type='lead_imported')
        self.client.force_login(self.staff)
        resp = self.client.get('/accounts/admin-panel/export/growth_journeys/?format=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resp['Content-Type'],
        )
        self.assertIn('attachment', resp.get('Content-Disposition', ''))


class JourneyDisplayNameTests(TestCase):
    def test_prefers_lead_display_name(self):
        lead = MarketingLead.objects.create(
            phone_normalized='09124445555',
            display_name='دفتر املاک X',
            status=MarketingLead.Status.COLD,
        )
        j = GrowthJourney.objects.create(
            phone_normalized='09124445555',
            lead=lead,
            stage=GrowthJourney.Stage.COLD_LEAD,
        )
        self.assertEqual(journey_display_name(j), 'دفتر املاک X')
