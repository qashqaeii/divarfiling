"""CRM sync — نگاشت customer_id در معاملات."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMDeal, Customer
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
