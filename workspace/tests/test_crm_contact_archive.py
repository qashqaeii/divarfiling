"""تست بایگانی مخاطبین CRM."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from workspace.models import CRMAgency, CRMAgencyMember, CRMDeal, CRMProperty, Customer, PropertyContact, Reminder
from workspace.services.crm import filter_contacts, update_customer_status
from workspace.services.crm_contact_archive import (
    archive_contact,
    bulk_archive_contacts,
    bulk_restore_contacts,
    is_contact_archived,
    restore_contact,
)
from workspace.models import CustomerActivity
from workspace.services.crm_matching import _score_customer_for_property, get_customer_matches
from workspace.services.crm_sharing import share_customer

User = get_user_model()


class CRMContactArchiveServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='carch', password='x', phone='09130001001')
        self.viewer = User.objects.create_user(username='cview', password='x', phone='09130001002')
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار تست',
            customer_type='خریدار',
            status='قرارداد',
        )

    def test_archive_preserves_communication_status(self):
        archive_contact(self.user, self.customer)
        self.customer.refresh_from_db()
        self.assertTrue(is_contact_archived(self.customer))
        self.assertEqual(self.customer.status, 'قرارداد')
        self.assertIsNotNone(self.customer.archived_at)

    def test_restore_keeps_status(self):
        archive_contact(self.user, self.customer)
        restore_contact(self.user, self.customer)
        self.customer.refresh_from_db()
        self.assertFalse(is_contact_archived(self.customer))
        self.assertEqual(self.customer.status, 'قرارداد')

    def test_legacy_status_archive_compat(self):
        legacy = Customer.objects.create(
            user=self.user,
            name='قدیمی',
            status='بایگانی',
            archived_at=timezone.now(),
        )
        self.assertTrue(is_contact_archived(legacy))

    def test_legacy_restore_requires_status(self):
        legacy = Customer.objects.create(user=self.user, name='لگسی', status='بایگانی', archived_at=timezone.now())
        with self.assertRaises(ValueError):
            restore_contact(self.user, legacy)
        restore_contact(self.user, legacy, restore_status='جدید')
        legacy.refresh_from_db()
        self.assertEqual(legacy.status, 'جدید')
        self.assertFalse(is_contact_archived(legacy))

    def test_viewer_cannot_archive(self):
        agency = CRMAgency.objects.create(name='آ', owner=self.user)
        CRMAgencyMember.objects.create(agency=agency, user=self.user, role='owner', is_active=True)
        member = CRMAgencyMember.objects.create(agency=agency, user=self.viewer, role='advisor', is_active=True)
        self.customer.agency = agency
        self.customer.save(update_fields=['agency'])
        share_customer(self.user, self.customer, member.pk)
        with self.assertRaises(PermissionError):
            archive_contact(self.viewer, self.customer)

    def test_property_link_preserved(self):
        prop = CRMProperty.objects.create(user=self.user, title='ملک', deal_mode='فروش')
        PropertyContact.objects.create(property=prop, customer=self.customer, role='خریدار')
        archive_contact(self.user, self.customer)
        self.assertEqual(PropertyContact.objects.filter(customer=self.customer).count(), 1)

    def test_deal_preserved(self):
        CRMDeal.objects.create(user=self.user, customer=self.customer, title='معامله')
        archive_contact(self.user, self.customer)
        self.assertEqual(CRMDeal.objects.filter(customer=self.customer).count(), 1)

    def test_open_reminder_not_auto_done(self):
        reminder = Reminder.objects.create(
            user=self.user,
            customer=self.customer,
            title='پیگیری',
            due_at=timezone.now(),
        )
        archive_contact(self.user, self.customer)
        reminder.refresh_from_db()
        self.assertFalse(reminder.is_done)

    def test_matching_excludes_archived(self):
        prop = CRMProperty.objects.create(user=self.user, title='ملک', deal_mode='فروش', property_type='آپارتمان')
        archive_contact(self.user, self.customer)
        self.assertIsNone(_score_customer_for_property(self.customer, prop))

    def test_bulk_partial(self):
        other = Customer.objects.create(user=self.user, name='دوم', status='جدید')
        result = bulk_archive_contacts(self.user, [self.customer.pk, other.pk, 99999])
        self.assertEqual(result['archived'], 2)
        self.assertEqual(result['skipped'], 1)

    def test_bulk_restore_modern_keeps_status_without_restore_status(self):
        archive_contact(self.user, self.customer)
        result = bulk_restore_contacts(self.user, [self.customer.pk])
        self.assertEqual(result, {'restored': 1, 'skipped': 0, 'errors': 0})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, 'قرارداد')
        self.assertFalse(is_contact_archived(self.customer))

    def test_bulk_restore_legacy_requires_restore_status(self):
        legacy = Customer.objects.create(
            user=self.user,
            name='لگسی گروهی',
            status='بایگانی',
            archived_at=timezone.now(),
        )
        result = bulk_restore_contacts(self.user, [legacy.pk])
        self.assertEqual(result['restored'], 0)
        self.assertEqual(result['errors'], 1)
        legacy.refresh_from_db()
        self.assertTrue(is_contact_archived(legacy))

    def test_bulk_restore_mixed_legacy_and_modern(self):
        archive_contact(self.user, self.customer)
        legacy = Customer.objects.create(
            user=self.user,
            name='لگسی مخلوط',
            status='بایگانی',
            archived_at=timezone.now(),
        )
        result = bulk_restore_contacts(
            self.user,
            [self.customer.pk, legacy.pk],
            restore_status='جدید',
        )
        self.assertEqual(result['restored'], 2)
        self.assertEqual(result['errors'], 0)
        self.customer.refresh_from_db()
        legacy.refresh_from_db()
        self.assertEqual(self.customer.status, 'قرارداد')
        self.assertEqual(legacy.status, 'جدید')
        self.assertFalse(is_contact_archived(self.customer))
        self.assertFalse(is_contact_archived(legacy))

    def test_archive_invalid_reactivation_does_not_partially_apply(self):
        acts_before = CustomerActivity.objects.filter(customer=self.customer).count()
        with self.assertRaises(ValueError):
            archive_contact(
                self.user,
                self.customer,
                reactivation_due_jalali='not-a-date',
            )
        self.customer.refresh_from_db()
        self.assertFalse(is_contact_archived(self.customer))
        self.assertEqual(CustomerActivity.objects.filter(customer=self.customer).count(), acts_before)

    def test_get_customer_matches_returns_empty_for_archived(self):
        archive_contact(self.user, self.customer)
        payload = get_customer_matches(self.customer, self.user, divar_enabled=False)
        self.assertFalse(payload['eligible'])
        self.assertEqual(payload['crm_matches'], [])
        self.assertEqual(payload['divar_matches'], [])


class CRMContactArchiveFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cfilt', password='x', phone='09130002001')
        self.active = Customer.objects.create(user=self.user, name='جاری', status='جدید')
        self.archived = Customer.objects.create(
            user=self.user,
            name='بایگانی',
            status='قرارداد',
            archived_at=timezone.now(),
        )

    def test_default_excludes_archived(self):
        ids = list(filter_contacts(self.user, {}).values_list('pk', flat=True))
        self.assertEqual(ids, [self.active.pk])

    def test_archived_scope(self):
        ids = list(filter_contacts(self.user, {'archive_scope': 'archived'}).values_list('pk', flat=True))
        self.assertEqual(ids, [self.archived.pk])

    def test_status_filter_with_archived_scope(self):
        ids = list(
            filter_contacts(self.user, {'archive_scope': 'archived', 'status': 'قرارداد'}).values_list('pk', flat=True)
        )
        self.assertEqual(ids, [self.archived.pk])


class CRMContactArchiveViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cweb', password='x', phone='09130003001')
        self.client = Client()
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(user=self.user, name='وب', status='در حال پیگیری')

    def test_detail_shows_archive_action(self):
        url = reverse('workspace:crm_detail', kwargs={'customer_id': self.customer.pk})
        res = self.client.get(url)
        self.assertContains(res, 'بایگانی')

    def test_archive_api(self):
        url = reverse('workspace:crm_contact_archive', kwargs={'customer_id': self.customer.pk})
        res = self.client.post(url, data=json.dumps({'reason': 'عدم نیاز فعلی'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(is_contact_archived(self.customer))

    def test_legacy_status_update_routes_to_archive(self):
        update_customer_status(self.customer, 'بایگانی', user=self.user)
        self.customer.refresh_from_db()
        self.assertTrue(is_contact_archived(self.customer))

    def test_archived_scope_with_pipeline_request_shows_table(self):
        archive_contact(self.user, self.customer)
        url = reverse('workspace:crm_contacts')
        res = self.client.get(f'{url}?archive_scope=archived&view=pipeline')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'crm-contacts-table-wrap')
        self.assertNotContains(res, 'crm-contacts-pipeline')

    def test_bulk_restore_form_in_archived_tab(self):
        archive_contact(self.user, self.customer)
        url = reverse('workspace:crm_contacts')
        res = self.client.get(f'{url}?archive_scope=archived')
        self.assertContains(res, 'name="restore_status"')
        self.assertContains(res, 'data-for="restore"')

    def test_archived_scope_with_pipeline_request_paginates_table_rows(self):
        """view=pipeline روی تب بایگانی نباید همه مخاطبین را یک‌جا بارگذاری کند."""
        for i in range(30):
            c = Customer.objects.create(user=self.user, name=f'بایگانی {i:02d}', status='جدید')
            archive_contact(self.user, c)
        url = reverse('workspace:crm_contacts')
        res = self.client.get(f'{url}?archive_scope=archived&view=pipeline')
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('crm-contacts-table-wrap', html)
        self.assertNotIn('crm-contacts-pipeline', html)
        self.assertIn('data-has-next="1"', html)
        self.assertEqual(html.count('crm-row-check'), 25)

        partial = self.client.get(f'{url}?archive_scope=archived&view=pipeline&partial=1&page=2')
        self.assertEqual(partial.status_code, 200)
        data = partial.json()
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page'])
        self.assertEqual(data['html'].count('crm-row-check'), 5)
