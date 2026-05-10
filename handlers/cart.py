from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from models.database import get_db
from keyboards.client_kb import cart_kb, confirm_order_kb, main_menu_kb
from utils.helpers import generate_order_number, format_price


router = Router()
# In-memory cart: {telegram_id: {product_id: qty}}
carts = {}

@router.callback_query(F.data.startswith("add_cart_"))
async def add_to_cart(callback: CallbackQuery):
    parts = callback.data.split("_")
    product_id = int(parts[2])
    qty = int(parts[3])
    tg_id = callback.from_user.id

    async with get_db() as db:
        cur = await db.execute("SELECT name, client_price, stock_qty FROM products WHERE id=?", (product_id,))
        p = await cur.fetchone()

    if tg_id not in carts:
        carts[tg_id] = {}
    current = carts[tg_id].get(product_id, 0)
    carts[tg_id][product_id] = min(current + qty, p["stock_qty"])

    await callback.answer(f"✅ {p['name']} додано до кошика ({carts[tg_id][product_id]} шт)", show_alert=False)

@router.message(F.text == "🛒 Кошик")
async def show_cart(message: Message):
    tg_id = message.from_user.id
    cart = carts.get(tg_id, {})
    if not cart:
        await message.answer("🛒 Кошик порожній.\n\nПерейдіть до 🛍 Каталогу щоб додати товари.")
        return
    await _render_cart(message, tg_id, cart)

async def _render_cart(message_or_cb, tg_id, cart):
    items = []
    total = 0
    async with get_db() as db:
        for pid, qty in cart.items():
            cur = await db.execute("SELECT id, name, client_price FROM products WHERE id=?", (pid,))
            p = await cur.fetchone()
            subtotal = p["client_price"] * qty
            total += subtotal
            items.append({**p, "product_id": pid, "qty": qty, "subtotal": subtotal})

    text = "🛒 <b>Ваш кошик:</b>\n\n"
    for item in items:
        text += f"• {item['name']} × {item['qty']} = {item['subtotal']:.2f} грн\n"
    text += f"\n💰 <b>Разом: {total:.2f} грн</b>"

    if hasattr(message_or_cb, "answer"):
        await message_or_cb.answer(text, parse_mode="HTML", reply_markup=cart_kb(items))
    else:
        await message_or_cb.message.edit_text(text, parse_mode="HTML", reply_markup=cart_kb(items))

@router.callback_query(F.data.startswith("cart_minus_"))
async def cart_minus(callback: CallbackQuery):
    pid = int(callback.data.split("_")[2])
    tg_id = callback.from_user.id
    if tg_id in carts and pid in carts[tg_id]:
        carts[tg_id][pid] = max(carts[tg_id][pid] - 1, 1)
    await _render_cart(callback, tg_id, carts.get(tg_id, {}))

@router.callback_query(F.data.startswith("cart_plus_"))
async def cart_plus(callback: CallbackQuery):
    pid = int(callback.data.split("_")[2])
    tg_id = callback.from_user.id
    async with get_db() as db:
        cur = await db.execute("SELECT stock_qty FROM products WHERE id=?", (pid,))
        p = await cur.fetchone()
    max_qty = p[0] if p else 99
    if tg_id in carts and pid in carts[tg_id]:
        carts[tg_id][pid] = min(carts[tg_id][pid] + 1, max_qty)
    await _render_cart(callback, tg_id, carts.get(tg_id, {}))

@router.callback_query(F.data.startswith("cart_remove_"))
async def cart_remove(callback: CallbackQuery):
    pid = int(callback.data.split("_")[2])
    tg_id = callback.from_user.id
    if tg_id in carts:
        carts[tg_id].pop(pid, None)
    cart = carts.get(tg_id, {})
    if not cart:
        await callback.message.edit_text("🛒 Кошик порожній.")
        return
    await _render_cart(callback, tg_id, cart)

@router.callback_query(F.data == "cart_clear")
async def cart_clear(callback: CallbackQuery):
    carts.pop(callback.from_user.id, None)
    await callback.message.edit_text("🗑 Кошик очищено.")

@router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery):
    tg_id = callback.from_user.id
    await _render_cart(callback, tg_id, carts.get(tg_id, {}))

@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    tg_id = callback.from_user.id
    cart = carts.get(tg_id, {})
    if not cart:
        await callback.answer("Кошик порожній!", show_alert=True)
        return

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,))
        user = await cur.fetchone()
        cur2 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = await cur2.fetchone()

    np_info = ""
    if user.get("np_city"):
        np_info = f"\n🚚 Нова Пошта: {user['np_city']}, відд. {user['np_branch']}, {user['np_recipient'] or user['first_name']+' '+user['last_name']}"

    total = 0
    items_text = ""
    async with get_db() as db:
        for pid, qty in cart.items():
            cur = await db.execute("SELECT name, client_price FROM products WHERE id=?", (pid,))
            p = await cur.fetchone()
            sub = p["client_price"] * qty
            total += sub
            items_text += f"• {p['name']} × {qty} = {sub:.2f} грн\n"

    fop_block = ""
    if fop.get("fop_name"):
        fop_block = (
            f"\n\n💳 <b>Реквізити для оплати (ФОП):</b>\n"
            f"👤 {fop['fop_name']}\n"
            f"🏦 IBAN: <code>{fop['iban'] or '—'}</code>\n"
            f"📋 ЄДРПОУ/ІПН: {fop['edrpou'] or '—'}"
        )

    text = (
        f"📋 <b>Підтвердження замовлення</b>\n\n"
        f"{items_text}"
        f"\n💰 <b>Разом: {total:.2f} грн</b>"
        f"{np_info}"
        f"{fop_block}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=confirm_order_kb())

@router.callback_query(F.data == "order_confirm")
async def confirm_order(callback: CallbackQuery):
    tg_id = callback.from_user.id
    cart = carts.get(tg_id, {})
    if not cart:
        await callback.answer("Кошик порожній!", show_alert=True)
        return

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,))
        user = await cur.fetchone()
        cur2 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = await cur2.fetchone()

    order_number = generate_order_number()
    total = 0
    items_data = []
    async with get_db() as db:
        for pid, qty in cart.items():
            cur = await db.execute("SELECT name, client_price, stock_qty FROM products WHERE id=?", (pid,))
            p = await cur.fetchone()
            sub = p["client_price"] * qty
            total += sub
            items_data.append({"pid": pid, "qty": qty, "price": p["client_price"], "sub": sub, "name": p["name"]})

    async with get_db() as db:
        await db.execute("""INSERT INTO orders (order_number,user_id,status,total_amount,np_city,np_branch,np_recipient)
            VALUES (?,?,'new',?,?,?,?)""",
            (order_number, user["id"], total,
             user.get("np_city",""), user.get("np_branch",""), user.get("np_recipient","")))
        await db.commit()
        cur = await db.execute("SELECT id FROM orders WHERE order_number=?", (order_number,))
        order_id = (await cur.fetchone())["id"]
        for item in items_data:
            await db.execute("INSERT INTO order_items (order_id,product_id,quantity,unit_price,subtotal) VALUES (?,?,?,?,?)",
                (order_id, item["pid"], item["qty"], item["price"], item["sub"]))
            await db.execute("UPDATE products SET stock_qty=MAX(0, stock_qty-?) WHERE id=?", (item["qty"], item["pid"]))
        await db.commit()

    carts.pop(tg_id, None)

    fop_block = ""
    if fop.get("fop_name"):
        purpose = (fop.get("payment_template") or "Оплата за замовленням №{order_number}").replace("{order_number}", order_number)
        fop_block = (
            f"\n\n💳 <b>Реквізити для оплати:</b>\n"
            f"👤 {fop['fop_name']}\n"
            f"🏦 IBAN: <code>{fop['iban'] or '—'}</code>\n"
            f"📋 ЄДРПОУ/ІПН: {fop['edrpou'] or '—'}\n"
            f"💬 Призначення: {purpose}"
        )

    await callback.message.edit_text(
        f"✅ <b>Замовлення #{order_number} прийнято!</b>\n\n"
        f"Очікуйте підтвердження менеджера."
        f"{fop_block}",
        parse_mode="HTML"
    )

    import os
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
    for admin_id in ADMIN_IDS:
        try:
            items_text = "\n".join([f"• {i['name']} × {i['qty']} = {i['sub']:.2f} грн" for i in items_data])
            await callback.bot.send_message(
                admin_id,
                f"🔔 <b>Нове замовлення #{order_number}</b>\n"
                f"👤 {user['first_name']} {user['last_name']}\n"
                f"📱 {user.get('phone','—')}\n\n"
                f"{items_text}\n\n"
                f"💰 <b>Разом: {total:.2f} грн</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
