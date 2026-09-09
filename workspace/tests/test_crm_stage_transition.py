"""تست‌های Smart Stage Transition."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workspace.models import CRMDeal, Customer
from workspace.services.crm_deals import update_deal_stage

User = get_user_model()


class CRMStageTransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='stage_tx', password='x')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09120000001')
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, title='معامله', stage='مذاکره',
        )

    def test_stage_update_json(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_deal_stage', kwargs={'deal_id': self.deal.pk})
        resp = self.client.post(
            url,
            data='{"stage": "بازدید"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'بازدید')

    def test_lost_requires_reason(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_deal_stage', kwargs={'deal_id': self.deal.pk})
        resp = self.client.post(
            url,
            data='{"stage": "از دست رفته"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_lost_with_reason(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_deal_stage', kwargs={'deal_id': self.deal.pk})
        resp = self.client.post(
            url,
            data='{"stage": "از دست رفته", "lost_reason": "قیمت"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'از دست رفته')
        self.assertEqual(self.deal.lost_reason, 'قیمت')

    def test_won_sets_closed_at(self):
        update_deal_stage(self.deal, 'بسته‌شده')
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'بسته‌شده')
        self.assertIsNotNone(self.deal.closed_at)

    def test_deals_list_has_transition_dialog(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:crm_deals') + '?view=pipeline')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'djStageTransition')
        self.assertContains(resp, 'crm-stage-transition.js')

    def test_deal_detail_has_transition_dialog(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_deal_detail', kwargs={'deal_id': self.deal.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'dj-lost-chips')
