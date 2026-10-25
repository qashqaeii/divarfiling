"""تست به‌روزرسانی مخاطب با فیلدهای مالی پویا."""
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMAgency, CRMAgencyMember, Customer
from workspace.services.crm_contact_archive import archive_contact, is_contact_archived
from workspace.services.crm_sharing import share_customer

User = get_user_model()


class ContactUpdateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09125556666', password='test')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='متقاضی اجاره',
            phone='09125556666',
            customer_type='متقاضی اجاره',
            status='جدید',
        )

    def test_patch_rent_fields(self):
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {
                'deposit_min': 200_000_000,
                'deposit_max': 500_000_000,
                'rent_min': 15_000_000,
                'rent_max': 25_000_000,
                'areas': 'ونک، نیاوران',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['deposit_min'], 200_000_000)
        self.assertEqual(data['rent_max'], 25_000_000)
        self.assertEqual(data['areas'], 'ونک، نیاوران')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.deposit_min, 200_000_000)
        self.assertEqual(self.customer.rent_max, 25_000_000)

    def test_patch_budget_fields(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09127778888',
            customer_type='خریدار',
        )
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{buyer.pk}',
            {
                'budget_min': 5_000_000_000,
                'budget_max': 8_000_000_000,
                'property_type': 'آپارتمان',
                'min_area': 90,
                'max_area': 130,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['budget_min'], 5_000_000_000)
        self.assertEqual(data['property_type'], 'آپارتمان')
        self.assertEqual(data['min_area'], 90)

    def test_patch_optional_identity_and_lease_deadline(self):
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {
                'email': 'rent@example.com',
                'city': 'تهران',
                'district': 'ونک',
                'job': 'مهندس',
                'company_name': 'شرکت آریا',
                'national_id': '0012345678',
                'lease_deadline': '۱۴۰۵/۰۴/۲۷',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['email'], 'rent@example.com')
        self.assertEqual(data['job'], 'مهندس')
        self.assertEqual(data['company_name'], 'شرکت آریا')
        self.assertEqual(data['national_id'], '0012345678')
        self.assertEqual(data['lease_deadline'], '2026-07-18')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.job, 'مهندس')
        self.assertEqual(str(self.customer.lease_deadline), '2026-07-18')

    def test_clear_lease_deadline(self):
        from datetime import date
        self.customer.lease_deadline = date(2026, 7, 18)
        self.customer.save(update_fields=['lease_deadline'])
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {'lease_deadline': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['data']['lease_deadline'])
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.lease_deadline)


class ContactPatchPermissionTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='09121110001', password='test', phone='09121110001')
        self.viewer = User.objects.create_user(username='09121110002', password='test', phone='09121110002')
        agency = CRMAgency.objects.create(name='آژانس تست', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner', is_active=True)
        member = CRMAgencyMember.objects.create(agency=agency, user=self.viewer, role='advisor', is_active=True)
        self.customer = Customer.objects.create(
            user=self.owner,
            agency=agency,
            name='مشترک',
            phone='09129998877',
            customer_type='خریدار',
            status='جدید',
        )
        share_customer(self.owner, self.customer, member.pk)
        token = RefreshToken.for_user(self.viewer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.url = f'/api/mobile/v1/crm/contacts/{self.customer.pk}'

    def _assert_forbidden(self, payload):
        resp = self.client.patch(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['code'], 'FORBIDDEN')

    def test_non_owner_cannot_patch_city(self):
        self._assert_forbidden({'city': 'تهران'})

    def test_non_owner_cannot_patch_phone_alt(self):
        self._assert_forbidden({'phone_alt': '09123334444'})

    def test_non_owner_cannot_patch_budget_max(self):
        self._assert_forbidden({'budget_max': 9_000_000_000})

    def test_non_owner_cannot_patch_matching_tolerance(self):
        self._assert_forbidden({'matching_tolerance_percent': 15})

    def test_non_owner_cannot_patch_social_links(self):
        self._assert_forbidden({'social_links': {'telegram': '@x'}})


class ContactArchivePatchApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445555', password='test', phone='09124445555')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='بایگانی API',
            phone='09124445555',
            customer_type='خریدار',
            status='در حال پیگیری',
        )
        self.url = f'/api/mobile/v1/crm/contacts/{self.customer.pk}'

    def test_is_archived_true_without_status(self):
        resp = self.client.patch(self.url, {'is_archived': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(is_contact_archived(self.customer))
        self.assertEqual(self.customer.status, 'در حال پیگیری')

    def test_patch_fields_with_archive_preserved(self):
        resp = self.client.patch(
            self.url,
            {'city': 'اصفهان', 'is_archived': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.city, 'اصفهان')
        self.assertTrue(is_contact_archived(self.customer))

    def test_restore_legacy_with_restore_status(self):
        self.customer.status = 'بایگانی'
        self.customer.archived_at = timezone.now()
        self.customer.save(update_fields=['status', 'archived_at'])
        resp = self.client.patch(
            self.url,
            {'is_archived': False, 'restore_status': 'جدید'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertFalse(is_contact_archived(self.customer))
        self.assertEqual(self.customer.status, 'جدید')

    def test_conflicting_archive_restore_rejected(self):
        archive_contact(self.user, self.customer)
        resp = self.client.patch(
            self.url,
            {'is_archived': False, 'status': 'بایگانی'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_status_change_on_archived_without_restore_rejected(self):
        archive_contact(self.user, self.customer)
        resp = self.client.patch(self.url, {'status': 'قرارداد'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_patch_empty_body_does_not_update_timestamp(self):
        before = self.customer.updated_at
        resp = self.client.patch(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.updated_at, before)

    def test_patch_null_fields_only_does_not_update_timestamp(self):
        before = self.customer.updated_at
        resp = self.client.patch(
            self.url,
            {'full_name': None, 'city': None, 'is_archived': None},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.updated_at, before)
