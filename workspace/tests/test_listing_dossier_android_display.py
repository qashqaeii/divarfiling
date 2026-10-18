"""پرونده آگهی — پنهان‌سازی کلیدهای فنی JSON اندروید و نمایش مالی/مکان."""
from django.test import SimpleTestCase

from workspace.models import Listing
from workspace.services.display import (
    apply_convertible_rent_to_dossier,
    build_listing_display_data,
    dedupe_listing_dossier_rows,
    format_field_rows,
    format_sections,
    location_accuracy_for_map,
    resolve_convertible_rent_card,
    transaction_profile,
)


def _rent_listing(data: dict, **fields) -> Listing:
    return Listing(
        token='t-rent',
        title='اجاره تست',
        deposit=fields.get('deposit'),
        rent=fields.get('rent'),
        price=None,
        area=fields.get('area', 250),
        city=fields.get('city', 'فریدون‌کنار'),
        neighborhood='',
        data=data,
    )


class ListingDossierAndroidDisplayTests(SimpleTestCase):
    def _convertible_android_raw(self):
        return {
            'مالی_قیمت_کل_وضعیت': 'unknown',
            'مالی_قیمت_کل_عدد': 0,
            'مالی_قیمت_هر_متر_وضعیت': 'unknown',
            'مالی_منبع_قیمت_وب‌انگیج': 'تومان',
            'اجاره_ودیعه_وضعیت': 'numeric',
            'اجاره_ودیعه_عدد': 3_000_000_000,
            'اجاره_ودیعه_تبدیل_عدد': 1_300_000_000,
            'اجاره_ماهانه_وضعیت': 'numeric',
            'اجاره_ماهانه_عدد': 0,
            'اجاره_ماهانه_تبدیل_عدد': 50_000_000,
            'اجاره_قابل_تبدیل': 'قابل تبدیل',
            'متراژ_عدد': 250,
            'متراژ': 250,
        }

    def test_convertible_rent_hides_internal_money_keys(self):
        raw = self._convertible_android_raw()
        listing = _rent_listing(raw, deposit=3_000_000_000, rent=0, area=250)
        self.assertEqual(listing.data.get('اجاره_ودیعه_عدد'), 3_000_000_000)

        profile = transaction_profile('اجاره')
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        self.assertNotIn('اجاره_ودیعه_وضعیت', data)
        self.assertNotIn('مالی_قیمت_کل_عدد', data)
        self.assertNotIn('متراژ_عدد', data)

        sections = format_sections(data, profile)
        money = sections.get('مالی', {})
        self.assertIn('ودیعه', money)
        self.assertIn('اجاره', money)
        self.assertIn('ودیعه و اجاره', money)
        self.assertIn('ودیعه (شرایط تبدیل)', money)
        self.assertIn('اجاره ماهانه (شرایط تبدیل)', money)
        self.assertNotIn('اجاره_ودیعه_عدد', money)
        labels = [r['key'] for r in dedupe_listing_dossier_rows(format_field_rows(money, data))]
        self.assertEqual(labels.count('ودیعه'), 1)

    def test_convertible_rent_card_dual_mode_android(self):
        raw = self._convertible_android_raw()
        listing = _rent_listing(raw, deposit=3_000_000_000, rent=0, area=250)
        profile = transaction_profile('اجاره')
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        card = resolve_convertible_rent_card(listing, data, profile, raw_data=raw)
        self.assertTrue(card['show_card'])
        self.assertEqual(card['states']['base']['deposit'], 3_000_000_000)
        self.assertEqual(card['states']['base']['rent'], 0)
        self.assertEqual(card['states']['alt']['deposit'], 1_300_000_000)
        self.assertEqual(card['states']['alt']['rent'], 50_000_000)
        self.assertEqual(card['states']['base']['rent_label'], 'رایگان')

        sections = format_sections(data, profile)
        section_rows = {
            name: dedupe_listing_dossier_rows(format_field_rows(fields, data))
            for name, fields in sections.items()
        }
        apply_convertible_rent_to_dossier(sections, section_rows, card)
        money_rows = section_rows.get('مالی', [])
        raw_keys = {r.get('raw_key') for r in money_rows}
        self.assertFalse(raw_keys & {'ودیعه', 'اجاره', 'ودیعه (شرایط تبدیل)'})

    def test_convertible_rent_card_excel_style_keys(self):
        raw = {
            'ودیعه': 3_000_000_000,
            'اجاره': 0,
            'ودیعه (شرایط تبدیل)': 1_300_000_000,
            'اجاره ماهانه (شرایط تبدیل)': 50_000_000,
            'ودیعه و اجاره': 'قابل تبدیل',
        }
        listing = _rent_listing(raw, deposit=3_000_000_000, rent=0)
        profile = transaction_profile('اجاره')
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        card = resolve_convertible_rent_card(listing, data, profile, raw_data=raw)
        self.assertTrue(card['show_card'])

    def test_convertible_rent_partial_data_no_card(self):
        raw = {
            'اجاره_قابل_تبدیل': 'قابل تبدیل',
            'اجاره_ودیعه_عدد': 2_000_000_000,
            'اجاره_ماهانه_عدد': 10_000_000,
        }
        listing = _rent_listing(raw, deposit=2_000_000_000, rent=10_000_000)
        profile = transaction_profile('اجاره')
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        card = resolve_convertible_rent_card(listing, data, profile, raw_data=raw)
        self.assertFalse(card['show_card'])
        self.assertTrue(card['convertible'])

    def test_rent_without_convertibility(self):
        raw = {
            'اجاره_ودیعه_عدد': 500_000_000,
            'اجاره_ماهانه_عدد': 12_000_000,
            'اجاره_قابل_تبدیل': 'غیر قابل تبدیل',
        }
        listing = _rent_listing(raw, deposit=500_000_000, rent=12_000_000)
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        sections = format_sections(data, transaction_profile('اجاره'))
        money = sections.get('مالی', {})
        self.assertNotIn('ودیعه (شرایط تبدیل)', money)
        self.assertNotIn('اجاره ماهانه (شرایط تبدیل)', money)

    def test_sale_apartment_price_fields(self):
        raw = {
            'مالی_قیمت_کل_وضعیت': 'numeric',
            'مالی_قیمت_کل_عدد': 672_000_000_000,
            'مالی_قیمت_هر_متر_عدد': 280_000_000,
            'اجاره_ودیعه_عدد': 1,
        }
        listing = Listing(
            token='t-sale',
            title='فروش',
            price=672_000_000_000,
            deposit=None,
            rent=None,
            area=2400,
            city='تهران',
            data=raw,
        )
        data = build_listing_display_data(listing, {}, transaction_type='فروش')
        sections = format_sections(data, transaction_profile('فروش'))
        money = sections.get('مالی', {})
        self.assertIn('قیمت', money)
        self.assertIn('قیمت هر متر', money)
        self.assertNotIn('ودیعه', money)
        self.assertNotIn('اجاره_ودیعه_عدد', data)

    def test_textual_money_unknown_status(self):
        raw = {
            'مالی_قیمت_کل_وضعیت': 'negotiable',
            'مالی_قیمت_کل_نمایش': 'توافقی',
            'اجاره_ودیعه_وضعیت': 'customary',
            'اجاره_ودیعه_نمایش': 'متعارف',
            'اجاره_ماهانه_نمایش': 'متعارف',
        }
        listing = _rent_listing(raw, deposit=None, rent=None)
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        sections = format_sections(data, transaction_profile('اجاره'))
        money = sections.get('مالی', {})
        self.assertEqual(money.get('ودیعه'), 'متعارف')
        self.assertEqual(money.get('اجاره'), 'متعارف')
        self.assertNotIn('unknown', ' '.join(money.values()).lower())

    def test_location_exact_and_fuzzy(self):
        raw_exact = {
            'شهر': 'فریدون‌کنار',
            'آدرس': 'فریدون‌کنار',
            'مکان_آدرس': 'فریدون‌کنار',
            'مکان_مختصات_اعتبار': 'valid',
            'نوع مختصات': 'EXACT',
        }
        listing = _rent_listing(raw_exact)
        data = build_listing_display_data(listing, {}, transaction_type='اجاره')
        self.assertNotIn('مکان_آدرس', data)
        self.assertNotIn('مکان_مختصات_اعتبار', data)
        self.assertNotIn('valid', data.values())
        loc = format_sections(data, transaction_profile('اجاره')).get('مکان', {})
        self.assertEqual(loc.get('نوع مختصات'), 'دقیق')
        self.assertNotIn('آدرس', loc)

        raw_fuzzy = {
            'شهر': 'رامسر',
            'نوع مختصات': 'FUZZY',
            'در شعاع (متر)': 500,
            'مکان_مختصات_اعتبار': 'fuzzy',
        }
        listing_f = _rent_listing(raw_fuzzy, city='رامسر')
        data_f = build_listing_display_data(listing_f, {}, transaction_type='اجاره')
        acc = location_accuracy_for_map(data_f)
        self.assertIn('تقریبی', acc.get('label', ''))
        self.assertEqual(
            format_sections(data_f, transaction_profile('اجاره')).get('مکان', {}).get('نوع مختصات'),
            'تقریبی',
        )

    def test_legacy_excel_minimal_fields(self):
        listing = Listing(
            token='legacy',
            title='قدیمی',
            price=1_000_000_000,
            deposit=None,
            rent=None,
            area=90,
            city='تهران',
            neighborhood='صادقیه',
            data={'قیمت': 1_000_000_000, 'متراژ': 90, 'شهر': 'تهران', 'محله': 'صادقیه'},
        )
        data = build_listing_display_data(listing, {}, transaction_type='فروش')
        sections = format_sections(data, transaction_profile('فروش'))
        self.assertIn('قیمت', sections.get('مالی', {}))
        self.assertIn('متراژ', sections.get('ملک', {}))
        self.assertIn('شهر', sections.get('مکان', {}))
