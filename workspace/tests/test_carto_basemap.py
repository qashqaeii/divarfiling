from django.test import SimpleTestCase, override_settings

from workspace.carto_basemap import (
    carto_tile_template,
    carto_tile_url,
    get_carto_basemap_api_key,
)


@override_settings(CARTO_BASEMAP_API_KEY='')
class CartoBasemapWithoutKeyTests(SimpleTestCase):
    def test_missing_key_returns_empty(self):
        self.assertEqual(get_carto_basemap_api_key(), '')

    def test_tile_template_without_key(self):
        self.assertIsNone(carto_tile_template('voyager'))
        self.assertIsNone(carto_tile_url('light', sub='a', z=10, x=1, y=2))


@override_settings(CARTO_BASEMAP_API_KEY='test-carto-key')
class CartoBasemapWithKeyTests(SimpleTestCase):
    def test_tile_template_includes_key_param(self):
        tmpl = carto_tile_template('voyager')
        self.assertIn('basemaps.cartocdn.com/rastertiles/voyager', tmpl)
        self.assertIn('?key=test-carto-key', tmpl)

    def test_tile_url_formats_coordinates(self):
        url = carto_tile_url('dark', sub='b', z=12, x=3, y=4)
        self.assertEqual(
            url,
            'https://b.basemaps.cartocdn.com/dark_all/12/3/4.png?key=test-carto-key',
        )


@override_settings(CARTO_BASEMAP_API_KEY='article-test-key')
class MarketArticleTileUrlTests(SimpleTestCase):
    def test_carto_style_includes_key(self):
        from blog.services.market_article_assets import _tile_url

        url = _tile_url('street', 10, 1, 2)
        self.assertIn('?key=article-test-key', url)
        self.assertIn('rastertiles/voyager', url)

    def test_missing_key_falls_back_to_osm(self):
        from blog.services.market_article_assets import _tile_url

        with override_settings(CARTO_BASEMAP_API_KEY=''):
            url = _tile_url('light', 10, 1, 2)
        self.assertIn('tile.openstreetmap.org', url)
