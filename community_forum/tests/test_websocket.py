from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings

from community_forum.models import ForumBan
from divar_shop.asgi_ws import application
from community_forum.services.members import get_or_create_member
from community_forum.services.moderation import invalidate_ban_cache

User = get_user_model()

FORUM_SETTINGS = {
    'COMMUNITY_FORUM_ENABLED': True,
    'DEBUG': True,
    'FORUM_REDIS_URL': '',
    'COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS': False,
    'COMMUNITY_FORUM_ROLLOUT_MODE': 'all',
    'ALLOWED_HOSTS': ['127.0.0.1', 'localhost', 'testserver'],
    'CHANNEL_LAYERS': {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
}


def _ws_communicator(path='/ws/forum/'):
    comm = WebsocketCommunicator(application, path)
    comm.scope['headers'] = [(b'origin', b'http://127.0.0.1')]
    return comm


@override_settings(**FORUM_SETTINGS)
class ForumWebsocketTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='09164444444', phone='09164444444', password='x')
        self.member = get_or_create_member(self.user)

    async def test_anonymous_rejected(self):
        comm = _ws_communicator()
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()

    async def test_authenticated_connects(self):
        comm = _ws_communicator()
        comm.scope['user'] = self.user
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()

    async def test_read_ban_rejects_connect(self):
        @sync_to_async
        def _ban():
            ForumBan.objects.create(member=self.member, can_read=False)
            invalidate_ban_cache(self.member.id)

        await _ban()
        comm = _ws_communicator()
        comm.scope['user'] = self.user
        connected, _ = await comm.connect()
        self.assertFalse(connected)
        await comm.disconnect()
