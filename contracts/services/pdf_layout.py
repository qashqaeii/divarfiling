"""Shared ReportLab layout helpers — safe page breaks for Persian PDFs."""
from __future__ import annotations

from typing import Any, Dict, List

from contracts.services.persian_text import rtl_paragraph_html

_C_PRIMARY = '#7c3aed'
_C_BORDER = '#e2e8f0'


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
    Article section with styled title band + body flowables.

    ReportLab cannot split a Paragraph that lives inside a single Table cell
    across pages (content gets clipped). Body items are therefore appended
    directly to the story so long clauses paginate correctly.
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
