"""تست پترن پیامک دعوت مشاور به آژانس."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.sms import SmsError
from workspace.models import CRMAgencyMember
from workspace.services.agency_invitations import (
    SMS_RESEND_COOLDOWN_SECONDS,
    _build_invite_url,
    _pattern_link_from_invite_url,
    create_agency_invitation,
    create_bulk_agency_invitations,
    resend_invitation_sms,
)
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.tests.test_agency_phase2 import AgencyPhase2TestBase


class AgencyInvitePatternSettingsTests(TestCase):
    def test_default_pattern_code_in_settings(self):
        patterns = getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}
        self.assertEqual(patterns.get('agency_invite'), 'mPibtIrJSo')


class AgencyInvitePatternLinkTests(TestCase):
    def test_strips_domain_and_leading_slash(self):
        url = 'https://divarfiling.ir/workspace/agency/invite/abc123/'
        self.assertEqual(
            _pattern_link_from_invite_url(url),
            'workspace/agency/invite/abc123/',
        )

    def test_preserves_query_string(self):
        url = 'https://www.divarfiling.ir/workspace/agency/invite/tok/?ref=1'
        self.assertEqual(
            _pattern_link_from_invite_url(url),
            'workspace/agency/invite/tok/?ref=1',
        )

    def test_rejects_foreign_domain(self):
        from accounts.services.sms import SmsSendError

        with self.assertRaises(SmsSendError):
            _pattern_link_from_invite_url('https://evil.example/invite/x/')


@override_settings(SITE_URL='https://divarfiling.ir')
class AgencyInvitePatternSmsTests(AgencyPhase2TestBase):
    def setUp(self):
        super().setUp()
        self._agency_order()
        self.agency = create_or_link_agency(self.owner, 'آژانس نمونه')
        CRMAgencyMember.objects.get_or_create(
            agency=self.agency, user=self.owner, defaults={'role': 'owner'},
        )

    def _expected_link_for_token(self, raw_token: str) -> str:
        full = _build_invite_url(None, raw_token)
        return _pattern_link_from_invite_url(full)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    @patch('workspace.services.agency_invitations._generate_invite_token')
    def test_create_invitation_sends_pattern_attributes(self, mock_gen, mock_sms):
        raw = f'invite-token-{uuid.uuid4().hex}'
        mock_gen.return_value = (raw, f'hash-{uuid.uuid4().hex}')
        mock_sms.return_value = None

        inv = create_agency_invitation(self.owner, self.phones[1], request=None)

        mock_sms.assert_called_once()
        _phone, kwargs = mock_sms.call_args[0][0], mock_sms.call_args[1]
        self.assertEqual(_phone, inv.phone)
        self.assertEqual(kwargs.get('purpose'), 'agency_invite')
        attrs = kwargs.get('attributes') or {}
        self.assertEqual(set(attrs.keys()), {'agency', 'link'})
        self.assertEqual(attrs['agency'], self.agency.name)
        self.assertEqual(attrs['link'], self._expected_link_for_token(raw))
        self.assertNotIn('https://', attrs['link'])
        self.assertNotIn('divarfiling.ir', attrs['link'])
        self.assertIn(raw, attrs['link'])
        inv.refresh_from_db()
        self.assertIsNotNone(inv.sms_sent_at)
        self.assertEqual(inv.sms_metadata.get('last_status'), 'sent')

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    @patch('workspace.services.agency_invitations._generate_invite_token')
    def test_bulk_invitations_use_pattern_for_each(self, mock_gen, mock_sms):
        tokens = [f'bulk-{i}-{uuid.uuid4().hex[:8]}' for i in range(2)]
        mock_gen.side_effect = [(t, f'h-{t}') for t in tokens]
        mock_sms.return_value = None

        phones = [self.phones[1], self.phones[2]]
        result = create_bulk_agency_invitations(self.owner, phones, request=None)

        self.assertEqual(len(result['created']), 2)
        self.assertEqual(mock_sms.call_count, 2)
        for call, raw in zip(mock_sms.call_args_list, tokens, strict=True):
            attrs = call[1]['attributes']
            self.assertEqual(attrs['agency'], self.agency.name)
            self.assertEqual(attrs['link'], self._expected_link_for_token(raw))

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    @patch('workspace.services.agency_invitations._generate_invite_token')
    def test_resend_uses_same_pattern_with_new_token(self, mock_gen, mock_sms):
        mock_gen.return_value = ('initial-token', 'hash-init')
        mock_sms.return_value = None
        inv = create_agency_invitation(self.owner, self.phones[1], request=None)
        mock_sms.reset_mock()

        inv.refresh_from_db()
        inv.sms_sent_at = timezone.now() - timedelta(seconds=SMS_RESEND_COOLDOWN_SECONDS + 10)
        inv.save(update_fields=['sms_sent_at'])

        resend_raw = f'resend-{uuid.uuid4().hex}'
        mock_gen.return_value = (resend_raw, f'hash-{resend_raw}')

        resend_invitation_sms(self.owner, inv.pk, request=None)

        mock_sms.assert_called_once()
        kwargs = mock_sms.call_args[1]
        self.assertEqual(kwargs.get('purpose'), 'agency_invite')
        attrs = kwargs['attributes']
        self.assertEqual(attrs['agency'], self.agency.name)
        self.assertEqual(attrs['link'], self._expected_link_for_token(resend_raw))
        self.assertIn(resend_raw, attrs['link'])

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    @patch('workspace.services.agency_invitations._generate_invite_token')
    def test_sms_failure_does_not_mark_sent(self, mock_gen, mock_sms):
        mock_gen.return_value = ('fail-token', 'hash-fail')
        mock_sms.side_effect = SmsError('fail')

        inv = create_agency_invitation(self.owner, self.phones[1], request=None)
        inv.refresh_from_db()
        self.assertIsNone(inv.sms_sent_at)
        self.assertEqual(inv.sms_metadata.get('last_status'), 'failed')

    @override_settings(SITE_URL='https://divarfiling.ir')
    def test_invite_path_matches_url_name(self):
        raw = 'path-check-token'
        path = reverse('workspace:agency_invite_accept', kwargs={'token': raw}).lstrip('/')
        link = _pattern_link_from_invite_url(_build_invite_url(None, raw))
        self.assertTrue(link.startswith('workspace/agency/invite/'))
        self.assertIn(raw, link)
        self.assertEqual(link.split('?')[0], path)
