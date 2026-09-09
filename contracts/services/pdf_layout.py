"""Shared ReportLab layout helpers — safe page breaks for Persian PDFs."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from contracts.services.persian_text import rtl_paragraph_html

_C_PRIMARY = '#7c3aed'

_SENTENCE_SPLIT = re.compile(r'(?<=[\.؛!\?؟])\s+')


def body_to_flowables(body: str, style, *, max_chunk: int = 260) -> List[Any]:
    """
    Split legal clause text into multiple Paragraph flowables.

    ReportLab cannot paginate a Paragraph inside a Table cell. Even outside
    tables, pre-bidi text may fail to split — smaller chunks are safer.
    """
    from reportlab.platypus import Paragraph, Spacer

    text = (body or '').strip()
    if not text:
        return []

    chunks: List[str] = []
    for block in re.split(r'\n\s*\n', text):
        block = block.strip()
        if not block:
            continue
        for line in block.split('\n'):
            line = line.strip()
            if not line:
                continue
            if len(line) <= max_chunk:
                chunks.append(line)
                continue
            parts = [p.strip() for p in _SENTENCE_SPLIT.split(line) if p.strip()]
            if len(parts) <= 1:
                parts = [line]
            buf = ''
            for part in parts:
                if len(part) > max_chunk:
                    if buf:
                        chunks.append(buf)
                        buf = ''
                    for i in range(0, len(part), max_chunk):
                        chunks.append(part[i:i + max_chunk])
                    continue
                candidate = f'{buf} {part}'.strip() if buf else part
                if len(candidate) <= max_chunk:
                    buf = candidate
                else:
                    if buf:
                        chunks.append(buf)
                    buf = part
            if buf:
                chunks.append(buf)

    flowables: List[Any] = []
    for i, chunk in enumerate(chunks):
        flowables.append(Paragraph(rtl_paragraph_html(chunk), style))
        if i < len(chunks) - 1:
            flowables.append(Spacer(1, 4))
    return flowables


def article_box(
    title: str,
    content_flowables: List[Any],
    content_width: float,
    styles: Dict,
    *,
    title_style: str = 'heading',
    border_width: float = 0.55,
    title_line_width: float = 1.2,
) -> List[Any]:
    """
    Article section: styled title band + body flowables in the story.

    Body items are NOT wrapped in a Table so Paragraphs can paginate.
    """
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    if not content_flowables:
        return []

    result: List[Any] = []

    title_tbl = Table(
        [[Paragraph(rtl_paragraph_html(title, bold=True), styles[title_style])]],
        colWidths=[content_width],
    )
    title_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), border_width, colors.HexColor('#cbd5e1')),
        ('LINEBELOW', (0, 0), (-1, -1), title_line_width, colors.HexColor(_C_PRIMARY)),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    result.append(title_tbl)

    for item in content_flowables:
        result.append(item)

    result.append(Spacer(1, 10))
    return result
