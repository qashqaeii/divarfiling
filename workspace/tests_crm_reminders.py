"""تست ثبت یادآور CRM با تاریخ شمسی."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from datetime import timedelta

from workspace.forms import CRMReminderForm, ReminderForm
from workspace.models import Customer, Reminder
from workspace.services.jalali_input import format_jalali_datetime, to_persian_digits

User = get_user_model()


class CRMReminderFormTests(TestCase):
    def test_accepts_jalali_datetime_string(self):
        due = format_jalali_datetime(timezone.now() + timedelta(days=1))
        form = CRMReminderForm({'title': 'تماس', 'note': '', 'due_at': due})
        self.assertTrue(form.is_valid(), form.errors)

    def test_accepts_persian_digit_jalali_datetime(self):
        due = to_persian_digits(format_jalali_datetime(timezone.now() + timedelta(days=1)))
        form = ReminderForm({'title': 'تماس', 'note': '', 'due_at': due})
        self.assertTrue(form.is_valid(), form.errors)


class CRMReminderCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121112233',
            phone='09121112233',
            password='testpass123',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            user=self.user,
            name='مخاطب تست',
            phone='09121112233',
            customer_type='خریدار',
        )

    def test_create_reminder_from_crm_list(self):
        due = format_jalali_datetime(timezone.now() + timedelta(days=2))
        response = self.client.post(reverse('workspace:crm_reminders'), {
            'title': 'پیگیری ملک',
            'note': 'تماس بگیر',
            'due_at': due,
            'customer_id': self.customer.id,
        })
        self.assertEqual(response.status_code, 302)
        reminder = Reminder.objects.get(user=self.user, title='پیگیری ملک')
        self.assertEqual(reminder.customer_id, self.customer.id)
        self.assertIsNotNone(reminder.due_at)

    def test_create_reminder_from_contact_detail(self):
        due = format_jalali_datetime(timezone.now() + timedelta(days=1))
        url = reverse('workspace:crm_detail', kwargs={'customer_id': self.customer.id})
        response = self.client.post(url, {
            'action': 'add_reminder',
            'title': 'یادآور مخاطب',
            'note': '',
            'due_at': due,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Reminder.objects.filter(user=self.user, customer=self.customer, title='یادآور مخاطب').exists()
        )
