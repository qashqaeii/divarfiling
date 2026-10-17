"""F07/Q02 — قیمت متنی، صفر، و نامشخص."""
import sys
import unittest
from pathlib import Path

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    export_rows_to_records,
    flatten_post_detail,
    parse_divar_money_display,
    parse_money_to_int,
)
from workspace.services.columns import export_record_to_listing_fields  # noqa: E402
from workspace.services.display import format_display_value, listing_map_price_label  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402
from workspace.models import Listing  # noqa: E402


class ParseDivarMoneyDisplayTest(unittest.TestCase):
    def test_numeric_and_zero(self):
        self.assertEqual(parse_divar_money_display("۱۲۰,۰۰۰,۰۰۰ تومان")["status"], "numeric")
        self.assertEqual(parse_divar_money_display("۱۲۰,۰۰۰,۰۰۰ تومان")["amount"], 120000000)
        self.assertEqual(parse_divar_money_display("۰ تومان")["status"], "zero")
        self.assertEqual(parse_divar_money_display("۰ تومان")["amount"], 0)

    def test_textual_states(self):
        self.assertEqual(parse_divar_money_display("رایگان")["status"], "free")
        self.assertEqual(parse_divar_money_display("توافقی")["status"], "negotiable")
        self.assertEqual(parse_divar_money_display("متعارف")["status"], "customary")
        self.assertEqual(parse_divar_money_display("رهن کامل")["status"], "full_deposit")

    def test_unknown_empty(self):
        self.assertEqual(parse_divar_money_display("")["status"], "unknown")
        self.assertIsNone(parse_divar_money_display("")["amount"])


class NegotiableBlocksWebengageTest(unittest.TestCase):
    def test_sell_negotiable_ignores_webengage_price(self):
        detail = {
            "seo": {"web_info": {"title": "آپارتمان", "city_persian": "تهران"}},
            "share": {"web_url": "https://divar.ir/v/test-negotiable"},
            "webengage": {
                "token": "test-negotiable",
                "business_type": "personal",
                "price": 999000000,
            },
            "sections": [
                {
                    "section_name": "LIST_DATA",
                    "widgets": [
                        {
                            "widget_type": "UNEXPANDABLE_ROW",
                            "data": {"title": "قیمت کل", "value": "توافقی"},
                        },
                    ],
                },
            ],
        }
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("مالی_قیمت_کل_وضعیت"), "negotiable")
        self.assertIsNone(flat.get("مالی_قیمت_کل_عدد"))
        rec = export_rows_to_records([flat], category="apartment-sell")[0]
        self.assertEqual(rec.get("قیمت"), "توافقی")
        fields = export_record_to_listing_fields(rec)
        self.assertIsNone(fields["price"])
        self.assertEqual(fields["data"].get("مالی_قیمت_کل_وضعیت"), "negotiable")


class ZeroDisplayTest(unittest.TestCase):
    def test_format_display_zero_not_dash(self):
        self.assertIn("0", format_display_value("قیمت", 0))
        self.assertIn("0", format_display_value("اجاره ماهانه", "0"))


class ReimportTextualPriceTest(unittest.TestCase):
    def test_reimport_clears_stale_numeric_price(self):
        listing = Listing(token="t1", price=500_000_000, data={"قیمت": 500_000_000})
        fields = {
            "price": None,
            "deposit": None,
            "rent": None,
            "data": {
                "قیمت": "توافقی",
                "مالی_قیمت_کل_وضعیت": "negotiable",
                "مالی_قیمت_کل_نمایش": "توافقی",
            },
        }
        self.assertTrue(_update_listing_from_fields(listing, fields))
        self.assertIsNone(listing.price)


class ListingMapZeroPriceTest(unittest.TestCase):
    def test_zero_price_shown(self):
        listing = Listing(token="z", price=0)
        label = listing_map_price_label(
            listing,
            {"show_price": True, "show_rent": False, "show_deposit": False, "is_rent": False},
        )
        self.assertIn("0", label)


if __name__ == "__main__":
    unittest.main()
