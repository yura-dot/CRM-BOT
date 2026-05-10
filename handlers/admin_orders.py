from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from models.database import get_db
from keyboards.admin_kb import orders_filter_kb, order_status_kb, confirm_delete_order_kb
from utils.helpers import format_status, format_delivery
import os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

@router.message(F.text == "📋 Замовлення")
async def admin_orders(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("📋 <b>Замовлення</b>\nОберіть фільтр:", parse_mode="HTML",
                         reply_markup=orders_filter_kb())

@router.callback_query(F.data == "admin_orders_filter")
async def show_filter(callback: CallbackQuery):
    try:
        await callback.message.edit_text("📋 Оберіть фільтр:", reply_markup=orders_filter_kb())
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("admin_orders_"))
async def filter_orders(callback: CallbackQuery):
    status_map = {
        "admin_orders_all":          None,
        "admin_orders_new":          "new",
        "admin_orders_in_progress":  "in_progress",
        "admin_orders_delivery":     "delivery",
        "admin_orders_paid":         "paid",
        "admin_orders_completed":    "completed",
        "admin_orders_invoice_req":  "invoice_req",
    }
    filter_key = status_map.get(callback.data)

    async with get_db() as db:
        if filter_key == "invoice_req":
            cur = await db.execute("""SELECT o.*, u.first_name, u.last_name FROM orders o
                JOIN users u ON o.user_id=u.id WHERE o.invoice_requested=1 ORDER BY o.created_at DESC""")
        elif filter_key:
            cur = await db.execute("""SELECT o.*, u.first_name, u.last_name FROM orders o
                JOIN users u ON o.user_id=u.id WHERE o.status=? ORDER BY o.created_at DESC""", (filter_key,))
        else:
            cur = await db.execute("""SELECT o.*, u.first_name, u.last_name FROM orders o
                JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 50""")
        orders = await cur.fetchall()

    if not orders:
        try:
            await callback.message.edit_text("📭 Замовлень не знайдено.", reply_markup=orders_filter_kb())
        except TelegramBadRequest:
            pass
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for o in orders:
        inv_icon = "🔔 " if o["invoice_requested"] else ""
        buttons.append([InlineKeyboardButton(
            text=f"{inv_icon}#{o['order_number']} {format_status(o['status'])} — {o['total_amount']:.2f} грн | {o['first_name']} {o['last_name']}",
            callback_data=f"admin_order_{o['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔄 Фільтри", callback_data="admin_orders_filter")])
    try:
        await callback.message.edit_text(
            f"📋 <b>Замовлень: {len(orders)}</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("admin_order_"))
async def admin_order_detail(callback: CallbackQuery):
    # Уникаємо конфлікту з admin_orders_*
    raw = callback.data[len("admin_order_"):]
    if not raw.isdigit():
        return
    order_id = int(raw)

    async with get_db() as db:
        cur = await db.execute("""SELECT o.*, u.first_name, u.last_name, u.phone, u.email
            FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?""", (order_id,))
        order = await cur.fetchone()
        if not order:
            await callback.answer("Замовлення не знайдено", show_alert=True)
            return
        cur2 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = await cur2.fetchall()
        cur3 = await db.execute("SELECT id FROM invoices WHERE order_id=?", (order_id,))
        inv = await cur3.fetchone()
        has_invoice = bool(inv)

    items_text = "\n".join([f"  • {i['name']} × {i['quantity']} = {i['subtotal']:.2f} грн" for i in items])
    delivery_text = format_delivery(order)

    text = (
        f"📦 <b>Замовлення #{order['order_number']}</b>\n"
        f"📅 {order['created_at'][:10]}\n"
        f"Статус: {format_status(order['status'])}\n\n"
        f"👤 {order['first_name']} {order['last_name']}\n"
        f"📱 {order.get('phone','—')}\n\n"
        f"🚚 {delivery_text}\n\n"
        f"<b>Товари:</b>\n{items_text}\n\n"
        f"💰 <b>Разом: {order['total_amount']:.2f} грн</b>"
    )
    if has_invoice:
        cur4_res = await _get_db_invoice(order_id)
        if cur4_res:
            text += f"\n\n🧾 Рахунок #{cur4_res['invoice_number']} — виставлено"

    try:
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=order_status_kb(order_id, order["status"], has_invoice)
        )
    except TelegramBadRequest:
        await callback.answer("ℹ️ Вже актуально", show_alert=False)

async def _get_db_invoice(order_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM invoices WHERE order_id=?", (order_id,))
        return await cur.fetchone()

@router.callback_query(F.data.startswith("set_status_"))
async def set_order_status(callback: CallbackQuery):
    parts = callback.data.split("_")
    order_id = int(parts[2])
    new_status = parts[3]

    async with get_db() as db:
        await db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        await db.commit()
        cur = await db.execute("SELECT telegram_id FROM users u JOIN orders o ON o.user_id=u.id WHERE o.id=?", (order_id,))
        client_row = await cur.fetchone()

    client_tg = client_row["telegram_id"] if client_row else None

    # Сповіщення клієнту про зміну статусу
    STATUS_MSGS = {
        "in_progress": "🟠 Ваше замовлення взято в роботу!",
        "delivery":    "🟣 Ваше замовлення передано на доставку!",
        "paid":        "💚 Ваш платіж підтверджено! Дякуємо!",
        "completed":   "🟢 Ваше замовлення виконано! Дякуємо за покупку!",
    }
    if client_tg and new_status in STATUS_MSGS:
        try:
            await callback.bot.send_message(client_tg, STATUS_MSGS[new_status])
        except Exception:
            pass

    # Якщо статус "оплачений" — генеруємо видаткову накладну
    if new_status == "paid":
        await _generate_expense_doc(callback, order_id, client_tg)
        return

    await callback.answer(f"✅ Статус: {format_status(new_status)}", show_alert=False)
    # Оновлюємо повідомлення
    fake_cb = callback
    fake_cb.data = f"admin_order_{order_id}"
    await admin_order_detail(fake_cb)

async def _generate_expense_doc(callback: CallbackQuery, order_id: int, client_tg):
    """Генеруємо видаткову накладну і надсилаємо клієнту"""
    from utils.pdf_generator import generate_expense_pdf
    from utils.helpers import generate_expense_number
    from aiogram.types import BufferedInputFile
    from datetime import date

    exp_number = generate_expense_number()
    today = date.today().strftime("%d.%m.%Y")

    async with get_db() as db:
        cur = await db.execute("""SELECT o.*, u.first_name, u.last_name, u.phone
            FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?""", (order_id,))
        order = await cur.fetchone()
        cur2 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = await cur2.fetchall()
        cur3 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = await cur3.fetchone() or {}

    pdf_data = {
        "expense_number": exp_number,
        "expense_date": today,
        "seller": {
            "name": fop.get("fop_name", ""),
            "edrpou": fop.get("edrpou", ""),
            "iban": fop.get("iban", ""),
            "address": fop.get("legal_address", ""),
            "phone": fop.get("phone", ""),
        },
        "buyer": {
            "name": f"{order['first_name']} {order['last_name']}",
            "phone": order.get("phone", ""),
        },
        "items": [{"name": i["name"], "qty": i["quantity"], "price": i["unit_price"], "subtotal": i["subtotal"]} for i in items],
        "total": order["total_amount"],
    }
    pdf_bytes = generate_expense_pdf(pdf_data)
    pdf_file = BufferedInputFile(pdf_bytes, filename=f"expense_{exp_number}.pdf")

    await callback.message.answer_document(
        pdf_file,
        caption=f"💚 <b>Оплата підтверджена!</b>\n📄 Видаткова накладна <b>{exp_number}</b>",
        parse_mode="HTML"
    )
    if client_tg:
        try:
            await callback.bot.send_document(
                client_tg, pdf_file,
                caption=f"💚 <b>Дякуємо за оплату!</b>\n\n"
                        f"📄 Ваша видаткова накладна <b>{exp_number}</b>\n"
                        f"Замовлення виконано — очікуйте доставку!"
            )
        except Exception:
            pass

    await callback.answer("💚 Оплата підтверджена, накладну надіслано!", show_alert=True)
    fake_cb = callback
    fake_cb.data = f"admin_order_{order_id}"
    await admin_order_detail(fake_cb)

# ─── ПЕРЕГЛЯД РАХУНКУ АДМІНОМ ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_view_invoice_"))
async def admin_view_invoice(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM invoices WHERE order_id=?", (order_id,))
        inv = await cur.fetchone()
        if not inv:
            await callback.answer("Рахунок не знайдено", show_alert=True)
            return
        cur2 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = await cur2.fetchall()
        cur3 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = await cur3.fetchone() or {}

    items_text = "\n".join([f"  {i+1}. {items[i]['name']} × {items[i]['quantity']} = {items[i]['subtotal']:.2f} грн" for i in range(len(items))])
    from utils.helpers import format_invoice_status
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    text = (
        f"🧾 <b>РАХУНОК #{inv['invoice_number']}</b>\n"
        f"Дата: {inv['invoice_date']}\n"
        f"Статус: {format_invoice_status(inv['status'])}\n\n"
        f"<b>Товари:</b>\n{items_text}\n\n"
        f"💰 <b>Разом: {inv['total_amount']:.2f} грн</b>\n"
        f"{'Оплатити до: ' + inv['due_date'] if inv.get('due_date') else ''}"
    )
    from keyboards.admin_kb import invoice_status_kb
    kb = InlineKeyboardMarkup(inline_keyboard=[
        *invoice_status_kb(inv["id"]).inline_keyboard,
        [InlineKeyboardButton(text="◀️ До замовлення", callback_data=f"admin_order_{order_id}")],
    ])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest:
        pass

# ─── ВИДАЛЕННЯ ЗАМОВЛЕННЯ ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_delete_order_"))
async def admin_delete_order(callback: CallbackQuery):
    raw = callback.data[len("admin_delete_order_"):]
    if raw.startswith("confirm_"):
        order_id = int(raw[len("confirm_"):])
        await _do_delete_order(callback, order_id)
    else:
        order_id = int(raw)
        try:
            await callback.message.edit_text(
                f"🗑 <b>Видалити замовлення?</b>\n\nЦю дію не можна скасувати. Клієнт отримає повідомлення.",
                parse_mode="HTML",
                reply_markup=confirm_delete_order_kb(order_id)
            )
        except TelegramBadRequest:
            pass

async def _do_delete_order(callback: CallbackQuery, order_id: int):
    async with get_db() as db:
        cur = await db.execute("""SELECT o.order_number, u.telegram_id, u.first_name
            FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?""", (order_id,))
        row = await cur.fetchone()
        if not row:
            await callback.answer("Замовлення не знайдено", show_alert=True)
            return
        order_number = row["order_number"]
        client_tg = row["telegram_id"]
        await db.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
        await db.execute("DELETE FROM invoices WHERE order_id=?", (order_id,))
        await db.execute("DELETE FROM orders WHERE id=?", (order_id,))
        await db.commit()

    # Сповіщення клієнту
    try:
        await callback.bot.send_message(
            client_tg,
            f"❌ <b>Замовлення #{order_number} скасовано.</b>\n\n"
            f"Якщо у вас є питання — зверніться до менеджера.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("🗑 Замовлення видалено", show_alert=True)
    try:
        await callback.message.edit_text("📋 Оберіть фільтр:", reply_markup=orders_filter_kb())
    except TelegramBadRequest:
        pass
