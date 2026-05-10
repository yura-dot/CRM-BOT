from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from models.database import get_db
from utils.states import EditProfileStates
from keyboards.client_kb import main_menu_kb
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


router = Router()

def profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редагувати профіль", callback_data="edit_profile")],
        [InlineKeyboardButton(text="🚚 Дані Нової Пошти", callback_data="edit_np")],
    ])

@router.message(F.text == "👤 Профіль")
async def show_profile(message: Message):
    async with get_db() as db:
        cur = await db.execute("""SELECT u.*, co.name as co_name FROM users u
            LEFT JOIN companies co ON u.company_id=co.id WHERE u.telegram_id=?""", (message.from_user.id,))
        u = await cur.fetchone()

    np_block = ""
    if u.get("np_city"):
        np_block = f"\n\n🚚 <b>Нова Пошта:</b>\n🏙 Місто: {u['np_city']}\n📦 Відділення: {u.get('np_branch','—')}\n👤 Отримувач: {u.get('np_recipient','—')}"

    text = (
        f"👤 <b>Профіль</b>\n\n"
        f"Ім'я: {u['first_name']} {u['last_name']}\n"
        f"📧 Email: {u['email']}\n"
        f"📱 Телефон: {u.get('phone','—')}\n"
        f"🏢 Компанія: {u.get('co_name') or 'не призначена'}"
        f"{np_block}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=profile_kb())

@router.callback_query(F.data == "edit_profile")
async def start_edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть нове <b>ім'я</b> (або /skip щоб залишити поточне):", parse_mode="HTML")
    await state.set_state(EditProfileStates.first_name)

@router.message(EditProfileStates.first_name)
async def edit_first_name(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(first_name=message.text.strip())
    await message.answer("Введіть нове <b>прізвище</b> (або /skip):", parse_mode="HTML")
    await state.set_state(EditProfileStates.last_name)

@router.message(EditProfileStates.last_name)
async def edit_last_name(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(last_name=message.text.strip())
    await message.answer("Введіть новий <b>телефон</b> (або /skip):", parse_mode="HTML")
    await state.set_state(EditProfileStates.phone)

@router.message(EditProfileStates.phone)
async def edit_phone(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(phone=message.text.strip())
    data = await state.get_data()
    tg_id = message.from_user.id
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,))
        current = await cur.fetchone()
        await db.execute("""UPDATE users SET first_name=?, last_name=?, phone=? WHERE telegram_id=?""",
            (data.get("first_name", current["first_name"]),
             data.get("last_name", current["last_name"]),
             data.get("phone", current["phone"]),
             tg_id))
        await db.commit()
    await state.clear()
    await message.answer("✅ Профіль оновлено!", reply_markup=main_menu_kb())

@router.callback_query(F.data == "edit_np")
async def edit_np_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть <b>місто</b> для доставки Новою Поштою:", parse_mode="HTML")
    await state.set_state(EditProfileStates.np_city)

@router.message(EditProfileStates.np_city)
async def edit_np_city(message: Message, state: FSMContext):
    await state.update_data(np_city=message.text.strip())
    await message.answer("Введіть <b>номер відділення</b>:", parse_mode="HTML")
    await state.set_state(EditProfileStates.np_branch)

@router.message(EditProfileStates.np_branch)
async def edit_np_branch(message: Message, state: FSMContext):
    await state.update_data(np_branch=message.text.strip())
    await message.answer("Введіть <b>ім'я отримувача</b> (або /skip — буде використано ваше ім'я):", parse_mode="HTML")
    await state.set_state(EditProfileStates.np_recipient)

@router.message(EditProfileStates.np_recipient)
async def edit_np_recipient(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(np_recipient=message.text.strip())
    data = await state.get_data()
    tg_id = message.from_user.id
    async with get_db() as db:
        await db.execute("UPDATE users SET np_city=?, np_branch=?, np_recipient=? WHERE telegram_id=?",
            (data.get("np_city",""), data.get("np_branch",""), data.get("np_recipient",""), tg_id))
        await db.commit()
    await state.clear()
    await message.answer("✅ Дані доставки збережено!", reply_markup=main_menu_kb())
