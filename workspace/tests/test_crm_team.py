"""تست مدیریت تیم CRM."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.constants import TEAM_VISIBILITY_INBOX
from workspace.models import CRMAgencyMember, CRMProperty, Customer
from workspace.services.crm_agency import apply_lead_routing, create_agency, regenerate_api_key
from workspace.services.crm_sharing import share_property
from workspace.services.crm_webhooks import create_lead_from_api

User = get_user_model()


class CRMTeamProTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner1', password='pass12345')
        self.agency = create_agency(self.owner, 'آژانس تست')

    def test_regenerate_api_key(self):
        old = self.agency.api_key
        new_key = regenerate_api_key(self.owner)
        self.agency.refresh_from_db()
        self.assertNotEqual(old, new_key)
        self.assertEqual(self.agency.api_key, new_key)

    def test_lead_routing_inbox(self):
        customer = Customer.objects.create(
            user=self.owner, agency=self.agency, name='سرنخ', phone='09120000001',
        )
        apply_lead_routing(self.agency, customer)
        customer.refresh_from_db()
        self.assertEqual(customer.team_visibility, TEAM_VISIBILITY_INBOX)

    def test_api_lead_creates_inbox_lead(self):
        customer = create_lead_from_api(
            self.agency, owner_user=self.owner, name='API Lead', phone='09120000002',
        )
        self.assertEqual(customer.team_visibility, TEAM_VISIBILITY_INBOX)

    def test_bad_path_redirects(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get('/workspace/crm/team/undefined/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=sync', resp.url)

    def test_bad_path_redirects_without_trailing_slash(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get('/workspace/crm/team/undefined')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=sync', resp.url)

    def test_team_page_renders_inbox_tab(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get(reverse('workspace:crm_team'), {'tab': 'inbox'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'صندوق سرنخ')

    def test_team_page_renders_command_tab(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get(reverse('workspace:crm_team'), {'tab': 'command'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرکز مدیریت')
        self.assertContains(resp, 'سرنخ بدون تخصیص')

    def test_regenerate_api_json_endpoint(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.post(reverse('workspace:crm_team_api_key_regenerate'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['key'])

    def test_sync_export_requires_manager(self):
        advisor = User.objects.create_user(username='adv1', password='pass12345', phone='09121111111')
        CRMAgencyMember.objects.create(agency=self.agency, user=advisor, role='advisor')
        client = Client()
        client.force_login(advisor)
        resp = client.get(reverse('workspace:crm_sync_export'))
        self.assertEqual(resp.status_code, 403)

    def test_share_property_without_agency_attaches_agency(self):
        advisor = User.objects.create_user(username='adv2', password='pass12345', phone='09122222222')
        CRMAgencyMember.objects.create(agency=self.agency, user=advisor, role='advisor')
        prop = CRMProperty.objects.create(user=self.owner, title='ملک تست')
        self.assertIsNone(prop.agency_id)
        member = CRMAgencyMember.objects.get(agency=self.agency, user=advisor)
        share_property(self.owner, prop, member.pk, share_mode='collaborative')
        prop.refresh_from_db()
        self.assertEqual(prop.agency_id, self.agency.pk)
