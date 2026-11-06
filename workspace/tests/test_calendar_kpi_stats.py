from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
import jdatetime

from workspace.models import Customer, Reminder
from workspace.services.crm_calendar import get_calendar_month


User = get_user_model()


class CalendarKpiStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kpi_cal', password='x')
        self.customer = Customer.objects.create(
            user=self.user, name='مشتری تقویم', phone='09126660000', status='جدید',
        )
        self.today = timezone.localdate()
        self.today_j = jdatetime.date.fromgregorian(date=self.today)

    def test_empty_month_kpis(self):
        cal = get_calendar_month(self.user, self.today_j.year, self.today_j.month)
        self.assertEqual(cal['kpis']['month_total'], 0)
        self.assertEqual(cal['kpis']['today'], 0)
        self.assertEqual(cal['kpis']['overdue'], 0)
        self.assertEqual(cal['kpis']['upcoming_followups'], 0)
        self.assertEqual(cal['kpis']['mix_segments'], [])

    def test_advisor_actionable_kpis(self):
        self.customer.next_follow_up = self.today
        self.customer.save(update_fields=['next_follow_up'])

        Customer.objects.create(
            user=self.user, name='معوق', phone='09126660001', status='در حال پیگیری',
            next_follow_up=self.today - timedelta(days=2),
        )
        Reminder.objects.create(
            user=self.user,
            title='یادآور آینده',
            due_at=timezone.now() + timedelta(days=3),
            is_done=False,
        )

        cal = get_calendar_month(self.user, self.today_j.year, self.today_j.month)
        self.assertGreaterEqual(cal['kpis']['month_total'], 2)
        self.assertGreaterEqual(cal['kpis']['today'], 1)
        self.assertGreaterEqual(cal['kpis']['overdue'], 1)
        self.assertGreaterEqual(cal['kpis']['upcoming_followups'], 1)
        self.assertTrue(cal['kpis']['mix_segments'])
        self.assertTrue(cal['kpis']['hero_meta'])
