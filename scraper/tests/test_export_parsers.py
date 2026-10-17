"""تست پارسرهای export_divar_items — بدون API زنده."""
import sys
import unittest
from pathlib import Path

SCRAPER_DIR = Path(__file__).resolve().parents[1]
if str(SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPER_DIR))

from export_divar_items import (  # noqa: E402
    _rent_convertibility_from_feature_title,
    export_rows_to_records,
    flatten_post_detail,
    format_metraj_export,
    parse_area_sqm,
    parse_divar_schedule_label,
)


class MetrajParserTest(unittest.TestCase):
    def test_area_thousand_separators(self):
        cases = [
            ("۲,۴۰۰ متر مربع", 2400.0),
            ("2,400 متر", 2400.0),
            ("۲٬۴۰۰", 2400.0),
            ("۵۰۰ متر مربع", 500.0),
            ("۱۲۰", 120.0),
        ]
        for raw, expected in cases:
            self.assertEqual(parse_area_sqm(raw), expected)
            self.assertEqual(format_metraj_export(raw), str(int(expected)))

    def test_area_empty_is_unknown(self):
        self.assertIsNone(parse_area_sqm(""))
        self.assertEqual(format_metraj_export(""), "-")
        self.assertEqual(format_metraj_export(None), "-")


class RentSliderTest(unittest.TestCase):
    def test_rent_slider_uses_primary_not_transformed(self):
        detail = {
            "seo": {"web_info": {"title": "اجاره", "city_persian": "تهران"}},
            "share": {"web_url": "https://divar.ir/v/gayCl7bs"},
            "webengage": {
                "token": "gayCl7bs",
                "business_type": "personal",
                "credit": 17000000000,
                "rent": 45000000,
            },
            "sections": [
                {
                    "section_name": "LIST_DATA",
                    "widgets": [
                        {
                            "widget_type": "RENT_SLIDER",
                            "data": {
                                "credit": {
                                    "value": 18500000000,
                                    "transformed_value": 17000000000,
                                },
                                "rent": {
                                    "value": 100000,
                                    "transformed_value": 45000000,
                                },
                            },
                        },
                    ],
                },
            ],
        }
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("اجاره_ودیعه_عدد"), 18500000000)
        self.assertEqual(flat.get("اجاره_ماهانه_عدد"), 100000)
        self.assertEqual(flat.get("اجاره_ودیعه_تبدیل_عدد"), 17000000000)
        self.assertEqual(flat.get("اجاره_ماهانه_تبدیل_عدد"), 45000000)

        records = export_rows_to_records([flat], category="apartment-rent")
        self.assertEqual(records[0].get("ودیعه"), 18500000000)
        self.assertEqual(records[0].get("اجاره ماهانه"), 100000)


class SellPriceTitleTest(unittest.TestCase):
    def test_land_total_price_title(self):
        detail = {
            "seo": {"web_info": {"title": "زمین", "city_persian": "تهران"}},
            "share": {"web_url": "https://divar.ir/v/gaNLnNp6"},
            "webengage": {
                "token": "gaNLnNp6",
                "business_type": "personal",
                "price": 1,
            },
            "sections": [
                {
                    "section_name": "LIST_DATA",
                    "widgets": [
                        {
                            "widget_type": "UNEXPANDABLE_ROW",
                            "data": {"title": "متراژ", "value": "۲,۴۰۰ متر مربع"},
                        },
                        {
                            "widget_type": "UNEXPANDABLE_ROW",
                            "data": {
                                "title": "قیمت کل ملک",
                                "value": "۶۷۲٬۰۰۰٬۰۰۰٬۰۰۰ تومان",
                            },
                        },
                        {
                            "widget_type": "UNEXPANDABLE_ROW",
                            "data": {
                                "title": "قیمت هر متر",
                                "value": "۲۸۰٬۰۰۰٬۰۰۰ تومان",
                            },
                        },
                    ],
                },
            ],
        }
        records = export_rows_to_records([flatten_post_detail(detail)], category="residential-sell")
        rec = records[0]
        self.assertEqual(str(rec.get("متراژ")), "2400")
        self.assertEqual(rec.get("قیمت"), 672000000000)
        self.assertEqual(rec.get("قیمت هر متر"), 280000000)


class ConvertibilityTest(unittest.TestCase):
    def test_non_convertible_before_convertible_substring(self):
        self.assertEqual(
            _rent_convertibility_from_feature_title("ودیعه و اجاره غیر قابل تبدیل است"),
            "غیر قابل تبدیل",
        )
        self.assertEqual(
            _rent_convertibility_from_feature_title("ودیعه و اجارهٔ این ملک قابل تبدیل است"),
            "قابل تبدیل",
        )


class PublishScheduleTest(unittest.TestCase):
    def test_parse_divar_schedule_label(self):
        parsed = parse_divar_schedule_label("۲۱ شهریور ۱۴۰۵، ۱۳:۳۴")
        self.assertEqual(parsed, "1405/06/21 13:34")

    def test_flatten_publish_from_title_section(self):
        detail = {
            "seo": {"web_info": {"title": "آپارتمان", "city_persian": "تهران"}},
            "share": {"web_url": "https://divar.ir/v/galOydW-"},
            "webengage": {"token": "galOydW-", "business_type": "personal"},
            "sections": [
                {
                    "section_name": "TITLE",
                    "widgets": [
                        {
                            "widget_type": "EXPANDABLE_SECTION",
                            "data": {
                                "widget_list": [
                                    {
                                        "widget_type": "DESCRIPTION_ROW",
                                        "data": {"text": "انتشار: ۲۱ شهریور ۱۴۰۵، ۱۳:۳۴"},
                                    },
                                    {
                                        "widget_type": "DESCRIPTION_ROW",
                                        "data": {"text": "آخرین نردبان: ۱۶ مهر ۱۴۰۵، ۱۴:۰۲"},
                                    },
                                ],
                            },
                        },
                    ],
                },
            ],
        }
        flat = flatten_post_detail(detail)
        self.assertEqual(flat.get("انتشار_تاریخ_شمسی"), "1405/06/21 13:34")
        self.assertEqual(flat.get("انتشار_آخرین_نردبان_شمسی"), "1405/07/16 14:02")


if __name__ == "__main__":
    unittest.main()
