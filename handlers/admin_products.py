from aiogram.exceptions import TelegramBadRequest
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from models.database import get_db
from keyboards.admin_kb import products_admin_kb, product_admin_detail_kb, select_brand_kb, select_category_kb
from utils.states import AddProductStates, EditProductStates, StockUpdateStates
import os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

@router.message(F.text == "📦 Товари")
async def admin_products(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE is_active=1 ORDER BY name")
        products = await cur.fetchall()
    if not products:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await message.answer("📭 Товарів ще немає.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Додати товар", callback_data="add_product")]
            ]))
        return
    await message.answer(f"📦 <b>Товари ({len(products)})</b>:", parse_mode="HTML",
                         reply_markup=products_admin_kb(products))

@router.callback_query(F.data == "admin_products")
async def cb_admin_products(callback: CallbackQuery):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE is_active=1 ORDER BY name")
        products = await cur.fetchall()
    try:
        await callback.message.edit_text(f"📦 <b>Товари ({len(products)})</b>:", parse_mode="HTML",
                                     reply_markup=products_admin_kb(products))
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("admin_prod_"))
async def admin_product_detail(callback: CallbackQuery):
    pid = int(callback.data.split("_")[2])
    async with get_db() as db:
        cur = await db.execute("""SELECT p.*, b.name as brand_name, c.name as cat_name FROM products p
            LEFT JOIN brands b ON p.brand_id=b.id
            LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=?""", (pid,))
        p = await cur.fetchone()
    text = (
        f"📦 <b>{p['name']}</b>\n"
        f"Артикул: {p['sku']}\n"
        f"Бренд: {p.get('brand_name','—')} | Категорія: {p.get('cat_name','—')}\n"
        f"Об'єм: {p.get('volume','—')}\n"
        f"💰 Ціна клієнта: {p['client_price']:.2f} грн\n"
        f"💵 Закупочна ціна: {p.get('purchase_price',0):.2f} грн\n"
        f"📦 Залишок: <b>{p['stock_qty']} шт</b>\n"
        f"{'Опис: '+p['description'] if p.get('description') else ''}"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=product_admin_detail_kb(pid))
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "add_product")
async def start_add_product(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📦 Додавання нового товару\n\nВведіть <b>назву товару</b>:", parse_mode="HTML")
    await state.set_state(AddProductStates.name)

@router.message(AddProductStates.name)
async def ap_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введіть <b>артикул (SKU)</b>:", parse_mode="HTML")
    await state.set_state(AddProductStates.sku)

@router.message(AddProductStates.sku)
async def ap_sku(message: Message, state: FSMContext):
    sku = message.text.strip()
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM products WHERE sku=?", (sku,))
        if await cur.fetchone():
            await message.answer("❌ Такий артикул вже існує. Введіть інший:")
            return
    await state.update_data(sku=sku)
    await message.answer("Надішліть <b>фото товару</b> або /skip щоб пропустити:", parse_mode="HTML")
    await state.set_state(AddProductStates.photo)

@router.message(AddProductStates.photo, F.photo)
async def ap_photo(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await message.answer("Введіть <b>опис товару</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddProductStates.description)

@router.message(AddProductStates.photo, F.text == "/skip")
async def ap_photo_skip(message: Message, state: FSMContext):
    await message.answer("Введіть <b>опис товару</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddProductStates.description)

@router.message(AddProductStates.description)
async def ap_description(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(description=message.text.strip())
    await message.answer("Введіть <b>склад/інгредієнти</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddProductStates.ingredients)

@router.message(AddProductStates.ingredients)
async def ap_ingredients(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(ingredients=message.text.strip())
    await message.answer("Введіть <b>об'єм</b> (напр. 500 мл) або /skip:", parse_mode="HTML")
    await state.set_state(AddProductStates.volume)

@router.message(AddProductStates.volume)
async def ap_volume(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(volume=message.text.strip())
    await message.answer("Введіть <b>ціну для клієнта</b> (грн):", parse_mode="HTML")
    await state.set_state(AddProductStates.client_price)

@router.message(AddProductStates.client_price)
async def ap_client_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(client_price=price)
        await message.answer("Введіть <b>закупочну ціну</b> (грн, тільки для адміна) або /skip:", parse_mode="HTML")
        await state.set_state(AddProductStates.purchase_price)
    except ValueError:
        await message.answer("❌ Невірний формат. Введіть число (напр. 150.00):")

@router.message(AddProductStates.purchase_price)
async def ap_purchase_price(message: Message, state: FSMContext):
    if message.text != "/skip":
        try:
            await state.update_data(purchase_price=float(message.text.replace(",", ".")))
        except ValueError:
            await message.answer("❌ Невірний формат. Введіть число або /skip:")
            return
    await message.answer("Введіть <b>кількість на складі</b>:", parse_mode="HTML")
    await state.set_state(AddProductStates.stock_qty)

@router.message(AddProductStates.stock_qty)
async def ap_stock(message: Message, state: FSMContext):
    try:
        qty = int(message.text)
        await state.update_data(stock_qty=qty)
    except ValueError:
        await message.answer("❌ Введіть ціле число:")
        return
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM brands ORDER BY name")
        brands = await cur.fetchall()
    if brands:
        await message.answer("Оберіть <b>бренд</b>:", parse_mode="HTML", reply_markup=select_brand_kb(brands))
        await state.set_state(AddProductStates.brand)
    else:
        await state.update_data(brand_id=None)
        await _ask_category(message, state)

@router.callback_query(AddProductStates.brand, F.data.startswith("sel_brand_"))
async def ap_brand(callback: CallbackQuery, state: FSMContext):
    brand_id = int(callback.data.split("_")[2])
    await state.update_data(brand_id=brand_id if brand_id else None)
    await _ask_category(callback.message, state)

async def _ask_category(message, state):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM categories ORDER BY name")
        cats = await cur.fetchall()
    if cats:
        await message.answer("Оберіть <b>категорію</b>:", parse_mode="HTML", reply_markup=select_category_kb(cats))
        await state.set_state(AddProductStates.category)
    else:
        await state.update_data(category_id=None)
        await _save_product(message, state)

@router.callback_query(AddProductStates.category, F.data.startswith("sel_cat_"))
async def ap_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id if cat_id else None)
    await _save_product(callback.message, state)

async def _save_product(message, state):
    data = await state.get_data()
    async with get_db() as db:
        await db.execute("""INSERT INTO products
            (name,sku,photo_file_id,description,ingredients,volume,client_price,purchase_price,stock_qty,brand_id,category_id,comment)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["sku"], data.get("photo_file_id"),
             data.get("description"), data.get("ingredients"), data.get("volume"),
             data["client_price"], data.get("purchase_price"),
             data.get("stock_qty", 0), data.get("brand_id"), data.get("category_id"),
             data.get("comment")))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Товар <b>{data['name']}</b> додано до каталогу!", parse_mode="HTML")

@router.callback_query(F.data.startswith("stock_prod_"))
async def update_stock_start(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    await state.update_data(stock_product_id=pid)
    await callback.message.answer("Введіть нову кількість на складі:")
    from utils.states import AddProductStates, EditProductStates, StockUpdateStates
    await state.set_state("stock_update")

@router.message(StockUpdateStates.qty)
async def update_stock_value(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("stock_product_id")
    if not pid:
        return
    qty = int(message.text)
    async with get_db() as db:
        await db.execute("UPDATE products SET stock_qty=? WHERE id=?", (qty, pid))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Залишок оновлено: <b>{qty} шт</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("del_prod_"))
async def delete_product(callback: CallbackQuery):
    pid = int(callback.data.split("_")[2])
    async with get_db() as db:
        await db.execute("UPDATE products SET is_active=0 WHERE id=?", (pid,))
        await db.commit()
    await callback.answer("🗑 Товар видалено", show_alert=False)
    await cb_admin_products(callback)


# ── Edit Product ──
@router.callback_query(F.data.startswith("edit_prod_"))
async def edit_product_start(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[2])
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()
    if not p:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    text = (
        f"✏️ <b>Редагування: {p['name']}</b>\n\n"
        f"Оберіть поле для зміни:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Назва", callback_data=f"epf_{prod_id}_name"),
         InlineKeyboardButton(text="🔖 Артикул", callback_data=f"epf_{prod_id}_sku")],
        [InlineKeyboardButton(text="📄 Опис", callback_data=f"epf_{prod_id}_description"),
         InlineKeyboardButton(text="🧪 Склад", callback_data=f"epf_{prod_id}_ingredients")],
        [InlineKeyboardButton(text="📦 Обʼєм", callback_data=f"epf_{prod_id}_volume"),
         InlineKeyboardButton(text="💰 Ціна клієнта", callback_data=f"epf_{prod_id}_client_price")],
        [InlineKeyboardButton(text="💵 Закупівельна", callback_data=f"epf_{prod_id}_purchase_price"),
         InlineKeyboardButton(text="📊 Залишок", callback_data=f"epf_{prod_id}_stock_qty")],
        [InlineKeyboardButton(text="💬 Коментар", callback_data=f"epf_{prod_id}_comment")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_prod_{prod_id}")],
    ])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest:
        pass
    await state.update_data(edit_prod_id=prod_id)


@router.callback_query(F.data.startswith("epf_"))
async def edit_product_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    prod_id = int(parts[1])
    field = "_".join(parts[2:])

    field_labels = {
        "name": "назву",
        "sku": "артикул",
        "description": "опис",
        "ingredients": "склад товару",
        "volume": "обʼєм",
        "client_price": "ціну для клієнта (число)",
        "purchase_price": "закупівельну ціну (число)",
        "stock_qty": "кількість на складі (ціле число)",
        "comment": "коментар",
    }
    label = field_labels.get(field, field)
    await state.update_data(edit_prod_id=prod_id, edit_field=field)
    await state.set_state(EditProductStates.value)
    await callback.message.answer(
        f"✏️ Введіть нове значення для поля <b>{label}</b>:\n"
        f"(або /cancel щоб скасувати)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(EditProductStates.value)
async def edit_product_save(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Редагування скасовано.")
        return

    data = await state.get_data()
    prod_id = data.get("edit_prod_id")
    field = data.get("edit_field")

    allowed_fields = ["name", "sku", "description", "ingredients", "volume",
                      "client_price", "purchase_price", "stock_qty", "comment"]
    if field not in allowed_fields:
        await state.clear()
        return

    value = message.text.strip()

    # Числові поля — перевіряємо формат
    if field in ("client_price", "purchase_price"):
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            await message.answer("⚠️ Введіть числове значення (напр. 150.00)")
            return
    elif field == "stock_qty":
        try:
            value = int(value)
        except ValueError:
            await message.answer("⚠️ Введіть ціле число (напр. 10)")
            return

    async with get_db() as db:
        await db.execute(f"UPDATE products SET {field}=? WHERE id=?", (value, prod_id))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Поле оновлено успішно!")

    # Показуємо оновлену картку товару
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if p:
        from keyboards.admin_kb import product_admin_detail_kb
        text = (
            f"📦 <b>{p['name']}</b> | {p.get('sku','')}\n"
            f"💰 {p['client_price']} грн | 📊 {p.get('stock_qty', 0)} шт"
        )
        await message.answer(text, parse_mode="HTML",
                             reply_markup=product_admin_detail_kb(prod_id))
