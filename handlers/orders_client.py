from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from models.database import get_db
from keyboards.client_kb import my_orders_kb, order_detail_client_kb
from utils.helpers import format_status, format_invoice_status
import aiosqlite

router = Router()

@router.message(F.text == "📦 Мої замовлення")
async def my_orders(message: Message):
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id FROM users WHERE telegram_id=?", (message.from_user.id,))
        u = await cur.fetchone()
        if not u:
            await message.answer("⛔ Акаунт не знайдено.")
            return
        cur2 = await db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (u["id"],))
        orders = [dict(r) for r in await cur2.fetchall()]

    if not orders:
        await message.answer("📭 У вас ще немає замовлень.\n\nПерейдіть до 🛍 Каталогу!")
        return
    await message.answer("📦 <b>Ваші замовлення:</b>", parse_mode="HTML", reply_markup=my_orders_kb(orders))

@router.callback_query(F.data == "my_orders")
async def cb_my_orders(callback: CallbackQuery):
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id FROM users WHERE telegram_id=?", (callback.from_user.id,))
        u = await cur.fetchone()
        cur2 = await db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (u["id"],))
        orders = [dict(r) for r in await cur2.fetchall()]
    await callback.message.edit_text("📦 <b>Ваші замовлення:</b>", parse_mode="HTML", reply_markup=my_orders_kb(orders))

@router.callback_query(F.data.startswith("order_"))
async def order_detail(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        order = dict(await cur.fetchone())
        cur2 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = [dict(r) for r in await cur2.fetchall()]
        cur3 = await db.execute("SELECT * FROM invoices WHERE order_id=?", (order_id,))
        invoice = await cur3.fetchone()
        if invoice:
            invoice = dict(invoice)

    items_text = "\n".join([f"• {i['name']} × {i['quantity']} = {i['subtotal']:.2f} грн" for i in items])
    text = (
        f"📦 <b>Замовлення #{order['order_number']}</b>\n"
        f"📅 {order['created_at'][:10]}\n"
        f"Статус: {format_status(order['status'])}\n\n"
        f"{items_text}\n\n"
        f"💰 <b>Разом: {order['total_amount']:.2f} грн</b>"
    )
    if invoice:
        text += f"\n\n🧾 Рахунок #{invoice['invoice_number']} — {format_invoice_status(invoice['status'])}"

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=order_detail_client_kb(order_id, bool(invoice), bool(order["invoice_requested"]))
    )

@router.callback_query(F.data.startswith("req_invoice_"))
async def request_invoice(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    async with await get_db() as db:
        await db.execute("UPDATE orders SET invoice_requested=1 WHERE id=?", (order_id,))
        await db.commit()
        cur = await db.execute("SELECT order_number FROM orders WHERE id=?", (order_id,))
        o = await cur.fetchone()

    import os
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"📄 <b>Запит рахунку!</b>\nКлієнт запросив рахунок для замовлення <b>#{o[0]}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    await callback.answer("✅ Запит на рахунок відправлено адміністратору!", show_alert=True)
    await order_detail(callback)

@router.callback_query(F.data.startswith("view_invoice_"))
async def view_invoice(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM invoices WHERE order_id=?", (order_id,))
        inv = await cur.fetchone()
        if not inv:
            await callback.answer("Рахунок ще не створено.", show_alert=True)
            return
        inv = dict(inv)
        cur2 = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        order = dict(await cur2.fetchone())
        cur3 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = [dict(r) for r in await cur3.fetchall()]
        cur4 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = dict(await cur4.fetchone())
        cur5 = await db.execute("SELECT u.*, co.name as co_name, co.iban as co_iban, co.edrpou as co_edrpou FROM users u LEFT JOIN companies co ON u.company_id=co.id WHERE u.id=?", (order["user_id"],))
        client = dict(await cur5.fetchone())

    items_text = "\n".join([f"  {i+1}. {items[i]['name']} × {items[i]['quantity']} шт × {items[i]['unit_price']:.2f} = {items[i]['subtotal']:.2f} грн" for i in range(len(items))])
    text = (
        f"🧾 <b>РАХУНОК НА ОПЛАТУ №{inv['invoice_number']}</b>\n"
        f"від {inv['invoice_date'] or '—'}\n\n"
        f"<b>ПОСТАЧАЛЬНИК:</b>\n"
        f"{fop.get('fop_name','—')}\n"
        f"IBAN: <code>{fop.get('iban','—')}</code>\n"
        f"ЄДРПОУ/ІПН: {fop.get('edrpou','—')}\n\n"
        f"<b>ПОКУПЕЦЬ:</b>\n"
        f"{client.get('co_name') or client['first_name']+' '+client['last_name']}\n\n"
        f"<b>Товари:</b>\n{items_text}\n\n"
        f"💰 <b>РАЗОМ: {inv['total_amount']:.2f} грн</b>\n\n"
        f"Статус: {format_invoice_status(inv['status'])}\n"
        f"{'Оплатити до: '+inv['due_date'] if inv.get('due_date') else ''}"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ До замовлення", callback_data=f"order_{order_id}")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
