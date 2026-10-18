"""E02 — استخراج پنل تجاری مشاور/آژانس (lazy + flatten + import)."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    _extract_consultant_from_widget_list,
    _normalize_business_lazy_rest_path,
    _normalize_consultant_active_ads_subtitle,
    export_rows_to_records,
    fetch_business_lazy_widgets,
    flatten_post_detail,
)
from workspace.models import Listing  # noqa: E402
from workspace.services.columns import export_record_to_listing_fields, extract_consultant_name  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "divar"


def _load_detail(token: str) -> dict:
    return json.loads((FIXTURES / f"{token}.json").read_text(encoding="utf-8"))


def _attach_lazy_widgets(detail: dict, token: str = "gayGYn4o") -> dict:
    lazy = json.loads((FIXTURES / f"{token}_business_lazy_widgets.json").read_text(encoding="utf-8"))
    detail = dict(detail)
    detail["business_lazy_widget_list"] = lazy.get("widget_list") or []
    return detail


class BusinessLazyPathTest(unittest.TestCase):
    def test_allowed_path_matches_token(self):
        path = "/v8/premium-user/post-page/business-data/gayGYn4o/lazy"
        self.assertEqual(_normalize_business_lazy_rest_path(path, "gayGYn4o"), path)

    def test_rejects_foreign_host_path(self):
        self.assertIsNone(
            _normalize_business_lazy_rest_path("https://evil.example/lazy", "gayGYn4o"),
        )

    def test_rejects_token_mismatch(self):
        path = "/v8/premium-user/post-page/business-data/otherToken/lazy"
        self.assertIsNone(_normalize_business_lazy_rest_path(path, "gayGYn4o"))


class ConsultantParserUnitTest(unittest.TestCase):
    def test_active_subtitle_rejects_bare_number(self):
        self.assertEqual(_normalize_consultant_active_ads_subtitle("۴"), "")
        self.assertEqual(_normalize_consultant_active_ads_subtitle("۱۴ آگهی فعال"), "۱۴ آگهی فعال")

    def test_unknown_widget_ignored(self):
        parsed = _extract_consultant_from_widget_list([
            {"widget_type": "UNKNOWN_ROW", "data": {"title": "x", "phone_text": "09"}},
            {
                "widget_type": "EVENT_ROW",
                "data": {
                    "title": "آژانس تست",
                    "subtitle": "۳ آگهی فعال",
                    "action": {"type": "PREMIUM_PANEL_BRAND_LANDING"},
                },
            },
        ])
        self.assertEqual(parsed["مشاور_نام"], "آژانس تست")
        self.assertEqual(parsed["مشاور_آگهی_فعال"], "۳ آگهی فعال")


class BusinessLazyFetchMockTest(unittest.TestCase):
    @patch("export_divar_items.request_with_retry")
    def test_personal_listing_skips_http(self, mock_retry):
        detail = _load_detail("gateBT51")
        widgets = fetch_business_lazy_widgets(detail, "gateBT51")
        self.assertEqual(widgets, [])
        mock_retry.assert_not_called()

    @patch("export_divar_items.request_with_retry")
    def test_premium_lazy_success(self, mock_retry):
        detail = _load_detail("gayGYn4o")
        lazy = json.loads((FIXTURES / "gayGYn4o_business_lazy_widgets.json").read_text(encoding="utf-8"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = lazy
        mock_retry.return_value = mock_resp
        widgets = fetch_business_lazy_widgets(detail, "gayGYn4o")
        self.assertEqual(len(widgets), 2)
        mock_retry.assert_called_once()

    @patch("export_divar_items.request_with_retry")
    def test_http_error_returns_empty(self, mock_retry):
        detail = _load_detail("gayGYn4o")
        mock_retry.return_value = None
        self.assertEqual(fetch_business_lazy_widgets(detail, "gayGYn4o"), [])

    @patch("export_divar_items.request_with_retry")
    def test_invalid_json_returns_empty(self, mock_retry):
        detail = _load_detail("gayGYn4o")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("x", "", 0)
        mock_retry.return_value = mock_resp
        self.assertEqual(fetch_business_lazy_widgets(detail, "gayGYn4o"), [])

    @patch("export_divar_items.request_with_retry")
    def test_invalid_path_skips_request(self, mock_retry):
        detail = _load_detail("gayGYn4o")
        detail["webengage"]["business_type"] = "personal"
        for sec in detail.get("sections") or []:
            if sec.get("section_name") != "BUSINESS_SECTION":
                continue
            for w in sec.get("widgets") or []:
                if w.get("widget_type") == "LAZY_SECTION":
                    w["data"]["rest_request_path"] = "/v8/evil/path"
        self.assertEqual(fetch_business_lazy_widgets(detail, "gayGYn4o"), [])
        mock_retry.assert_not_called()


class BusinessFlattenFixtureTest(SimpleTestCase):
    def test_personal_no_consultant_fields(self):
        flat = flatten_post_detail(_load_detail("gateBT51"))
        self.assertEqual(flat.get("business_type"), "personal")
        self.assertEqual(flat.get("مشاور_نام"), "")
        self.assertFalse(flat.get("مشاور_business_ref"))

    def test_premium_without_lazy_has_ref_only(self):
        flat = flatten_post_detail(_load_detail("gayGYn4o"))
        self.assertEqual(flat.get("business_type"), "premium-panel")
        self.assertEqual(flat.get("مشاور_business_ref"), "kCDVPCnz_BqldThbG")
        self.assertEqual(flat.get("مشاور_نام"), "")

    def test_premium_with_mock_lazy_full_pipeline(self):
        detail = _attach_lazy_widgets(_load_detail("gayGYn4o"))
        flat = flatten_post_detail(detail)
        rec = export_rows_to_records([flat], category="apartment-sell")[0]
        fields = export_record_to_listing_fields(rec)
        data = fields.get("data") or {}
        self.assertEqual(flat.get("مشاور_نام"), "املاک ارم شمرون")
        self.assertEqual(flat.get("مشاور_آگهی_فعال"), "۱۴ آگهی فعال")
        self.assertEqual(rec.get("نام مشاور / آژانس"), "املاک ارم شمرون")
        self.assertEqual(rec.get("آگهی‌های فعال مشاور"), "۱۴ آگهی فعال")
        self.assertEqual(rec.get("نوع آگهی دهنده"), "مشاور")
        self.assertEqual(extract_consultant_name(data), "املاک ارم شمرون")
        self.assertNotIn("hashed_post_owner_user_id", json.dumps(data, ensure_ascii=False))
        self.assertNotIn("business_lazy_widget_list", data)

    def test_incomplete_lazy_name_only(self):
        detail = _attach_lazy_widgets(_load_detail("gayGYn4o"))
        detail["business_lazy_widget_list"] = [{
            "widget_type": "EVENT_ROW",
            "data": {
                "title": "فقط نام",
                "subtitle": "۴",
                "action": {"type": "PREMIUM_PANEL_BRAND_LANDING"},
            },
        }]
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("مشاور_نام"), "فقط نام")
        self.assertEqual(flat.get("مشاور_آگهی_فعال"), "")


class BusinessReimportOrmTest(TestCase):
    def test_reimport_preserves_consultant_when_sparse(self):
        detail = _attach_lazy_widgets(_load_detail("gayGYn4o"))
        rec = export_rows_to_records([flatten_post_detail(detail)], category="apartment-sell")[0]
        fields = export_record_to_listing_fields(rec)
        listing = Listing(token="gayGYn4o", data=dict(fields["data"]))
        sparse = {"token": "gayGYn4o", "data": {"توضیحات": "ناقص"}}
        _update_listing_from_fields(listing, sparse)
        self.assertEqual(listing.data.get("مشاور_نام"), "املاک ارم شمرون")
        self.assertEqual(listing.data.get("مشاور_business_ref"), "kCDVPCnz_BqldThbG")

    def test_flatten_failure_lazy_does_not_break_listing_fields(self):
        detail = _load_detail("galOydW-")
        flat = flatten_post_detail(detail)
        fields = export_record_to_listing_fields(
            export_rows_to_records([flat], category="apartment-sell")[0],
        )
        self.assertEqual(flat.get("business_type"), "personal")
        self.assertTrue(fields.get("title"))


if __name__ == "__main__":
    unittest.main()
