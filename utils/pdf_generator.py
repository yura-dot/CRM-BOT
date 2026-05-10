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

FONT_DIR = "/tmp/supercrm_fonts"
_fonts_loaded = False

FONT_URLS = {
    "DejaVu": [
        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans.ttf",
        "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf",
    ],
    "DejaVu-Bold": [
        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf",
        "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf",
    ],
}

def ensure_fonts():
    global _fonts_loaded
    if _fonts_loaded:
        return True

    os.makedirs(FONT_DIR, exist_ok=True)

    for name, urls in FONT_URLS.items():
        path = os.path.join(FONT_DIR, f"{name}.ttf")

        # Завантажуємо якщо немає
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            downloaded = False
            for url in urls:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        data = r.read()
                    if len(data) > 10000:  # перевіряємо що це реальний TTF
                        with open(path, "wb") as f:
                            f.write(data)
                        downloaded = True
                        break
                except Exception:
                    continue
            if not downloaded:
                return False

        # Реєструємо шрифт
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            return False

    _fonts_loaded = True
    return True


def generate_invoice_pdf(data: dict) -> bytes:
    fonts_ok = ensure_fonts()

    # Якщо шрифти не завантажились — використовуємо ASCII-сумісний fallback
    font_name = "DejaVu" if fonts_ok else "Helvetica"
    font_bold = "DejaVu-Bold" if fonts_ok else "Helvetica-Bold"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    normal = ParagraphStyle("inv_normal", fontName=font_name, fontSize=9, leading=13)
    bold   = ParagraphStyle("inv_bold",   fontName=font_bold, fontSize=9, leading=13)
    title  = ParagraphStyle("inv_title",  fontName=font_bold, fontSize=14, leading=18, alignment=TA_CENTER)
    center = ParagraphStyle("inv_center", fontName=font_name, fontSize=9, leading=13, alignment=TA_CENTER)
    right  = ParagraphStyle("inv_right",  fontName=font_name, fontSize=9, leading=13, alignment=TA_RIGHT)
    small  = ParagraphStyle("inv_small",  fontName=font_name, fontSize=8, leading=12)

    seller = data.get("seller", {})
    buyer  = data.get("buyer", {})
    items  = data.get("items", [])
    total  = data.get("total", 0)

    story = []

    # Заголовок
    story.append(Paragraph(f"РАХУНОК НА ОПЛАТУ № {data.get('invoice_number','')}", title))
    story.append(Paragraph(f"Дата: {data.get('invoice_date','')}", center))
    if data.get("due_date"):
        story.append(Paragraph(f"Оплатити до: {data['due_date']}", center))
    story.append(Spacer(1, 8*mm))

    # Постачальник / Покупець
    def make_party(header, d):
        return [
            Paragraph(f"<b>{header}</b>", bold),
            Paragraph(d.get("name", "—"), normal),
            Paragraph(f"ЄДРПОУ/ІПН: {d.get('edrpou','—')}", normal),
            Paragraph(f"IBAN: {d.get('iban','—')}", normal),
            Paragraph(f"Адреса: {d.get('address','—')}", normal),
            Paragraph(f"Тел: {d.get('phone','—')}", normal),
        ]

    parties = Table(
        [[make_party("ПОСТАЧАЛЬНИК", seller), make_party("ПОКУПЕЦЬ", buyer)]],
        colWidths=[90*mm, 90*mm]
    )
    parties.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID",  (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("PADDING",    (0,0), (-1,-1), 6),
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#f0f4f8")),
        ("BACKGROUND", (1,0), (1,0), colors.HexColor("#f8f8f8")),
    ]))
    story.append(parties)
    story.append(Spacer(1, 6*mm))

    # Таблиця товарів
    rows = [[
        Paragraph("№",                           bold),
        Paragraph("Найменування товару/послуги", bold),
        Paragraph("К-ть",                        bold),
        Paragraph("Ціна, грн",                   bold),
        Paragraph("Сума, грн",                   bold),
    ]]
    for i, item in enumerate(items, 1):
        rows.append([
            Paragraph(str(i),                              normal),
            Paragraph(str(item.get("name", "")),           normal),
            Paragraph(str(item.get("qty", 1)),             center),
            Paragraph(f"{float(item.get('price',0)):.2f}",    right),
            Paragraph(f"{float(item.get('subtotal',0)):.2f}",  right),
        ])

    items_tbl = Table(rows, colWidths=[10*mm, 90*mm, 18*mm, 28*mm, 28*mm])
    items_tbl.setStyle(TableStyle([
        ("BOX",            (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID",      (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("BACKGROUND",     (0,0), (-1,0),  colors.HexColor("#2c7873")),
        ("TEXTCOLOR",      (0,0), (-1,0),  colors.white),
        ("FONTNAME",       (0,0), (-1,0),  font_bold),
        ("ALIGN",          (2,0), (-1,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f9f9f9")]),
        ("PADDING",        (0,0), (-1,-1), 5),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 4*mm))

    # Разом
    total_tbl = Table(
        [[Paragraph("РАЗОМ ДО СПЛАТИ:", bold),
          Paragraph(f"<b>{total:.2f} грн</b>", bold)]],
        colWidths=[128*mm, 46*mm]
    )
    total_tbl.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN",      (1,0), (1,0),   "RIGHT"),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#e8f4f8")),
        ("PADDING",    (0,0), (-1,-1), 6),
    ]))
    story.append(total_tbl)
    story.append(Spacer(1, 6*mm))

    purpose = data.get("payment_purpose", "")
    if purpose:
        story.append(Paragraph(f"<b>Призначення платежу:</b> {purpose}", normal))
        story.append(Spacer(1, 3*mm))

    notes = data.get("notes", "")
    if notes:
        story.append(Paragraph(f"<b>Примітка:</b> {notes}", small))

    doc.build(story)
    return buffer.getvalue()
