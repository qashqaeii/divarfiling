"""تست همگام‌سازی دفترچه تلفن فراز."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.services.admin_phonebook_sync import (
    collect_site_users,
    get_phonebook_sync_status,
    sync_users_to_phonebook,
)

User = get_user_model()


def _phonebook_page(total_items: int, mobiles: list[str], page: int = 1, per_page: int = 200):
    return {
        'currentPage': page,
        'totalPages': 1,
        'totalItems': total_items,
        'itemsPerPage': per_page,
        'items': [{'id': i + 1, 'mobile': m, 'name': '', 'prefix': 'man', 'attributes': []}
                  for i, m in enumerate(mobiles)],
    }


@override_settings(FARAZSMS_PHONEBOOK_USERS_ID=119558)
class PhonebookSyncServiceTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username='pb1', password='x', phone='09121111111', first_name='علی', last_name='رضایی',
        )
        User.objects.create_user(
            username='pb2', password='x', phone='09122222222', first_name='سارا',
        )
        User.objects.create_user(
            username='pb3', password='x', phone='invalid',
        )

    def test_collect_site_users_filters_invalid(self):
        items, total, invalid = collect_site_users()
        self.assertEqual(total, 3)
        self.assertEqual(invalid, 1)
        self.assertEqual(len(items), 2)
        mobiles = {i['mobile'] for i in items}
        self.assertEqual(mobiles, {'09121111111', '09122222222'})

    @patch('accounts.services.admin_phonebook_sync.iter_phonebook_contacts')
    @patch('accounts.services.admin_phonebook_sync.get_phonebook_contacts_page')
    def test_status_counts_missing(self, mock_page, mock_iter):
        mock_page.return_value = _phonebook_page(1, ['09121111111'])
        mock_iter.return_value = [{'mobile': '09121111111'}]
        status = get_phonebook_sync_status()
        self.assertTrue(status.ok)
        self.assertEqual(status.site_users_valid, 2)
        self.assertEqual(status.phonebook_total, 1)
        self.assertEqual(status.missing_in_phonebook, 1)
        self.assertEqual(status.extra_in_phonebook, 0)

    @patch('accounts.services.admin_phonebook_sync.get_phonebook_contacts_page')
    @patch('accounts.services.admin_phonebook_sync.bulk_upsert_phonebook_contacts')
    def test_sync_bulk_upsert(self, mock_bulk, mock_page):
        mock_page.side_effect = [
            _phonebook_page(0, []),
            _phonebook_page(2, ['09121111111', '09122222222']),
        ]
        result = sync_users_to_phonebook()
        self.assertTrue(result.ok)
        self.assertEqual(result.synced, 2)
        self.assertEqual(result.batches, 1)
        mock_bulk.assert_called_once()
        items = mock_bulk.call_args.kwargs['items']
        self.assertEqual(len(items), 2)


@override_settings(FARAZSMS_PHONEBOOK_USERS_ID=119558)
class PhonebookSyncViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='staffpb', password='pass1234', phone='09129999999', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.admin)

    @patch('accounts.admin_views.get_phonebook_sync_status')
    def test_status_json(self, mock_status):
        from accounts.services.admin_phonebook_sync import PhonebookSyncStatus
        mock_status.return_value = PhonebookSyncStatus(
            ok=True,
            phonebook_id=119558,
            phonebook_title='کاربران',
            site_users_valid=1,
            site_users_total=1,
            phonebook_total=0,
            missing_in_phonebook=1,
            extra_in_phonebook=0,
        )
        resp = self.client.get(reverse('admin_panel_phonebook_status'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['phonebook_id'], 119558)

    def test_status_denied_for_non_staff(self):
        user = User.objects.create_user(username='u1', password='x', phone='09128888888')
        self.client.force_login(user)
        resp = self.client.get(reverse('admin_panel_phonebook_status'))
        self.assertEqual(resp.status_code, 403)

    @patch('accounts.admin_views.sync_users_to_phonebook')
    def test_sync_post(self, mock_sync):
        from accounts.services.admin_phonebook_sync import PhonebookSyncResult
        mock_sync.return_value = PhonebookSyncResult(
            ok=True,
            phonebook_id=119558,
            synced=5,
            batches=1,
            site_users_valid=5,
            phonebook_total_before=0,
            phonebook_total_after=5,
            skipped_invalid=0,
        )
        resp = self.client.post(reverse('admin_panel_phonebook_sync'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['synced'], 5)
