"""Regression coverage for Persian dates in newly generated contract PDFs."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, override_settings

from contracts.services.date_display import jalali_pdf_date, jalali_pdf_datetime


class ContractPdfJalaliDisplayTests(SimpleTestCase):
    def test_date_only_never_shifts_with_timezone(self):
        self.assertEqual(jalali_pdf_date(date(2026, 9, 10)), "۱۴۰۵/۰۶/۱۹")
        self.assertEqual(jalali_pdf_date(date(2025, 3, 20)), "۱۴۰۳/۱۲/۳۰")

    @override_settings(TIME_ZONE="UTC")
    def test_utc_instants_use_tehran_civil_date(self):
        self.assertEqual(
            jalali_pdf_datetime(datetime(2026, 9, 10, 22, 0, tzinfo=timezone.utc)),
            "۱۴۰۵/۰۶/۲۰ ۰۱:۳۰",
        )

    def test_midnight_is_explicitly_displayed(self):
        self.assertEqual(
            jalali_pdf_datetime(
                datetime(2026, 9, 10, 0, 0, tzinfo=ZoneInfo("Asia/Tehran"))
            ),
            "۱۴۰۵/۰۶/۱۹ ۰۰:۰۰",
        )

    def test_missing_date_has_neutral_placeholder(self):
        self.assertEqual(jalali_pdf_date(None), "—")
        self.assertEqual(jalali_pdf_datetime(None), "—")
