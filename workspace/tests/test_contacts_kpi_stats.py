from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import Customer
from workspace.services.crm import build_contacts_kpi_stats, customers_qs, filter_contacts
from workspace.services.crm_contact_archive import archived_contacts_q


User = get_user_model()


class ContactsKpiStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kpi_contacts', password='x')
        self.today = timezone.now().date()

    def _create(self, **kwargs):
        defaults = {
            'user': self.user,
            'name': 'مخاطب',
            'phone': f'0912{Customer.objects.count():07d}',
            'status': 'جدید',
            'priority': 'متوسط',
        }
        defaults.update(kwargs)
        return Customer.objects.create(**defaults)

    def test_empty_stats(self):
        qs = customers_qs(self.user).exclude(archived_contacts_q())
        stats = build_contacts_kpi_stats(qs, today=self.today)
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['needs_action'], 0)
        self.assertEqual(stats['no_followup'], 0)
        self.assertEqual(stats['high_priority'], 0)
        self.assertEqual(stats['mix_segments'], [])

    def test_advisor_actionable_kpis(self):
        self._create(name='جدید بدون تاریخ', status='جدید', next_follow_up=None)
        self._create(
            name='پیگیری امروز',
            status='در حال پیگیری',
            next_follow_up=self.today,
        )
        self._create(
            name='معوق',
            status='در حال پیگیری',
            next_follow_up=self.today - timedelta(days=2),
            priority='بالا',
        )
        self._create(name='قرارداد', status='قرارداد', priority='بالا')

        qs = customers_qs(self.user).exclude(archived_contacts_q())
        stats = build_contacts_kpi_stats(qs, today=self.today)

        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['needs_action'], 2)  # today + overdue
        self.assertEqual(stats['overdue'], 1)
        self.assertEqual(stats['due_today'], 1)
        self.assertEqual(stats['no_followup'], 1)
        self.assertEqual(stats['high_priority'], 2)
        self.assertIn('معوق', stats['needs_action_meta'])
        self.assertIn('امروز', stats['needs_action_meta'])

    def test_action_and_unscheduled_filters(self):
        self._create(name='بدون تاریخ', status='جدید', next_follow_up=None)
        self._create(
            name='معوق',
            status='در حال پیگیری',
            next_follow_up=self.today - timedelta(days=1),
        )
        self._create(
            name='امروز',
            status='در حال پیگیری',
            next_follow_up=self.today,
        )
        self._create(name='قرارداد بدون تاریخ', status='قرارداد', next_follow_up=None)

        action_ids = set(filter_contacts(self.user, {'due': 'action'}).values_list('id', flat=True))
        unscheduled_ids = set(
            filter_contacts(self.user, {'due': 'unscheduled'}).values_list('id', flat=True)
        )
        self.assertEqual(len(action_ids), 2)
        self.assertEqual(len(unscheduled_ids), 1)
