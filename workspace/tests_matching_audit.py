"""تست ابزار ممیزی read-only."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching_audit import audit_customer_matches

User = get_user_model()


class MatchingAuditSampleCapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09127770001', phone='09127770001', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09127770002',
            customer_type='خریدار',
            budget_min=10_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
        )
        for i in range(40):
            CRMProperty.objects.create(
                user=self.user,
                title=f'رد {i}',
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=15_000_000_000,
                neighborhood='نیاوران',
                city='تهران',
                area=100,
            )

    def test_sample_cap_limits_rows_examined_including_rejects(self):
        report = audit_customer_matches(
            self.buyer, self.user, divar_enabled=False, crm_sample_cap=10,
        )
        crm = report['crm']
        self.assertEqual(crm['rows_examined'], 10)
        self.assertGreater(crm['sql_candidates_total'], 10)
        self.assertFalse(crm['sample_complete'])
        self.assertFalse(report['audit_meta']['touches_match_index_cache'])
