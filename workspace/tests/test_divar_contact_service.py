"""تست‌های Mock سرویس نشست دیوار."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import PhoneDetectorExtractionLine
from workspace.divar_session_models import DivarAccountSession, DivarContactFeatureConfig
from workspace.services.divar_session.crypto import decrypt_payload, encrypt_payload
from workspace.services.divar_session.phone_detector_bridge import (
    on_central_session_invalidated,
    unlink_session_from_line,
)
from workspace.services.divar_session.pd_sync_block import is_phone_detector_file_sync_blocked
from workspace.services.divar_session.errors import DivarSessionError
from workspace.services.divar_session.service import (
    _persist_session,
    fetch_listing_phone,
    get_primary_session,
    public_session_status,
    send_divar_otp,
)
from workspace.services.divar_session.runtime import DivarUserRuntime, SessionHealth

User = get_user_model()


def _session_payload(phone: str = '09121234567') -> dict:
    return {
        'phone': phone,
        'device_id': 'dev',
        'cookies': [{'name': 'sAccessToken', 'value': 'x', 'domain': '.divar.ir', 'path': '/'}],
    }


class DivarSessionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129990001',
            phone='09129990001',
            password='x',
            is_superuser=True,
        )
        DivarContactFeatureConfig.objects.update_or_create(
            singleton_key='default',
            defaults={'rollout_mode': DivarContactFeatureConfig.RolloutMode.ADMIN_ONLY},
        )

    def test_persist_session_preserves_captcha_status(self):
        row = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121234567',
            auth_status=DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED,
            hip_status='captcha_blocked',
            encrypted_session=encrypt_payload(_session_payload()),
        )
        runtime = DivarUserRuntime()
        runtime.apply_session_payload(_session_payload())
        with patch.object(
            DivarUserRuntime,
            'health_check',
            return_value=SessionHealth(ok=True, needs_relogin=False, status='active'),
        ):
            _persist_session(row, runtime, preserve_captcha=True)
        row.refresh_from_db()
        self.assertEqual(row.auth_status, DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED)
        self.assertEqual(row.hip_status, 'captcha_blocked')

    def test_expired_session_shows_reconnect(self):
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121234567',
            auth_status=DivarAccountSession.AuthStatus.EXPIRED,
            encrypted_session=encrypt_payload(_session_payload()),
        )
        status = public_session_status(self.user)
        self.assertEqual(status['button_state'], 'reconnect')

    @patch('workspace.services.divar_session.service._try_refresh_session_row', return_value=False)
    def test_token_expiry_marks_reconnect_when_refresh_fails(self, _mock_refresh):
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121234567',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload()),
            token_expires_at=timezone.now() - timedelta(minutes=5),
        )
        status = public_session_status(self.user)
        self.assertEqual(status['button_state'], 'reconnect')

    @patch('workspace.services.divar_session.service._try_refresh_session_row', return_value=True)
    def test_token_expiry_refresh_keeps_fetch(self, _mock_refresh):
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121234567',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload()),
            token_expires_at=timezone.now() - timedelta(minutes=5),
        )
        status = public_session_status(self.user)
        self.assertEqual(status['button_state'], 'fetch')

    def test_captcha_status_includes_post_url(self):
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121234567',
            auth_status=DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED,
            captcha_post_url='https://divar.ir/v/abc',
            encrypted_session=encrypt_payload(_session_payload()),
        )
        status = public_session_status(self.user)
        self.assertEqual(status['captcha_post_url'], 'https://divar.ir/v/abc')

    @patch('workspace.services.divar_session.service.DivarUserRuntime.send_login_otp', return_value='09121234567')
    @patch('workspace.services.divar_session.service.DivarUserRuntime.export_otp_pending')
    def test_resend_otp_keeps_existing_session(self, mock_pending, _mock_send):
        mock_pending.return_value = {'phone': '09121234567', 'pre_auth_session_id': 'p'}
        encrypted = encrypt_payload(_session_payload())
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09121234567',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypted,
        )
        send_divar_otp(self.user, '09121234567')
        row = DivarAccountSession.objects.get(user=self.user, divar_phone='09121234567')
        self.assertEqual(row.encrypted_session, encrypted)
        self.assertEqual(get_primary_session(self.user).auth_status, DivarAccountSession.AuthStatus.CONNECTED)

    def test_decrypt_legacy_key_fallback(self):
        from cryptography.fernet import Fernet

        legacy = Fernet.generate_key().decode()
        token = Fernet(legacy.encode()).encrypt(b'{"phone":"09120000000","cookies":[]}').decode()
        with self.settings(DIVAR_SESSION_ENCRYPTION_KEY_LEGACY=legacy, DIVAR_SESSION_ENCRYPTION_KEY=''):
            data = decrypt_payload(token)
        self.assertEqual(data.get('phone'), '09120000000')

    def test_disconnect_pauses_linked_line(self):
        session = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09123334444',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload('09123334444')),
        )
        line = PhoneDetectorExtractionLine.objects.create(
            phone='09123334444',
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
            divar_account_session=session,
        )
        on_central_session_invalidated(session, reason='disconnected')
        line.refresh_from_db()
        self.assertEqual(line.operational_status, PhoneDetectorExtractionLine.OperationalStatus.PAUSED)

    @patch('accounts.services.phone_detector_line_ops._sessions_index_phones', return_value=['09127778888'])
    def test_sync_pauses_only_fk_linked_invalid_central(self, _mock_phones):
        from accounts.services.phone_detector_line_ops import sync_lines_from_sessions

        session = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09127778888',
            auth_status=DivarAccountSession.AuthStatus.EXPIRED,
        )
        linked = PhoneDetectorExtractionLine.objects.create(
            phone='09127778888',
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
            divar_account_session=session,
        )
        independent = PhoneDetectorExtractionLine.objects.create(
            phone='09128889999',
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09128889999',
            auth_status=DivarAccountSession.AuthStatus.EXPIRED,
        )
        sync_lines_from_sessions()
        linked.refresh_from_db()
        independent.refresh_from_db()
        self.assertEqual(linked.operational_status, PhoneDetectorExtractionLine.OperationalStatus.PAUSED)
        self.assertEqual(independent.operational_status, PhoneDetectorExtractionLine.OperationalStatus.ACTIVE)

    @patch('accounts.services.phone_detector_line_ops._sessions_index_phones', return_value=['09124445555'])
    def test_unlink_blocks_sync_recreate(self, _mock_phones):
        from accounts.services.phone_detector_line_ops import sync_lines_from_sessions

        session = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09124445555',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload('09124445555')),
            phone_detector_consent=True,
        )
        PhoneDetectorExtractionLine.objects.create(
            phone='09124445555',
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.PAUSED,
            divar_account_session=session,
        )
        unlink_session_from_line(session)
        self.assertTrue(is_phone_detector_file_sync_blocked('09124445555'))
        sync_lines_from_sessions()
        self.assertFalse(
            PhoneDetectorExtractionLine.objects.filter(
                phone='09124445555',
                operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
            ).exists(),
        )

    @patch('workspace.services.divar_session.service.session_operation_lock')
    @patch('workspace.services.divar_session.service._runtime_from_row')
    def test_fetch_captcha_does_not_flip_to_connected(self, mock_runtime, mock_lock):
        mock_lock.return_value.__enter__ = lambda s: None
        mock_lock.return_value.__exit__ = lambda s, *a: None
        row = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09125556666',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload('09125556666')),
        )
        runtime = MagicMock()
        runtime.health_check.return_value = SessionHealth(ok=True, needs_relogin=False, status='active')
        scraper = MagicMock()
        scraper.fetch_contact_phone.return_value = (None, None, 'captcha_blocked')
        runtime.make_scraper.return_value = scraper
        runtime.export_session_payload.return_value = _session_payload('09125556666')
        mock_runtime.return_value = runtime

        listing = MagicMock()
        listing.token = 'tok123'
        listing.link = 'https://divar.ir/v/tok123'
        listing.data = {'تماس_contact_uuid': 'cu-1'}

        result = fetch_listing_phone(self.user, listing)
        self.assertFalse(result['ok'])
        row.refresh_from_db()
        self.assertEqual(row.auth_status, DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED)
        self.assertEqual(row.captcha_post_url, 'https://divar.ir/v/tok123')

    @patch('workspace.services.divar_session.service.session_operation_lock')
    @patch('workspace.services.divar_session.service._runtime_from_row')
    def test_no_phone_does_not_expire_session(self, mock_runtime, mock_lock):
        mock_lock.return_value.__enter__ = lambda s: None
        mock_lock.return_value.__exit__ = lambda s, *a: None
        row = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09126667777',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload('09126667777')),
        )
        runtime = MagicMock()
        runtime.health_check.return_value = SessionHealth(ok=True, needs_relogin=False, status='active')
        scraper = MagicMock()
        scraper.fetch_contact_phone.return_value = (None, None, None)
        runtime.make_scraper.return_value = scraper
        mock_runtime.return_value = runtime

        listing = MagicMock()
        listing.token = 'tok999'
        listing.link = ''
        listing.data = {'تماس_contact_uuid': 'cu-9'}

        with self.assertRaises(DivarSessionError) as ctx:
            fetch_listing_phone(self.user, listing)
        self.assertEqual(ctx.exception.code, 'no_phone')
        row.refresh_from_db()
        self.assertEqual(row.auth_status, DivarAccountSession.AuthStatus.CONNECTED)

    def test_lock_release_does_not_clear_newer_lock(self):
        from workspace.divar_session_models import DivarAccountSession as SessionModel

        row = DivarAccountSession.objects.create(
            user=self.user,
            divar_phone='09120001111',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session=encrypt_payload(_session_payload('09120001111')),
        )
        newer = timezone.now() + timedelta(minutes=5)
        SessionModel.objects.filter(pk=row.pk).update(operation_lock_until=newer)
        stale_acquired = timezone.now() - timedelta(minutes=1)
        SessionModel.objects.filter(pk=row.pk, operation_lock_until=stale_acquired).update(
            operation_lock_until=None,
        )
        row.refresh_from_db()
        self.assertEqual(row.operation_lock_until, newer)
