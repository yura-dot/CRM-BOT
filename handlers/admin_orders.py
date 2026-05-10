from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from models.database import get_db
from keyboards.admin_kb import orders_filter_kb, order_status_kb
from utils.helpers import format_status
import aiosqlite, os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

@router.message(F.text == "📋 Замовлення")
async def admin_orders(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("📋 <b>Замовлення</b>\nОберіть фільтр:", parse_mode="HTML",
                         reply_markup=orders_filter_kb())

@router.callback_query(F.data.startswith("admin_orders_"))
async def filter_orders(callback: CallbackQuery):
    status_map = {
        "admin_orders_all": None,
        "admin_orders_new": "new",
        "admin_orders_in_progress": "in_progress",
        "admin_orders_delivery": "delivery",
        "admin_orders_completed": "completed",
        "admin_orders_invoice_req": "invoice_req",
    }
    filter_key = status_map.get(callback.data)

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if filter_key == "invoice_req":
            cur = await db.execute("""SELECT o.*, u.first_name, u.last_name FROM orders o
                JOIN users u ON o.user_id=u.id WHERE o.invoice_requested=1 ORDER BY o.created_at DESC""")
        elif filter_key:
            cur = await db.execute("""SELECT o.*, u.first_name, u.last_name FROM orders o
                JOIN users u ON o.user_id=u.id WHERE o.status=? ORDER BY o.created_at DESC""", (filter_key,))
        else:
            cur = await db.execute("""SELECT o.*, u.first_name, u.last_name FROM orders o
                JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 50""")
        orders = [dict(r) for r in await cur.fetchall()]

    if not orders:
        await callback.message.edit_text("📭 Замовлень не знайдено.", reply_markup=orders_filter_kb())
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
    await callback.message.edit_text(
        f"📋 <b>Замовлень: {len(orders)}</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data == "admin_orders_filter")
async def show_filter(callback: CallbackQuery):
    await callback.message.edit_text("📋 Оберіть фільтр:", reply_markup=orders_filter_kb())

@router.callback_query(F.data.startswith("admin_order_"))
async def admin_order_detail(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""SELECT o.*, u.first_name, u.last_name, u.phone, u.email,
            co.name as co_name FROM orders o
            JOIN users u ON o.user_id=u.id
            LEFT JOIN companies co ON u.company_id=co.id
            WHERE o.id=?""", (order_id,))
        order = dict(await cur.fetchone())
        cur2 = await db.execute("""SELECT oi.*, p.name, p.sku FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = [dict(r) for r in await cur2.fetchall()]

    items_text = "\n".join([f"  • {i['name']} [{i['sku']}] × {i['quantity']} = {i['subtotal']:.2f} грн" for i in items])
    np_text = ""
    if order.get("np_city"):
        np_text = f"\n🚚 НП: {order['np_city']}, відд. {order.get('np_branch','—')}, {order.get('np_recipient','—')}"
    inv_flag = "\n🔔 <b>Клієнт запросив рахунок!</b>" if order["invoice_requested"] else ""

    text = (
        f"📦 <b>Замовлення #{order['order_number']}</b>\n"
        f"📅 {order['created_at'][:10]}\n"
        f"Статус: {format_status(order['status'])}{inv_flag}\n\n"
        f"👤 {order['first_name']} {order['last_name']}\n"
        f"📱 {order.get('phone','—')} | 📧 {order.get('email','—')}\n"
        f"🏢 {order.get('co_name') or '—'}{np_text}\n\n"
        f"{items_text}\n\n"
        f"💰 <b>Разом: {order['total_amount']:.2f} грн</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=order_status_kb(order_id, order["status"]))

@router.callback_query(F.data.startswith("set_status_"))
async def set_order_status(callback: CallbackQuery):
    parts = callback.data.split("_")
    order_id = int(parts[2])
    new_status = parts[3]

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        await db.commit()
        cur = await db.execute("""SELECT o.order_number, u.telegram_id, u.first_name FROM orders o
            JOIN users u ON o.user_id=u.id WHERE o.id=?""", (order_id,))
        row = dict(await cur.fetchone())

    status_messages = {
        "new": "🔵 Ваше замовлення отримано",
        "in_progress": "🟠 Ваше замовлення обробляється",
        "delivery": "🟣 Ваше замовлення передано в доставку",
        "completed": "🟢 Ваше замовлення виконано! Дякуємо!",
    }
    try:
        await callback.bot.send_message(
            row["telegram_id"],
            f"📦 <b>Оновлення замовлення #{row['order_number']}</b>\n\n"
            f"{status_messages.get(new_status, format_status(new_status))}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer(f"✅ Статус змінено: {format_status(new_status)}", show_alert=False)
    await admin_order_detail(callback)
