"""Unit tests for shared desktop license validation rules."""
import sys
from datetime import timedelta
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))

from license_core import (
    evaluate_offline_validation,
    is_expired,
    merge_server_payload,
    now_utc,
    offline_grace_active,
)


class LicenseCoreTests(TestCase):
    def test_expired_license_detected(self):
        past = (now_utc() - timedelta(days=1)).isoformat()
        self.assertTrue(is_expired(past))

    def test_offline_requires_prior_server_validation(self):
        ok, err = evaluate_offline_validation({'expires_at': None})
        self.assertFalse(ok)
        self.assertIn('آنلاین', err)

    def test_offline_grace_respected(self):
        data = {
            'expires_at': (now_utc() + timedelta(days=10)).isoformat(),
            'last_server_validation_at': now_utc().isoformat(),
            'offline_grace_until': (now_utc() + timedelta(hours=48)).isoformat(),
        }
        ok, err = evaluate_offline_validation(data)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertTrue(offline_grace_active(data))

    def test_merge_server_payload_sets_last_validation(self):
        merged = merge_server_payload(
            {'license_key': 'ABCD-1234-5678-9ABC'},
            {'valid': True, 'expires_at': '2030-01-01T00:00:00+00:00'},
        )
        self.assertIn('last_server_validation_at', merged)
