from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from models.database import get_db
from utils.states import RegisterStates
from utils.helpers import is_valid_email
from keyboards.client_kb import accept_terms_kb, main_menu_kb
from keyboards.admin_kb import admin_menu_kb
import os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    async with await get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,))
        user = await cur.fetchone()

    if tg_id in ADMIN_IDS:
        async with await get_db() as db:
            await db.execute("""INSERT OR IGNORE INTO users (telegram_id,first_name,last_name,email,role,is_approved,accepted_terms)
                VALUES (?,?,?,?,'admin',1,1)""",
                (tg_id, message.from_user.first_name or "Admin", message.from_user.last_name or "", f"admin_{tg_id}@supercrm.local"))
            await db.commit()
        await message.answer("👋 Вітаємо, Адміністратор!", reply_markup=admin_menu_kb())
        return

    if user:
        if not user["is_approved"]:
            await message.answer("⏳ Ваш акаунт ще не підтверджений адміністратором. Очікуйте.")
            return
        await message.answer(f"👋 З поверненням, {user['first_name']}!", reply_markup=main_menu_kb())
        return

    await message.answer(
        "👋 Вітаємо в <b>SuperCRM</b>!\n\nДля реєстрації введіть ваше <b>ім'я</b>:",
        parse_mode="HTML"
    )
    await state.set_state(RegisterStates.first_name)

@router.message(RegisterStates.first_name)
async def reg_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip())
    await message.answer("Введіть ваше <b>прізвище</b>:", parse_mode="HTML")
    await state.set_state(RegisterStates.last_name)

@router.message(RegisterStates.last_name)
async def reg_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await message.answer("Введіть ваш <b>email</b>:", parse_mode="HTML")
    await state.set_state(RegisterStates.email)

@router.message(RegisterStates.email)
async def reg_email(message: Message, state: FSMContext):
    email = message.text.strip().lower()
    if not is_valid_email(email):
        await message.answer("❌ Невірний формат email. Спробуйте ще раз:")
        return
    async with await get_db() as db:
        cur = await db.execute("SELECT id FROM users WHERE email=?", (email,))
        if await cur.fetchone():
            await message.answer("❌ Цей email вже зареєстрований. Введіть інший:")
            return
    await state.update_data(email=email)
    await message.answer("Введіть ваш <b>номер телефону</b> (напр. +380XXXXXXXXX):", parse_mode="HTML")
    await state.set_state(RegisterStates.phone)

@router.message(RegisterStates.phone)
async def reg_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer(
        "📋 <b>Базове положення SuperCRM</b>\n\n"
        "Реєструючись, ви погоджуєтесь з умовами використання сервісу SuperCRM. "
        "Ваші дані (ім'я, email, телефон) використовуються виключно для управління замовленнями.",
        parse_mode="HTML",
        reply_markup=accept_terms_kb()
    )
    await state.set_state(RegisterStates.accept_terms)

@router.callback_query(RegisterStates.accept_terms, F.data == "accept_terms")
async def reg_accept(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tg_id = callback.from_user.id
    async with await get_db() as db:
        await db.execute("""INSERT INTO users (telegram_id,first_name,last_name,email,phone,role,is_approved,accepted_terms)
            VALUES (?,?,?,?,?,'client',0,1)""",
            (tg_id, data["first_name"], data["last_name"], data["email"], data.get("phone","")))
        await db.commit()
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Дякуємо за реєстрацію, {data['first_name']}!</b>\n\n"
        "Ваш акаунт відправлено на перевірку адміністратору. "
        "Ви отримаєте повідомлення, коли доступ буде підтверджено.",
        parse_mode="HTML"
    )
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🔔 <b>Новий клієнт чекає підтвердження!</b>\n"
                f"👤 {data['first_name']} {data['last_name']}\n"
                f"📧 {data['email']}\n"
                f"📱 {data.get('phone','—')}\n\n"
                f"Перейдіть до <b>👥 Клієнти</b> для підтвердження.",
                parse_mode="HTML"
            )
        except Exception:
            pass

@router.callback_query(RegisterStates.accept_terms, F.data == "decline_terms")
async def reg_decline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Реєстрацію скасовано. Натисніть /start щоб почати знову.")
