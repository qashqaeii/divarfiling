import os
import threading
import uuid
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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

    def test_channel_layers_redis_hosts_use_blocking_socket_timeout(self):
        """redis-py 8 defaults socket_timeout=5s; Channels BRPOP needs blocking reads."""
        settings_path = Path(settings.BASE_DIR) / 'divar_shop' / 'settings.py'
        source = settings_path.read_text(encoding='utf-8')
        self.assertIn("'address': FORUM_REDIS_URL", source)
        self.assertIn("'socket_timeout': None", source)

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


def _redis_channel_layers(redis_url):
    return {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [
                    {
                        'address': redis_url,
                        'socket_timeout': None,
                    },
                ],
            },
        },
    }


@override_settings()
class ForumRedisChannelLayerIntegrationTests(TestCase):
    """Requires local Redis (same host as production FORUM_REDIS_URL)."""

    def setUp(self):
        self.redis_url = (os.environ.get('FORUM_REDIS_URL') or '').strip()
        if not self.redis_url:
            self.redis_url = 'redis://127.0.0.1:6379/15'

    def test_send_receive_between_channels(self):
        try:
            import redis

            client = redis.from_url(self.redis_url, socket_connect_timeout=1)
            client.ping()
        except Exception as exc:
            self.skipTest(f'Redis unavailable: {exc}')

        with self.settings(CHANNEL_LAYERS=_redis_channel_layers(self.redis_url)):
            from channels.layers import channel_layers

            channel_layers.backends.clear()
            layer = get_channel_layer()
            channel_a = async_to_sync(layer.new_channel)()
            channel_b = async_to_sync(layer.new_channel)()

            async_to_sync(layer.send)(channel_a, {'type': 'forum.test', 'value': 42})
            message = async_to_sync(layer.receive)(channel_a)
            self.assertEqual(message['value'], 42)

            async_to_sync(layer.send)(channel_b, {'type': 'forum.test', 'value': 99})
            message_b = async_to_sync(layer.receive)(channel_b)
            self.assertEqual(message_b['value'], 99)
