import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache, caches
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from community_forum.models import ForumMessage
from community_forum.services.members import get_or_create_member
from community_forum.services.messages import send_message

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
class ForumPinMessageTests(TestCase):
    def setUp(self):
        cache.clear()
        caches['forum_rate_limit'].clear()
        caches['forum_shared'].clear()
        self.user = User.objects.create_user(username='mod', phone='09161112222', password='x')
        self.other = User.objects.create_user(username='u2', phone='09163334444', password='x')
        ct = ContentType.objects.get(app_label='community_forum', model='forummessage')
        perm = Permission.objects.get(content_type=ct, codename='can_moderate_forum')
        self.user.user_permissions.add(perm)
        self.client = Client()
        self.client.force_login(self.user)
        self.other_client = Client()
        self.other_client.force_login(self.other)

    def test_moderator_can_pin_and_bootstrap_returns_it(self):
        member = get_or_create_member(self.other)
        msg = send_message(member, 'پیام مهم')
        pin_url = reverse('workspace:community_forum:api_message_pin', args=[msg.pk])
        r = self.client.post(pin_url, data=json.dumps({'pin': True}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['pinned_message']['id'], msg.pk)

        boot = self.client.get(reverse('workspace:community_forum:api_bootstrap'))
        boot_data = boot.json()
        self.assertEqual(boot_data['pinned_message']['body'], 'پیام مهم')

        stored = ForumMessage.objects.get(pk=msg.pk)
        self.assertIsNotNone(stored.pinned_at)

    def test_non_moderator_cannot_pin(self):
        member = get_or_create_member(self.other)
        msg = send_message(member, 'عادی')
        pin_url = reverse('workspace:community_forum:api_message_pin', args=[msg.pk])
        r = self.other_client.post(pin_url, data=json.dumps({'pin': True}), content_type='application/json')
        self.assertEqual(r.status_code, 403)

    def test_pin_replaces_previous(self):
        m1 = send_message(get_or_create_member(self.user), 'اول')
        m2 = send_message(get_or_create_member(self.other), 'دوم')
        pin_url = lambda mid: reverse('workspace:community_forum:api_message_pin', args=[mid])
        self.client.post(pin_url(m1.pk), data=json.dumps({'pin': True}), content_type='application/json')
        self.client.post(pin_url(m2.pk), data=json.dumps({'pin': True}), content_type='application/json')
        self.assertIsNone(ForumMessage.objects.get(pk=m1.pk).pinned_at)
        self.assertIsNotNone(ForumMessage.objects.get(pk=m2.pk).pinned_at)
