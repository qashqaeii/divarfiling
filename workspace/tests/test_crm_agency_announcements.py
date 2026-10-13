"""تست تابلو اطلاعیه‌های آژانس."""
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from workspace.models import CRMAgencyAnnouncement, CRMAgencyMember, CRMAgencyPanelNotification
from workspace.services.crm_agency import create_agency
from workspace.services.crm_agency_announcements import (
    announcements_unread_for_hub,
    announcements_with_team_unread_count,
    create_announcement,
    list_announcements,
    mark_announcement_read,
    unread_announcement_count,
)

User = get_user_model()


class CRMAgencyAnnouncementsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_ann', password='pass12345')
        self.manager = User.objects.create_user(username='mgr_ann', phone='09122222222', password='pass12345')
        self.advisor = User.objects.create_user(username='advisor_ann', phone='09121111111', password='pass12345')
        self.agency = create_agency(self.owner, 'آژانس اطلاعیه')
        self.manager_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.manager, role='manager',
        )
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor',
        )

    def test_create_announcement_manager_only(self):
        ann = create_announcement(
            self.owner,
            title='جلسه فروش',
            body='فردا ساعت ۱۰',
            importance=CRMAgencyAnnouncement.IMPORTANCE_HIGH,
            is_pinned=True,
        )
        self.assertEqual(ann.title, 'جلسه فروش')
        self.assertTrue(ann.is_pinned)
        self.assertEqual(unread_announcement_count(self.advisor), 1)
        self.assertEqual(unread_announcement_count(self.owner), 0)
        self.assertEqual(announcements_with_team_unread_count(self.owner), 1)
        self.assertEqual(announcements_unread_for_hub(self.owner), 1)
        self.assertEqual(announcements_unread_for_hub(self.advisor), 1)

    def test_advisor_cannot_create(self):
        client = Client()
        client.force_login(self.advisor)
        resp = client.post(
            reverse('workspace:api_crm_team_announcements'),
            data=json.dumps({'title': 'نباید برود', 'body': 'متن'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_role_targeting(self):
        create_announcement(
            self.owner,
            title='فقط مشاوران',
            body='متن',
            target_roles=['advisor'],
        )
        items, total = list_announcements(self.advisor)
        self.assertEqual(total, 1)
        items_mgr, total_mgr = list_announcements(self.manager)
        self.assertEqual(total_mgr, 0)

    def test_mark_read(self):
        ann = create_announcement(self.owner, title='خواندن', body='متن')
        self.assertTrue(mark_announcement_read(self.advisor, ann.pk))
        self.assertEqual(unread_announcement_count(self.advisor), 0)

    def test_announcements_api_list(self):
        create_announcement(self.owner, title='API', body='تست')
        client = Client()
        client.force_login(self.advisor)
        resp = client.get(reverse('workspace:api_crm_team_announcements'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['unread'], 1)

    def test_announcement_detail_get(self):
        ann = create_announcement(self.owner, title='جزئیات', body='متن کامل')
        client = Client()
        client.force_login(self.advisor)
        url = reverse('workspace:api_crm_team_announcement_detail', kwargs={'announcement_id': ann.pk})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['announcement']['title'], 'جزئیات')

    def test_patch_mark_read_via_api(self):
        ann = create_announcement(self.owner, title='خواندن API', body='متن')
        client = Client()
        client.force_login(self.advisor)
        url = reverse('workspace:api_crm_team_announcement_detail', kwargs={'announcement_id': ann.pk})
        resp = client.patch(url, data=json.dumps({'action': 'read'}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(unread_announcement_count(self.advisor), 0)

    def test_create_with_attachment_multipart(self):
        client = Client()
        client.force_login(self.owner)
        f = SimpleUploadedFile('note.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        resp = client.post(
            reverse('workspace:api_crm_team_announcements'),
            data={'title': 'با ضمیمه', 'body': 'متن', 'attachment': f},
        )
        self.assertEqual(resp.status_code, 200)
        ann = CRMAgencyAnnouncement.objects.get(pk=resp.json()['id'])
        self.assertTrue(ann.attachment)

    def test_panel_notification_on_create(self):
        create_announcement(self.owner, title='اعلان', body='متن')
        self.assertEqual(
            CRMAgencyPanelNotification.objects.filter(user=self.advisor, kind='announcement').count(),
            1,
        )

    def test_manager_sees_scheduled_in_manage_mode(self):
        future = timezone.now() + timezone.timedelta(days=2)
        ann = create_announcement(
            self.owner,
            title='آینده',
            body='زمان‌بندی',
            published_at=future,
        )
        items, total = list_announcements(self.advisor)
        self.assertEqual(total, 0)
        items_mgr, total_mgr = list_announcements(self.owner, include_all=True)
        self.assertEqual(total_mgr, 1)
        self.assertEqual(items_mgr[0]['status'], 'scheduled')

    def test_create_with_jalali_datetime(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.post(
            reverse('workspace:api_crm_team_announcements'),
            data={
                'title': 'شمسی',
                'body': 'متن',
                'published_at': '1404/04/23 10:30',
            },
        )
        self.assertEqual(resp.status_code, 200)
        ann = CRMAgencyAnnouncement.objects.get(pk=resp.json()['id'])
        self.assertIsNotNone(ann.published_at)

    def test_detail_includes_read_stats_for_manager(self):
        ann = create_announcement(
            self.owner,
            title='آمار',
            body='متن',
            target_roles=['advisor'],
        )
        mark_announcement_read(self.advisor, ann.pk)
        client = Client()
        client.force_login(self.owner)
        url = reverse('workspace:api_crm_team_announcement_detail', kwargs={'announcement_id': ann.pk})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['announcement']
        self.assertIn('read_stats', data)
        self.assertEqual(data['read_stats']['read_count'], 1)
        self.assertEqual(data['read_stats']['unread_count'], 0)

    def test_detail_hides_read_stats_for_advisor(self):
        ann = create_announcement(self.owner, title='مخفی', body='متن')
        client = Client()
        client.force_login(self.advisor)
        url = reverse('workspace:api_crm_team_announcement_detail', kwargs={'announcement_id': ann.pk})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('read_stats', resp.json()['announcement'])

    def test_delete_announcement(self):
        ann = create_announcement(self.owner, title='حذف', body='متن')
        client = Client()
        client.force_login(self.owner)
        url = reverse('workspace:api_crm_team_announcement_detail', kwargs={'announcement_id': ann.pk})
        resp = client.delete(url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CRMAgencyAnnouncement.objects.filter(pk=ann.pk).exists())
