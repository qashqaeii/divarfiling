"""تست داشبورد TV آژانس."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMAgencyAnnouncement, CRMAgencyMember, CRMDeal, Customer
from workspace.services.crm_agency import create_agency
from workspace.services.crm_agency_announcements import create_announcement
from workspace.services.crm_agency_tv import get_tv_dashboard_payload

User = get_user_model()


class CRMAgencyTVTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_tv', password='pass12345')
        self.advisor = User.objects.create_user(username='advisor_tv', phone='09123333333', password='pass12345')
        self.agency = create_agency(self.owner, 'آژانس TV')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.advisor, role='advisor')

    def test_tv_page_requires_membership(self):
        outsider = User.objects.create_user(username='outsider_tv', phone='09124444444', password='pass12345')
        client = Client()
        client.force_login(outsider)
        resp = client.get(reverse('workspace:crm_team_tv'))
        self.assertEqual(resp.status_code, 302)

    def test_tv_page_loads_for_manager(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get(reverse('workspace:crm_team_tv'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'crm-tv-app')
        self.assertContains(resp, 'آژانس TV')

    def test_tv_api_returns_sanitized_payload(self):
        customer = Customer.objects.create(
            agency=self.agency,
            user=self.owner,
            name='مشتری محرمانه',
            phone='09120000000',
            source='دیوار',
        )
        CRMDeal.objects.create(
            agency=self.agency,
            user=self.owner,
            customer=customer,
            title='معامله تست',
            stage='مذاکره',
        )
        create_announcement(self.owner, title='اطلاعیه TV', body='متن عمومی')

        client = Client()
        client.force_login(self.owner)
        resp = client.get(reverse('workspace:api_crm_team_tv'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['agency_name'], 'آژانس TV')
        self.assertIn('kpis', data)
        self.assertIn('leaderboard', data)
        raw = json.dumps(data, ensure_ascii=False)
        self.assertNotIn('09120000000', raw)
        self.assertNotIn('مشتری محرمانه', raw)

    def test_advisor_gets_reduced_tv_view(self):
        payload = get_tv_dashboard_payload(self.advisor)
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['team_view'])
        self.assertIn('kpis', payload)
        self.assertEqual(payload['leads']['unassigned'], 0)

    def test_tv_payload_includes_announcements(self):
        create_announcement(
            self.owner,
            title='جلسه صبح',
            body='حضور اجباری',
            importance=CRMAgencyAnnouncement.IMPORTANCE_HIGH,
        )
        payload = get_tv_dashboard_payload(self.advisor)
        self.assertEqual(len(payload['announcements']), 1)
        self.assertEqual(payload['announcements'][0]['title'], 'جلسه صبح')

    def test_tv_api_denied_without_agency(self):
        outsider = User.objects.create_user(username='no_agency_tv', phone='09125555555', password='pass12345')
        client = Client()
        client.force_login(outsider)
        resp = client.get(reverse('workspace:api_crm_team_tv'))
        self.assertEqual(resp.status_code, 404)
