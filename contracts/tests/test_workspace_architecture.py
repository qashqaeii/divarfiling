"""تست‌های معماری workspace قراردادها و قیف معاملات."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.constants import CONTRACT_TYPE_LEASE
from contracts.models import Contract
from contracts.services.lifecycle import create_contract
from contracts.tests.helpers import grant_bot_license
from contracts.services.scope import contracts_qs
from workspace.models import CRMDeal, Customer

User = get_user_model()


class ContractWorkspaceArchitectureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ws_arch', password='x')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09120000000')
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, title='معامله تست', stage='مذاکره',
        )
        grant_bot_license(self.user)

    def test_standalone_contract_without_deal(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=None)
        self.assertIsNone(c.deal_id)
        self.assertEqual(c.user_id, self.user.pk)
        self.assertTrue(contracts_qs(self.user).filter(pk=c.pk).exists())

    def test_contract_linked_to_deal(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        self.assertEqual(c.deal_id, self.deal.pk)

    def test_contracts_dashboard_accessible(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contracts_dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_standalone_create_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contract_create_standalone'))
        self.assertEqual(resp.status_code, 200)

    def test_standalone_create_post(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('workspace:contract_create_standalone'), {
            'contract_type': 'lease',
            'deal_mode': 'none',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Contract.objects.filter(user=self.user, deal__isnull=True).count(), 1)

    def test_legacy_deal_contracts_redirects(self):
        self.client.force_login(self.user)
        url = reverse('workspace:deal_contracts', kwargs={'deal_id': self.deal.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('deal=', resp.url)

    def test_deal_funnel_page_loads(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:crm_deals'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'قیف معاملات')

    def test_deal_detail_journey_loads(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_deal_detail', kwargs={'deal_id': self.deal.pk})
        resp = self.client.get(url + '?tab=overview')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'قدم بعدی')
        self.assertContains(resp, 'dj-stage-rail')

    def test_standalone_wizard_manage_pdf_views(self):
        self.client.force_login(self.user)
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=None)
        wizard_url = reverse('workspace:contract_wizard_standalone', kwargs={'contract_id': c.pk})
        manage_url = reverse('workspace:contract_manage_standalone', kwargs={'contract_id': c.pk})
        self.assertEqual(self.client.get(wizard_url).status_code, 200)
        self.assertEqual(self.client.get(manage_url).status_code, 200)
        pdf_url = reverse('workspace:contract_pdf_standalone', kwargs={'contract_id': c.pk})
        self.assertIn(self.client.get(pdf_url).status_code, (200, 302, 404))

    def test_deal_search_api(self):
        self.client.force_login(self.user)
        url = reverse('workspace:contract_deal_search')
        resp = self.client.get(url, {'q': 'تست'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(any(r['id'] == self.deal.pk for r in data.get('results', [])))

    def test_create_page_has_type_cards(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contract_create_standalone'))
        self.assertContains(resp, 'ct-create-card')
        self.assertContains(resp, 'رهن و اجاره')

    def test_manage_lifecycle_ui(self):
        self.client.force_login(self.user)
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=None)
        url = reverse('workspace:contract_manage_standalone', kwargs={'contract_id': c.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'ct-lifecycle')
        self.assertContains(resp, 'ct-party-grid')
