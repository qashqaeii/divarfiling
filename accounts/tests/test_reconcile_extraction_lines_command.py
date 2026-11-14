"""تست exit code دستور reconcile_extraction_lines."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class ReconcileExtractionLinesCommandTests(TestCase):
    @patch(
        'accounts.management.commands.reconcile_extraction_lines.reconcile_extraction_lines',
        return_value={'ok': False, 'skipped_concurrent': True},
    )
    def test_exits_nonzero_when_lock_busy(self, _mock):
        with self.assertRaises(CommandError):
            call_command('reconcile_extraction_lines', stdout=StringIO())

    @patch(
        'accounts.management.commands.reconcile_extraction_lines.reconcile_extraction_lines',
        return_value={'ok': False, 'reason': 'phone_detector_not_configured'},
    )
    def test_exits_nonzero_when_reconcile_fails(self, _mock):
        with self.assertRaises(CommandError):
            call_command('reconcile_extraction_lines', stdout=StringIO())

    @patch(
        'accounts.management.commands.reconcile_extraction_lines.reconcile_extraction_lines',
        return_value={'ok': True, 'provisioned': 0},
    )
    def test_exits_zero_on_success(self, _mock):
        out = StringIO()
        call_command('reconcile_extraction_lines', stdout=out)
        self.assertIn('OK', out.getvalue())