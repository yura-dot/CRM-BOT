from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import urllib.request
import os
import io

def ensure_fonts():
    """Завантажує DejaVu шрифти з підтримкою кирилиці"""
    font_dir = "/tmp/fonts"
    os.makedirs(font_dir, exist_ok=True)

    fonts = {
        "DejaVu": "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf",
        "DejaVu-Bold": "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf",
    }

    for name, url in fonts.items():
        path = f"{font_dir}/{name}.ttf"
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
            except Exception:
                pass
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            pass

ensure_fonts()

def generate_invoice_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    # Стилі з кириличним шрифтом
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal", fontName="DejaVu", fontSize=9, leading=13)
    bold = ParagraphStyle("bold", fontName="DejaVu-Bold", fontSize=9, leading=13)
    title = ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=14, leading=18, alignment=TA_CENTER)
    center = ParagraphStyle("center", fontName="DejaVu", fontSize=9, leading=13, alignment=TA_CENTER)
    right = ParagraphStyle("right", fontName="DejaVu", fontSize=9, leading=13, alignment=TA_RIGHT)
    small = ParagraphStyle("small", fontName="DejaVu", fontSize=8, leading=12)

    seller = data.get("seller", {})
    buyer = data.get("buyer", {})
    items = data.get("items", [])
    total = data.get("total", 0)

    story = []

    # Заголовок
    story.append(Paragraph(f"РАХУНОК НА ОПЛАТУ № {data.get('invoice_number','')}", title))
    story.append(Paragraph(f"Дата: {data.get('invoice_date','')}", center))
    story.append(Spacer(1, 8*mm))

    # Таблиця постачальник / покупець
    seller_text = [
        Paragraph("<b>ПОСТАЧАЛЬНИК</b>", bold),
        Paragraph(seller.get("name", "—"), normal),
        Paragraph(f"ЄДРПОУ/ІПН: {seller.get('edrpou','—')}", normal),
        Paragraph(f"IBAN: {seller.get('iban','—')}", normal),
        Paragraph(f"Адреса: {seller.get('address','—')}", normal),
        Paragraph(f"Тел: {seller.get('phone','—')}", normal),
    ]
    buyer_text = [
        Paragraph("<b>ПОКУПЕЦЬ</b>", bold),
        Paragraph(buyer.get("name", "—"), normal),
        Paragraph(f"ЄДРПОУ: {buyer.get('edrpou','—')}", normal),
        Paragraph(f"IBAN: {buyer.get('iban','—')}", normal),
        Paragraph(f"Адреса: {buyer.get('address','—')}", normal),
        Paragraph(f"Тел: {buyer.get('phone','—')}", normal),
    ]

    parties_table = Table(
        [[seller_text, buyer_text]],
        colWidths=[90*mm, 90*mm]
    )
    parties_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("PADDING", (0,0), (-1,-1), 6),
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#f0f4f8")),
        ("BACKGROUND", (1,0), (1,0), colors.HexColor("#f8f8f8")),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 6*mm))

    # Таблиця товарів
    table_data = [[
        Paragraph("№", bold),
        Paragraph("Найменування товару/послуги", bold),
        Paragraph("К-ть", bold),
        Paragraph("Ціна, грн", bold),
        Paragraph("Сума, грн", bold),
    ]]
    for i, item in enumerate(items, 1):
        table_data.append([
            Paragraph(str(i), normal),
            Paragraph(str(item.get("name","")), normal),
            Paragraph(str(item.get("qty",1)), center),
            Paragraph(f"{float(item.get('price',0)):.2f}", right),
            Paragraph(f"{float(item.get('subtotal',0)):.2f}", right),
        ])

    items_table = Table(
        table_data,
        colWidths=[10*mm, 90*mm, 18*mm, 28*mm, 28*mm]
    )
    items_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2c7873")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "DejaVu-Bold"),
        ("ALIGN", (2,0), (-1,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f9f9f9")]),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4*mm))

    # Підсумок
    total_table = Table(
        [[Paragraph("РАЗОМ ДО СПЛАТИ:", bold), Paragraph(f"<b>{total:.2f} грн</b>", bold)]],
        colWidths=[128*mm, 46*mm]
    )
    total_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#e8f4f8")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 6*mm))

    # Призначення платежу
    purpose = data.get("payment_purpose", "")
    if purpose:
        story.append(Paragraph(f"<b>Призначення платежу:</b> {purpose}", normal))
        story.append(Spacer(1, 3*mm))

    # Нотатки
    notes = data.get("notes", "")
    if notes:
        story.append(Paragraph(f"<b>Примітка:</b> {notes}", small))
        story.append(Spacer(1, 3*mm))

    # Термін оплати
    due = data.get("due_date", "")
    if due:
        story.append(Paragraph(f"<b>Оплатити до:</b> {due}", bold))

    doc.build(story)
    return buffer.getvalue()
