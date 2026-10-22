"""پیام راهنما و diagnostics برای نتیجه خالی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Customer
from workspace.services.crm_matching import get_customer_matches

User = get_user_model()


class MatchingDiagnosticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff_match', password='x', phone='09120009988', is_staff=True,
        )
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار خالی',
            phone='09120009988',
            customer_type='خریدار',
            status='در حال پیگیری',
        )

    def test_empty_matches_include_guidance_message(self):
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        self.assertEqual(data['total_count'], 0)
        self.assertTrue(data.get('message'))
        self.assertIn('پروفایل', data['message'])

    def test_staff_gets_diagnostics_on_empty(self):
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        self.assertIn('diagnostics', data)
        self.assertIn('crm_sql_candidates', data['diagnostics'])
