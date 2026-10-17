"""E05 — ویژگی‌های زمین و ملک کلنگی (modal، chip، import)."""
import json
import sys
import unittest
from pathlib import Path

from django.test import SimpleTestCase, TestCase

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    FEATURE_EXCEL_COLUMNS,
    _parse_feature_widget_list,
    export_rows_to_records,
    flatten_post_detail,
    parse_area_sqm,
)
from workspace.models import Listing  # noqa: E402
from workspace.services.columns import export_record_to_listing_fields  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "divar"

LAND_EXPECT_GA_NLN = {
    "کاربری ملک": "مسکونی",
    "موقعیت ملک": "دوکله",
    "وضعیت سند": "قولنامه",
    "قابل معاوضه": "دارد",
}

DILAP_EXPECT_GA_TJ = {
    "کاربری ملک": "مسکونی",
    "جهت ملک": "شمالی",
    "وضعیت سند": "سند تک‌برگ",
    "دسترسی به انشعابات": "همه",
    "مناسب برای": "سرمایه‌گذاری",
    "عرض ملک": "۱۶ متر",
    "عرض گذر": "۳۲ متر",
    "بنای کلنگی": "دارد",
}


class FeatureParserUnitTest(unittest.TestCase):
    def test_thousand_separator_area(self):
        self.assertEqual(parse_area_sqm("۲,۴۰۰ متر مربع"), 2400.0)
        self.assertEqual(parse_area_sqm("2,400"), 2400.0)

    def test_chip_list_from_description_wrapper(self):
        widgets = [
            {
                "widget_type": "DESCRIPTION_ROW",
                "data": {"text": "مناسب برای"},
            },
            {
                "widget_type": "WRAPPER_ROW",
                "data": {"chip_list": {"chips": [{"text": "سرمایه‌گذاری"}, {"text": "ساخت"}]}},
            },
        ]
        parsed = _parse_feature_widget_list(widgets)
        self.assertEqual(parsed["مناسب برای"], "سرمایه‌گذاری، ساخت")

    def test_position_vs_direction_distinct(self):
        widgets = [
            {"widget_type": "UNEXPANDABLE_ROW", "data": {"title": "موقعیت ملک", "value": "دوکله"}},
            {"widget_type": "UNEXPANDABLE_ROW", "data": {"title": "جهت ملک", "value": "شمالی"}},
        ]
        parsed = _parse_feature_widget_list(widgets)
        self.assertEqual(parsed["موقعیت ملک"], "دوکله")
        self.assertEqual(parsed["جهت ملک"], "شمالی")

    def test_list_data_metrage_over_subtitle(self):
        detail = json.loads((FIXTURES / "gaNLnNp6.json").read_text(encoding="utf-8"))
        for sec in detail.get("sections") or []:
            if sec.get("section_name") == "TITLE":
                for w in sec.get("widgets") or []:
                    if w.get("widget_type") == "LEGEND_TITLE_ROW":
                        w.setdefault("data", {})["subtitle"] = "۲۲۰۴ متر"
        flat = flatten_post_detail(detail)
        self.assertEqual(int(float(flat.get("متراژ"))), 2400)


class LandPlotFixtureTest(SimpleTestCase):
    def test_gaNLnNp6_land_features(self):
        detail = json.loads((FIXTURES / "gaNLnNp6.json").read_text(encoding="utf-8"))
        flat = flatten_post_detail(detail)
        rec = export_rows_to_records([flat], category="plot-old")[0]
        fields = export_record_to_listing_fields(rec)
        data = fields.get("data") or {}
        self.assertEqual(int(fields.get("area")), 2400)
        for key, val in LAND_EXPECT_GA_NLN.items():
            self.assertEqual(flat.get(key), val, key)
            self.assertEqual(rec.get(key), val, key)
            self.assertEqual(data.get(key), val, key)
        self.assertNotIn("جهت ملک", flat)

    def test_gaTjEd6J_dilapidated_features(self):
        detail = json.loads((FIXTURES / "gaTjEd6J.json").read_text(encoding="utf-8"))
        flat = flatten_post_detail(detail)
        rec = export_rows_to_records([flat], category="plot-old")[0]
        fields = export_record_to_listing_fields(rec)
        data = fields.get("data") or {}
        for key, val in DILAP_EXPECT_GA_TJ.items():
            self.assertEqual(flat.get(key), val, key)
            self.assertEqual(data.get(key), val, key)
        self.assertNotIn("موقعیت ملک", flat)

    def test_apartment_fixture_no_land_only_fields(self):
        detail = json.loads((FIXTURES / "gateBT51.json").read_text(encoding="utf-8"))
        flat = flatten_post_detail(detail)
        self.assertNotIn("بنای کلنگی", flat)
        self.assertNotIn("عرض گذر", flat)

    def test_feature_excel_columns_include_land(self):
        for col in ("کاربری ملک", "موقعیت ملک", "جهت ملک", "بنای کلنگی", "دسترسی به انشعابات", "عرض گذر"):
            self.assertIn(col, FEATURE_EXCEL_COLUMNS)


class PropertyFeaturesReimportOrmTest(TestCase):
    def test_reimport_preserves_land_features_when_sparse(self):
        detail = json.loads((FIXTURES / "gaTjEd6J.json").read_text(encoding="utf-8"))
        rec = export_rows_to_records([flatten_post_detail(detail)], category="plot-old")[0]
        fields = export_record_to_listing_fields(rec)
        listing = Listing(
            token="gaTjEd6J",
            area=fields["area"],
            data=dict(fields["data"]),
        )
        sparse = dict(fields)
        sparse["data"] = {"توضیحات": "فقط متن"}
        _update_listing_from_fields(listing, sparse)
        for key, val in DILAP_EXPECT_GA_TJ.items():
            self.assertEqual(listing.data.get(key), val, key)

    def test_reimport_preserves_coords_when_only_map_type_in_data(self):
        detail = json.loads((FIXTURES / "gateBT51.json").read_text(encoding="utf-8"))
        fields = export_record_to_listing_fields(
            export_rows_to_records([flatten_post_detail(detail)], category="apartment-rent")[0],
        )
        listing = Listing(
            token="gateBT51",
            latitude=fields["latitude"],
            longitude=fields["longitude"],
            data={"نقشه_نوع": "EXACT"},
        )
        orig_lat, orig_lng = listing.latitude, listing.longitude
        sparse = dict(fields)
        sparse["latitude"] = None
        sparse["longitude"] = None
        sparse["data"] = {"نقشه_نوع": "FUZZY", "توضیحات": "ناقص"}
        _update_listing_from_fields(listing, sparse)
        self.assertEqual(listing.latitude, orig_lat)
        self.assertEqual(listing.longitude, orig_lng)

    def test_reimport_does_not_clear_video_flag_without_url(self):
        listing = Listing(
            token="vid-t",
            data={"رسانه_ویدیو_دارد": "1", "رسانه_ویدیو": "https://video.example/x.mp4"},
        )
        sparse = {"token": "vid-t", "data": {"توضیحات": "بدون رسانه"}}
        _update_listing_from_fields(listing, sparse)
        self.assertEqual(listing.data.get("رسانه_ویدیو_دارد"), "1")
        self.assertIn("video.example", listing.data.get("رسانه_ویدیو", ""))

    def test_legacy_row_without_new_land_keys_still_imports(self):
        row = {
            "token": "legacy-plot",
            "title": "زمین",
            "متراژ": 1000,
            "قیمت": 1000000000,
            "کاربری ملک": "مسکونی",
        }
        fields = export_record_to_listing_fields(row)
        self.assertEqual(fields["data"].get("کاربری ملک"), "مسکونی")
        self.assertEqual(int(fields.get("area")), 1000)


if __name__ == "__main__":
    unittest.main()
