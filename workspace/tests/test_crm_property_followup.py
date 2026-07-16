from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from workspace.models import CRMProperty, CustomerActivity
from workspace.services.crm import (
    complete_property_follow_up,
    property_follow_up_state,
    schedule_property_follow_up,
)


class CRMPropertyFollowUpTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='propfu', password='pass', phone='09128888888')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان تست',
            phone='09121112222',
            owner_name='مالک تست',
        )

    def test_schedule_and_complete_property_follow_up(self):
        today = timezone.now().date()
        follow_date = today + timedelta(days=3)
        schedule_property_follow_up(self.user, self.prop, follow_date, note='تماس با مالک')
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.next_follow_up, follow_date)
        self.assertEqual(property_follow_up_state(self.prop, today), 'upcoming')
        self.assertTrue(
            CustomerActivity.objects.filter(property=self.prop, activity_type='پیگیری').exists()
        )
        self.assertIsNotNone(complete_property_follow_up(self.user, self.prop))
        self.prop.refresh_from_db()
        self.assertIsNone(self.prop.next_follow_up)

    def test_property_detail_schedule_followup_post(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk})
        follow_date = timezone.now().date() + timedelta(days=1)
        response = self.client.post(url, {
            'action': 'schedule_followup',
            'next_follow_up': follow_date.strftime('%Y-%m-%d'),
            'note': 'پیگیری فردا',
        })
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.next_follow_up, follow_date)
