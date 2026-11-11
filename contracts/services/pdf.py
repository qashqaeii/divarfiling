"""تولید PDF قرارداد — از contract_display مشترک با Public View."""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse

from contracts.constants import LEGAL_DISCLAIMER_SHORT
from contracts.models import ContractVersion
from contracts.services.audit import log_audit_event
from contracts.services.date_display import jalali_pdf_datetime
from contracts.services.contract_display import build_contract_display
from contracts.services.persian_text import (
    prepare_rtl_text,
    resolve_persian_font_paths,
    rtl_paragraph_html,
    rtl_plain,
)
from contracts.services.pdf_layout import article_box as _article_box, body_to_flowables

logger = logging.getLogger(__name__)

_FONT_REGULAR = 'PF'
_FONT_BOLD = 'PF-Bold'

_C_PRIMARY = '#7c3aed'
_C_PRIMARY_SOFT = '#f5f3ff'
_C_BORDER = '#e2e8f0'
_C_TEXT = '#0f172a'
_C_MUTED = '#64748b'
_C_SUCCESS = '#059669'
_C_SUCCESS_BG = '#ecfdf5'
_C_SUCCESS_BORDER = '#6ee7b7'


def _register_fonts() -> tuple[str, str]:
    regular_path, bold_path = resolve_persian_font_paths()
    font_regular = 'Helvetica'
    font_bold = 'Helvetica-Bold'
    if not regular_path:
        logger.warning('Persian font not found — PDF may render incorrectly')
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
        logger.warning('Font registration failed: %s', exc)
    return font_regular, font_bold


def _verify_url(verify_raw_token: str, request=None) -> str:
    if not verify_raw_token:
        return ''
    path = reverse('public_verify', kwargs={'token': verify_raw_token})
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, 'SITE_URL', 'https://divarfiling.ir')
    return f'{site.rstrip("/")}{path}'


def generate_contract_pdf(
    version: ContractVersion,
    *,
    verify_raw_token: str = '',
    request=None,
) -> str:
    pdf_bytes = generate_contract_pdf_bytes(
        version, verify_raw_token=verify_raw_token, request=request, preview=False,
    )
    if not pdf_bytes:
        return ''
    contract = version.contract
    filename = f'{contract.internal_number}_v{version.version_number}.pdf'
    version.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    log_audit_event(contract, 'PDF_GENERATED', version=version, metadata={'filename': filename})
    return version.pdf_file.name


def render_contract_pdf_bytes(
    version: ContractVersion,
    *,
    verify_raw_token: str = '',
    request=None,
    preview: bool = False,
    refresh_stored: bool = False,
) -> bytes:
    """
    Always generate a fresh PDF (same pipeline as workspace preview).
    Optionally replace a stale stored file on finalized contracts.
    """
    pdf_bytes = generate_contract_pdf_bytes(
        version,
        verify_raw_token=verify_raw_token,
        request=request,
        preview=preview,
    )
    if not pdf_bytes:
        return b''
    if refresh_stored and not preview and version.contract.status == 'finalized':
        contract = version.contract
        filename = f'{contract.internal_number}_v{version.version_number}.pdf'
        try:
            version.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
            version.save(update_fields=['pdf_file'])
        except Exception as exc:
            logger.warning('Could not refresh stored contract PDF: %s', exc)
    return pdf_bytes


def _pdf_styles(font_name: str, font_bold: str):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle

    return {
        'title': ParagraphStyle(
            'title', fontName=font_bold, fontSize=17, alignment=TA_CENTER, leading=26,
            textColor=colors.HexColor(_C_TEXT),
        ),
        'subtitle': ParagraphStyle(
            'subtitle', fontName=font_name, fontSize=9.5, alignment=TA_CENTER, leading=15,
            textColor=colors.HexColor(_C_MUTED),
        ),
        'heading': ParagraphStyle(
            'heading', fontName=font_bold, fontSize=11.5, alignment=TA_RIGHT, leading=18,
            textColor=colors.HexColor(_C_TEXT),
        ),
        'body': ParagraphStyle(
            'body', fontName=font_name, fontSize=10, alignment=TA_RIGHT, leading=17,
            textColor=colors.HexColor('#1e293b'),
            leftIndent=10, rightIndent=10, spaceBefore=4, spaceAfter=2,
        ),
        'meta': ParagraphStyle(
            'meta', fontName=font_name, fontSize=8.5, alignment=TA_RIGHT, leading=13,
            textColor=colors.HexColor(_C_MUTED),
        ),
        'footer': ParagraphStyle(
            'footer', fontName=font_name, fontSize=8, alignment=TA_CENTER, leading=12,
            textColor=colors.grey,
        ),
        'card_role': ParagraphStyle(
            'cardRole', fontName=font_bold, fontSize=9.5, alignment=TA_RIGHT, leading=14,
            textColor=colors.HexColor(_C_PRIMARY),
        ),
        'card_label': ParagraphStyle(
            'cardLabel', fontName=font_name, fontSize=7.5, alignment=TA_RIGHT, leading=11,
            textColor=colors.HexColor(_C_MUTED),
        ),
        'card_value': ParagraphStyle(
            'cardValue', fontName=font_bold, fontSize=9, alignment=TA_RIGHT, leading=13,
            textColor=colors.HexColor(_C_TEXT),
        ),
        'sig_center': ParagraphStyle(
            'sigCenter', fontName=font_bold, fontSize=10, alignment=TA_CENTER, leading=14,
            textColor=colors.HexColor(_C_SUCCESS),
        ),
        'sig_center_meta': ParagraphStyle(
            'sigCenterMeta', fontName=font_name, fontSize=8, alignment=TA_CENTER, leading=12,
            textColor=colors.HexColor(_C_MUTED),
        ),
    }


def _kv_grid_table(
    pairs: List[Tuple[str, str]],
    content_width: float,
    font_name: str,
    font_bold: str,
    styles: Dict,
) -> Any:
    """Two-column key/value grid inside an article."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    rows = []
    col_w = content_width / 2 - 6
    for i in range(0, len(pairs), 2):
        chunk = pairs[i:i + 2]
        cells = []
        for label, value in chunk:
            cell = [
                Paragraph(rtl_paragraph_html(label), styles['card_label']),
                Paragraph(rtl_paragraph_html(value or '—', bold=True), styles['card_value']),
            ]
            cells.append(cell)
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
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, colors.HexColor('#f1f5f9')),
    ]))
    return tbl


def _party_panel_table(party: Dict, panel_width: float, styles: Dict):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    role = party.get('role_label') or party.get('role') or 'طرف قرارداد'
    label_w = panel_width * 0.34
    value_w = panel_width * 0.66

    field_rows: List[Tuple[str, str]] = []
    if party.get('first_name') or party.get('last_name'):
        field_rows.extend([
            ('نام', party.get('first_name') or '—'),
            ('نام خانوادگی', party.get('last_name') or '—'),
        ])
    else:
        field_rows.append(('نام', party.get('name') or '—'))
    if party.get('father_name'):
        field_rows.append(('نام پدر', party['father_name']))
    if party.get('national_id'):
        field_rows.append(('کد ملی', party['national_id']))
    if party.get('mobile'):
        verified = ' ✓' if party.get('mobile_verified') else ''
        field_rows.append(('موبایل', f"{party['mobile']}{verified}"))
    if party.get('address'):
        field_rows.append(('نشانی', party['address']))
    if party.get('postal_code'):
        field_rows.append(('کد پستی', party['postal_code']))
    if party.get('ownership_share'):
        field_rows.append(('قدرالسهم', party['ownership_share']))

    rows = [[Paragraph(rtl_paragraph_html(role, bold=True), styles['card_role']), '']]
    for label, value in field_rows:
        rows.append([
            Paragraph(rtl_paragraph_html(label), styles['card_label']),
            Paragraph(rtl_paragraph_html(str(value), bold=True), styles['card_value']),
        ])

    tbl = Table(rows, colWidths=[label_w, value_w])
    tbl.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(_C_PRIMARY_SOFT)),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fafafa')),
        ('BOX', (0, 0), (-1, -1), 0.65, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 1), (-1, -1), 0.45, colors.HexColor('#e2e8f0')),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor(_C_PRIMARY)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return tbl


def _parties_two_column_flow(
    parties: List[Dict],
    content_width: float,
    styles: Dict,
) -> List[Any]:
    from reportlab.platypus import Table, TableStyle

    if not parties:
        return []

    gap = 8
    half_w = (content_width - gap) / 2
    cells = []
    for party in parties[:2]:
        cells.append(_party_panel_table(party, half_w - 4, styles))
    while len(cells) < 2:
        cells.append('')

    tbl = Table([cells], colWidths=[half_w, half_w], hAlign='RIGHT')
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [tbl]


def _property_grid_flow(prop: Dict, content_width: float, font_name: str, font_bold: str, styles: Dict) -> List[Any]:
    labels = [
        ('نوع ملک', prop.get('property_type')),
        ('شهر', prop.get('city')),
        ('منطقه', prop.get('district')),
        ('آدرس', prop.get('address')),
        ('متراژ', prop.get('area')),
        ('طبقه', prop.get('floor')),
        ('تعداد اتاق', prop.get('bedrooms')),
        ('واحد', prop.get('unit')),
        ('سال ساخت', prop.get('build_year')),
        ('پلاک اصلی', prop.get('main_plaque')),
        ('پلاک فرعی', prop.get('sub_plaque')),
    ]
    pairs = [(k, str(v)) for k, v in labels if v not in (None, '', False)]
    amenities = prop.get('amenities') or []
    if amenities:
        pairs.append(('امکانات', '، '.join(amenities)))
    if not pairs:
        return []
    return [_kv_grid_table(pairs, content_width, font_name, font_bold, styles)]


def _load_signature_image(image_field, max_w: float, max_h: float):
    from reportlab.platypus import Image as RLImage

    if not image_field:
        return None
    try:
        with image_field.open('rb') as fh:
            data = fh.read()
        if not data:
            return None
        buf = io.BytesIO(data)
        img = RLImage(buf)
        iw, ih = img.imageWidth, img.imageHeight
        if iw and ih:
            scale = min(max_w / iw, max_h / ih)
            img.drawWidth = iw * scale
            img.drawHeight = ih * scale
        else:
            img.drawWidth = max_w
            img.drawHeight = max_h
        img.hAlign = 'CENTER'
        return img
    except Exception as exc:
        logger.warning('Could not embed signature image in PDF: %s', exc)
        return None


def _otp_signature_stamp(styles: Dict, width: float, height: float):
    """Visual stamp for OTP-only acceptance (matches public web view)."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    stamp = Table([
        [Paragraph(rtl_paragraph_html('✓'), styles['sig_center'])],
        [Paragraph(rtl_paragraph_html('تأیید دیجیتال OTP'), styles['sig_center_meta'])],
    ], colWidths=[width - 12])
    stamp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(_C_SUCCESS_BG)),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor(_C_SUCCESS_BORDER)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), max(8, height * 0.18)),
        ('BOTTOMPADDING', (0, 0), (-1, -1), max(8, height * 0.18)),
    ]))
    return stamp


def _signature_pad_flow(acc, styles: Dict, pad_w: float, pad_h: float) -> List[Any]:
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    sig_img = None
    try:
        sig = acc.signature
        if sig and sig.image:
            sig_img = _load_signature_image(sig.image, pad_w - 16, pad_h - 20)
    except Exception:
        sig_img = None

    if sig_img:
        pad_content = [[sig_img]]
    else:
        pad_content = [[_otp_signature_stamp(styles, pad_w, pad_h)]]

    pad = Table(pad_content, colWidths=[pad_w - 8], rowHeights=[pad_h])
    pad.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    party = acc.party
    name = ''
    if party:
        name = party.company_name or f'{party.first_name or ""} {party.last_name or ""}'.strip()
    line = Table(
        [[Paragraph(rtl_paragraph_html('—' * 18), styles['meta'])]],
        colWidths=[pad_w - 8],
    )
    line.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [pad, Spacer(1, 2), line, Paragraph(rtl_paragraph_html(name or '—', bold=True), styles['card_value'])]


def generate_contract_pdf_bytes(
    version: ContractVersion,
    *,
    verify_raw_token: str = '',
    request=None,
    preview: bool = False,
) -> bytes:
    if not preview and not version.is_published and version.contract.status != 'finalized':
        raise ValueError('PDF فقط از نسخه published/finalized تولید می‌شود.')

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image as RLImage,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )
    except ImportError as exc:
        logger.warning('reportlab not available: %s', exc)
        return b''

    contract = version.contract
    display = build_contract_display(contract, version)
    verify_url = display.get('verify_url') or _verify_url(verify_raw_token, request)

    font_name, font_bold = _register_fonts()
    styles = _pdf_styles(font_name, font_bold)

    buffer = io.BytesIO()
    page_w, page_h = A4
    margin_r = 1.8 * cm
    margin_l = 1.8 * cm
    margin_t = 2.2 * cm
    margin_b = 2.6 * cm
    content_width = page_w - margin_l - margin_r

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(_C_PRIMARY))
        canvas.rect(0, page_h - 0.35 * cm, page_w, 0.35 * cm, fill=1, stroke=0)
        canvas.setFont(font_name, 7)
        disclaimer = prepare_rtl_text(LEGAL_DISCLAIMER_SHORT[:140])
        canvas.drawCentredString(page_w / 2, 1.05 * cm, disclaimer)
        page_lbl = prepare_rtl_text(f'صفحه {canvas.getPageNumber()}')
        canvas.drawCentredString(page_w / 2, 0.6 * cm, page_lbl)
        if display.get('content_hash_short'):
            hash_lbl = prepare_rtl_text(f'اثر انگشت: {display["content_hash_short"]}')
            canvas.drawRightString(page_w - margin_r, 0.6 * cm, hash_lbl)
        canvas.setFillColor(colors.HexColor(_C_MUTED))
        brand = prepare_rtl_text('فایلینگ دیوار — سند قرارداد دیجیتال')
        canvas.drawRightString(page_w - margin_r, page_h - 0.85 * cm, brand)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin_r,
        leftMargin=margin_l,
        topMargin=margin_t,
        bottomMargin=margin_b,
        title=prepare_rtl_text(contract.get_contract_type_display()),
    )

    story: List[Any] = []

    # Cover header band
    story.extend(_article_box(
        contract.get_contract_type_display(),
        [
            Paragraph(
                rtl_paragraph_html(
                    f'شناسه: {contract.internal_number} · نسخه {version.version_number}',
                ),
                styles['subtitle'],
            ),
            Paragraph(
                rtl_paragraph_html(
                    f'تاریخ نهایی‌سازی: {jalali_pdf_datetime(contract.finalized_at)}'
                    if contract.finalized_at else 'پیش‌نمایش قرارداد',
                ),
                styles['subtitle'],
            ),
        ],
        content_width,
        styles,
    ))

    pay = display.get('payment_schedule') or {}
    parties = display.get('parties') or []
    prop = display.get('property') or {}

    for sec in display.get('document_sections') or []:
        title = sec.get('title', '')
        body = sec.get('body', '')
        kind = sec.get('section_kind') or sec.get('nav_key') or ''

        if kind == 'payments' and pay.get('has_rows'):
            content = _payment_table_flow(pay, font_name, font_bold, styles['meta'])
            story.extend(_article_box(title, content, content_width, styles))
            continue

        if kind == 'parties' and parties:
            content = _parties_two_column_flow(parties, content_width, styles)
            story.extend(_article_box(title, content, content_width, styles))
            continue

        if kind == 'property' and prop.get('has_data'):
            content = _property_grid_flow(prop, content_width, font_name, font_bold, styles)
            if content:
                story.extend(_article_box(title, content, content_width, styles))
            continue

        if not body and not title:
            continue

        story.extend(_article_box(
            title,
            body_to_flowables(body, styles['body']),
            content_width,
            styles,
        ))

    has_payment_section = any(
        s.get('section_kind') == 'payments' for s in (display.get('document_sections') or [])
    )
    if pay.get('has_rows') and not has_payment_section:
        story.extend(_article_box(
            'جدول برنامه پرداخت',
            _payment_table_flow(pay, font_name, font_bold, styles['meta']),
            content_width,
            styles,
        ))

    penalties = display.get('penalty_summary') or []
    if penalties:
        lines = []
        for p in penalties:
            line = f'{p.get("label", "")}: {p.get("amount_display", "")} ({p.get("unit", "")})'
            lines.append(Paragraph(rtl_paragraph_html(line), styles['body']))
        story.extend(_article_box('وجه التزام‌ها', lines, content_width, styles))

    costs = display.get('costs_summary') or []
    if costs:
        lines = []
        for c in costs:
            line = f'{c.get("label", "")}: {c.get("value", "")}'
            lines.append(Paragraph(rtl_paragraph_html(line), styles['body']))
        story.extend(_article_box('تقسیم هزینه‌ها', lines, content_width, styles))

    sig_block = _build_signature_pdf_block(
        version, font_name, font_bold, styles, content_width,
    )
    if sig_block:
        story.append(PageBreak())
        story.extend(sig_block)

    if verify_url:
        story.append(Spacer(1, 12))
        story.append(Paragraph(
            rtl_paragraph_html('تأیید آنلاین اصالت سند — فایلینگ دیوار'),
            styles['footer'],
        ))
        try:
            import qrcode
            qr = qrcode.make(verify_url)
            qr_buf = io.BytesIO()
            qr.save(qr_buf, format='PNG')
            qr_buf.seek(0)
            story.append(Spacer(1, 6))
            qr_img = RLImage(qr_buf, width=2.6 * cm, height=2.6 * cm)
            qr_img.hAlign = 'CENTER'
            story.append(qr_img)
        except Exception:
            story.append(Paragraph(rtl_paragraph_html(verify_url), styles['footer']))

    if display.get('content_hash'):
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            rtl_paragraph_html(f'هش نسخه: {display["content_hash"]}'),
            styles['footer'],
        ))

    story.append(Spacer(1, 10))
    story.append(Paragraph(rtl_paragraph_html(LEGAL_DISCLAIMER_SHORT), styles['footer']))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()


def _payment_table_flow(pay: Dict, font_name: str, font_bold: str, meta_style):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    rows = [[
        rtl_plain('ردیف'),
        rtl_plain('عنوان'),
        rtl_plain('مبلغ (تومان)'),
        rtl_plain('سررسید'),
        rtl_plain('روش'),
    ]]
    for row in pay.get('rows') or []:
        rows.append([
            rtl_plain(str(row.get('index', ''))),
            rtl_plain(row.get('label', '')),
            rtl_plain(row.get('amount_display', '')),
            rtl_plain(str(row.get('due_date', '') or '—')),
            rtl_plain(row.get('method', '') or '—'),
        ])
    if pay.get('total_display'):
        rows.append(['', rtl_plain('جمع'), rtl_plain(pay['total_display']), '', ''])
    col_w = [1.1 * cm, 5.2 * cm, 3.8 * cm, 2.8 * cm, 3.1 * cm]
    tbl = Table(rows, colWidths=col_w, repeatRows=1, hAlign='RIGHT', splitByRow=1)
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(_C_PRIMARY_SOFT)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(_C_TEXT)),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor(_C_BORDER)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    out = [tbl]
    if pay.get('mismatch'):
        out.append(Spacer(1, 4))
        out.append(Paragraph(
            rtl_paragraph_html('توجه: جمع اقساط با مبلغ کل معامله مطابقت ندارد.'),
            meta_style,
        ))
    return out


def _build_signature_pdf_block(
    version,
    font_name,
    font_bold,
    styles: Dict,
    content_width: float,
):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from contracts.services.final_view_context import PARTY_ROLE_LABELS

    acceptances = list(
        version.acceptances
        .filter(party__isnull=False)
        .select_related('party', 'signature')
        .order_by('party__sort_order', 'accepted_at', 'pk')
    )
    if not acceptances:
        return []

    pad_w = (content_width - 10) / 2
    pad_h = 2.4 * cm

    def _signature_cell(acc):
        party = acc.party
        role = PARTY_ROLE_LABELS.get(party.role, party.role)
        dt = jalali_pdf_datetime(acc.accepted_at)
        cell = [
            Paragraph(rtl_paragraph_html(role, bold=True), styles['card_role']),
            Spacer(1, 4),
            Paragraph(rtl_paragraph_html(f'موبایل: {acc.mobile or party.mobile or "—"}'), styles['meta']),
            Paragraph(rtl_paragraph_html(f'زمان تأیید: {dt}'), styles['meta']),
            Spacer(1, 8),
        ]
        cell.extend(_signature_pad_flow(acc, styles, pad_w, pad_h))
        return cell

    rows = []
    row = []
    for acc in acceptances:
        row.append(_signature_cell(acc))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        row.append([Spacer(1, 1)])
        rows.append(row)

    sig_table = Table(rows, colWidths=[pad_w, pad_w], hAlign='RIGHT')
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.55, colors.HexColor(_C_BORDER)),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#eef2f7')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafbfc')),
    ]))

    return _article_box(
        'امضا و تأیید طرفین قرارداد',
        [
            sig_table,
            Spacer(1, 6),
            Paragraph(
                rtl_paragraph_html(
                    'امضای دیجیتال طرفین با تأیید OTP و ثبت در سامانه فایلینگ دیوار انجام شده است.',
                ),
                styles['meta'],
            ),
        ],
        content_width,
        styles,
    )
