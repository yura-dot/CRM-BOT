import re
from datetime import datetime

def generate_order_number():
    now = datetime.now()
    return f"ORD-{now.strftime('%Y%m%d%H%M%S')}"

def generate_invoice_number():
    now = datetime.now()
    return f"INV-{now.strftime('%Y%m%d%H%M%S')}"

def format_price(price):
    return f"{price:,.2f} грн".replace(",", " ")

def format_status(status):
    statuses = {
        "new": "🔵 Новий",
        "in_progress": "🟠 В роботі",
        "delivery": "🟣 Доставка",
        "completed": "🟢 Виконаний"
    }
    return statuses.get(status, status)

def format_invoice_status(status):
    statuses = {
        "draft": "📝 Чернетка",
        "sent": "📤 Відправлений",
        "paid": "✅ Оплачений"
    }
    return statuses.get(status, status)

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None
