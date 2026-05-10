from aiogram.exceptions import TelegramBadRequest
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from models.database import get_db
from keyboards.admin_kb import clients_admin_kb, client_admin_detail_kb
import os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

@router.message(F.text == "👥 Клієнти")
async def admin_clients(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE role='client' ORDER BY is_approved, first_name")
        users = await cur.fetchall()
    if not users:
        await message.answer("👥 Клієнтів ще немає.")
        return
    pending = sum(1 for u in users if not u["is_approved"])
    text = f"👥 <b>Клієнти ({len(users)})</b>"
    if pending:
        text += f"\n🔔 Очікують підтвердження: <b>{pending}</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=clients_admin_kb(users))

@router.callback_query(F.data == "admin_clients")
async def cb_admin_clients(callback: CallbackQuery):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE role='client' ORDER BY is_approved, first_name")
        users = await cur.fetchall()
    try:
        await callback.message.edit_text(f"👥 <b>Клієнти ({len(users)})</b>", parse_mode="HTML",
                                     reply_markup=clients_admin_kb(users))
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("admin_client_"))
async def admin_client_detail(callback: CallbackQuery):
    uid = int(callback.data.split("_")[2])
    async with get_db() as db:
        cur = await db.execute("""SELECT u.*, co.name as co_name FROM users u
            LEFT JOIN companies co ON u.company_id=co.id WHERE u.id=?""", (uid,))
        u = await cur.fetchone()
        cur2 = await db.execute("SELECT * FROM companies ORDER BY name")
        companies = await cur2.fetchall()

    approved_text = "✅ Підтверджений" if u["is_approved"] else "⏳ Очікує підтвердження"
    text = (
        f"👤 <b>{u['first_name']} {u['last_name']}</b>\n"
        f"📧 {u['email']}\n"
        f"📱 {u.get('phone','—')}\n"
        f"🏢 Компанія: {u.get('co_name') or '—'}\n"
        f"Статус: {approved_text}"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=client_admin_detail_kb(uid, bool(u["is_approved"]), companies))
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("approve_"))
async def approve_client(callback: CallbackQuery):
    uid = int(callback.data.split("_")[1])
    async with get_db() as db:
        await db.execute("UPDATE users SET is_approved=1 WHERE id=?", (uid,))
        await db.commit()
        cur = await db.execute("SELECT telegram_id, first_name FROM users WHERE id=?", (uid,))
        u = await cur.fetchone()
    try:
        await callback.bot.send_message(
            u["telegram_id"],
            f"✅ <b>Вітаємо, {u['first_name']}!</b>\n\n"
            "Ваш акаунт підтверджено адміністратором.\n"
            "Натисніть /start щоб розпочати роботу!",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("✅ Клієнта підтверджено!", show_alert=False)
    await admin_client_detail(callback)

@router.callback_query(F.data.startswith("disapprove_"))
async def disapprove_client(callback: CallbackQuery):
    uid = int(callback.data.split("_")[1])
    async with get_db() as db:
        await db.execute("UPDATE users SET is_approved=0 WHERE id=?", (uid,))
        await db.commit()
    await callback.answer("🚫 Доступ відкликано", show_alert=False)
    await admin_client_detail(callback)

@router.callback_query(F.data.startswith("assign_co_"))
async def assign_company(callback: CallbackQuery):
    parts = callback.data.split("_")
    uid = int(parts[2])
    co_id = int(parts[3])
    async with get_db() as db:
        await db.execute("UPDATE users SET company_id=? WHERE id=?", (co_id, uid))
        await db.commit()
    await callback.answer("✅ Компанію призначено!", show_alert=False)
    await admin_client_detail(callback)

@router.message(F.text == "🏢 Компанії")
async def admin_companies_msg(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    from keyboards.admin_kb import companies_kb
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM companies ORDER BY name")
        companies = await cur.fetchall()
    if not companies:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await message.answer(
            "🏢 <b>Компанії</b>\n\nКомпаній ще немає.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Додати компанію", callback_data="add_company")]
            ])
        )
        return
    await message.answer("🏢 <b>Компанії</b>", parse_mode="HTML", reply_markup=companies_kb(companies))
