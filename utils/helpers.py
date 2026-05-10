import re
from datetime import datetime

def generate_order_number():
    now = datetime.now()
    return f"ORD-{now.strftime('%Y%m%d%H%M%S')}"

def generate_invoice_number():
    """Формат: ММДД + порядковий номер (напр. 0510001)
    Порядковий номер зберігається в пам'яті (reset щодня)
    """
    now = datetime.now()
    day_key = now.strftime('%m%d')
    counter = _get_day_counter(day_key)
    return f"{day_key}{counter:03d}"

def generate_expense_number():
    """Видаткова накладна: ВН-ММДД-NN"""
    now = datetime.now()
    day_key = now.strftime('%m%d')
    counter = _get_day_counter(day_key, prefix="exp")
    return f"ВН-{day_key}-{counter:03d}"

# Внутрішній лічильник по днях
_counters: dict = {}

def _get_day_counter(day_key: str, prefix: str = "inv") -> int:
    key = f"{prefix}_{day_key}"
    _counters[key] = _counters.get(key, 0) + 1
    return _counters[key]

def format_price(price):
    return f"{price:,.2f} грн".replace(",", " ")

def format_status(status):
    statuses = {
        "new": "🔵 Новий",
        "in_progress": "🟠 В роботі",
        "delivery": "🟣 Доставка",
        "paid": "💚 Оплачений",
        "completed": "🟢 Виконаний",
    }
    return statuses.get(status, status)

def format_delivery(order) -> str:
    dtype = order.get("delivery_type", "pickup")
    if dtype == "pickup":
        return "🏠 Самовивіз — Київ, Бойчука 11, оф 9"
    elif dtype == "nova_poshta":
        city = order.get("np_city") or ""
        branch = order.get("np_branch") or ""
        recipient = order.get("np_recipient") or ""
        return f"📦 Нова Пошта — {city}, відд. {branch}" + (f", {recipient}" if recipient else "")
    elif dtype == "taxi":
        addr = order.get("delivery_address") or "—"
        ddate = order.get("delivery_date") or "—"
        return f"🚕 Таксі — {addr} / {ddate}"
    return "—"

def format_invoice_status(status):
    statuses = {
        "draft": "📝 Чернетка",
        "sent": "📤 Відправлений",
        "paid": "✅ Оплачений",
    }
    return statuses.get(status, status)

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None
