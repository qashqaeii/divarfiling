"""F08 — قرارداد مشترک خروجی فروش/اجاره و سازگاری Import."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    SHARED_EXPORT_EXCEL_COLUMNS,
    SHARED_SCHEDULE_EXPORT_COLUMNS,
    export_rows_to_records,
    export_to_csv,
    export_to_json,
    flatten_post_detail,
)
from workspace.models import Listing  # noqa: E402
from workspace.services.columns import export_record_to_listing_fields  # noqa: E402
from workspace.services.importer import _update_listing_from_fields  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "divar"

KIND_TO_CATEGORY = {
    "apartment_rent": "apartment-rent",
    "apartment_sell": "apartment-sell",
    "premium_panel_sell": "apartment-sell",
    "convertible_rent": "apartment-rent",
    "plot_old_sell": "plot-old",
}

# ستون‌هایی که در هر دو مسیر باید وجود داشته باشند (مقدار می‌تواند «-» باشد)
F08_SHARED_EXPORT_COLUMNS = frozenset({
    "شناسه", "عنوان", "لینک", "شماره تماس",
    *SHARED_SCHEDULE_EXPORT_COLUMNS,
    *SHARED_EXPORT_EXCEL_COLUMNS,
    "شهر", "محله", "متراژ", "ساخت", "اتاق", "طبقه",
    "آسانسور", "پارکینگ", "انباری",
    "نوع آگهی دهنده", "نام مشاور / آژانس", "آگهی‌های فعال مشاور",
    "عرض جغرافیایی", "طول جغرافیایی", "نوع مختصات", "در شعاع (متر)",
    "تعداد تصاویر", "ویدیو دارد؟",
    "ویژگی‌ها و امکانات", "توضیحات",
    "لینک تصاویر", "لینک تصویر اول",
})

F08_SELL_ONLY = frozenset({"قیمت", "قیمت هر متر"})
F08_RENT_ONLY = frozenset({"ودیعه", "اجاره ماهانه", "ودیعه و اجاره"})


def _load_expected():
    with open(FIXTURES_DIR / "expected_cases.json", encoding="utf-8") as f:
        return json.load(f)


class ExportContractParityTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = _load_expected()

    def _record(self, token: str):
        detail = json.loads((FIXTURES_DIR / f"{token}.json").read_text(encoding="utf-8"))
        kind = self.expected[token]["kind"]
        cat = KIND_TO_CATEGORY[kind]
        flat = flatten_post_detail(detail)
        rec = export_rows_to_records([flat], category=cat)[0]
        return flat, rec, kind

    def test_all_fixtures_have_shared_columns(self):
        for token in self.expected:
            _flat, rec, kind = self._record(token)
            missing = F08_SHARED_EXPORT_COLUMNS - set(rec.keys())
            self.assertFalse(missing, f"{token} missing shared cols: {missing}")

    def test_sell_and_rent_only_columns(self):
        for token, meta in self.expected.items():
            _flat, rec, _kind = self._record(token)
            keys = set(rec.keys())
            is_rent = "rent" in KIND_TO_CATEGORY[meta["kind"]]
            if is_rent:
                self.assertTrue(F08_RENT_ONLY <= keys, token)
            else:
                self.assertTrue(F08_SELL_ONLY <= keys, token)

    def test_csv_json_same_keys_as_record(self):
        token = "galOydW-"
        flat, rec, _ = self._record(token)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "out.csv"
            json_path = Path(tmp) / "out.json"
            export_to_csv([flat], str(csv_path))
            export_to_json([flat], str(json_path))
            import pandas as pd

            csv_cols = set(pd.read_csv(csv_path, encoding="utf-8-sig").columns)
            json_rows = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(json_rows), 1)
            json_keys = set(json_rows[0].keys())
            export_keys = set(rec.keys())
            self.assertTrue(F08_SHARED_EXPORT_COLUMNS <= csv_cols)
            self.assertTrue(F08_SHARED_EXPORT_COLUMNS <= json_keys)
            self.assertTrue(F08_SHARED_EXPORT_COLUMNS <= export_keys)

    def test_flatten_passthrough_in_listing_data(self):
        token = "gayCl7bs"
        _flat, rec, _ = self._record(token)
        fields = export_record_to_listing_fields(rec)
        data = fields["data"]
        self.assertIn("اجاره_ودیعه_تبدیل_عدد", data)
        self.assertIn("اجاره_ماهانه_تبدیل_عدد", data)
        self.assertIn("دسته‌بندی_عنوان", data)


class ExportContractReimportTest(SimpleTestCase):
    def test_reimport_keeps_category_when_incoming_sparse(self):
        token = "gateBT51"
        detail = json.loads((FIXTURES_DIR / f"{token}.json").read_text(encoding="utf-8"))
        rec = export_rows_to_records([flatten_post_detail(detail)], category="apartment-rent")[0]
        fields = export_record_to_listing_fields(rec)
        listing = Listing(token=token, title="old", data=dict(fields["data"]))
        original_cat = listing.data.get("دسته‌بندی_عنوان")
        sparse_fields = dict(fields)
        sparse_fields["title"] = "new title"
        sparse_fields["data"] = {"توضیحات": "only desc"}
        self.assertTrue(_update_listing_from_fields(listing, sparse_fields))
        self.assertEqual(listing.data.get("دسته‌بندی_عنوان"), original_cat)
        self.assertEqual(listing.data.get("توضیحات"), "only desc")


if __name__ == "__main__":
    unittest.main()
