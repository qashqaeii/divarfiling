"""خروجی آژانس — الزام ExportSecurity."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMAgency, CRMAgencyMember
from workspace.services.crm_agency import create_agency

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
@patch('workspace.mixins.has_active_bot_license', return_value=True)
class AgencyExportSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='ag_own', password='x', phone='09120001001')
        self.agency = create_agency(self.owner, 'آژانس امن')
        self.advisor = User.objects.create_user(username='ag_adv', password='x', phone='09120001002')
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
        )

    @patch('workspace.export_security.is_export_authorized', return_value=False)
    def test_advisor_export_requires_verification(self, _lic, _auth):
        member = CRMAgencyMember.objects.get(agency=self.agency, user=self.advisor)
        url = reverse('workspace:agency_advisor_export', kwargs={'member_id': member.pk})
        self.client.force_login(self.owner)
        resp = self.client.get(url, {'type': 'contacts', 'format': 'csv'})
        self.assertEqual(resp.status_code, 403)

    @patch('workspace.export_security.is_export_authorized', return_value=True)
    def test_advisor_export_ok_when_authorized(self, _lic, _auth):
        member = CRMAgencyMember.objects.get(agency=self.agency, user=self.advisor)
        url = reverse('workspace:agency_advisor_export', kwargs={'member_id': member.pk})
        self.client.force_login(self.owner)
        resp = self.client.get(url, {'type': 'contacts', 'format': 'csv'})
        self.assertIn(resp.status_code, (200, 302))
