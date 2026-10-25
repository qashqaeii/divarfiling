"""تمدید اجاره — تاریخ جلالی و یادآور."""
import json

import jdatetime
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty, Reminder
from workspace.services.crm_property_archive import archive_property
from workspace.services.crm_property_rental_renewal import (
    RENEWAL_REMINDER_KIND,
    format_renewal_reminder_note,
    renewal_followup_date,
    sanitize_reminder_note_for_display,
    subtract_one_jalali_month,
    suggest_contract_end_one_year_after,
    upsert_renewal_schedule,
)

User = get_user_model()


class JalaliMonthSubtractTests(TestCase):
    def test_example_1406_08_03(self):
        end = jdatetime.date(1406, 8, 3).togregorian()
        follow = subtract_one_jalali_month(end)
        j = jdatetime.date.fromgregorian(date=follow)
        self.assertEqual((j.year, j.month, j.day), (1406, 7, 3))

    def test_31_day_month_clamp(self):
        end = jdatetime.date(1405, 7, 30).togregorian()
        follow = subtract_one_jalali_month(end)
        j = jdatetime.date.fromgregorian(date=follow)
        self.assertEqual((j.year, j.month, j.day), (1405, 6, 30))

    def test_esfand_leap_clamp(self):
        end = jdatetime.date(1403, 12, 30).togregorian()
        follow = subtract_one_jalali_month(end)
        j = jdatetime.date.fromgregorian(date=follow)
        self.assertEqual(j.month, 11)
        self.assertLessEqual(j.day, 30)

    def test_suggest_contract_end_is_one_jalali_year_ahead(self):
        ref = jdatetime.date(1405, 8, 3).togregorian()
        suggested = suggest_contract_end_one_year_after(ref)
        j = jdatetime.date.fromgregorian(date=suggested)
        self.assertEqual((j.year, j.month, j.day), (1406, 8, 3))


class RentalRenewalReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rent', password='x', phone='09120005001')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='اجاره تست',
            deal_mode='رهن و اجاره',
        )
        archive_property(self.user, self.prop)

    def test_upsert_links_property_and_kind(self):
        end = jdatetime.date(1406, 8, 3).togregorian()
        reminder = upsert_renewal_schedule(self.user, self.prop, end, create_reminder=True)
        self.assertIsNotNone(reminder)
        self.assertEqual(reminder.property_id, self.prop.pk)
        self.assertEqual(reminder.reminder_kind, RENEWAL_REMINDER_KIND)
        follow = renewal_followup_date(end)
        self.assertEqual(reminder.due_at.date(), follow)
        self.assertEqual(reminder.note, format_renewal_reminder_note(end, follow))
        self.assertNotIn('property_id', reminder.note)

    def test_sanitize_legacy_property_id_in_note(self):
        raw = 'پایان قرارداد: 1406/08/03 · پیگیری تمدید: 1406/07/03 · property_id=40'
        self.assertNotIn('property_id', sanitize_reminder_note_for_display(raw))

    def test_no_duplicate_active_reminder(self):
        end = jdatetime.date(1406, 8, 3).togregorian()
        upsert_renewal_schedule(self.user, self.prop, end, create_reminder=True)
        upsert_renewal_schedule(self.user, self.prop, end, create_reminder=True)
        self.assertEqual(
            Reminder.objects.filter(
                user=self.user, property=self.prop, reminder_kind=RENEWAL_REMINDER_KIND, is_done=False,
            ).count(),
            1,
        )


class PropertyDetailArchiveUxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='det', password='x', phone='09120005002')
        self.client = Client()
        self.client.force_login(self.user)
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='نمایش',
            deal_mode='فروش',
            transaction_status='فعال',
            publish_status='منتشرشده',
            archived_at=timezone.now(),
        )

    def test_detail_shows_archived_primary_status(self):
        res = self.client.get(reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk}))
        self.assertContains(res, 'بایگانی‌شده')
        self.assertContains(res, 'بازگردانی از بایگانی')
        self.assertContains(res, 'معامله: فعال')

    def test_archive_invalid_contract_date_does_not_archive(self):
        rental = CRMProperty.objects.create(
            user=self.user, title='ر۲', deal_mode='اجاره', transaction_status='فعال',
        )
        url = reverse('workspace:crm_property_archive', kwargs={'property_id': rental.pk})
        res = self.client.post(
            url,
            data=json.dumps({'contract_end_jalali': 'not-a-date'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        rental.refresh_from_db()
        self.assertIsNone(rental.archived_at)

    def test_archive_endpoint_preserves_transaction_status(self):
        rental = CRMProperty.objects.create(
            user=self.user, title='ر', deal_mode='اجاره', transaction_status='در مذاکره',
        )
        url = reverse('workspace:crm_property_archive', kwargs={'property_id': rental.pk})
        res = self.client.post(
            url,
            data=json.dumps({'skip_contract_end': True}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        rental.refresh_from_db()
        self.assertEqual(rental.transaction_status, 'در مذاکره')
        self.assertIsNotNone(rental.archived_at)
