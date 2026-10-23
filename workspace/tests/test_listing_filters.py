from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Dataset, Listing
from workspace.services.filters import (
    apply_amenity_filters,
    apply_listing_filters,
    normalize_listing_search_query,
    parse_filter_params,
    parse_filter_params_from_mapping,
)


class ListingSearchQueryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='searchuser', password='pass', phone='09128887766')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='search-test',
            original_filename='s.xlsx',
            file_format='xlsx',
        )
        self.by_token = Listing.objects.create(
            dataset=self.dataset,
            token='gabTSMvj',
            title='آپارتمان نمونه',
        )
        Listing.objects.create(
            dataset=self.dataset,
            token='otherTok',
            title='ویلا شمال',
        )

    def test_q_matches_divar_token(self):
        qs = apply_listing_filters(self.dataset.listings.all(), {'q': 'gabTSMvj'}, self.user)
        self.assertEqual(list(qs), [self.by_token])

    def test_q_matches_partial_token(self):
        qs = apply_listing_filters(self.dataset.listings.all(), {'q': 'gabTS'}, self.user)
        self.assertEqual(list(qs), [self.by_token])

    def test_q_extracts_token_from_divar_url(self):
        self.assertEqual(
            normalize_listing_search_query('https://divar.ir/v/gabTSMvj'),
            'gabTSMvj',
        )
        qs = apply_listing_filters(
            self.dataset.listings.all(),
            {'q': 'https://divar.ir/v/gabTSMvj'},
            self.user,
        )
        self.assertEqual(list(qs), [self.by_token])


class ListingRoomsFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='filteruser', password='pass', phone='09129999999')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='rooms-filter-test',
            original_filename='t.xlsx',
            file_format='xlsx',
        )
        self.three_rooms = Listing.objects.create(
            dataset=self.dataset,
            token='r3',
            title='آپارتمان 3 خواب',
            rooms='',
            data={'اتاق': '۳'},
        )
        self.two_rooms = Listing.objects.create(
            dataset=self.dataset,
            token='r2',
            title='دو خواب',
            rooms='2',
        )

    def test_rooms_filter_matches_data_json_when_db_field_empty(self):
        qs = apply_listing_filters(self.dataset.listings.all(), {'rooms': '3'}, self.user)
        filtered = apply_amenity_filters(list(qs), {'rooms': '3'})
        tokens = {lst.token for lst in filtered}
        self.assertIn('r3', tokens)
        self.assertNotIn('r2', tokens)

    def test_rooms_filter_accepts_persian_digits(self):
        qs = apply_listing_filters(self.dataset.listings.all(), {'rooms': '۳'}, self.user)
        filtered = apply_amenity_filters(list(qs), {'rooms': '۳'})
        self.assertEqual({lst.token for lst in filtered}, {'r3'})

    def test_map_markers_include_rooms_from_data_json(self):
        from workspace.services.charts import map_markers

        self.three_rooms.latitude = 35.7
        self.three_rooms.longitude = 51.4
        self.three_rooms.save(update_fields=['latitude', 'longitude'])
        markers = map_markers([self.three_rooms])
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]['rooms'], '3')

    def test_parse_filter_params_normalizes_rooms(self):
        class Req:
            GET = {'rooms': '3'}
        self.assertEqual(parse_filter_params(Req())['rooms'], '3')

    def test_year_params_reject_phone_and_out_of_range(self):
        parsed = parse_filter_params_from_mapping({
            'year_min': '0935792033',
            'year_max': '۱۴۰۳',
        })
        self.assertIsNone(parsed['year_min'])
        self.assertEqual(parsed['year_max'], 1403)

    def test_year_params_accept_jalali_range(self):
        parsed = parse_filter_params_from_mapping({'year_min': '1395', 'year_max': '1400'})
        self.assertEqual(parsed['year_min'], 1395)
        self.assertEqual(parsed['year_max'], 1400)
