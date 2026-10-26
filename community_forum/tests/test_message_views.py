import json

from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from community_forum.models import ForumMessage
from community_forum.services.members import get_or_create_member
from community_forum.services.messages import send_message
from community_forum.services.message_views import record_message_views

User = get_user_model()

FORUM_SETTINGS = {
    'COMMUNITY_FORUM_ENABLED': True,
    'DEBUG': True,
    'FORUM_REDIS_URL': '',
    'COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS': False,
    'COMMUNITY_FORUM_ROLLOUT_MODE': 'all',
    'CHANNEL_LAYERS': {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
}


@override_settings(**FORUM_SETTINGS)
class ForumMessageViewTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.u1 = User.objects.create_user(username='a', phone='09161110001', password='x')
        self.u2 = User.objects.create_user(username='b', phone='09161110002', password='x')
        self.m1 = get_or_create_member(self.u1)
        self.m2 = get_or_create_member(self.u2)

    def test_sender_has_initial_view_on_send(self):
        msg = send_message(self.m1, 'سلام')
        self.assertGreaterEqual(msg.view_count, 1)

    def test_view_count_idempotent_per_member(self):
        msg = send_message(self.m1, 'تست')
        start = ForumMessage.objects.get(pk=msg.pk).view_count
        record_message_views(self.m2, [msg.pk])
        record_message_views(self.m2, [msg.pk])
        updated = ForumMessage.objects.get(pk=msg.pk)
        self.assertEqual(updated.view_count, start + 1)

    def test_views_api_returns_counts(self):
        msg = send_message(self.m1, 'api')
        client = Client()
        client.force_login(self.u2)
        url = reverse('workspace:community_forum:api_views')
        r = client.post(url, data=json.dumps({'message_ids': [msg.pk]}), content_type='application/json')
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['views'][str(msg.pk)], 2)
