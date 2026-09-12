"""تست سریع دسترسی اشتراک فایل با هم‌تیمی — بدون رندر کامل صفحه."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMAgencyMember, CRMProperty
from workspace.services.agency_entitlement import can_share_team_resources
from workspace.services.crm_agency import create_agency
from workspace.services.crm_sharing import share_property
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class CRMPropertyTeamShareVisibilityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='owner-share', password='pass12345', phone='09120000001',
        )
        self.advisor = User.objects.create_user(
            username='adv-share', password='pass12345', phone='09120000002',
        )
        self.solo = User.objects.create_user(
            username='solo-share', password='pass12345', phone='09120000003',
        )
        self.agency = create_agency(self.owner, 'آژانس اشتراک')
        ensure_agency_subscription(self.owner, self.agency)
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
        )
        self.owner_prop = CRMProperty.objects.create(
            user=self.owner, title='ملک مالک', agency=self.agency,
        )

    def test_owner_with_subscription_can_share_team_resources(self):
        self.assertTrue(can_share_team_resources(self.owner))

    def test_solo_user_cannot_share_team_resources(self):
        self.assertFalse(can_share_team_resources(self.solo))

    def test_advisor_without_seat_cannot_share_team_resources(self):
        self.assertFalse(can_share_team_resources(self.advisor))

    def test_share_api_rejects_member_without_entitlement(self):
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.solo, role='advisor', is_active=True,
        )
        solo_in_agency_prop = CRMProperty.objects.create(
            user=self.solo, title='ملک عضو بدون لایسنس', agency=self.agency,
        )
        self.client.force_login(self.solo)
        resp = self.client.post(
            reverse('workspace:crm_property_share', kwargs={'property_id': solo_in_agency_prop.pk}),
            {'member_id': self.advisor_member.pk, 'share_mode': 'collaborative'},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()['ok'])

    def test_share_service_requires_entitlement(self):
        advisor_prop = CRMProperty.objects.create(
            user=self.advisor, title='ملک مشاور', agency=self.agency,
        )
        with self.assertRaisesMessage(ValueError, 'لایسنس'):
            share_property(self.advisor, advisor_prop, self.advisor_member.pk)

    def test_owner_can_share_via_api(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('workspace:crm_property_share', kwargs={'property_id': self.owner_prop.pk}),
            {'member_id': self.advisor_member.pk, 'share_mode': 'collaborative'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
