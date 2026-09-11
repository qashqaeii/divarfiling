"""تست صندوق پیام داخلی آژانس."""
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMAgencyMember, CRMAgencyMessageThread
from workspace.services.crm_agency import create_agency
from workspace.services.crm_agency_messages import (
    delete_message,
    delete_thread_for_user,
    get_thread_detail,
    list_threads_for_user,
    send_broadcast_message,
    send_direct_message,
    unread_message_count,
)

User = get_user_model()


class CRMAgencyMessagesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_msg', password='pass12345')
        self.advisor = User.objects.create_user(username='advisor_msg', phone='09121111111', password='pass12345')
        self.agency = create_agency(self.owner, 'آژانس پیام')
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor',
        )

    def test_send_direct_message(self):
        thread = send_direct_message(self.owner, self.advisor_member.pk, 'سلام همکار')
        self.assertEqual(thread.kind, CRMAgencyMessageThread.KIND_DIRECT)
        self.assertEqual(thread.messages.count(), 1)
        self.assertEqual(unread_message_count(self.advisor), 1)
        items, total = list_threads_for_user(self.advisor)
        self.assertEqual(total, 1)
        self.assertEqual(items[0]['unread_count'], 1)

    def test_messages_api_list(self):
        send_direct_message(self.owner, self.advisor_member.pk, 'تست API')
        client = Client()
        client.force_login(self.advisor)
        resp = client.get(reverse('workspace:api_crm_team_messages'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 1)

    def test_broadcast_requires_manager(self):
        client = Client()
        client.force_login(self.advisor)
        resp = client.post(
            reverse('workspace:api_crm_team_messages'),
            data=json.dumps({'kind': 'broadcast', 'body': 'نباید برود'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_broadcast_sender_sees_thread_when_targeting_other_roles(self):
        """فرستنده باید مکالمه گروهی را ببیند حتی اگر نقش خودش در مخاطبان نباشد."""
        thread = send_broadcast_message(
            self.owner,
            'اطلاعیه برای مشاوران',
            subject='جلسه فردا',
            target_roles=['advisor'],
        )
        detail = get_thread_detail(self.owner, thread.pk)
        self.assertIsNotNone(detail)
        items, total = list_threads_for_user(self.owner)
        self.assertEqual(total, 1)
        self.assertEqual(items[0]['id'], thread.pk)
        self.assertEqual(unread_message_count(self.advisor), 1)

    def test_broadcast_api_multipart_target_roles(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.post(
            reverse('workspace:api_crm_team_messages'),
            {
                'kind': 'broadcast',
                'body': 'پیام گروهی تست',
                'subject': 'موضوع',
                'target_roles': ['advisor', 'secretary'],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIsNotNone(data.get('thread'))
        self.assertEqual(data['thread']['thread']['kind'], 'broadcast')

    def test_broadcast_two_advisors_all_members(self):
        advisor2 = User.objects.create_user(username='advisor2', phone='09122222222', password='pass12345')
        CRMAgencyMember.objects.create(agency=self.agency, user=advisor2, role='advisor')
        thread = send_broadcast_message(self.owner, 'پیام برای همه', subject='اطلاعیه', target_roles=[])
        self.assertEqual(thread.participants.count(), 3)
        detail = get_thread_detail(self.owner, thread.pk)
        self.assertIsNotNone(detail)
        self.assertEqual(unread_message_count(self.advisor), 1)
        self.assertEqual(unread_message_count(advisor2), 1)

    def test_broadcast_two_advisors_via_api_form(self):
        advisor2 = User.objects.create_user(username='advisor2b', phone='09123333333', password='pass12345')
        CRMAgencyMember.objects.create(agency=self.agency, user=advisor2, role='advisor')
        client = Client()
        client.force_login(self.owner)
        resp = client.post(
            reverse('workspace:api_crm_team_messages'),
            {
                'kind': 'broadcast',
                'body': 'سلام مشاوران',
                'subject': 'جلسه',
                'target_roles': 'advisor',
            },
        )
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        data = resp.json()
        self.assertTrue(data['ok'], data)
        self.assertIsNotNone(data.get('thread'))
        self.assertEqual(data['thread']['thread']['kind'], 'broadcast')
        self.assertEqual(unread_message_count(self.advisor), 1)
        self.assertEqual(unread_message_count(advisor2), 1)

    def test_team_messages_tab_renders(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get(reverse('workspace:agency_hub_messages'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرکز پیام تیم')

    def test_delete_own_message(self):
        thread = send_direct_message(self.owner, self.advisor_member.pk, 'پیام قابل حذف')
        msg_id = thread.messages.first().pk
        thread_id = thread.pk
        delete_message(self.owner, thread_id, msg_id)
        self.assertFalse(CRMAgencyMessageThread.objects.filter(pk=thread_id).exists())

    def test_delete_thread_for_user(self):
        thread = send_direct_message(self.owner, self.advisor_member.pk, 'مکالمه')
        delete_thread_for_user(self.owner, thread.pk)
        items, total = list_threads_for_user(self.owner)
        self.assertEqual(total, 0)

    def test_delete_message_api(self):
        thread = send_direct_message(self.owner, self.advisor_member.pk, 'حذف از API')
        msg_id = thread.messages.first().pk
        client = Client()
        client.force_login(self.owner)
        url = reverse('workspace:api_crm_team_message_item', args=[thread.pk, msg_id])
        resp = client.delete(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('thread_removed') or data.get('messages') == [])

    def test_attachment_validation(self):
        bad = SimpleUploadedFile('virus.exe', b'x', content_type='application/octet-stream')
        with self.assertRaises(ValueError):
            send_direct_message(self.owner, self.advisor_member.pk, 'با فایل', attachments=[bad])
