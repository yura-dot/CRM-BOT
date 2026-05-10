from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from models.database import get_db
from keyboards.client_kb import catalog_categories_kb, product_list_kb, product_detail_kb
import aiosqlite

router = Router()

async def get_approved_user(tg_id):
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=? AND is_approved=1", (tg_id,))
        return await cur.fetchone()

@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message):
    user = await get_approved_user(message.from_user.id)
    if not user:
        await message.answer("⛔ Доступ закрито. Очікуйте підтвердження адміністратора.")
        return
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM categories ORDER BY name")
        cats = [dict(r) for r in await cur.fetchall()]
    if not cats:
        await message.answer("📭 Каталог поки порожній.")
        return
    await message.answer("📂 Оберіть категорію:", reply_markup=catalog_categories_kb(cats))

@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery):
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM categories ORDER BY name")
        cats = [dict(r) for r in await cur.fetchall()]
    await callback.message.edit_text("📂 Оберіть категорію:", reply_markup=catalog_categories_kb(cats))

@router.callback_query(F.data.startswith("cat_"))
async def show_category_products(callback: CallbackQuery):
    cat_id = callback.data.split("_")[1]
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        if cat_id == "all":
            cur = await db.execute("SELECT * FROM products WHERE is_active=1 ORDER BY name")
        else:
            cur = await db.execute("SELECT * FROM products WHERE is_active=1 AND category_id=? ORDER BY name", (cat_id,))
        products = [dict(r) for r in await cur.fetchall()]
    if not products:
        await callback.message.edit_text("📭 Товарів у цій категорії немає.", reply_markup=product_list_kb([], cat_id))
        return
    text = f"🛍 Знайдено товарів: <b>{len(products)}</b>\nОберіть товар:"
    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=product_list_kb(products, cat_id if cat_id != "all" else None))

@router.callback_query(F.data.startswith("prod_"))
async def show_product_detail(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""SELECT p.*, b.name as brand_name, c.name as cat_name
            FROM products p
            LEFT JOIN brands b ON p.brand_id=b.id
            LEFT JOIN categories c ON p.category_id=c.id
            WHERE p.id=?""", (product_id,))
        p = dict(await cur.fetchone())

    in_stock = p["stock_qty"] > 0
    stock_text = f"✅ В наявності: {p['stock_qty']} шт" if in_stock else "❌ Немає в наявності"
    brand_line = ("🏷 Бренд: " + p["brand_name"]) if p.get("brand_name") else ""
    ingredients_line = ("\n🧪 Склад: " + p["ingredients"]) if p.get("ingredients") else ""
    description = p.get("description", "")
    volume = p.get("volume", "—")
    text = (
        f"<b>{p['name']}</b>\n"
        f"{brand_line}\n"
        f"📦 Обʼєм: {volume}\n"
        f"💰 Ціна: <b>{p['client_price']:.2f} грн</b>\n"
        f"{stock_text}\n\n"
        f"{description}"
        f"{ingredients_line}"
    )

    if p.get("photo_file_id"):
        await callback.message.answer_photo(
            photo=p["photo_file_id"],
            caption=text, parse_mode="HTML",
            reply_markup=product_detail_kb(product_id, 1, in_stock)
        )
        await callback.message.delete()
    else:
        await callback.message.edit_text(text, parse_mode="HTML",
                                         reply_markup=product_detail_kb(product_id, 1, in_stock))

@router.callback_query(F.data.startswith("qty_"))
async def change_qty(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]
    product_id = int(parts[2])
    qty = int(parts[3])

    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT stock_qty FROM products WHERE id=?", (product_id,))
        p = await cur.fetchone()
    max_qty = p["stock_qty"]

    if action == "plus":
        qty = min(qty + 1, max_qty)
    elif action == "minus":
        qty = max(qty - 1, 1)

    await callback.message.edit_reply_markup(
        reply_markup=product_detail_kb(product_id, qty, max_qty > 0)
    )
