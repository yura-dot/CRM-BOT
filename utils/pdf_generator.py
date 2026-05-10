from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io
import os

def generate_invoice_pdf(invoice_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', fontSize=14, alignment=TA_CENTER, spaceAfter=6, fontName='Helvetica-Bold')
    header_style = ParagraphStyle('header', fontSize=9, alignment=TA_LEFT, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('normal', fontSize=9, alignment=TA_LEFT, fontName='Helvetica')
    right_style = ParagraphStyle('right', fontSize=11, alignment=TA_RIGHT, fontName='Helvetica-Bold')

    story = []

    # Title
    story.append(Paragraph(f"РАХУНОК НА ОПЛАТУ № {invoice_data['invoice_number']}", title_style))
    story.append(Paragraph(f"від {invoice_data['invoice_date']}", ParagraphStyle('sub', fontSize=10, alignment=TA_CENTER, fontName='Helvetica')))
    story.append(Spacer(1, 8*mm))

    # Seller / Buyer table
    seller = invoice_data.get('seller', {})
    buyer = invoice_data.get('buyer', {})

    parties_data = [
        ['ПОСТАЧАЛЬНИК', 'ПОКУПЕЦЬ'],
        [seller.get('name',''), buyer.get('name','')],
        [f"ЄДРПОУ/ІПН: {seller.get('edrpou','')}", f"ЄДРПОУ: {buyer.get('edrpou','')}"],
        [f"IBAN: {seller.get('iban','')}", f"IBAN: {buyer.get('iban','')}"],
        [f"Адреса: {seller.get('address','')}", f"Адреса: {buyer.get('address','')}"],
        [f"Тел: {seller.get('phone','')}", f"Тел: {buyer.get('phone','')}"],
    ]
    parties_table = Table(parties_data, colWidths=[90*mm, 90*mm])
    parties_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e8f4f8')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 6*mm))

    # Items table
    items_header = [['№', 'Назва товару', 'К-сть', 'Ціна, грн', 'Сума, грн']]
    items_rows = []
    for i, item in enumerate(invoice_data.get('items', []), 1):
        items_rows.append([
            str(i),
            item['name'],
            str(item['qty']),
            f"{item['price']:.2f}",
            f"{item['subtotal']:.2f}"
        ])
    total_row = [['', 'РАЗОМ ДО СПЛАТИ:', '', '', f"{invoice_data['total']:.2f} грн"]]

    items_table = Table(items_header + items_rows + total_row,
                        colWidths=[10*mm, 100*mm, 20*mm, 25*mm, 25*mm])
    items_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#01696f')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f0f7f7')),
        ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 6*mm))

    # Payment purpose
    purpose = invoice_data.get('payment_purpose', '')
    story.append(Paragraph(f"Призначення платежу: {purpose}", normal_style))
    story.append(Spacer(1, 4*mm))

    if invoice_data.get('notes'):
        story.append(Paragraph(f"Примітка: {invoice_data['notes']}", normal_style))
        story.append(Spacer(1, 4*mm))

    # Due date
    if invoice_data.get('due_date'):
        story.append(Paragraph(f"Оплатити до: {invoice_data['due_date']}", header_style))

    doc.build(story)
    return buffer.getvalue()
