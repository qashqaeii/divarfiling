import threading
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.db import connection
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from community_forum.services.members import get_or_create_member
from django.core.exceptions import ValidationError

from community_forum.services.messages import edit_message, list_sync_changes, send_message
from community_forum.services.rate_limit import enforce_send_rate_limit

User = get_user_model()

FORUM_SETTINGS = {
    'COMMUNITY_FORUM_ENABLED': True,
    'DEBUG': True,
    'FORUM_REDIS_URL': '',
    'COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS': False,
    'COMMUNITY_FORUM_ROLLOUT_MODE': 'all',
    'CHANNEL_LAYERS': {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
}


class ForumSettingsTests(TestCase):
    @override_settings(FORUM_REDIS_URL='redis://127.0.0.1:6379/3')
    def test_forum_redis_url_exposed_on_settings(self):
        from django.conf import settings as s

        self.assertEqual(s.FORUM_REDIS_URL, 'redis://127.0.0.1:6379/3')

    @override_settings(COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS=True)
    def test_rate_limit_require_redis_setting(self):
        self.assertTrue(settings.COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS)

    @override_settings(
        COMMUNITY_FORUM_ENABLED=True,
        DEBUG=False,
        FORUM_REDIS_URL='',
        COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS=False,
    )
    def test_production_forum_without_redis_fails_closed(self):
        user = User.objects.create_user(username='09169999999', phone='09169999999', password='x')
        with self.assertRaises(ValidationError) as ctx:
            enforce_send_rate_limit(1, user)
        self.assertEqual(ctx.exception.code, 'rate_unavailable')


@override_settings(**FORUM_SETTINGS)
class ForumIdempotencyConcurrencyTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.user = User.objects.create_user(username='09165555555', phone='09165555555', password='x')
        self.member = get_or_create_member(self.user)

    @patch('community_forum.services.messages.enforce_send_rate_limit')
    def test_concurrent_client_id_creates_one_row(self, _noop_rate):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite cannot exercise concurrent writers; use PostgreSQL in CI/staging.')
        cid = str(uuid.uuid4())
        results = []
        errors = []

        def worker():
            try:
                results.append(
                    send_message(self.member, 'همزمان', client_message_id=cid),
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors, errors)
        ids = {m.pk for m in results}
        self.assertEqual(len(ids), 1)


@override_settings(**FORUM_SETTINGS)
class ForumSyncAPITests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.user = User.objects.create_user(username='09166666666', phone='09166666666', password='x')
        self.member = get_or_create_member(self.user)

    def test_sync_returns_edited_message(self):
        since = timezone.now().isoformat()
        msg = send_message(self.member, 'نسخه اول')
        edit_message(self.member, msg.pk, 'نسخه دوم')
        page = list_sync_changes(self.member, anchor_id=msg.pk, since_iso=since)
        self.assertTrue(any(m['body'] == 'نسخه دوم' for m in page['messages']))
