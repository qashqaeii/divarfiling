"""PDF صورت‌جلسه تحویل — طراحی حرفه‌ای هم‌سطح PDF قرارداد."""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.core.files.base import ContentFile
from django.utils import timezone

from contracts.constants import HANDOVER_CONDITION_STATUSES, HANDOVER_METER_UTILITIES
from contracts.models import ContractHandover
from contracts.services.persian_text import (
    prepare_rtl_text,
    resolve_persian_font_paths,
    rtl_paragraph_html,
    rtl_plain,
)

logger = logging.getLogger(__name__)

_FONT_REGULAR = 'HPF'
_FONT_BOLD = 'HPF-Bold'
_C_PRIMARY = '#7c3aed'
_C_BORDER = '#e2e8f0'
_C_TEXT = '#0f172a'
_C_MUTED = '#64748b'
_STATUS_LABELS = dict(HANDOVER_CONDITION_STATUSES)
_METER_LABELS = {u: label for u, label, _icon, _unit in HANDOVER_METER_UTILITIES}


def _register_fonts() -> tuple[str, str]:
    regular_path, bold_path = resolve_persian_font_paths()
    font_regular = 'Helvetica'
    font_bold = 'Helvetica-Bold'
    if not regular_path:
        return font_regular, font_bold
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont(_FONT_REGULAR, regular_path))
        font_regular = _FONT_REGULAR
        if bold_path:
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, bold_path))
            font_bold = _FONT_BOLD
        else:
            font_bold = _FONT_REGULAR
    except Exception as exc:
        logger.warning('Handover PDF font registration failed: %s', exc)
    return font_regular, font_bold


def _pdf_styles(font_name: str, font_bold: str):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle

    return {
        'title': ParagraphStyle(
            'hoTitle', fontName=font_bold, fontSize=16, alignment=TA_CENTER, leading=24,
            textColor=colors.HexColor(_C_TEXT),
        ),
        'subtitle': ParagraphStyle(
            'hoSub', fontName=font_name, fontSize=9.5, alignment=TA_CENTER, leading=15,
            textColor=colors.HexColor(_C_MUTED),
        ),
        'heading': ParagraphStyle(
            'hoHead', fontName=font_bold, fontSize=11.5, alignment=TA_RIGHT, leading=18,
            textColor=colors.HexColor(_C_TEXT),
        ),
        'body': ParagraphStyle(
            'hoBody', fontName=font_name, fontSize=9.5, alignment=TA_RIGHT, leading=16,
            textColor=colors.HexColor('#1e293b'),
        ),
        'meta': ParagraphStyle(
            'hoMeta', fontName=font_name, fontSize=8.5, alignment=TA_RIGHT, leading=13,
            textColor=colors.HexColor(_C_MUTED),
        ),
        'footer': ParagraphStyle(
            'hoFoot', fontName=font_name, fontSize=8, alignment=TA_CENTER, leading=12,
            textColor=colors.grey,
        ),
        'card_role': ParagraphStyle(
            'hoRole', fontName=font_bold, fontSize=9.5, alignment=TA_RIGHT, leading=14,
            textColor=colors.HexColor(_C_PRIMARY),
        ),
        'card_label': ParagraphStyle(
            'hoLbl', fontName=font_name, fontSize=7.5, alignment=TA_RIGHT, leading=11,
            textColor=colors.HexColor(_C_MUTED),
        ),
        'card_value': ParagraphStyle(
            'hoVal', fontName=font_bold, fontSize=9, alignment=TA_RIGHT, leading=13,
            textColor=colors.HexColor(_C_TEXT),
        ),
    }


def _article_box(title: str, content: List[Any], content_width: float, styles: Dict) -> List[Any]:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    if not content:
        return []
    rows = [[Paragraph(rtl_paragraph_html(title, bold=True), styles['heading'])]]
    for item in content:
        rows.append([item])
    tbl = Table(rows, colWidths=[content_width])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.55, colors.HexColor(_C_BORDER)),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, colors.HexColor(_C_PRIMARY)),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return [tbl, Spacer(1, 10)]


def _kv_grid(pairs: List[Tuple[str, str]], content_width: float, styles: Dict):
    from reportlab.platypus import Paragraph, Table, TableStyle

    rows = []
    col_w = content_width / 2 - 6
    for i in range(0, len(pairs), 2):
        cells = []
        for label, value in pairs[i:i + 2]:
            cells.append([
                Paragraph(rtl_paragraph_html(label), styles['card_label']),
                Paragraph(rtl_paragraph_html(value or '—', bold=True), styles['card_value']),
            ])
        while len(cells) < 2:
            cells.append([Paragraph('', styles['meta']), Paragraph('', styles['meta'])])
        rows.append(cells)
    tbl = Table(rows, colWidths=[col_w, col_w], hAlign='RIGHT')
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _party_card(party: Optional[dict], role_title: str, styles: Dict) -> List[Any]:
    from reportlab.platypus import Paragraph, Spacer

    if not party:
        return [Paragraph(rtl_paragraph_html('—'), styles['body'])]
    name = f"{party.get('first_name') or ''} {party.get('last_name') or ''}".strip() or '—'
    cell = [
        Paragraph(rtl_paragraph_html(role_title, bold=True), styles['card_role']),
        Spacer(1, 4),
        Paragraph(rtl_paragraph_html('نام'), styles['card_label']),
        Paragraph(rtl_paragraph_html(name, bold=True), styles['card_value']),
        Spacer(1, 3),
    ]
    if party.get('mobile'):
        cell.extend([
            Paragraph(rtl_paragraph_html('موبایل'), styles['card_label']),
            Paragraph(rtl_paragraph_html(party['mobile'], bold=True), styles['card_value']),
            Spacer(1, 3),
        ])
    if party.get('national_id'):
        cell.extend([
            Paragraph(rtl_paragraph_html('کد ملی'), styles['card_label']),
            Paragraph(rtl_paragraph_html(party['national_id'], bold=True), styles['card_value']),
        ])
    return cell


def _parties_two_col(delivered, received, content_width: float, styles: Dict):
    from reportlab.lib import colors
    from reportlab.platypus import Spacer, Table, TableStyle

    half = (content_width - 8) / 2
    tbl = Table(
        [[_party_card(delivered, 'تحویل‌دهنده', styles), _party_card(received, 'تحویل‌گیرنده', styles)]],
        colWidths=[half, half],
        hAlign='RIGHT',
    )
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
        ('BOX', (0, 0), (-1, -1), 0.45, colors.HexColor(_C_BORDER)),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#eef2f7')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _simple_table(headers: List[str], rows: List[List[str]], font_name: str, font_bold: str, col_widths):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    data = [[rtl_plain(h) for h in headers]]
    for row in rows:
        data.append([rtl_plain(c) for c in row])
    tbl = Table(data, colWidths=col_widths, repeatRows=1, hAlign='RIGHT')
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f3ff')),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor(_C_BORDER)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return tbl


def render_handover_pdf_bytes(handover: ContractHandover, *, preview: bool = False) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        logger.warning('reportlab not available: %s', exc)
        return b''

    from contracts.services.handover_wizard import build_handover_wizard_context
    from workspace.services.jalali_input import format_jalali_date

    wizard = build_handover_wizard_context(handover, step='review')
    review = wizard.get('review') or {}
    prop = wizard.get('property_data') or {}
    snap = handover.snapshot_json or {}

    font_name, font_bold = _register_fonts()
    styles = _pdf_styles(font_name, font_bold)

    buffer = io.BytesIO()
    page_w, page_h = A4
    margin_r = margin_l = 1.8 * cm
    margin_t = 2.2 * cm
    margin_b = 2.6 * cm
    content_width = page_w - margin_l - margin_r

    date_label = review.get('date_display') or (
        format_jalali_date(handover.handover_date) if handover.handover_date else '—'
    )
    time_label = review.get('time_display') or (
        handover.handover_time.strftime('%H:%M') if handover.handover_time else '—'
    )

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(_C_PRIMARY))
        canvas.rect(0, page_h - 0.35 * cm, page_w, 0.35 * cm, fill=1, stroke=0)
        canvas.setFont(font_name, 7)
        canvas.drawCentredString(page_w / 2, 0.6 * cm, prepare_rtl_text(f'صفحه {canvas.getPageNumber()}'))
        brand = prepare_rtl_text('فایلینگ دیوار — صورت‌جلسه تحویل ملک')
        canvas.drawRightString(page_w - margin_r, page_h - 0.85 * cm, brand)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin_r,
        leftMargin=margin_l,
        topMargin=margin_t,
        bottomMargin=margin_b,
        title=prepare_rtl_text('صورت‌جلسه تحویل ملک'),
    )

    story: List[Any] = []
    story.extend(_article_box(
        'صورت‌جلسه تحویل ملک',
        [
            Paragraph(rtl_paragraph_html(
                f'قرارداد {handover.contract.internal_number} · {handover.get_handover_type_display()}',
            ), styles['subtitle']),
            Paragraph(rtl_paragraph_html(
                f'تاریخ تحویل: {date_label} · ساعت: {time_label}',
            ), styles['subtitle']),
            Paragraph(rtl_paragraph_html(
                f'وضعیت: {handover.get_status_display()}'
                + (f' · هش: {handover.content_hash[:16]}…' if handover.content_hash else ''),
            ), styles['subtitle']),
        ],
        content_width,
        styles,
    ))

    delivered = snap.get('delivered_by') or {}
    received = snap.get('received_by') or {}
    story.extend(_article_box(
        'ماده ۱ — طرفین تحویل',
        [_parties_two_col(delivered, received, content_width, styles)],
        content_width,
        styles,
    ))

    prop_pairs = [
        ('نوع ملک', prop.get('property_type')),
        ('شهر', prop.get('city')),
        ('منطقه', prop.get('district')),
        ('آدرس', prop.get('address')),
        ('متراژ', prop.get('area')),
        ('طبقه', prop.get('floor')),
    ]
    prop_pairs = [(k, str(v)) for k, v in prop_pairs if v]
    if prop_pairs:
        story.extend(_article_box(
            'ماده ۲ — مشخصات ملک',
            [_kv_grid(prop_pairs, content_width, styles)],
            content_width,
            styles,
        ))

    keys = review.get('keys') or []
    if keys:
        key_rows = []
        for k in keys:
            key_rows.append([
                k.get('type') or '—',
                str(k.get('count') or 0),
                k.get('notes') or '—',
            ])
        story.extend(_article_box(
            'ماده ۳ — کلیدها و اقلام تحویلی',
            [_simple_table(
                ['نوع', 'تعداد', 'یادداشت'],
                key_rows,
                font_name,
                font_bold,
                [5.5 * cm, 2.2 * cm, content_width - 7.7 * cm],
            )],
            content_width,
            styles,
        ))

    meters = review.get('meters') or []
    if meters:
        m_rows = []
        for m in meters:
            util = m.get('utility') or ''
            m_rows.append([
                _METER_LABELS.get(util, util),
                m.get('meter_number') or '—',
                m.get('reading') or '—',
                m.get('notes') or '—',
            ])
        story.extend(_article_box(
            'ماده ۴ — قرائت کنتورها',
            [_simple_table(
                ['کنتور', 'شماره', 'قرائت', 'یادداشت'],
                m_rows,
                font_name,
                font_bold,
                [2.8 * cm, 3.5 * cm, 3.2 * cm, content_width - 9.5 * cm],
            )],
            content_width,
            styles,
        ))

    conditions = review.get('conditions') or []
    checked = [c for c in conditions if c.get('status') != 'unchecked']
    if checked:
        c_rows = []
        for c in checked:
            c_rows.append([
                c.get('item') or '—',
                c.get('status_label') or _STATUS_LABELS.get(c.get('status'), '—'),
                c.get('note') or '—',
            ])
        story.extend(_article_box(
            'ماده ۵ — وضعیت ملک',
            [_simple_table(
                ['مورد', 'وضعیت', 'توضیح'],
                c_rows,
                font_name,
                font_bold,
                [4.5 * cm, 3 * cm, content_width - 7.5 * cm],
            )],
            content_width,
            styles,
        ))

    equipment = review.get('equipment') or []
    if equipment:
        e_rows = []
        for eq in equipment:
            status = eq.get('status_label') or _STATUS_LABELS.get(eq.get('status'), eq.get('status') or '—')
            e_rows.append([
                eq.get('name') or '—',
                str(eq.get('count') or '1'),
                status,
                eq.get('notes') or '—',
            ])
        story.extend(_article_box(
            'ماده ۶ — تجهیزات',
            [_simple_table(
                ['نام', 'تعداد', 'وضعیت', 'یادداشت'],
                e_rows,
                font_name,
                font_bold,
                [4 * cm, 1.8 * cm, 2.5 * cm, content_width - 8.3 * cm],
            )],
            content_width,
            styles,
        ))

    notes = (handover.notes or review.get('notes') or '').strip()
    if notes:
        story.extend(_article_box(
            'یادداشت تحویل',
            [Paragraph(rtl_paragraph_html(notes), styles['body'])],
            content_width,
            styles,
        ))

    acceptances = list(handover.acceptances.order_by('accepted_at', 'pk'))
    if acceptances:
        sig_rows = []
        for acc in acceptances:
            side = 'تحویل‌دهنده' if acc.side == 'delivered_by' else 'تحویل‌گیرنده'
            dt = timezone.localtime(acc.accepted_at).strftime('%Y/%m/%d %H:%M')
            sig_rows.append([
                side,
                acc.mobile or '—',
                dt,
                'تأیید OTP',
            ])
        story.extend(_article_box(
            'امضا و تأیید طرفین',
            [_simple_table(
                ['نقش', 'موبایل', 'زمان تأیید', 'نوع'],
                sig_rows,
                font_name,
                font_bold,
                [3 * cm, 3.5 * cm, 3.5 * cm, content_width - 10 * cm],
            )],
            content_width,
            styles,
        ))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        rtl_paragraph_html(
            'این صورت‌جلسه وضعیت ملک، کلیدها، کنتورها و تجهیزات را در زمان تحویل '
            'ثبت می‌کند و در سامانه فایلینگ دیوار نگهداری می‌شود.',
        ),
        styles['footer'],
    ))
    if preview:
        story.append(Paragraph(
            rtl_paragraph_html('پیش‌نمایش — قبل از تأیید نهایی طرفین'),
            styles['footer'],
        ))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()


def generate_handover_pdf(handover: ContractHandover, *, request=None) -> str:
    pdf_bytes = render_handover_pdf_bytes(handover, preview=False)
    if not pdf_bytes:
        return ''
    filename = f'handover_{handover.contract.internal_number}_{handover.pk}.pdf'
    handover.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    return filename
