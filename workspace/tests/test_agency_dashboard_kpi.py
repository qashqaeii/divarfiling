from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMAgency, CRMAgencyMember, Customer
from workspace.services.agency_hub import build_dashboard_context
from workspace.tests.agency_test_utils import ensure_agency_subscription


User = get_user_model()


class AgencyDashboardKpiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='ag_owner', phone='09127770000', password='x')
        self.agency = CRMAgency.objects.create(name='آژانس تست', owner=self.owner)
        ensure_agency_subscription(self.owner, self.agency)
        CRMAgencyMember.objects.create(
            agency=self.agency,
            user=self.owner,
            role='owner',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.advisor = User.objects.create_user(username='ag_adv', phone='09127770001', password='x')
        CRMAgencyMember.objects.create(
            agency=self.agency,
            user=self.advisor,
            role='advisor',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        Customer.objects.create(
            user=self.advisor, agency=self.agency, name='مخاطب آژانس', phone='09127770002',
        )

    def test_owner_kpi_enrichment(self):
        ctx = build_dashboard_context(self.owner, days=30)
        summary = ctx.get('summary') or {}
        self.assertIn('hero_meta', summary)
        self.assertIn('mix_segments', summary)
        self.assertGreaterEqual(summary.get('active_advisors', 0), 1)
        self.assertGreaterEqual(summary.get('contacts_new', 0), 1)
        self.assertIn('advisors', ctx.get('kpi_links') or {})
        self.assertIn('contacts_meta', summary)
