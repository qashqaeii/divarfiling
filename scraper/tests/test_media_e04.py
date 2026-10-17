"""E04 — یکپارچگی رسانه (تصویر، اصالت، تزئینی)."""
import json
import sys
import unittest
from pathlib import Path

from django.test import SimpleTestCase, TestCase

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    _deduplicate_divar_image_urls,
    _flatten_passthrough_payload,
    _parse_decorative_image_tooltip,
    _parse_image_originality_answer,
    export_rows_to_records,
    flatten_post_detail,
)
from mobile_api.services.divar_flatten import _merge_client_images  # noqa: E402
from workspace.models import Listing  # noqa: E402
from workspace.services.columns import export_record_to_listing_fields  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "divar"


class MediaParserUnitTest(unittest.TestCase):
    def test_originality_yes_no_unknown(self):
        self.assertEqual(_parse_image_originality_answer("بله")["status"], "yes")
        self.assertEqual(_parse_image_originality_answer("خیر")["status"], "no")
        self.assertEqual(_parse_image_originality_answer("")["status"], "unknown")

    def test_decorative_tooltip_not_numeric(self):
        dec = _parse_decorative_image_tooltip("عکس‌ها: تزئینی")
        self.assertTrue(dec["decorative"])
        num = _parse_decorative_image_tooltip("۴")
        self.assertIsNone(num["decorative"])

    def test_dedupe_prefers_post_over_thumbnail(self):
        thumb = "https://s100.divarcdn.com/webp_thumbnail/foo.webp"
        full = "https://s100.divarcdn.com/webp_post/foo.webp"
        out = _deduplicate_divar_image_urls([thumb, full])
        self.assertEqual(len(out), 1)
        self.assertIn("/webp_post/", out[0])

    def test_passthrough_blocks_contact_metadata(self):
        payload = _flatten_passthrough_payload({
            "رسانه_تصاویر": "http://x",
            "تماس_contact_uuid": "secret",
            "سیستمی_webengage_price": 1,
        })
        self.assertIn("رسانه_تصاویر", payload)
        self.assertNotIn("تماس_contact_uuid", payload)
        self.assertNotIn("سیستمی_webengage_price", payload)


class MediaFixtureTest(SimpleTestCase):
    def test_galOydW_decorative_tooltip(self):
        detail = json.loads((FIXTURES / "galOydW-.json").read_text(encoding="utf-8"))
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("رسانه_تصاویر_تزئینی"), "بله")
        self.assertIn("تزئین", flat.get("رسانه_برچسب_تصاویر_tooltip", ""))

    def test_export_record_keeps_media_metadata(self):
        detail = json.loads((FIXTURES / "galOydW-.json").read_text(encoding="utf-8"))
        rec = export_rows_to_records([flatten_post_detail(detail)], category="apartment-sell")[0]
        fields = export_record_to_listing_fields(rec)
        data = fields["data"]
        self.assertEqual(data.get("رسانه_تصاویر_تزئینی"), "بله")
        self.assertIn("رسانه_اصالت_تصویر_وضعیت", data)


class MergeClientImagesTest(unittest.TestCase):
    def test_client_full_urls_before_thumbnail(self):
        row = {"token": "t1"}
        item = {
            "thumbnail_url": "https://s100.divarcdn.com/webp_thumbnail/a.webp",
            "image_urls": ["https://s100.divarcdn.com/webp_post/a.webp"],
        }
        _merge_client_images(row, item)
        self.assertIn("/webp_post/", row["لینک تصویر اول"])


class MediaReimportOrmTest(TestCase):
    def test_reimport_preserves_images_when_incoming_sparse(self):
        detail = json.loads((FIXTURES / "gateBT51.json").read_text(encoding="utf-8"))
        rec = export_rows_to_records([flatten_post_detail(detail)], category="apartment-rent")[0]
        fields = export_record_to_listing_fields(rec)
        images = fields.get("images") or []
        listing = Listing(token="gateBT51", images=images, data=dict(fields["data"]))
        sparse = dict(fields)
        sparse["images"] = []
        sparse["data"] = {"توضیحات": "only"}
        _update_listing_from_fields(listing, sparse)
        self.assertTrue(listing.images)
        self.assertIn("رسانه_تصاویر", listing.data)


if __name__ == "__main__":
    unittest.main()
