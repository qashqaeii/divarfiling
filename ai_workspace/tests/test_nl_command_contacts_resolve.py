"""Contact name resolution for nl_command."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_workspace.services.nl_command.contacts import (
    resolve_contact_by_name,
    strip_contact_honorifics,
)
from workspace.models import Customer

User = get_user_model()


class NLCommandContactResolveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='resolve_u', password='x')
        self.saadat = Customer.objects.create(
            user=self.user,
            name='سعادت',
            phone='09185663222',
        )

    def test_strip_honorific_aqay(self):
        self.assertEqual(strip_contact_honorifics('آقای سعادت'), 'سعادت')

    def test_resolve_aqay_saadat_matches_short_name(self):
        cid, candidates, amb = resolve_contact_by_name(self.user, 'آقای سعادت')
        self.assertEqual(amb, '')
        self.assertEqual(cid, self.saadat.pk)
        self.assertEqual(len(candidates), 1)

    def test_resolve_plain_name(self):
        cid, _, amb = resolve_contact_by_name(self.user, 'سعادت')
        self.assertEqual(cid, self.saadat.pk)
        self.assertEqual(amb, '')

    def test_resolve_khanom_prefix(self):
        cid, _, amb = resolve_contact_by_name(self.user, 'خانم سعادت')
        self.assertEqual(cid, self.saadat.pk)
        self.assertEqual(amb, '')

    def test_resolve_unknown(self):
        cid, candidates, amb = resolve_contact_by_name(self.user, 'آقای ناموجود')
        self.assertIsNone(cid)
        self.assertEqual(amb, 'none')
        self.assertEqual(candidates, [])
