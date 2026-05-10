from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from models.database import get_db
from keyboards.client_kb import cart_kb, confirm_order_kb, main_menu_kb, delivery_type_kb
from utils.helpers import generate_order_number, format_price, format_delivery
from utils.states import DeliveryStates

router = Router()
# In-memory cart: {telegram_id: {product_id: qty}}
carts = {}
# Тимчасові дані доставки: {telegram_id: {delivery_type, np_city, np_branch, ...}}
delivery_data: dict = {}

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
        from aiogram.exceptions import TelegramBadRequest
        try:
            await message_or_cb.message.edit_text(text, parse_mode="HTML", reply_markup=cart_kb(items))
        except TelegramBadRequest:
            pass

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
    max_qty = p["stock_qty"] if p else 99
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
        from aiogram.exceptions import TelegramBadRequest
        try:
            await callback.message.edit_text("🛒 Кошик порожній.")
        except TelegramBadRequest:
            pass
        return
    await _render_cart(callback, tg_id, cart)

@router.callback_query(F.data == "cart_clear")
async def cart_clear(callback: CallbackQuery):
    carts.pop(callback.from_user.id, None)
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text("🗑 Кошик очищено.")
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = callback.from_user.id
    await _render_cart(callback, tg_id, carts.get(tg_id, {}))

# ─── ОФОРМЛЕННЯ: вибір доставки ─────────────────────────────────────────────

@router.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    cart = carts.get(tg_id, {})
    if not cart:
        await callback.answer("Кошик порожній!", show_alert=True)
        return
    await state.set_state(DeliveryStates.choose_type)
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            "🚚 <b>Оберіть спосіб доставки:</b>",
            parse_mode="HTML",
            reply_markup=delivery_type_kb()
        )
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "change_delivery")
async def change_delivery(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DeliveryStates.choose_type)
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            "🚚 <b>Оберіть спосіб доставки:</b>",
            parse_mode="HTML",
            reply_markup=delivery_type_kb()
        )
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "delivery_pickup")
async def delivery_pickup(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    delivery_data[tg_id] = {"delivery_type": "pickup"}
    await state.clear()
    await _show_order_confirm(callback)

@router.callback_query(F.data == "delivery_nova_poshta")
async def delivery_nova_poshta(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DeliveryStates.nova_poshta_city)
    delivery_data[callback.from_user.id] = {"delivery_type": "nova_poshta"}
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            "📦 <b>Нова Пошта</b>\n\nВведіть місто (наприклад: Київ):",
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

@router.message(DeliveryStates.nova_poshta_city)
async def np_city_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    delivery_data.setdefault(tg_id, {})["np_city"] = message.text.strip()
    await state.set_state(DeliveryStates.nova_poshta_branch)
    await message.answer("Введіть номер відділення (наприклад: 15):")

@router.message(DeliveryStates.nova_poshta_branch)
async def np_branch_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    delivery_data.setdefault(tg_id, {})["np_branch"] = message.text.strip()
    await state.set_state(DeliveryStates.nova_poshta_recipient)
    await message.answer("Введіть ПІБ отримувача або /skip (якщо ваше ім'я):")

@router.message(DeliveryStates.nova_poshta_recipient)
async def np_recipient_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    if message.text.strip().lower() != "/skip":
        delivery_data.setdefault(tg_id, {})["np_recipient"] = message.text.strip()
    await state.clear()
    # Показуємо підтвердження через нове повідомлення
    await _show_order_confirm_message(message)

@router.callback_query(F.data == "delivery_taxi")
async def delivery_taxi(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DeliveryStates.taxi_address)
    delivery_data[callback.from_user.id] = {"delivery_type": "taxi"}
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            "🚕 <b>Доставка таксі</b>\n\nВведіть адресу доставки:",
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

@router.message(DeliveryStates.taxi_address)
async def taxi_address_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    delivery_data.setdefault(tg_id, {})["delivery_address"] = message.text.strip()
    await state.set_state(DeliveryStates.taxi_datetime)
    await message.answer("Введіть дату та час доставки (наприклад: 15.05.2026 14:00):")

@router.message(DeliveryStates.taxi_datetime)
async def taxi_datetime_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    delivery_data.setdefault(tg_id, {})["delivery_date"] = message.text.strip()
    await state.clear()
    await _show_order_confirm_message(message)

async def _build_confirm_text(tg_id: int) -> str:
    cart = carts.get(tg_id, {})
    ddata = delivery_data.get(tg_id, {})
    total = 0
    items_text = ""
    async with get_db() as db:
        for pid, qty in cart.items():
            cur = await db.execute("SELECT name, client_price FROM products WHERE id=?", (pid,))
            p = await cur.fetchone()
            sub = p["client_price"] * qty
            total += sub
            items_text += f"• {p['name']} × {qty} = {sub:.2f} грн\n"

    delivery_text = format_delivery(ddata)
    return (
        f"📋 <b>Підтвердження замовлення</b>\n\n"
        f"{items_text}"
        f"\n💰 <b>Разом: {total:.2f} грн</b>\n\n"
        f"🚚 <b>Доставка:</b> {delivery_text}"
    )

async def _show_order_confirm(callback: CallbackQuery):
    text = await _build_confirm_text(callback.from_user.id)
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=confirm_order_kb())
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=confirm_order_kb())

async def _show_order_confirm_message(message: Message):
    text = await _build_confirm_text(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=confirm_order_kb())

# ─── ПІДТВЕРДЖЕННЯ ЗАМОВЛЕННЯ ────────────────────────────────────────────────

@router.callback_query(F.data == "order_confirm")
async def confirm_order(callback: CallbackQuery):
    tg_id = callback.from_user.id
    cart = carts.get(tg_id, {})
    if not cart:
        await callback.answer("Кошик порожній!", show_alert=True)
        return

    ddata = delivery_data.get(tg_id, {"delivery_type": "pickup"})

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
        await db.execute(
            """INSERT INTO orders
               (order_number,user_id,status,total_amount,
                delivery_type,delivery_address,delivery_date,
                np_city,np_branch,np_recipient)
               VALUES (?,?,'new',?,?,?,?,?,?,?)""",
            (order_number, user["id"], total,
             ddata.get("delivery_type","pickup"),
             ddata.get("delivery_address",""),
             ddata.get("delivery_date",""),
             ddata.get("np_city",""),
             ddata.get("np_branch",""),
             ddata.get("np_recipient",""))
        )
        await db.commit()
        cur = await db.execute("SELECT id FROM orders WHERE order_number=?", (order_number,))
        order_id = (await cur.fetchone())["id"]
        for item in items_data:
            await db.execute(
                "INSERT INTO order_items (order_id,product_id,quantity,unit_price,subtotal) VALUES (?,?,?,?,?)",
                (order_id, item["pid"], item["qty"], item["price"], item["sub"])
            )
            await db.execute("UPDATE products SET stock_qty=MAX(0, stock_qty-?) WHERE id=?", (item["qty"], item["pid"]))
        await db.commit()

    carts.pop(tg_id, None)
    delivery_data.pop(tg_id, None)

    delivery_text = format_delivery(ddata)
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.message.edit_text(
            f"✅ <b>Замовлення #{order_number} прийнято!</b>\n\n"
            f"🚚 {delivery_text}\n\n"
            f"Очікуйте підтвердження менеджера.",
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    import os
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
    for admin_id in ADMIN_IDS:
        try:
            items_text = "\n".join([f"• {i['name']} × {i['qty']} = {i['sub']:.2f} грн" for i in items_data])
            await callback.bot.send_message(
                admin_id,
                f"🔔 <b>Нове замовлення #{order_number}</b>\n"
                f"👤 {user['first_name']} {user['last_name']}\n"
                f"📱 {user.get('phone','—')}\n"
                f"🚚 {delivery_text}\n\n"
                f"{items_text}\n\n"
                f"💰 <b>Разом: {total:.2f} грн</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
