from django.template import Context, Template
from django.test import SimpleTestCase

from shop.decor_icons import DECOR_ICONS, ICON_SIZES
from shop.lucide_icons import DECOR_TO_LUCIDE, resolve_lucide_name, render_lucide_svg


class DecorIconTagTests(SimpleTestCase):
    def test_decor_icon_renders_svg(self):
        template = Template(
            '{% load decor_icons %}{% decor_icon "rocket" size="md" %}'
        )
        html = template.render(Context())
        self.assertIn('<svg', html)
        self.assertIn('df-decor-icon--md', html)
        self.assertNotIn('icons/rocket.png', html)

    def test_unknown_icon_renders_nothing(self):
        template = Template('{% load decor_icons %}{% decor_icon "missing" %}')
        html = template.render(Context())
        self.assertEqual(html.strip(), '')

    def test_registry_has_decor_icons(self):
        self.assertGreaterEqual(len(DECOR_ICONS), 40)
        self.assertIn('house', DECOR_ICONS)
        self.assertIn('elevator', DECOR_ICONS)

    def test_all_decor_icons_have_lucide_mapping(self):
        missing = [name for name in DECOR_ICONS if not resolve_lucide_name(name)]
        self.assertEqual(missing, [], msg=f'Missing Lucide mapping: {missing}')

    def test_icon_tag_renders_svg(self):
        template = Template('{% load icon_tags %}{% icon "upload" size="nav" %}')
        html = template.render(Context())
        self.assertIn('<svg', html)
        self.assertIn('data-icon-size="nav"', html)
        self.assertNotIn('width="', html)

    def test_render_lucide_svg_defers_stroke_to_css(self):
        html = str(render_lucide_svg('settings', size='sm'))
        self.assertIn('class="df-lucide-svg"', html)
        self.assertNotIn('stroke="currentColor"', html)
        self.assertNotIn('stroke-width', html)

    def test_context_sizes(self):
        self.assertEqual(ICON_SIZES['nav'], 20)
        self.assertEqual(ICON_SIZES['inline'], 18)
        self.assertEqual(ICON_SIZES['metric'], 24)


class LucideMappingTests(SimpleTestCase):
    def test_key_mappings(self):
        cases = {
            'upload': 'cloud-upload',
            'building': 'building-2',
            'user': 'user-round',
            'users': 'users-round',
            'folder': 'files',
            'map_pin': 'map-pin',
            'handshake': 'briefcase',
            'calendar': 'calendar-days',
            'bell': 'bell-dot',
            'help_center': 'circle-help',
            'settings': 'settings-2',
            'trending_up': 'chart-no-axes-combined',
            'house': 'layout-dashboard',
            'team': 'contact-round',
        }
        for decor, lucide in cases.items():
            self.assertEqual(resolve_lucide_name(decor), lucide)
            self.assertIn(lucide, DECOR_TO_LUCIDE.values())

    def test_extra_icons(self):
        self.assertEqual(resolve_lucide_name('ai'), 'sparkles')
        self.assertEqual(resolve_lucide_name('exit'), 'log-out')
