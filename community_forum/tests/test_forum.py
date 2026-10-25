import json
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import caches
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
    'CHANNEL_LAYERS': {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
}


@override_settings(**FORUM_SETTINGS)
class ForumAccessTests(TestCase):
    def setUp(self):
        caches['forum_rate_limit'].clear()
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
