from django.template import Context, Template
from django.test import SimpleTestCase

from shop.decor_icons import DECOR_ICONS


class DecorIconTagTests(SimpleTestCase):
    def test_decor_icon_renders_img(self):
        template = Template(
            '{% load decor_icons %}{% decor_icon "rocket" size="md" %}'
        )
        html = template.render(Context())
        self.assertIn('icons/rocket.png', html)
        self.assertIn('df-decor-icon--md', html)
        self.assertIn('<img', html)

    def test_unknown_icon_renders_nothing(self):
        template = Template('{% load decor_icons %}{% decor_icon "missing" %}')
        html = template.render(Context())
        self.assertEqual(html.strip(), '')

    def test_registry_has_decor_icons(self):
        self.assertGreaterEqual(len(DECOR_ICONS), 40)
        self.assertIn('house', DECOR_ICONS)
        self.assertIn('calculator', DECOR_ICONS)
