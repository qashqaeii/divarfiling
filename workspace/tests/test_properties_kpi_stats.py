from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMProperty
from workspace.services.crm import build_properties_kpi_stats, filter_properties, properties_qs
from workspace.services.crm_property_archive import archived_properties_q


User = get_user_model()


class PropertiesKpiStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kpi_props', password='x')
        self.today = timezone.now().date()

    def _create(self, **kwargs):
        defaults = {
            'user': self.user,
            'title': 'ملک',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
        }
        defaults.update(kwargs)
        return CRMProperty.objects.create(**defaults)

    def test_empty(self):
        qs = properties_qs(self.user).exclude(archived_properties_q())
        stats = build_properties_kpi_stats(qs, today=self.today)
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['needs_action'], 0)
        self.assertEqual(stats['no_followup'], 0)
        self.assertEqual(stats['draft'], 0)
        self.assertEqual(stats['mix_segments'], [])

    def test_advisor_actionable_kpis(self):
        self._create(title='بدون تاریخ', next_follow_up=None, publish_status='پیش‌نویس')
        self._create(
            title='امروز',
            next_follow_up=self.today,
            publish_status='منتشرشده',
        )
        self._create(
            title='معوق',
            next_follow_up=self.today - timedelta(days=2),
            publish_status='منتشرشده',
            deal_mode='رهن و اجاره',
        )
        self._create(
            title='قرارداد بدون تاریخ',
            transaction_status='قرارداد',
            next_follow_up=None,
            publish_status='پیش‌نویس',
        )

        qs = properties_qs(self.user).exclude(archived_properties_q())
        stats = build_properties_kpi_stats(qs, today=self.today)

        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['needs_action'], 2)
        self.assertEqual(stats['overdue'], 1)
        self.assertEqual(stats['due_today'], 1)
        self.assertEqual(stats['no_followup'], 1)  # فقط فعال/مذاکره
        self.assertEqual(stats['draft'], 2)
        self.assertIn('معوق', stats['needs_action_meta'])

    def test_action_and_unscheduled_filters(self):
        self._create(title='بدون تاریخ', next_follow_up=None)
        self._create(
            title='معوق',
            next_follow_up=self.today - timedelta(days=1),
        )
        self._create(
            title='امروز',
            next_follow_up=self.today,
        )
        self._create(
            title='قرارداد بدون تاریخ',
            transaction_status='قرارداد',
            next_follow_up=None,
        )

        self.assertEqual(filter_properties(self.user, {'due': 'action'}).count(), 2)
        self.assertEqual(filter_properties(self.user, {'due': 'unscheduled'}).count(), 1)
