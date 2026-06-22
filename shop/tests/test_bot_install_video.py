"""Tests for bot install video helper."""
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from shop.bot_install_video import (
    BOT_INSTALL_VIDEO_MEDIA,
    get_bot_install_video_context,
    get_bot_install_video_url,
    resolve_guide_video,
)


@override_settings(MEDIA_ROOT='/tmp/test-media', MEDIA_URL='/media/')
class BotInstallVideoTests(SimpleTestCase):
    def test_missing_file_returns_unavailable(self):
        with patch('shop.bot_install_video.bot_install_video_exists', return_value=False):
            ctx = get_bot_install_video_context()
        self.assertFalse(ctx['available'])
        self.assertEqual(ctx['mode'], 'none')

    def test_existing_file_returns_media_url(self):
        with patch('shop.bot_install_video.bot_install_video_exists', return_value=True):
            url = get_bot_install_video_url()
        self.assertEqual(url, f'/media/{BOT_INSTALL_VIDEO_MEDIA}')

    def test_resolve_guide_video_uses_default_when_url_empty(self):
        with patch('shop.bot_install_video.bot_install_video_exists', return_value=True):
            mode, src = resolve_guide_video({'url': ''})
        self.assertEqual(mode, 'file')
        self.assertIn('ROBOT-INSTALLING.mp4', src)

    def test_resolve_guide_video_embed(self):
        mode, src = resolve_guide_video({'url': 'https://www.youtube.com/embed/abc'})
        self.assertEqual(mode, 'embed')
        self.assertEqual(src, 'https://www.youtube.com/embed/abc')

    def test_resolve_guide_video_media_prefix(self):
        fake = Path('/tmp/test-media/Video/custom.mp4')
        with patch('shop.bot_install_video.bot_install_video_exists', return_value=False):
            with patch.object(Path, 'is_file', return_value=True):
                mode, src = resolve_guide_video({'url': 'media:Video/custom.mp4'})
        self.assertEqual(mode, 'file')
        self.assertEqual(src, '/media/Video/custom.mp4')
