"""E2E: JSON واقعی → flatten → export → فیلدهای Listing (آفلاین)."""
import json
import sys
import unittest
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER_DIR = Path(__file__).resolve().parents[1]
DJANGO_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "divar"
MONOREPO_SRC = DJANGO_DIR.parent / "src"

if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import export_rows_to_records, flatten_post_detail  # noqa: E402

from workspace.services.columns import export_record_to_listing_fields  # noqa: E402
from workspace.services.display import to_jalali_display  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402
from workspace.models import Listing  # noqa: E402

KIND_TO_EXPORT_CATEGORY = {
    "apartment_rent": "apartment-rent",
    "apartment_sell": "apartment-sell",
    "premium_panel_sell": "apartment-sell",
    "convertible_rent": "apartment-rent",
    "plot_old_sell": "plot-old",
}


def _load_json(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _norm_shamsi(val: str) -> str:
    s = str(val or "").strip()
    if len(s) >= 16 and s[4] == "/" and s[13] == ":":
        return s[:16]
    return s


class RealFixturesPipelineTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES_DIR / "expected_cases.json", encoding="utf-8") as f:
            cls.expected = json.load(f)

    def _pipeline(self, token: str):
        detail = _load_json(f"{token}.json")
        kind = self.expected[token]["kind"]
        category = KIND_TO_EXPORT_CATEGORY[kind]
        flat = flatten_post_detail(detail)
        records = export_rows_to_records([flat], category=category)
        self.assertEqual(len(records), 1)
        rec = records[0]
        fields = export_record_to_listing_fields(rec)
        return flat, rec, fields

    def test_all_six_fixtures_publish_dates(self):
        for token, exp in self.expected.items():
            flat, rec, fields = self._pipeline(token)
            self.assertEqual(
                _norm_shamsi(flat.get("انتشار_تاریخ_شمسی")),
                exp["published_jalali"],
                token,
            )
            self.assertEqual(
                _norm_shamsi(rec.get("ایجاد آگهی")),
                exp["published_jalali"],
                token,
            )
            self.assertEqual(
                _norm_shamsi(rec.get("تاریخ انتشار")),
                exp["published_jalali"],
                token,
            )
            bump = exp.get("last_bumped_jalali")
            bump_val = _norm_shamsi(flat.get("انتشار_آخرین_نردبان_شمسی") or rec.get("آخرین نردبان") or "-")
            if bump is None:
                self.assertIn(bump_val, ("-", "—", ""), msg=token)
            else:
                self.assertEqual(bump_val, bump, token)
            self.assertIsNotNone(fields.get("published_at"), token)
            display = to_jalali_display(fields["published_at"])
            self.assertEqual(_norm_shamsi(display), exp["published_jalali"], token)

    def test_land_and_price_fixtures(self):
        for token in ("gaNLnNp6", "gaTjEd6J"):
            exp = self.expected[token]
            _flat, rec, fields = self._pipeline(token)
            self.assertEqual(int(float(rec.get("متراژ"))), exp["area_sqm"], token)
            self.assertEqual(int(rec.get("قیمت")), exp["price_toman"], token)
            self.assertEqual(int(rec.get("قیمت هر متر")), exp["price_per_sqm_toman"], token)
            self.assertEqual(int(fields.get("price")), exp["price_toman"], token)
            self.assertEqual(int(fields.get("area")), exp["area_sqm"], token)

    def test_convertible_rent_fixture(self):
        exp = self.expected["gayCl7bs"]
        _flat, rec, fields = self._pipeline("gayCl7bs")
        self.assertEqual(int(rec.get("ودیعه")), exp["original_deposit_toman"])
        self.assertEqual(int(rec.get("اجاره ماهانه")), exp["original_rent_toman"])
        self.assertEqual(int(fields.get("deposit")), exp["original_deposit_toman"])
        self.assertEqual(int(fields.get("rent")), exp["original_rent_toman"])

    def test_no_synthetic_publish_from_expiry_only(self):
        detail = _load_json("gaNLnNp6.json")
        detail["seo"] = {"unavailable_after": "2030-01-15T12:00:00Z", "web_info": {}}
        for sec in detail.get("sections") or []:
            if sec.get("section_name") == "TITLE":
                sec["widgets"] = []
        flat = flatten_post_detail(detail)
        rec = export_rows_to_records([flat], category="plot-old")[0]
        self.assertEqual(str(rec.get("ایجاد آگهی")).strip(), "-")
        self.assertFalse(flat.get("انتشار_تاریخ_شمسی"))

    def test_reimport_preserves_publish_when_incoming_has_no_explicit_date(self):
        exp = self.expected["galOydW-"]
        _flat, rec, fields = self._pipeline("galOydW-")
        listing = Listing(
            token="galOydW-",
            title="t",
            published_at=fields["published_at"],
            data=dict(rec),
        )
        stale_fields = dict(fields)
        stale_fields["published_at"] = None
        stale_fields["data"] = {k: v for k, v in rec.items() if k not in ("ایجاد آگهی", "تاریخ انتشار", "انتشار_تاریخ_شمسی")}
        original_pub = listing.published_at
        _update_listing_from_fields(listing, stale_fields)
        self.assertEqual(listing.published_at, original_pub)
        self.assertEqual(to_jalali_display(listing.published_at), exp["published_jalali"])

    def test_windows_src_byte_identical_to_django_scraper(self):
        django_file = SCRAPER_DIR / "export_divar_items.py"
        src_file = MONOREPO_SRC / "export_divar_items.py"
        if not src_file.exists():
            self.skipTest("src export module not present")
        self.assertEqual(
            django_file.read_bytes(),
            src_file.read_bytes(),
            "src/export_divar_items.py must stay synced with django/scraper",
        )


if __name__ == "__main__":
    unittest.main()
