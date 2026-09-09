"""Persian/Arabic text shaping for ReportLab and other renderers."""
from __future__ import annotations

import html
import re
from functools import lru_cache
from pathlib import Path

_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')


def contains_arabic_script(text: str) -> bool:
    return bool(text and _ARABIC_RE.search(text))


def prepare_rtl_text(text: str) -> str:
    """Reshape + bidi reorder Persian/Arabic for LTR renderers (ReportLab)."""
    if not text:
        return ''
    raw = str(text)
    if not contains_arabic_script(raw):
        return raw
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = arabic_reshaper.reshape(raw)
        try:
            return get_display(reshaped, base_dir='R')
        except TypeError:
            return get_display(reshaped)
    except Exception:
        return raw


def _reshape_line(line: str) -> str:
    """Arabic/Persian glyph shaping only — no bidi reorder (ReportLab Paragraph wraps itself)."""
    if not line or not contains_arabic_script(line):
        return line or ''
    try:
        import arabic_reshaper
        return arabic_reshaper.reshape(line)
    except Exception:
        return line


def rtl_paragraph_html(text: str, *, bold: bool = False) -> str:
    """Plain text → reshaped + escaped HTML for ReportLab Paragraph (TA_RIGHT)."""
    lines = (text or '').split('\n')
    parts = [html.escape(_reshape_line(line)) for line in lines]
    body = '<br/>'.join(parts)
    return f'<b>{body}</b>' if bold else body


def rtl_plain(text: str) -> str:
    """Shaped plain string for Table cells / canvas.drawString."""
    return prepare_rtl_text(text or '')


@lru_cache(maxsize=1)
def resolve_persian_font_paths() -> tuple[str, str]:
    """
    Return (regular_path, bold_path). Bold falls back to regular.
  Search bundled assets, then OS fonts.
    """
    base = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
    blog_fonts = Path(__file__).resolve().parent.parent.parent / 'blog' / 'assets' / 'fonts'
    candidates_regular = [
        base / 'Vazirmatn-Regular.ttf',
        base / 'Vazirmatn-Medium.ttf',
        blog_fonts / 'Vazirmatn-Regular.ttf',
        blog_fonts / 'Vazirmatn-Medium.ttf',
        Path('C:/Windows/Fonts/tahoma.ttf'),
        Path('C:/Windows/Fonts/arial.ttf'),
        Path('C:/Windows/Fonts/B Nazanin.ttf'),
        Path('/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf'),
        Path('/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf'),
        Path('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'),
        Path('/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    ]
    candidates_bold = [
        base / 'Vazirmatn-Bold.ttf',
        base / 'Vazirmatn-SemiBold.ttf',
        blog_fonts / 'Vazirmatn-Bold.ttf',
        blog_fonts / 'Vazirmatn-SemiBold.ttf',
        Path('C:/Windows/Fonts/tahomabd.ttf'),
        Path('C:/Windows/Fonts/arialbd.ttf'),
        Path('/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf'),
        Path('/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf'),
    ]
    regular = next((str(p) for p in candidates_regular if p.is_file()), '')
    bold = next((str(p) for p in candidates_bold if p.is_file()), '') or regular
    return regular, bold
