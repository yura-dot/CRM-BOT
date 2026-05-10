from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Кошик")],
        [KeyboardButton(text="📦 Мої замовлення"), KeyboardButton(text="👤 Профіль")],
    ], resize_keyboard=True)

def catalog_categories_kb(categories: list):
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=f"📂 {cat['name']}", callback_data=f"cat_{cat['id']}")])
    buttons.append([InlineKeyboardButton(text="🔍 Всі товари", callback_data="cat_all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_list_kb(products: list, category_id=None):
    buttons = []
    for p in products:
        stock_icon = "✅" if p["stock_qty"] > 0 else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{stock_icon} {p['name']} — {p['client_price']:.2f} грн",
            callback_data=f"prod_{p['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_detail_kb(product_id: int, qty: int = 1, in_stock: bool = True):
    buttons = []
    if in_stock:
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"qty_minus_{product_id}_{qty}"),
            InlineKeyboardButton(text=f"  {qty}  ", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"qty_plus_{product_id}_{qty}"),
        ])
        buttons.append([InlineKeyboardButton(text="🛒 Додати до кошика", callback_data=f"add_cart_{product_id}_{qty}")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Немає в наявності", callback_data="noop")])
    buttons.append([InlineKeyboardButton(text="◀️ До каталогу", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def cart_kb(items: list):
    buttons = []
    for item in items:
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"cart_minus_{item['product_id']}"),
            InlineKeyboardButton(text=f"{item['name'][:20]} x{item['qty']}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_plus_{item['product_id']}"),
            InlineKeyboardButton(text="❌", callback_data=f"cart_remove_{item['product_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="🗑 Очистити кошик", callback_data="cart_clear")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def delivery_type_kb():
    """Вибір типу доставки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Самовивіз (Київ, Бойчука 11, оф 9)", callback_data="delivery_pickup")],
        [InlineKeyboardButton(text="📦 Нова Пошта", callback_data="delivery_nova_poshta")],
        [InlineKeyboardButton(text="🚕 Таксі", callback_data="delivery_taxi")],
        [InlineKeyboardButton(text="◀️ Назад до кошика", callback_data="back_to_cart")],
    ])

def confirm_order_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити замовлення", callback_data="order_confirm")],
        [InlineKeyboardButton(text="🔄 Змінити доставку", callback_data="change_delivery")],
        [InlineKeyboardButton(text="◀️ Назад до кошика", callback_data="back_to_cart")],
    ])

def my_orders_kb(orders: list):
    buttons = []
    for o in orders:
        from utils.helpers import format_status
        buttons.append([InlineKeyboardButton(
            text=f"#{o['order_number']} {format_status(o['status'])} — {o['total_amount']:.2f} грн",
            callback_data=f"order_{o['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def order_detail_client_kb(order_id: int, has_invoice: bool, invoice_requested: bool):
    buttons = []
    if has_invoice:
        buttons.append([InlineKeyboardButton(text="🧾 Переглянути рахунок", callback_data=f"view_invoice_{order_id}")])
        buttons.append([InlineKeyboardButton(text="💳 Реквізити для оплати", callback_data=f"payment_details_{order_id}")])
    elif not invoice_requested:
        buttons.append([InlineKeyboardButton(text="📄 Запросити рахунок / Реквізити", callback_data=f"req_invoice_{order_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="⏳ Рахунок запитано", callback_data="noop")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="my_orders")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def payment_details_kb(order_id: int):
    """Кнопки для зручного копіювання реквізитів"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ До замовлення", callback_data=f"order_{order_id}")],
    ])

def accept_terms_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Приймаю умови", callback_data="accept_terms")],
        [InlineKeyboardButton(text="❌ Відмовитись", callback_data="decline_terms")],
    ])
