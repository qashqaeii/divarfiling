"""اعلان dismissed دوباره ایجاد نشود."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer, PropertyMatchAlert
from workspace.services.crm_match_notifications import filter_new_matches, record_match_alerts

User = get_user_model()


class MatchAlertDismissedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128887777', phone='09128887777', password='x')
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار اعلان',
            phone='09128887777',
            customer_type='خریدار',
        )

    def test_dismissed_match_not_rediscovered(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='فایل اعلان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=5_000_000_000,
        )
        PropertyMatchAlert.objects.create(
            user=self.user,
            customer=self.customer,
            match_key=f'crm:{prop.pk}',
            source='crm',
            crm_property_id=prop.pk,
            status=PropertyMatchAlert.STATUS_DISMISSED,
            score=70,
        )
        fresh = filter_new_matches(
            self.customer,
            self.user,
            [{'source': 'crm', 'property_id': prop.pk, 'score': 80}],
        )
        self.assertEqual(fresh, [])

    def test_record_skips_dismissed(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='فایل دوم',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=6_000_000_000,
        )
        key = f'crm:{prop.pk}'
        created = record_match_alerts(
            self.user,
            self.customer,
            [{'source': 'crm', 'property_id': prop.pk, 'score': 60, 'match_key': key}],
        )
        PropertyMatchAlert.objects.filter(
            user=self.user,
            customer=self.customer,
            match_key=key,
        ).update(status=PropertyMatchAlert.STATUS_DISMISSED)
        created2 = record_match_alerts(
            self.user,
            self.customer,
            [{'source': 'crm', 'property_id': prop.pk, 'score': 65, 'match_key': key}],
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(len(created2), 0)
