"""تست محدودیت لایسنس برای قراردادها."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.constants import CONTRACT_TYPE_LEASE
from contracts.services.invitations import send_invitations
from contracts.services.lifecycle import ContractError, create_contract
from contracts.tests.helpers import grant_bot_license
from workspace.models import CRMDeal, Customer

User = get_user_model()


class ContractLicenseGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ct_free', password='x', phone='09125550001')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09125550002')
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, title='معامله', stage='مذاکره',
        )

    def test_dashboard_accessible_without_license_shows_locked(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contracts_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'برای استفاده از قراردادهای دیجیتال، نیاز به لایسنس فعال دارید.')
        self.assertContains(resp, 'فعال‌سازی لایسنس')
        self.assertNotContains(resp, 'لیست قراردادها')

    def test_create_page_blocked_without_license(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contract_create_standalone'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/crm/contracts/', resp.url)

    def test_deal_api_blocked_without_license(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contract_deal_search'))
        self.assertEqual(resp.status_code, 403)

    def test_manage_view_blocked_without_license(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        url = reverse('workspace:contract_manage_standalone', kwargs={'contract_id': contract.pk})
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 200)
        from licenses.models import License
        License.objects.filter(order__user=self.user).update(status='inactive')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/crm/contracts/', resp.url)

    def test_create_contract_service_requires_license(self):
        with self.assertRaises(ContractError):
            create_contract(self.user, CONTRACT_TYPE_LEASE)

    def test_licensed_user_full_access(self):
        grant_bot_license(self.user)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:contracts_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'لیست قراردادها')
        self.assertNotContains(resp, 'ct-dash-locked__card')

    def test_send_invitations_service_requires_license(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        from licenses.models import License
        License.objects.filter(order__user=self.user).update(status='inactive')
        with self.assertRaises(ContractError):
            send_invitations(contract, user=self.user)
