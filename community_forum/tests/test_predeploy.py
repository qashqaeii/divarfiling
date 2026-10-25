from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_forum.services import messages as messages_service
from community_forum.services.members import get_or_create_member
from community_forum.services.messages import (
    edit_message,
    list_sync_changes,
    send_message,
    set_reaction,
)
from community_forum.services.retention import purge_expired_messages

User = get_user_model()

FORUM_BASE = {
    'COMMUNITY_FORUM_ENABLED': True,
    'DEBUG': True,
    'FORUM_REDIS_URL': '',
    'COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS': False,
    'CHANNEL_LAYERS': {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
}


@override_settings(**FORUM_BASE)
class ForumRolloutTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.user = User.objects.create_user(username='09167777777', phone='09167777777', password='x')
        self.other = User.objects.create_user(username='09168888888', phone='09168888888', password='x')
        self.client = Client()
        self.client.force_login(self.user)

    @override_settings(COMMUNITY_FORUM_ROLLOUT_MODE='none')
    def test_enabled_without_rollout_denies_page(self):
        r = self.client.get(reverse('workspace:community_forum:home'))
        self.assertEqual(r.status_code, 404)

    @override_settings(
        COMMUNITY_FORUM_ROLLOUT_MODE='allowlist',
        COMMUNITY_FORUM_ALLOWED_USER_IDS=frozenset(),
    )
    def test_allowlist_blocks_unknown_user(self):
        r = self.client.get(reverse('workspace:community_forum:home'))
        self.assertEqual(r.status_code, 404)

    def test_allowlist_permits_listed_user(self):
        with override_settings(
            COMMUNITY_FORUM_ROLLOUT_MODE='allowlist',
            COMMUNITY_FORUM_ALLOWED_USER_IDS=frozenset({self.user.pk}),
        ):
            r = self.client.get(reverse('workspace:community_forum:home'))
        self.assertEqual(r.status_code, 200)

    @override_settings(COMMUNITY_FORUM_ROLLOUT_MODE='all')
    def test_rollout_all_permits_any_active_user(self):
        c = Client()
        c.force_login(self.other)
        r = c.get(reverse('workspace:community_forum:home'))
        self.assertEqual(r.status_code, 200)


class ForumPurgeLockTests(TestCase):
    @patch('community_forum.services.retention.shared_cache')
    @patch('community_forum.services.retention._pg_advisory_lock_state', return_value='busy')
    def test_postgres_busy_skips_without_cache_lock(self, _pg, mock_shared):
        mock_cache = MagicMock()
        mock_shared.return_value = mock_cache
        stats = purge_expired_messages()
        self.assertTrue(stats.get('skipped'))
        mock_cache.add.assert_not_called()

    @patch('community_forum.services.retention.shared_cache')
    @patch('community_forum.services.retention._pg_advisory_lock_state', return_value='unavailable')
    def test_non_postgres_uses_cache_lock(self, _pg, mock_shared):
        mock_cache = MagicMock()
        mock_cache.add.return_value = True
        mock_shared.return_value = mock_cache
        purge_expired_messages()
        mock_cache.add.assert_called_once()


@override_settings(**{**FORUM_BASE, 'COMMUNITY_FORUM_ROLLOUT_MODE': 'all'})
class ForumSyncPaginationTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.user = User.objects.create_user(username='09169000000', phone='09169000000', password='x')
        self.member = get_or_create_member(self.user)

    @patch('community_forum.services.messages.enforce_send_rate_limit')
    def test_sync_pages_without_dropping(self, _noop_rate):
        since = timezone.now().isoformat()
        msgs = [send_message(self.member, f'پیام {i}') for i in range(3)]
        for m in msgs:
            edit_message(self.member, m.pk, m.body + ' ویرایش')
        anchor = msgs[-1].pk
        cursor = 0
        seen = []
        with patch.object(messages_service, 'SYNC_PAGE_SIZE', 2):
            while True:
                page = list_sync_changes(
                    self.member,
                    anchor_id=anchor,
                    since_iso=since,
                    cursor_id=cursor,
                )
                seen.extend(page['messages'])
                if not page['has_more']:
                    break
                cursor = page['next_cursor']
        self.assertEqual(len(seen), 3)

    def test_sync_includes_reaction_changes(self):
        since = timezone.now().isoformat()
        msg = send_message(self.member, 'واکنش')
        set_reaction(self.member, msg.pk, '👍')
        page = list_sync_changes(self.member, anchor_id=msg.pk, since_iso=since)
        self.assertEqual(len(page['messages']), 1)
        rx = page['messages'][0].get('reactions') or []
        self.assertTrue(any(r.get('emoji') == '👍' for r in rx))
