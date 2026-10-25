from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ForumHiddenStateCssTests(SimpleTestCase):
    """Regression: flex bars ignored [hidden] before v5."""

    @classmethod
    def _forum_css(cls) -> str:
        path = Path(settings.BASE_DIR) / 'static' / 'community_forum' / 'css' / 'forum.css'
        return path.read_text(encoding='utf-8')

    def test_hidden_rule_covers_cf_page(self):
        css = self._forum_css()
        self.assertIn('.cf-page [hidden]', css)
        self.assertIn('display: none !important', css)

    def test_hidden_rule_covers_toast_and_dialogs(self):
        css = self._forum_css()
        self.assertIn('.cf-toast[hidden]', css)
        self.assertIn('.cf-dialog [hidden]', css)

    def test_flex_bars_still_declared_for_visible_state(self):
        css = self._forum_css()
        self.assertIn('.cf-reply-preview', css)
        self.assertIn('.cf-send-failed', css)
        self.assertIn('.cf-loading', css)


class ForumTemplateAssetVersionTests(SimpleTestCase):
    def test_forum_static_versions_bumped(self):
        path = Path(settings.BASE_DIR) / 'templates' / 'community_forum' / 'forum.html'
        html = path.read_text(encoding='utf-8')
        self.assertIn("community_forum/css/forum.css' %}?v=7", html)
        self.assertIn("community_forum/js/forum-emoji.js' %}?v=7", html)
        self.assertIn("community_forum/js/forum.js' %}?v=7", html)

    def test_composer_emoji_controls_present(self):
        path = Path(settings.BASE_DIR) / 'templates' / 'community_forum' / 'forum.html'
        html = path.read_text(encoding='utf-8')
        self.assertIn('id="cfEmojiToggle"', html)
        self.assertIn('id="cfEmojiPopover"', html)
