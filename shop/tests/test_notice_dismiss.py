from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from shop.models import Announcement

User = get_user_model()


class NoticeDismissTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.announcement = Announcement.objects.create(
            title='تست اطلاعیه',
            content='محتوا',
            is_active=True,
        )

    def test_dismiss_announcement_persists_in_session(self):
        url = reverse('dismiss_notice')
        response = self.client.post(
            url,
            data='{"kind":"announcement","id":%d}' % self.announcement.pk,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        session = self.client.session
        self.assertIn('dismissed_notices', session)
        self.assertTrue(session['dismissed_notices'].get(f'announcement:{self.announcement.pk}'))

        home = self.client.get(reverse('home'))
        self.assertNotContains(home, 'تست اطلاعیه')

    def test_dismiss_referral(self):
        response = self.client.post(
            reverse('dismiss_notice'),
            data='{"kind":"referral"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session['dismissed_notices'].get('referral'))

    def test_logout_clears_dismissed_notices(self):
        User.objects.create_user(
            username='u9133333333',
            phone='09133333333',
            password='ComplexPass123!',
        )
        self.client.login(username='09133333333', password='ComplexPass123!')
        self.client.post(
            reverse('dismiss_notice'),
            data='{"kind":"referral"}',
            content_type='application/json',
        )
        self.assertTrue(self.client.session.get('dismissed_notices', {}).get('referral'))

        self.client.logout()
        self.assertFalse(self.client.session.get('dismissed_notices', {}).get('referral'))
