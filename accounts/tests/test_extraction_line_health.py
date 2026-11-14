"""تست ممیزی آفلاین خطوط استخراج."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import PhoneDetectorExtractionLine
from accounts.services.extraction_line_health import (
    VERDICT_LABELS_FA,
    audit_extraction_line,
    audit_all_extraction_lines,
)
from workspace.divar_session_models import DivarAccountSession

User = get_user_model()


class ExtractionLineHealthOfflineTests(TestCase):
    @patch('accounts.services.extraction_line_health.session_file_exists', return_value=True)
    def test_admin_paused_verdict(self, _has_file):
        line = PhoneDetectorExtractionLine.objects.create(
            phone='09110001111',
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.PAUSED,
            admin_hold=True,
        )
        row = audit_extraction_line(line, probe=False)
        self.assertEqual(row['verdict'], 'admin_paused')
        self.assertEqual(row['verdict_label'], VERDICT_LABELS_FA['admin_paused'])

    @patch('accounts.services.extraction_line_health.session_file_exists', return_value=False)
    def test_missing_session_file(self, _has_file):
        line = PhoneDetectorExtractionLine.objects.create(
            phone='09110002222',
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.ACTIVE,
        )
        row = audit_extraction_line(line, probe=False)
        self.assertEqual(row['verdict'], 'session_file_missing')

    @patch('accounts.services.extraction_line_health.session_file_exists', return_value=True)
    def test_manual_with_filing_session_linked_not_duplicate(self, _has_file):
        user = User.objects.create_user(username='u1', phone='09120000001', password='x')
        session = DivarAccountSession.objects.create(
            user=user,
            divar_phone='09113334444',
            auth_status=DivarAccountSession.AuthStatus.CONNECTED,
            encrypted_session='enc',
        )
        line = PhoneDetectorExtractionLine.objects.create(
            phone='09113334444',
            line_source=PhoneDetectorExtractionLine.LineSource.MANUAL,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.BLOCKED_CAPTCHA,
            divar_account_session=session,
        )
        row = audit_extraction_line(line, probe=False)
        self.assertEqual(row['verdict'], 'captcha')
        qs = audit_all_extraction_lines(probe=False)
        phones = [r['phone'] for r in qs]
        self.assertEqual(phones.count('09113334444'), 1)

    @patch('accounts.services.extraction_line_health.session_file_exists', return_value=True)
    def test_central_expired_offline(self, _has_file):
        user = User.objects.create_user(username='u2', phone='09120000002', password='x')
        session = DivarAccountSession.objects.create(
            user=user,
            divar_phone='09115556666',
            auth_status=DivarAccountSession.AuthStatus.EXPIRED,
            encrypted_session='enc',
        )
        line = PhoneDetectorExtractionLine.objects.create(
            phone='09115556666',
            line_source=PhoneDetectorExtractionLine.LineSource.FILING,
            divar_account_session=session,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.EVICTED,
        )
        row = audit_extraction_line(line, probe=False)
        self.assertEqual(row['verdict'], 'session_expired')