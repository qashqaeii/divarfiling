"""CRM sync — نگاشت customer_id در معاملات."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMDeal, CRMProperty, Customer
from workspace.services.crm_sync import export_crm_payload, import_crm_payload

User = get_user_model()


class CRMSyncImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sync_u', password='x')

    def test_deal_uses_mapped_customer_not_wrong_pk(self):
        other = User.objects.create_user(username='sync_other', password='x', phone='09128887766')
        wrong = Customer.objects.create(
            user=other, name='دیگری', phone='09129990000', customer_type='سرنخ', status='جدید',
        )
        payload = {
            'contacts': [{'id': 99999, 'name': 'جدید', 'phone': '09121112233'}],
            'properties': [],
            'deals': [{'title': 'معامله الف', 'customer_id': 99999, 'stage': 'سرنخ'}],
        }
        stats = import_crm_payload(self.user, payload, merge=False, dry_run=False)
        self.assertEqual(stats['contacts'], 1)
        self.assertEqual(stats['deals'], 1)
        deal = CRMDeal.objects.get(user=self.user, title='معامله الف')
        self.assertNotEqual(deal.customer_id, wrong.pk)
        customer = Customer.objects.get(user=self.user, phone='09121112233')
        self.assertEqual(deal.customer_id, customer.pk)

    def test_property_reimport_skips_duplicate(self):
        payload = {
            'contacts': [],
            'properties': [{
                'id': 501,
                'title': 'ملک الف',
                'token': 'tok-501',
                'city': 'تهران',
            }],
            'deals': [],
        }
        s1 = import_crm_payload(self.user, payload, merge=False, dry_run=False)
        s2 = import_crm_payload(self.user, payload, merge=False, dry_run=False)
        self.assertEqual(s1['properties'], 1)
        self.assertEqual(s2['properties'], 0)
        self.assertEqual(s2['skipped'], 1)

    def test_dry_run_does_not_persist(self):
        before = Customer.objects.filter(user=self.user).count()
        payload = {
            'contacts': [{'id': 1, 'name': 'Dry', 'phone': '09121110000'}],
            'properties': [],
            'deals': [],
        }
        stats = import_crm_payload(self.user, payload, dry_run=True)
        self.assertEqual(stats['contacts'], 1)
        self.assertEqual(Customer.objects.filter(user=self.user).count(), before)

    def test_deal_with_new_contact_in_dry_run(self):
        payload = {
            'contacts': [{'id': 900, 'name': 'خریدار', 'phone': '09122220000'}],
            'properties': [],
            'deals': [{'title': 'معامله جدید', 'customer_id': 900, 'stage': 'سرنخ'}],
        }
        stats = import_crm_payload(self.user, payload, dry_run=True)
        self.assertEqual(stats['contacts'], 1)
        self.assertEqual(stats['deals'], 1)

    def test_deal_reimport_skips_duplicate(self):
        c = Customer.objects.create(
            user=self.user, name='خریدار', phone='09124445555',
            customer_type='سرنخ', status='جدید',
        )
        payload = {
            'contacts': [{'id': 700, 'name': 'خریدار', 'phone': '09124445555'}],
            'properties': [],
            'deals': [{
                'title': 'معامله ثابت',
                'customer_id': 700,
                'listing_token': 'lt-1',
                'stage': 'سرنخ',
            }],
        }
        s1 = import_crm_payload(self.user, payload, merge=False, dry_run=False)
        s2 = import_crm_payload(self.user, payload, merge=False, dry_run=False)
        self.assertEqual(s1['deals'], 1)
        self.assertEqual(s2['deals'], 0)
        self.assertEqual(CRMDeal.objects.filter(user=self.user, title='معامله ثابت').count(), 1)
        deal = CRMDeal.objects.get(user=self.user, title='معامله ثابت')
        self.assertEqual(deal.customer_id, c.pk)

    def test_triple_import_same_package_no_growth(self):
        payload = {
            'contacts': [{'id': 1, 'name': 'الف', 'phone': '09120001234'}],
            'properties': [{'id': 2, 'title': 'ملک', 'token': 't-2', 'city': 'اصفهان'}],
            'deals': [{'title': 'د', 'customer_id': 1, 'listing_token': 't-2', 'stage': 'سرنخ'}],
        }
        for _ in range(3):
            import_crm_payload(self.user, payload, merge=False, dry_run=False)
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 1)
        self.assertEqual(CRMDeal.objects.filter(user=self.user).count(), 1)

    def test_export_import_idempotent_contacts(self):
        Customer.objects.create(
            user=self.user, name='تکرار', phone='09123334444',
            customer_type='سرنخ', status='جدید',
        )
        payload = export_crm_payload(self.user)
        before = Customer.objects.filter(user=self.user).count()
        stats = import_crm_payload(self.user, payload, merge=False, dry_run=False)
        after = Customer.objects.filter(user=self.user).count()
        self.assertEqual(after, before)
        self.assertGreater(stats['skipped'], 0)
