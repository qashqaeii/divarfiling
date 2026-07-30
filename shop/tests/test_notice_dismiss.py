from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Announcement, UserDismissedNotice

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

    def test_logout_clears_session_dismissed_notices(self):
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

    def test_authenticated_dismiss_survives_logout(self):
        user = User.objects.create_user(
            username='u9144444444',
            phone='09144444444',
            password='ComplexPass123!',
        )
        self.client.login(username='09144444444', password='ComplexPass123!')
        response = self.client.post(
            reverse('dismiss_notice'),
            data='{"kind":"announcement","id":%d}' % self.announcement.pk,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserDismissedNotice.objects.filter(
                user=user,
                kind='announcement',
                notice_id=str(self.announcement.pk),
            ).exists()
        )

        self.client.logout()
        self.client.login(username='09144444444', password='ComplexPass123!')
        home = self.client.get(reverse('home'))
        self.assertNotContains(home, 'تست اطلاعیه')
        workspace = self.client.get(reverse('workspace:home'))
        self.assertNotContains(workspace, 'تست اطلاعیه')


class WorkspaceAnnouncementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='wsannounce',
            phone='09155555555',
            password='pass1234',
        )
        self.announcement = Announcement.objects.create(
            title='اطلاعیه میزکار',
            content='پیام تست برای نمای کلی',
            is_active=True,
        )

    def test_workspace_home_shows_active_announcement(self):
        self.client.login(username='wsannounce', password='pass1234')
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'اطلاعیه میزکار')
        self.assertContains(resp, 'data-notice-kind="announcement"')
        self.assertContains(resp, f'data-notice-id="{self.announcement.pk}"')

    def test_workspace_home_hides_dismissed_announcement(self):
        self.client.login(username='wsannounce', password='pass1234')
        self.client.post(
            reverse('dismiss_notice'),
            data='{"kind":"announcement","id":%d}' % self.announcement.pk,
            content_type='application/json',
        )
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'اطلاعیه میزکار')
