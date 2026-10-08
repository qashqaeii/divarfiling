"""تست پنل مشاور عضو — پیام‌ها و modals."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMAgencyMember
from workspace.services.crm_agency import create_agency  # noqa: F401 — used in isolation test
from workspace.services.crm_agency_messages import send_broadcast_message, send_direct_message
from workspace.tests.test_agency_phase3 import AgencyPhase3Base

User = get_user_model()


class AgencyMemberHubMessagesTests(AgencyPhase3Base):
    def test_advisor_messages_tab_renders_hub_and_modals(self):
        send_direct_message(self.owner_a, self.member_a.pk, 'پیام مدیر برای مشاور')
        self.client.force_login(self.advisor_a)
        url = reverse('workspace:agency_advisor_member') + '?tab=messages'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-crm-messages')
        self.assertContains(resp, 'modal-msg-compose')
        self.assertContains(resp, 'drawer-msg-notifications')
        self.assertContains(resp, 'modal-msg-confirm')
        self.assertContains(resp, 'data-api-threads')

    def test_advisor_api_lists_owner_message(self):
        send_direct_message(self.owner_a, self.member_a.pk, 'سلام مشاور')
        self.client.force_login(self.advisor_a)
        resp = self.client.get(reverse('workspace:api_crm_team_messages') + '?folder=inbox')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'], data)
        self.assertGreaterEqual(data['total'], 1)
        self.assertTrue(any('سلام مشاور' in (t.get('last_message') or {}).get('body', '') for t in data['threads']))

    def test_advisor_sees_broadcast_for_advisors(self):
        send_broadcast_message(
            self.owner_a,
            'اطلاعیه گروهی',
            subject='جلسه',
            target_roles=['advisor'],
        )
        self.client.force_login(self.advisor_a)
        resp = self.client.get(reverse('workspace:api_crm_team_messages') + '?folder=inbox')
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['total'], 1)

    def test_advisor_cannot_broadcast_via_api(self):
        self.client.force_login(self.advisor_a)
        resp = self.client.post(
            reverse('workspace:api_crm_team_messages'),
            {'kind': 'broadcast', 'body': 'نباید برود', 'subject': 'x'},
        )
        self.assertIn(resp.status_code, (400, 403))

    def test_advisor_messages_isolated_from_other_agency(self):
        other_owner = User.objects.create_user(username='own_iso', password='x')
        other_agency = create_agency(other_owner, 'Other')
        other_adv = User.objects.create_user(username='adv_iso', phone='09129998877', password='x')
        other_member = CRMAgencyMember.objects.create(
            agency=other_agency, user=other_adv, role='advisor', is_active=True,
        )
        send_direct_message(other_owner, other_member.pk, 'پیام آژانس دیگر')
        send_direct_message(self.owner_a, self.member_a.pk, 'پیام آژانس خودمان')

        self.client.force_login(self.advisor_a)
        resp = self.client.get(reverse('workspace:api_crm_team_messages'))
        data = resp.json()
        self.assertTrue(data['ok'])
        bodies = [
            (t.get('last_message') or {}).get('body', '')
            for t in data.get('threads') or []
        ]
        self.assertTrue(any('پیام آژانس خودمان' in b for b in bodies))
        self.assertFalse(any('پیام آژانس دیگر' in b for b in bodies))

    def test_owner_redirected_from_member_hub(self):
        self.client.force_login(self.owner_a)
        resp = self.client.get(reverse('workspace:agency_advisor_member'))
        self.assertRedirects(resp, reverse('workspace:agency_hub_advisors'), fetch_redirect_response=False)
