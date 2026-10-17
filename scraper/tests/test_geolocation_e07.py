"""E07 — یکپارچگی موقعیت مکانی (EXACT / FUZZY / شعاع)."""
import json
import sys
import unittest
from pathlib import Path

from django.test import SimpleTestCase, TestCase

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    _extract_map_fields_from_sections,
    _normalize_lat_lng_pair,
    export_rows_to_records,
    flatten_post_detail,
)
from workspace.models import Listing  # noqa: E402
from workspace.services.columns import export_record_to_listing_fields  # noqa: E402
from workspace.services.display import location_accuracy_for_map  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "divar"


class GeoParserUnitTest(unittest.TestCase):
    def test_swap_lat_lng_when_inverted(self):
        lat, lng = _normalize_lat_lng_pair(51.4, 35.7)
        self.assertAlmostEqual(lat, 35.7)
        self.assertAlmostEqual(lng, 51.4)

    def test_fuzzy_with_radius(self):
        sections = [{
            "section_name": "MAP",
            "widgets": [{
                "widget_type": "MAP_ROW",
                "data": {
                    "location": {
                        "type": "FUZZY",
                        "fuzzy_data": {
                            "point": {"latitude": 35.75, "longitude": 51.33},
                            "radius": 500,
                        },
                    },
                    "image_url": "https://map.example/x",
                },
            }],
        }]
        m = _extract_map_fields_from_sections(sections)
        self.assertEqual(m["نقشه_نوع"], "FUZZY")
        self.assertEqual(m["نقشه_شعاع_محدوده_متر"], "500")
        self.assertEqual(m["مکان_مختصات_اعتبار"], "valid")

    def test_fuzzy_without_radius(self):
        sections = [{
            "section_name": "MAP",
            "widgets": [{
                "widget_type": "MAP_ROW",
                "data": {
                    "location": {
                        "type": "FUZZY",
                        "fuzzy_data": {"point": {"latitude": 35.0, "longitude": 51.0}},
                    },
                },
            }],
        }]
        m = _extract_map_fields_from_sections(sections)
        self.assertEqual(m["نقشه_شعاع_محدوده_متر"], "")
        self.assertEqual(m["نقشه_نوع"], "FUZZY")

    def test_exact_does_not_set_radius(self):
        sections = [{
            "section_name": "MAP",
            "widgets": [{
                "widget_type": "MAP_ROW",
                "data": {
                    "location": {
                        "type": "EXACT",
                        "exact_data": {"point": {"latitude": 30.34, "longitude": 48.29}},
                    },
                },
            }],
        }]
        m = _extract_map_fields_from_sections(sections)
        self.assertEqual(m["نقشه_نوع"], "EXACT")
        self.assertEqual(m["نقشه_شعاع_محدوده_متر"], "")


class GeoFixtureTest(SimpleTestCase):
    def test_gateBT51_exact(self):
        detail = json.loads((FIXTURES / "gateBT51.json").read_text(encoding="utf-8"))
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("نقشه_نوع"), "EXACT")
        self.assertEqual(flat.get("مکان_مختصات_اعتبار"), "valid")
        self.assertFalse(flat.get("نقشه_شعاع_محدوده_متر"))

    def test_galOydW_fuzzy_500(self):
        detail = json.loads((FIXTURES / "galOydW-.json").read_text(encoding="utf-8"))
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("نقشه_نوع"), "FUZZY")
        self.assertEqual(str(flat.get("نقشه_شعاع_محدوده_متر")), "500")

    def test_display_no_guessed_radius(self):
        acc = location_accuracy_for_map({"نقشه_نوع": "FUZZY"})
        self.assertEqual(acc["kind"], "approx")
        self.assertEqual(acc["radius_m"], 0)

    def test_import_listing_fields(self):
        detail = json.loads((FIXTURES / "galOydW-.json").read_text(encoding="utf-8"))
        rec = export_rows_to_records([flatten_post_detail(detail)], category="apartment-sell")[0]
        fields = export_record_to_listing_fields(rec)
        self.assertIsNotNone(fields.get("latitude"))
        self.assertEqual(fields["data"].get("نقشه_نوع"), "FUZZY")


class GeoReimportOrmTest(TestCase):
    def test_reimport_preserves_coords_without_explicit_incoming(self):
        detail = json.loads((FIXTURES / "gateBT51.json").read_text(encoding="utf-8"))
        fields = export_record_to_listing_fields(
            export_rows_to_records([flatten_post_detail(detail)], category="apartment-rent")[0],
        )
        listing = Listing(
            token="gateBT51",
            latitude=fields["latitude"],
            longitude=fields["longitude"],
            data=dict(fields["data"]),
        )
        original_lat = listing.latitude
        sparse = dict(fields)
        sparse["latitude"] = None
        sparse["longitude"] = None
        sparse["data"] = {"توضیحات": "only"}
        _update_listing_from_fields(listing, sparse)
        self.assertEqual(listing.latitude, original_lat)
        self.assertEqual(listing.data.get("نقشه_نوع"), "EXACT")


if __name__ == "__main__":
    unittest.main()
