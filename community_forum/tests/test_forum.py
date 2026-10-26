import json
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache, caches
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community_forum.models import ForumMember, ForumMessage
from community_forum.services.identity import mask_phone, member_display_label
from community_forum.services.messages import send_message
from community_forum.services.members import get_or_create_member
from community_forum.services.retention import purge_expired_messages

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
class ForumAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.user = User.objects.create_user(
            username='u1',
            phone='09161234567',
            password='x',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_anonymous_denied_api(self):
        c = Client()
        url = reverse('workspace:community_forum:api_messages')
        r = c.get(url)
        self.assertEqual(r.status_code, 302)

    @override_settings(COMMUNITY_FORUM_ENABLED=False)
    def test_disabled_returns_404_page(self):
        url = reverse('workspace:community_forum:home')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_page_loads(self):
        url = reverse('workspace:community_forum:home')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_send_and_list(self):
        member = get_or_create_member(self.user)
        msg = send_message(member, 'سلام همکاران')
        url = reverse('workspace:community_forum:api_messages')
        r = self.client.get(url)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['messages'][-1]['body'], 'سلام همکاران')
        self.assertNotIn('09161234567', json.dumps(data, ensure_ascii=False))

    def test_idempotent_client_message_id(self):
        member = get_or_create_member(self.user)
        cid = str(uuid.uuid4())
        m1 = send_message(member, 'یک', client_message_id=cid)
        m2 = send_message(member, 'دو', client_message_id=cid)
        self.assertEqual(m1.pk, m2.pk)

    def test_mask_phone(self):
        self.assertEqual(mask_phone('09161234567'), '0916***4567')

    def test_display_label_masks_when_no_name(self):
        member = get_or_create_member(self.user)
        label = member_display_label(member)
        self.assertIn('***', label)
        self.assertNotIn('09161234567', label)

    def test_purge_old_messages(self):
        member = get_or_create_member(self.user)
        old = ForumMessage.objects.create(
            sender=member,
            body='قدیمی',
            created_at=timezone.now() - timedelta(days=31),
        )
        stats = purge_expired_messages(retention_days=30)
        self.assertGreaterEqual(stats['messages'], 1)
        self.assertFalse(ForumMessage.objects.filter(pk=old.pk).exists())

    def test_welcome_ack_once(self):
        member = get_or_create_member(self.user)
        self.assertIsNone(member.welcome_seen_at)
        url = reverse('workspace:community_forum:api_profile')
        bootstrap = reverse('workspace:community_forum:api_bootstrap')
        r0 = self.client.get(bootstrap)
        self.assertTrue(r0.json()['member']['welcome_seen'] is False)
        r1 = self.client.post(
            url,
            data=json.dumps({'welcome_ack': True}),
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()['welcome_seen'])
        member.refresh_from_db()
        first_seen = member.welcome_seen_at
        self.assertIsNotNone(first_seen)
        r2 = self.client.post(
            url,
            data=json.dumps({'welcome_ack': True}),
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 200)
        member.refresh_from_db()
        self.assertEqual(member.welcome_seen_at, first_seen)
        r3 = self.client.get(bootstrap)
        self.assertTrue(r3.json()['member']['welcome_seen'])
