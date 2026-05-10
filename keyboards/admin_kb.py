from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def admin_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Замовлення"), KeyboardButton(text="📦 Товари")],
        [KeyboardButton(text="🏢 Компанії"), KeyboardButton(text="👥 Клієнти")],
        [KeyboardButton(text="⚙️ Налаштування")],
    ], resize_keyboard=True)


def orders_filter_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔵 Нові", callback_data="admin_orders_new"),
         InlineKeyboardButton(text="🟠 В роботі", callback_data="admin_orders_in_progress")],
        [InlineKeyboardButton(text="🟣 Доставка", callback_data="admin_orders_delivery"),
         InlineKeyboardButton(text="💚 Оплачені", callback_data="admin_orders_paid")],
        [InlineKeyboardButton(text="🟢 Виконані", callback_data="admin_orders_completed"),
         InlineKeyboardButton(text="📄 Запит рахунку", callback_data="admin_orders_invoice_req")],
        [InlineKeyboardButton(text="📋 Всі", callback_data="admin_orders_all")],
    ])


def order_status_kb(order_id: int, current_status: str, has_invoice: bool = False):
    statuses = [
        ("new",         "🔵 Новий"),
        ("in_progress", "🟠 В роботі"),
        ("delivery",    "🟣 Доставка"),
        ("paid",        "💚 Оплачений"),
        ("completed",   "🟢 Виконаний"),
    ]
    buttons = []
    row = []
    for s_key, s_label in statuses:
        marker = "◉ " if s_key == current_status else ""
        row.append(InlineKeyboardButton(
            text=f"{marker}{s_label}",
            callback_data=f"set_status_{order_id}_{s_key}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if has_invoice:
        buttons.append([
            InlineKeyboardButton(text="🧾 Переглянути рахунок", callback_data=f"admin_view_invoice_{order_id}"),
        ])
    else:
        buttons.append([InlineKeyboardButton(text="🧾 Виставити рахунок", callback_data=f"create_invoice_{order_id}")])

    buttons.append([
        InlineKeyboardButton(text="🗑 Видалити замовлення", callback_data=f"admin_delete_order_{order_id}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_orders_all"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_order_kb(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"admin_delete_order_confirm_{order_id}")],
        [InlineKeyboardButton(text="◀️ Скасувати", callback_data=f"admin_order_{order_id}")],
    ])


def products_admin_kb(products: list):
    buttons = []
    for p in products:
        stock_icon = "✅" if p["stock_qty"] > 0 else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{stock_icon} {p['name']} [{p['sku']}] — {p['stock_qty']} шт",
            callback_data=f"admin_prod_{p['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Додати товар", callback_data="add_product")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_admin_detail_kb(product_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"edit_prod_{product_id}")],
        [InlineKeyboardButton(text="📦 Оновити залишок", callback_data=f"stock_prod_{product_id}")],
        [InlineKeyboardButton(text="🗑 Видалити", callback_data=f"del_prod_{product_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_products")],
    ])


def select_brand_kb(brands: list):
    buttons = []
    for b in brands:
        buttons.append([InlineKeyboardButton(
            text=f"🏷 {b['name']}",
            callback_data=f"sel_brand_{b['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⏭ Пропустити", callback_data="sel_brand_0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def select_category_kb(cats: list):
    buttons = []
    for c in cats:
        buttons.append([InlineKeyboardButton(
            text=f"📂 {c['name']}",
            callback_data=f"sel_cat_{c['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⏭ Пропустити", callback_data="sel_cat_0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def clients_admin_kb(users: list):
    buttons = []
    for u in users:
        approved = "✅" if u["is_approved"] else "⏳"
        buttons.append([InlineKeyboardButton(
            text=f"{approved} {u['first_name']} {u['last_name']}",
            callback_data=f"admin_client_{u['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def client_admin_detail_kb(user_id: int, is_approved: bool, companies: list):
    buttons = []
    if is_approved:
        buttons.append([InlineKeyboardButton(text="🚫 Відкликати доступ", callback_data=f"disapprove_{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ Підтвердити клієнта", callback_data=f"approve_{user_id}")])
    for c in companies:
        buttons.append([InlineKeyboardButton(
            text=f"🏢 Призначити: {c['name']}",
            callback_data=f"assign_co_{user_id}_{c['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_clients")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Реквізити ФОП", callback_data="fop_settings")],
        [InlineKeyboardButton(text="🏢 Компанії", callback_data="admin_companies")],
        [InlineKeyboardButton(text="🏷 Бренди", callback_data="admin_brands")],
        [InlineKeyboardButton(text="📂 Категорії", callback_data="admin_categories")],
    ])


def invoice_status_kb(inv_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Позначити відправленим", callback_data=f"inv_sent_{inv_id}")],
        [InlineKeyboardButton(text="✅ Позначити оплаченим", callback_data=f"inv_paid_{inv_id}")],
    ])


def fop_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редагувати реквізити", callback_data="fop_edit")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings")],
    ])


def companies_list_kb(companies: list):
    buttons = [[InlineKeyboardButton(text=f"🏢 {c['name']}", callback_data=f"co_{c['id']}")] for c in companies]
    buttons.append([InlineKeyboardButton(text="➕ Додати компанію", callback_data="add_company")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def company_detail_kb(co_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"edit_co_{co_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_companies")],
    ])


def brands_list_kb(brands: list):
    buttons = [[InlineKeyboardButton(text=f"🏷 {b['name']}", callback_data=f"brand_{b['id']}")] for b in brands]
    buttons.append([InlineKeyboardButton(text="➕ Додати бренд", callback_data="add_brand")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def categories_list_kb(cats: list):
    buttons = [[InlineKeyboardButton(text=f"📂 {c['name']}", callback_data=f"catadm_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton(text="➕ Додати категорію", callback_data="add_category")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def companies_kb(companies: list):
    buttons = []
    for c in companies:
        buttons.append([InlineKeyboardButton(text=f"🏢 {c['name']}", callback_data=f"co_{c['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Додати компанію", callback_data="add_company")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def brands_kb(brands: list):
    buttons = []
    for b in brands:
        buttons.append([InlineKeyboardButton(text=f"🏷 {b['name']}", callback_data=f"brand_{b['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Додати бренд", callback_data="add_brand")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def categories_kb(cats: list):
    buttons = []
    for c in cats:
        buttons.append([InlineKeyboardButton(text=f"📂 {c['name']}", callback_data=f"catadm_{c['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Додати категорію", callback_data="add_category")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
