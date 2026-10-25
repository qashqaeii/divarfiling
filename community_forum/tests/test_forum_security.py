import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.test import TestCase, override_settings

from community_forum.models import ForumBan, ForumMessage
from community_forum.services.members import get_or_create_member
from community_forum.services.messages import send_message
from community_forum.services.moderation import invalidate_ban_cache, member_can_read, on_ban_applied
from community_forum.services.serialization import serialize_message, serialize_message_public

User = get_user_model()

FORUM_SETTINGS = {
    'COMMUNITY_FORUM_ENABLED': True,
    'CHANNEL_LAYERS': {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
}


@override_settings(**FORUM_SETTINGS)
class ForumBroadcastSerializationTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        self.u1 = User.objects.create_user(username='09161111111', phone='09161111111', password='x')
        self.u2 = User.objects.create_user(username='09162222222', phone='09162222222', password='x')
        self.m1 = get_or_create_member(self.u1)
        self.m2 = get_or_create_member(self.u2)

    def test_public_payload_has_no_is_mine(self):
        msg = send_message(self.m1, 'سلام')
        pub = serialize_message_public(msg)
        self.assertNotIn('is_mine', pub)
        self.assertEqual(pub['sender_public_id'], str(self.m1.public_id))

    def test_rest_is_mine_per_viewer(self):
        msg = send_message(self.m1, 'تست')
        for viewer, expected in ((self.m1, True), (self.m2, False)):
            data = serialize_message(msg, viewer_member=viewer)
            self.assertEqual(data['is_mine'], expected)


@override_settings(**FORUM_SETTINGS)
class ForumBanTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        self.user = User.objects.create_user(username='09163333333', phone='09163333333', password='x')
        self.member = get_or_create_member(self.user)
        invalidate_ban_cache(self.member.id)

    def test_read_ban_blocks_read(self):
        ban = ForumBan.objects.create(member=self.member, can_read=False)
        on_ban_applied(ban)
        self.assertFalse(member_can_read(self.member))

    def test_send_only_ban_allows_read(self):
        ForumBan.objects.create(member=self.member, can_read=True)
        self.assertTrue(member_can_read(self.member))
