from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from models.database import get_db
from keyboards.admin_kb import settings_kb, companies_kb, brands_kb, categories_kb
from utils.states import FopSettingsStates, AddCompanyStates, AddBrandStates, AddCategoryStates
import os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

@router.message(F.text == "⚙️ Налаштування")
async def admin_settings(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⚙️ <b>Налаштування</b>", parse_mode="HTML", reply_markup=settings_kb())


@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    await callback.message.edit_text("⚙️ <b>Налаштування</b>", parse_mode="HTML", reply_markup=settings_kb())

# ── FOP Settings ──
@router.callback_query(F.data == "fop_settings")
async def show_fop_settings(callback: CallbackQuery):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = await cur.fetchone()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    text = (
        f"💳 <b>Реквізити ФОП</b>\n\n"
        f"👤 Назва: {fop.get('fop_name') or '—'}\n"
        f"🏦 IBAN: {fop.get('iban') or '—'}\n"
        f"📋 ЄДРПОУ/ІПН: {fop.get('edrpou') or '—'}\n"
        f"🏛 Банк: {fop.get('bank_name') or '—'}\n"
        f"📍 Адреса: {fop.get('legal_address') or '—'}\n"
        f"📱 Телефон: {fop.get('phone') or '—'}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редагувати реквізити", callback_data="edit_fop")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_settings")],
    ]))

@router.callback_query(F.data == "edit_fop")
async def edit_fop_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть <b>назву ФОП</b> (напр. ФОП Іваненко Іван Іванович):", parse_mode="HTML")
    await state.set_state(FopSettingsStates.fop_name)

@router.message(FopSettingsStates.fop_name)
async def fop_name(message: Message, state: FSMContext):
    await state.update_data(fop_name=message.text.strip())
    await message.answer("Введіть <b>IBAN</b>:", parse_mode="HTML")
    await state.set_state(FopSettingsStates.iban)

@router.message(FopSettingsStates.iban)
async def fop_iban(message: Message, state: FSMContext):
    await state.update_data(iban=message.text.strip())
    await message.answer("Введіть <b>ЄДРПОУ/ІПН</b>:", parse_mode="HTML")
    await state.set_state(FopSettingsStates.edrpou)

@router.message(FopSettingsStates.edrpou)
async def fop_edrpou(message: Message, state: FSMContext):
    await state.update_data(edrpou=message.text.strip())
    await message.answer("Введіть <b>назву банку</b> або /skip:", parse_mode="HTML")
    await state.set_state(FopSettingsStates.bank_name)

@router.message(FopSettingsStates.bank_name)
async def fop_bank(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(bank_name=message.text.strip())
    await message.answer("Введіть <b>юридичну адресу</b> або /skip:", parse_mode="HTML")
    await state.set_state(FopSettingsStates.legal_address)

@router.message(FopSettingsStates.legal_address)
async def fop_address(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(legal_address=message.text.strip())
    await message.answer("Введіть <b>телефон</b> або /skip:", parse_mode="HTML")
    await state.set_state(FopSettingsStates.phone)

@router.message(FopSettingsStates.phone)
async def fop_phone(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(phone=message.text.strip())
    data = await state.get_data()
    async with get_db() as db:
        await db.execute("""UPDATE fop_settings SET fop_name=?,iban=?,edrpou=?,bank_name=?,legal_address=?,phone=? WHERE id=1""",
            (data.get("fop_name"), data.get("iban"), data.get("edrpou"),
             data.get("bank_name"), data.get("legal_address"), data.get("phone")))
        await db.commit()
    await state.clear()
    await message.answer("✅ Реквізити ФОП збережено!")

# ── Companies ──
@router.callback_query(F.data == "admin_companies")
async def admin_companies(callback: CallbackQuery):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM companies ORDER BY name")
        companies = await cur.fetchall()
    await callback.message.edit_text("🏢 <b>Компанії</b>", parse_mode="HTML", reply_markup=companies_kb(companies))

@router.callback_query(F.data == "add_company")
async def add_company_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть <b>назву компанії</b>:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.name)

@router.message(AddCompanyStates.name)
async def co_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введіть <b>місто</b>:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.city)

@router.message(AddCompanyStates.city)
async def co_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("Введіть <b>IBAN компанії</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.iban)

@router.message(AddCompanyStates.iban)
async def co_iban(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(iban=message.text.strip())
    await message.answer("Введіть <b>назву для рахунків</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.display_name)

@router.message(AddCompanyStates.display_name)
async def co_display(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(display_name=message.text.strip())
    await message.answer("Введіть <b>ЄДРПОУ</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.edrpou)

@router.message(AddCompanyStates.edrpou)
async def co_edrpou(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(edrpou=message.text.strip())
    await message.answer("Введіть <b>юридичну адресу</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.legal_address)

@router.message(AddCompanyStates.legal_address)
async def co_legal(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(legal_address=message.text.strip())
    await message.answer("Введіть <b>ПІБ керівника</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.director)

@router.message(AddCompanyStates.director)
async def co_director(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(director=message.text.strip())
    await message.answer("Введіть <b>телефон компанії</b> або /skip:", parse_mode="HTML")
    await state.set_state(AddCompanyStates.phone)

@router.message(AddCompanyStates.phone)
async def co_phone(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(phone=message.text.strip())
    data = await state.get_data()
    async with get_db() as db:
        await db.execute("""INSERT INTO companies (name,city,iban,display_name,edrpou,legal_address,director,phone)
            VALUES (?,?,?,?,?,?,?,?)""",
            (data["name"], data.get("city"), data.get("iban"), data.get("display_name"),
             data.get("edrpou"), data.get("legal_address"), data.get("director"), data.get("phone")))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Компанію <b>{data['name']}</b> додано!", parse_mode="HTML")

# ── Brands ──
@router.callback_query(F.data == "admin_brands")
async def admin_brands(callback: CallbackQuery):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM brands ORDER BY name")
        brands = await cur.fetchall()
    await callback.message.edit_text("🏷 <b>Бренди</b>", parse_mode="HTML", reply_markup=brands_kb(brands))

@router.callback_query(F.data == "add_brand")
async def add_brand_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть <b>назву бренду</b>:", parse_mode="HTML")
    await state.set_state(AddBrandStates.name)

@router.message(AddBrandStates.name)
async def brand_name(message: Message, state: FSMContext):
    name = message.text.strip()
    async with get_db() as db:
        await db.execute("INSERT INTO brands (name) VALUES (?)", (name,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Бренд <b>{name}</b> додано!", parse_mode="HTML")

# ── Categories ──
@router.callback_query(F.data == "admin_categories")
async def admin_categories(callback: CallbackQuery):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM categories ORDER BY name")
        cats = await cur.fetchall()
    await callback.message.edit_text("📂 <b>Категорії</b>", parse_mode="HTML", reply_markup=categories_kb(cats))

@router.callback_query(F.data == "add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть <b>назву категорії</b>:", parse_mode="HTML")
    await state.set_state(AddCategoryStates.name)

@router.message(AddCategoryStates.name)
async def category_name(message: Message, state: FSMContext):
    name = message.text.strip()
    async with get_db() as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Категорію <b>{name}</b> додано!", parse_mode="HTML")

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
