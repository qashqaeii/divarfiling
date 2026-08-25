"""تست مراحل غنی معامله و کهنگی pipeline."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from workspace.constants import DEAL_STAGE_LOST, DEAL_STAGE_WON, DEFAULT_DEAL_STAGE_DEFS
from workspace.models import CRMDeal, Customer
from workspace.services.crm_deal_stages import (
    apply_stage_preset,
    get_user_deal_stage_defs,
    get_user_deal_stages,
    save_user_deal_stage_defs,
    serialize_stages_payload,
    validate_deal_stage_defs,
)
from workspace.services.crm_deals import create_deal, filter_deals, is_deal_stale, update_deal_stage

User = get_user_model()


class DealStagesServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120001111', password='test')
        self.customer = Customer.objects.create(
            user=self.user, name='مشتری قیف', phone='09120001111', status='جدید',
        )

    def test_default_defs_hydrate_from_empty(self):
        names = get_user_deal_stages(self.user)
        self.assertEqual(names[-2], DEAL_STAGE_WON)
        self.assertEqual(names[-1], DEAL_STAGE_LOST)
        defs = get_user_deal_stage_defs(self.user)
        self.assertGreaterEqual(len(defs), 3)
        self.assertTrue(all('color' in d and 'probability' in d for d in defs))

    def test_legacy_string_list_hydrates(self):
        from workspace.models import WorkspaceSettings
        settings, _ = WorkspaceSettings.objects.get_or_create(user=self.user)
        settings.crm_deal_stages = ['سرنخ', 'بازدید', DEAL_STAGE_WON, DEAL_STAGE_LOST]
        settings.save(update_fields=['crm_deal_stages'])
        defs = get_user_deal_stage_defs(self.user)
        self.assertEqual([d['name'] for d in defs], ['سرنخ', 'بازدید', DEAL_STAGE_WON, DEAL_STAGE_LOST])
        self.assertEqual(defs[0]['id'], 'lead')

    def test_save_rich_definitions_and_rename(self):
        defs = [dict(item) for item in DEFAULT_DEAL_STAGE_DEFS]
        defs[0]['name'] = 'فرصت جدید'
        saved = save_user_deal_stage_defs(self.user, defs)
        self.assertEqual(saved[0]['name'], 'فرصت جدید')
        deal = create_deal(self.user, self.customer, title='د', stage='فرصت جدید')
        self.assertEqual(deal.stage, 'فرصت جدید')
        self.assertEqual(deal.probability, 15)

    def test_preset_rent(self):
        defs = apply_stage_preset(self.user, 'rent')
        names = [d['name'] for d in defs]
        self.assertIn('مذاکره رهن', names)
        self.assertEqual(names[-1], DEAL_STAGE_LOST)

    def test_validate_requires_terminal_stages(self):
        with self.assertRaises(ValueError):
            validate_deal_stage_defs(['سرنخ', 'بازدید', 'قرارداد'])

    def test_stage_change_applies_probability_and_age(self):
        deal = create_deal(self.user, self.customer, title='د', stage='سرنخ')
        self.assertIsNotNone(deal.stage_changed_at)
        update_deal_stage(deal, 'مذاکره')
        deal.refresh_from_db()
        self.assertEqual(deal.stage, 'مذاکره')
        self.assertEqual(deal.probability, 35)

    def test_stale_deal_uses_rot_days(self):
        deal = create_deal(self.user, self.customer, title='کهنه', stage='سرنخ')
        deal.stage_changed_at = timezone.now() - timedelta(days=10)
        deal.save(update_fields=['stage_changed_at'])
        self.assertTrue(is_deal_stale(deal))

    def test_filter_stale_bucket_does_not_raise_field_error(self):
        deal = create_deal(self.user, self.customer, title='کهنه فیلتر', stage='سرنخ')
        deal.stage_changed_at = timezone.now() - timedelta(days=10)
        deal.save(update_fields=['stage_changed_at'])
        qs = filter_deals(self.user, {'bucket': 'stale'})
        ids = list(qs.values_list('id', flat=True))
        self.assertIn(deal.pk, ids)

    def test_payload_includes_presets(self):
        payload = serialize_stages_payload(self.user)
        self.assertIn('definitions', payload)
        self.assertIn('presets', payload)
        self.assertGreaterEqual(len(payload['presets']), 3)


class CRMDealListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120002222', password='test')
        self.customer = Customer.objects.create(
            user=self.user, name='مخاطب معامله', phone='09120002222', status='جدید',
        )
        self.client = Client()
        self.client.force_login(self.user)
        deal = create_deal(self.user, self.customer, title='کهنه لیست', stage='سرنخ')
        deal.stage_changed_at = timezone.now() - timedelta(days=10)
        deal.save(update_fields=['stage_changed_at'])

    def test_stale_bucket_page_returns_200(self):
        response = self.client.get(reverse('workspace:crm_deals'), {'bucket': 'stale'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'crm-deals-mobile.css')
        self.assertContains(response, 'کهنه لیست')
